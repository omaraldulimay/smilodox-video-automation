import asyncio
import json
import shutil
import time
from typing import Optional

TRANSIENT_MARKERS = (
    "429",
    "too many requests",
    "timeout",
    "captcha-delivery",
    "failed to decode response",
    "temporarily unavailable",
    "502",
    "503",
)

PERMANENT_MARKERS = (
    "missing required params",
    "invalid values",
    "unknown params",
    "nsfw",
    "ip_detected",
    "unknown model",
)

_model_schema_cache: dict[str, dict] = {}


class GenerationError(Exception):
    def __init__(self, message: str, transient: bool):
        super().__init__(message)
        self.transient = transient


def _sanitize_prompt(prompt: str) -> str:
    """The higgsfield CLI auto-parses a --prompt value that is itself valid JSON
    into an object, which the API then rejects ("prompt should be string, got
    object"). Our campaign prompt templates ARE raw JSON text, so prefix a short
    non-JSON preamble whenever that would otherwise happen.
    """
    try:
        json.loads(prompt)
    except (json.JSONDecodeError, ValueError):
        return prompt
    return "Follow this generation spec exactly:\n\n" + prompt


def _classify(stderr: str, stdout: str) -> bool:
    """Returns True if the failure looks transient (worth retrying)."""
    blob = f"{stderr}\n{stdout}".lower()
    if any(marker in blob for marker in PERMANENT_MARKERS):
        return False
    if any(marker in blob for marker in TRANSIENT_MARKERS):
        return True
    # Unknown failure shape: default to one retry rather than giving up silently.
    return True


