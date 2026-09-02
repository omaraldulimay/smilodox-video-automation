import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from . import config, db, drive_scan, gdrive
from . import higgsfield_adapter as hf
from . import logo_check
from . import qa

_shutdown = asyncio.Event()


async def _resolve_reference_paths(reference_paths: list[str]) -> list[str]:
    """Downloads any "gdrive://<id>" reference paths to local temp files so
    higgsfield_adapter (which uploads local files by path to the Higgsfield
    CLI) works completely unchanged; plain local paths pass through as-is.
    Cached by file id under config.UPLOADS_DIR -- the same two reference
    images get reused across retries of the same job without re-downloading.
    """
    resolved = []
    for ref in reference_paths:
        if not drive_scan.is_gdrive_ref(ref):
            resolved.append(ref)
            continue
        file_id = drive_scan.gdrive_file_id(ref)
        meta = await asyncio.to_thread(gdrive.get_file_metadata, file_id)
        suffix = Path(meta.get("name", "")).suffix or ".jpg"
        tmp_path = config.UPLOADS_DIR / f"{file_id}{suffix}"
        if not tmp_path.is_file():
            data = await asyncio.to_thread(gdrive.download_bytes, file_id)
            tmp_path.write_bytes(data)
        resolved.append(str(tmp_path))
    return resolved


def _now_iso() -> str:
    # Millisecond precision + trailing "Z" (not "+00:00" with 6-digit microseconds)
    # -- the latter parses inconsistently across browsers (notably Safari), which
    # showed up as wrong "time ago" values in the dashboard.
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _claim_next_job():
    """Atomically picks the oldest eligible job and flips it to 'processing'.

    Safe across the N worker coroutines: each call runs synchronously with no
    `await` inside, so asyncio never interleaves two calls mid-function.
    """
    now = _now_iso()
    with db.get_conn() as conn:
        row = conn.execute(
            """
            SELECT * FROM clips
            WHERE status = 'pending'
               OR (status = 'failed_transient' AND (next_retry_at IS NULL OR next_retry_at <= ?))
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (now,),
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE clips SET status = 'processing', updated_at = ? WHERE job_id = ?",
            (now, row["job_id"]),
        )
        db.log_event(conn, row["job_id"], "processing")
        return row


def _mark_dry_run_completed(job_id: str, credits_estimate: float):
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE clips SET status = 'completed_dry_run', credits_estimate = ?, updated_at = ? WHERE job_id = ?",
            (credits_estimate, _now_iso(), job_id),
        )
        db.log_event(conn, job_id, "completed_dry_run", f"{credits_estimate} credits")


def _mark_completed(job_id: str, output_path: str, qa_detail: str, logo_result: Optional[str] = None):
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE clips SET status = 'completed', output_path = ?, qa_status = ?, logo_check = ?, updated_at = ? WHERE job_id = ?",
            (output_path, qa_detail, logo_result, _now_iso(), job_id),
        )
        db.log_event(conn, job_id, "completed", qa_detail)
        if logo_result and logo_result.startswith("fail"):
            db.log_event(conn, job_id, "logo_check_failed", logo_result)


def _mark_qa_failed(job_id: str, output_path: str, detail: str):
    with db.get_conn() as conn:
        conn.execute(
            "UPDATE clips SET status = 'qa_failed', output_path = ?, qa_status = ?, updated_at = ? WHERE job_id = ?",
            (output_path, detail, _now_iso(), job_id),
        )
        db.log_event(conn, job_id, "qa_failed", detail)


def _mark_failed(job_id: str, transient: bool, message: str, retry_count: int):
    now = _now_iso()
    if transient and retry_count < config.MAX_RETRIES:
        backoff = config.RETRY_BACKOFF_BASE_SECONDS * (2**retry_count)
        next_retry = (datetime.now(timezone.utc) + timedelta(seconds=backoff)).isoformat()
        status = "failed_transient"
        new_retry_count = retry_count + 1
    else:
        next_retry = None
        status = "failed_permanent"
        new_retry_count = retry_count

    with db.get_conn() as conn:
        conn.execute(
            """
            UPDATE clips
            SET status = ?, error_message = ?, retry_count = ?, next_retry_at = ?, updated_at = ?
            WHERE job_id = ?
            """,
            (status, message[:2000], new_retry_count, next_retry, now, job_id),
        )
        db.log_event(conn, job_id, status, message[:500])


def _extract_result_url(job: dict) -> Optional[str]:
    """Best-effort lookup across the shapes seen in Higgsfield job payloads.

    NOTE: not yet validated against a real completed job (blocked on the 98-credit
    balance) -- confirm the actual field name on the first real Phase 1 test and
    adjust here if needed.
    """
    for key in ("result_url", "url", "output_url"):
        if job.get(key):
            return job[key]
    results = job.get("results") or job.get("outputs") or []
    if results and isinstance(results, list):
        first = results[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get("url") or first.get("result_url")
    return None


async def _download(url: str, job_id: str, dest_dir):
    import httpx

    dest = dest_dir / f"{job_id}.mp4"
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            with open(dest, "wb") as f:
                async for chunk in response.aiter_bytes():
                    f.write(chunk)
    return dest


_OUTPUT_SUBDIR_NAMES = {"oberteil": "Oberteil", "unterteil": "Unterteil"}


async def _upload_output_to_drive(local_path: Path, template_key: Optional[str]) -> str:
    """Uploads a finished clip into the Shared Drive's output/ folder (mirroring
    the local OUTPUT_SUBDIRS layout: output/Oberteil, output/Unterteil), and
    returns a "gdrive://<id>" reference for storing as the job's output_path."""
    output_root_id = await asyncio.to_thread(gdrive.find_root_folder, "output")
    subdir_name = _OUTPUT_SUBDIR_NAMES.get(template_key)
    parent_id = output_root_id
    if subdir_name:
        parent_id = await asyncio.to_thread(gdrive.find_or_create_folder, output_root_id, subdir_name)
    file_id = await asyncio.to_thread(gdrive.upload_file, parent_id, local_path, local_path.name, "video/mp4")
    return f"{drive_scan.GDRIVE_PREFIX}{file_id}"


