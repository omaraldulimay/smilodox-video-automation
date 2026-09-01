"""Cheap post-generation gate + automatic fix: does the finished clip's detail
shot still show the real Smilodox mark (a printed chest logo, a woven
waistband/hem tag, a sleeve patch, or occasionally hardware -- varies by
product), or did the model hallucinate a different (often Puma -- see
templates.py's brand_identity notes) logo onto it? If so, patch the correct
logo back in automatically via ffmpeg instead of a manual DaVinci Resolve
tracking session -- shot 4 is deliberately locked-off/static by prompt design
(see templates.py's choreography_discipline), so a single fixed-position
overlay for that shot's duration is a reasonable stand-in for real tracking,
without needing Resolve/Fusion or any GUI app at all.

Only meaningful for the 4-image models (gemini_omni, gemini_omni_flash_1_1) --
they have a dedicated locked-off detail shot (the last shot) with its own
reference photo. Kling has no such shot (see templates.py module docstring),
so there's nothing to extract/compare and this check is skipped for it.

Uses gemini-3.5-flash-lite, same model as image_classify.py: comparing the
detail reference photo against one extracted video frame (and asking for a
bounding box on failure) costs roughly double image_classify's ~0.03-0.04
cent/image, so well under 0.1 cent per checked video -- negligible next to the
video's own generation cost. Any failure here (no API key, extraction error,
model couldn't decide) returns None, i.e. "not checked", never blocks the job.
"""

import asyncio
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import config, qa

LOGO_CHECK_MODELS = {"gemini_omni", "gemini_omni_flash_1_1"}

_MODEL = "gemini-3.5-flash-lite"

_PROMPT = """You are comparing two photos of the same garment: the FIRST image is the \
original reference photo used to generate a product video; the SECOND image is a \
frame extracted from that generated video's close-up detail shot.

Focus specifically on whatever Smilodox branding is visible in the first image --
this varies by product and could be a printed chest logo, a woven waistband or \
hem tag, a sleeve patch, or occasionally a branded hardware piece. Ignore \
everything else (pose, lighting, motion blur, crop).

Does the second image show the SAME brand mark as the first, or no mark in \
both -- or has it been replaced with a different, invented, or competitor logo \
(e.g. Puma, Nike, Adidas)?

Reply with exactly one line:
PASS
or
FAIL: <one short reason, under 10 words> | BOX: x,y,w,h

Where BOX locates the WRONG mark in the SECOND image only: x,y is its \
top-left corner, w,h its width and height, each a fraction of the image's \
width/height between 0.0 and 1.0. Be as tight and precise as possible -- this \
box is used to paste the correct logo over that exact spot."""

_BOX_RE = re.compile(r"BOX:\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)")


@dataclass
class LogoCheckResult:
    status: str  # "pass" or "fail: <reason>" -- always lowercase-prefixed
    bbox: Optional[dict] = None  # {"x", "y", "width", "height"}, each 0.0-1.0


async def _extract_frame(video_path: Path, at_seconds: float) -> Optional[bytes]:
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-ss", str(max(at_seconds, 0)), "-i", str(video_path),
            "-frames:v", "1", str(tmp_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        if proc.returncode != 0 or not tmp_path.is_file():
            return None
        return tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)


def _mime_type(path: Path) -> str:
    return "image/png" if path.suffix.lower() == ".png" else "image/jpeg"


def _shot_window(duration: float, shot_count: int) -> tuple[float, float]:
    """Detail shot is the last of `shot_count` equal-length locked-off shots."""
    shot_len = duration / shot_count
    return duration - shot_len, duration