async def _run_cli(args: list[str], timeout_seconds: Optional[float] = None) -> tuple[int, str, str]:
    if shutil.which("higgsfield") is None:
        raise GenerationError("higgsfield CLI not found on PATH", transient=False)

    proc = await asyncio.create_subprocess_exec(
        "higgsfield",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise GenerationError("Local CLI call timed out", transient=True)

    return proc.returncode, stdout_b.decode(errors="replace"), stderr_b.decode(errors="replace")


async def get_model_schema(model: str, force_refresh: bool = False) -> dict:
    if not force_refresh and model in _model_schema_cache:
        return _model_schema_cache[model]

    code, stdout, stderr = await _run_cli(["model", "get", model, "--json"])
    if code != 0:
        raise GenerationError(stderr or stdout or "failed to fetch model schema", transient=True)

    schema = json.loads(stdout)
    _model_schema_cache[model] = schema
    return schema


async def list_models(models: list[str]) -> list[dict]:
    results = []
    for model in models:
        try:
            schema = await get_model_schema(model)
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller as a partial catalog
            results.append({"model": model, "error": str(exc)})
            continue
        results.append({"model": model, "schema": schema})
    return results


async def account_status() -> dict:
    code, stdout, stderr = await _run_cli(["account", "status", "--json"])
    if code != 0:
        raise GenerationError(stderr or stdout or "failed to fetch account status", transient=True)
    return json.loads(stdout)


async def _build_flags(
    model: str,
    prompt: str,
    reference_paths: Optional[list[str]],
    duration: float,
    aspect_ratio: str,
    resolution: Optional[str],
    mode: Optional[str] = None,
) -> tuple[list[str], int]:
    """Builds only the flags the model's own schema actually declares.

    Returns (flags, dropped_reference_count).

    Models differ: e.g. kling3_0 has no `resolution` param, and models with an
    `image_references` array (seedance_2_0, gemini_omni) take zero or more
    reference images via repeated `--image-references`, while single-slot models
    (kling3_0, kling3_0_turbo, ...) only expose `start_image`/`end_image` -- at
    most the first two references are usable there, extras are dropped (recorded
    by the caller via the returned `dropped_count`). Submitting an unsupported
    flag fails the whole job with "Unknown params", so this checks live schema first.
    """
    schema = await get_model_schema(model)
    params_by_name = {p["name"]: p for p in schema.get("params", [])}
    param_names = set(params_by_name)

    def _valid_or_default(value, param_name):
        param = params_by_name.get(param_name)
        enum = param.get("enum") if param else None
        if enum and value not in enum:
            return param.get("default", value)
        return value

    aspect_ratio = _valid_or_default(aspect_ratio, "aspect_ratio")

    flags = ["--prompt", _sanitize_prompt(prompt), "--duration", str(duration), "--aspect_ratio", aspect_ratio]
    if resolution and "resolution" in param_names:
        flags += ["--resolution", _valid_or_default(resolution, "resolution")]
    if "mode" in param_names:
        if model == "gemini_omni_flash_1_1":
            # Unlike Kling, this model's `mode` selects the generation workflow
            # (text-to-video/image-to-video/reference-to-video/edit), not a
            # quality tier. reference-to-video matches our actual pipeline, but
            # it REQUIRES at least one image -- the UI's cost-estimate call has
            # no reference images yet (nothing scanned/selected at that point),
            # so fall back to text-to-video for that case. Same price either
            # way (verified live: 30 credits for both @ 10s/9:16/720p).
            flags += ["--mode", "reference-to-video" if reference_paths else "text-to-video"]
        else:
            # Explicit quality/speed tier for models that expose it (Kling).
            # Defaults to "std" per team decision, but can be overridden (e.g.
            # Kling's "4k" mode) per job.
            flags += ["--mode", _valid_or_default(mode or "std", "mode")]
    if "sound" in param_names:
        # Zalando PDP videos must be silent, and the audio track was being
        # stripped again after download anyway (see qa.strip_audio). Generating
        # without it is also cheaper on Kling -- verified against the live cost
        # endpoint 2026-08-27: 10s 9:16 drops 20->15 credits (std) and 25->17
        # (pro); 4k is unchanged at 60.
        flags += ["--sound", _valid_or_default("off", "sound")]

    reference_paths = reference_paths or []
    dropped_count = 0
    if reference_paths:
        if "image_references" in param_names:
            for path in reference_paths:
                flags += ["--image-references", path]
        elif "start_image" in param_names:
            flags += ["--start-image", reference_paths[0]]
            if len(reference_paths) > 1 and "end_image" in param_names:
                flags += ["--end-image", reference_paths[1]]
                dropped_count = max(0, len(reference_paths) - 2)
            else:
                dropped_count = max(0, len(reference_paths) - 1)
        else:
            dropped_count = len(reference_paths)

    return flags, dropped_count


async def estimate_cost(
    model: str,
    prompt: str,
    duration: float,
    aspect_ratio: str,
    resolution: Optional[str] = None,
    mode: Optional[str] = None,
) -> float:
    flags, _ = await _build_flags(model, prompt, None, duration, aspect_ratio, resolution, mode)
    args = ["generate", "cost", model] + flags
    code, stdout, stderr = await _run_cli(args, timeout_seconds=30)
    if code != 0:
        transient = _classify(stderr, stdout)
        raise GenerationError(stderr or stdout or "cost estimation failed", transient=transient)

    # Output is plain text like "81 credits" (or "N/A" for some models). Parse the first number.
    for token in stdout.replace(",", "").split():
        try:
            return float(token)
        except ValueError:
            continue
    raise GenerationError(f"could not parse cost output: {stdout!r}", transient=False)


def _wait_timeout_to_seconds(wait_timeout: str) -> float:
    unit = wait_timeout[-1]
    value = float(wait_timeout[:-1])
    return {"s": value, "m": value * 60, "h": value * 3600}.get(unit, value)


async def generate(
    model: str,
    prompt: str,
    reference_paths: Optional[list[str]],
    duration: float,
    aspect_ratio: str,
    resolution: Optional[str],
    wait_timeout: str,
    mode: Optional[str] = None,
) -> dict:
    """Submits a real generation job and blocks (via --wait) until it finishes.

    Returns the parsed job object, with a `_dropped_reference_count` key added when
    the model's media slots couldn't fit all supplied reference images.
    Raises GenerationError (transient/permanent) on failure.
    """
    flags, dropped_count = await _build_flags(model, prompt, reference_paths, duration, aspect_ratio, resolution, mode)
    args = ["generate", "create", model] + flags
    args += ["--json", "--wait", "--wait-timeout", wait_timeout]

    subprocess_timeout = _wait_timeout_to_seconds(wait_timeout) + 30
    start = time.monotonic()
    code, stdout, stderr = await _run_cli(args, timeout_seconds=subprocess_timeout)
    elapsed = time.monotonic() - start

    if code != 0:
        transient = _classify(stderr, stdout)
        raise GenerationError(stderr.strip() or stdout.strip() or f"generate failed after {elapsed:.0f}s", transient=transient)

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise GenerationError(f"could not parse generate output: {exc}", transient=True) from exc

    # --wait --json returns an array with the final job object.
    job = payload[0] if isinstance(payload, list) else payload
    if dropped_count:
        job["_dropped_reference_count"] = dropped_count
    return job