async def _process_job(row):
    import json as _json

    job_id = row["job_id"]
    reference_paths = _json.loads(row["reference_paths_json"]) if row["reference_paths_json"] else []
    try:
        if row["dry_run"]:
            credits = await hf.estimate_cost(
                row["model"], row["prompt"], row["duration"], row["aspect_ratio"], row["resolution"], row["mode"]
            )
            _mark_dry_run_completed(job_id, credits)
            return

        generation_reference_paths = await _resolve_reference_paths(reference_paths)
        job = await hf.generate(
            row["model"],
            row["prompt"],
            generation_reference_paths,
            row["duration"],
            row["aspect_ratio"],
            row["resolution"],
            config.GENERATE_WAIT_TIMEOUT,
            row["mode"],
        )

        result_url = _extract_result_url(job)
        if not result_url:
            raise hf.GenerationError(f"job finished but no result URL found: {job}", transient=False)

        dest_dir = config.OUTPUT_SUBDIRS.get(row["template_key"], config.OUTPUT_DIR)
        output_path = await _download(result_url, job_id, dest_dir)
        await qa.strip_audio(output_path)
        # Some models/modes can't natively output above 720p (Gemini Omni) or
        # cap below 1080p on their cheapest tier (Kling std, 800x1152) --
        # upscale in place so every completed clip meets Zalando's stated
        # minimum resolution, at no extra Higgsfield cost. No-op for anything
        # already at/above 1080p on its short side (Kling pro/4k).
        upscaled = await qa.upscale_to_1080p(output_path, row["aspect_ratio"])

        # Upload to Drive (source of truth for the team) BEFORE thumbnailing,
        # so the local cache file already has its final name -- ensure_thumbnail
        # keys its cache by filename stem, and _get_output_path's Drive-mode
        # cache path uses the Drive file id as that stem, not the job id.
        stored_output_path = str(output_path)
        if config.USE_GDRIVE_API:
            drive_ref = await _upload_output_to_drive(output_path, row["template_key"])
            file_id = drive_scan.gdrive_file_id(drive_ref)
            cache_path = config.OUTPUT_CACHE_DIR / f"{file_id}.mp4"
            output_path = output_path.replace(cache_path)
            stored_output_path = drive_ref

        await qa.ensure_thumbnail(output_path)
        probe_result = await qa.probe(str(output_path))
        passed, detail = qa.check_against_target(probe_result, row["duration"])
        if upscaled:
            detail = f"{detail} (upscaled to {probe_result.width}x{probe_result.height})"
        dropped = job.get("_dropped_reference_count")
        if dropped:
            detail = f"{detail} (warning: {dropped} reference image(s) dropped, model only supports fewer slots)"

        if passed:
            # Detection only (cheap, stays on for dashboard visibility) -- the
            # ffmpeg auto-patch and the manual Resolve/Fusion follow-up were
            # both retired (2026-09-01, see memory: ffmpeg overlay looked like
            # a pasted sticker, Resolve workflow unused). A proper fix is
            # deferred to the deterministic OpenCV approach; see memory.
            logo_status = None
            if row["model"] in logo_check.LOGO_CHECK_MODELS and not config.USE_GDRIVE_API:
                # Not yet Drive-aware (reads reference_paths as local Paths
                # directly) -- skip rather than error; only Kling is offered
                # in the UI right now anyway, so LOGO_CHECK_MODELS never
                # matches in practice, see Info page / memory.
                check = await logo_check.check_logo_fidelity(reference_paths, output_path, row["duration"])
                logo_status = check.status if check else None
            _mark_completed(job_id, stored_output_path, detail, logo_status)
        else:
            _mark_qa_failed(job_id, stored_output_path, detail)

    except hf.GenerationError as exc:
        _mark_failed(job_id, exc.transient, str(exc), row["retry_count"])
    except Exception as exc:  # noqa: BLE001 - unclassified errors get one retry, then surface
        _mark_failed(job_id, True, f"unexpected error: {exc}", row["retry_count"])


async def _worker(worker_index: int):
    while not _shutdown.is_set():
        row = _claim_next_job()
        if row is None:
            await asyncio.sleep(config.WORKER_POLL_INTERVAL_SECONDS)
            continue
        await _process_job(row)


_worker_tasks: list[asyncio.Task] = []


def start_workers():
    _shutdown.clear()
    for i in range(config.WORKER_CONCURRENCY):
        _worker_tasks.append(asyncio.create_task(_worker(i)))


async def stop_workers():
    _shutdown.set()
    if _worker_tasks:
        await asyncio.gather(*_worker_tasks, return_exceptions=True)
        _worker_tasks.clear()