async def check_logo_fidelity(
    reference_paths: list[str], video_path: Path, duration: float, shot_count: int = 4
) -> Optional[LogoCheckResult]:
    """Returns a LogoCheckResult, or None (not checked/inconclusive)."""
    if len(reference_paths) < 4:
        return None  # no dedicated detail reference to compare against

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    detail_reference = Path(reference_paths[3])  # SHOT_ORDER: full, front, fullback, detail_one
    if not detail_reference.is_file():
        return None

    shot_start, shot_end = _shot_window(duration, shot_count)
    # Sample the midpoint, not the very start/end, to avoid the hard-cut frame.
    frame_bytes = await _extract_frame(video_path, (shot_start + shot_end) / 2)
    if frame_bytes is None:
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=_MODEL,
            contents=[
                types.Part.from_bytes(data=detail_reference.read_bytes(), mime_type=_mime_type(detail_reference)),
                types.Part.from_bytes(data=frame_bytes, mime_type="image/jpeg"),
                _PROMPT,
            ],
        )
        answer = (resp.text or "").strip()
    except Exception:  # noqa: BLE001 - any failure here just means "not checked"
        return None

    if answer.upper().startswith("PASS"):
        return LogoCheckResult(status="pass")

    if answer.upper().startswith("FAIL"):
        rest = answer[4:].lstrip(": ").strip()
        reason_part, _, box_part = rest.partition("|")
        status = f"fail: {reason_part.strip()}"[:200]

        bbox = None
        match = _BOX_RE.search(box_part)
        if match:
            x, y, w, h = (float(g) for g in match.groups())
            if 0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1 and x + w <= 1.05 and y + h <= 1.05:
                bbox = {"x": x, "y": y, "width": w, "height": h}
        return LogoCheckResult(status=status, bbox=bbox)

    return None


async def apply_auto_fix(
    video_path: Path, reference_image_path: Path, bbox: dict, duration: float, shot_count: int = 4
) -> bool:
    """Patches the correct logo over the wrong one via ffmpeg overlay, held for
    the whole (locked-off, near-static) detail shot -- no real motion tracking
    needed given how that shot is designed. The original file is preserved as
    "<job_id>_original.mp4" alongside it, never deleted, so nothing is lost if
    the patch doesn't look right. Returns True if the patch was applied.
    """
    probe_result = await qa.probe(str(video_path))
    if not probe_result.passed or not probe_result.width or not probe_result.height:
        return False
    w, h = probe_result.width, probe_result.height

    ox = max(0, int(bbox["x"] * w))
    oy = max(0, int(bbox["y"] * h))
    ow = max(2, (int(bbox["width"] * w) // 2) * 2)
    oh = max(2, (int(bbox["height"] * h) // 2) * 2)
    shot_start, shot_end = _shot_window(duration, shot_count)

    tmp_path = video_path.with_suffix(".logofix.mp4")
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", str(video_path), "-i", str(reference_image_path),
        "-filter_complex",
        f"[1:v]scale={ow}:{oh}[logo];[0:v][logo]overlay=x={ox}:y={oy}:enable='between(t,{shot_start},{shot_end})'",
        "-c:a", "copy",
        str(tmp_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()
    if proc.returncode != 0 or not tmp_path.is_file():
        tmp_path.unlink(missing_ok=True)
        return False

    backup_path = video_path.with_name(f"{video_path.stem}_original{video_path.suffix}")
    if not backup_path.is_file():
        shutil.copy2(video_path, backup_path)
    tmp_path.replace(video_path)

    # The dashboard's cached preview thumbnail was made from the old (wrong)
    # content at this same filename -- bust it so it regenerates from the fix.
    thumb_path = config.THUMBNAILS_DIR / f"{video_path.stem}.jpg"
    thumb_path.unlink(missing_ok=True)
    await qa.ensure_thumbnail(video_path)
    return True


def prepare_fix_package(
    job_id: str, reference_paths: list[str], video_path: Path, duration: float, reason: str, shot_count: int = 4
) -> Path:
    """Assembles a manual-fallback folder (original reference logo, a link to
    the video, a timecode note) for the rare case the automatic ffmpeg patch
    above doesn't apply (no bounding box) or doesn't look right -- kept as a
    DaVinci Resolve/Fusion fallback, not the primary path anymore.
    """
    folder = config.LOGO_FIXES_DIR / job_id
    folder.mkdir(parents=True, exist_ok=True)

    detail_reference = Path(reference_paths[3])
    shutil.copy2(detail_reference, folder / f"original_logo{detail_reference.suffix}")

    video_link = folder / "video.mp4"
    video_link.unlink(missing_ok=True)
    try:
        video_link.symlink_to(video_path)
    except OSError:
        shutil.copy2(video_path, video_link)

    shot_start, shot_end = _shot_window(duration, shot_count)
    (folder / "info.txt").write_text(
        f"Job: {job_id}\n"
        f"Fehlerhafter Bereich (Detail-Shot): {shot_start:.1f}s - {shot_end:.1f}s\n"
        f"Gemini-Befund: {reason}\n"
        f"Original-Logo: original_logo{detail_reference.suffix}\n"
    )
    return folder
