import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import config


@dataclass
class QAResult:
    passed: bool
    duration: Optional[float]
    width: Optional[int]
    height: Optional[int]
    codec: Optional[str]
    detail: str


async def probe(file_path: str) -> QAResult:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_b, stderr_b = await proc.communicate()

    if proc.returncode != 0:
        return QAResult(False, None, None, None, None, f"ffprobe failed: {stderr_b.decode(errors='replace')}")

    try:
        info = json.loads(stdout_b)
    except json.JSONDecodeError:
        return QAResult(False, None, None, None, None, "ffprobe returned invalid JSON")

    video_stream = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if video_stream is None:
        return QAResult(False, None, None, None, None, "no video stream found")

    duration = float(info.get("format", {}).get("duration") or video_stream.get("duration") or 0)
    width = video_stream.get("width")
    height = video_stream.get("height")
    codec = video_stream.get("codec_name")

    return QAResult(True, duration, width, height, codec, "ok")


# Floor for the short side, in px -- matches the 1080p resolution the other
# models (Kling pro/4k) already output natively.
_MIN_SHORT_SIDE = 1080


async def upscale_to_1080p(video_path: Path, aspect_ratio: str) -> bool:
    """Upscales a video in place via ffmpeg (Lanczos) if its short side is below
    _MIN_SHORT_SIDE, preserving the source's own aspect ratio.

    This is a plain pixel-dimension upscale (no added real detail) -- it exists
    only to satisfy Zalando's stated minimum resolution for models like Gemini
    Omni that can't natively output above 720p, at zero extra generation cost.

    Deliberately does NOT force a fixed target ratio (e.g. always exactly 9:16):
    Zalando accepts a RANGE of ratios (1.44-1.8, see the module docstring in
    templates.py), and Kling's native std-mode output (800x1152, ratio 1.44) is
    already inside that range. Forcing it to a different fixed ratio like
    1080x1920 (1.778) would visibly stretch/distort the video -- confirmed by
    a side-by-side frame comparison on 2026-08-27 after a team member asked
    whether Kling's crop was as exact as Gemini's; it wasn't, this is the fix.
    Returns True if an upscale was actually performed.
    """
    result = await probe(str(video_path))
    if not result.passed or not result.width or not result.height:
        return False

    short_side = min(result.width, result.height)
    if short_side >= _MIN_SHORT_SIDE:
        return False

    scale = _MIN_SHORT_SIDE / short_side
    # Even dimensions -- h264 requires them.
    target_w = round(result.width * scale / 2) * 2
    target_h = round(result.height * scale / 2) * 2

    tmp_path = video_path.with_suffix(".upscaled.mp4")
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", f"scale={target_w}:{target_h}:flags=lanczos",
        "-c:a", "copy",
        str(tmp_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()
    if proc.returncode != 0 or not tmp_path.is_file():
        tmp_path.unlink(missing_ok=True)
        return False

    tmp_path.replace(video_path)
    return True


async def ensure_thumbnail(video_path: Path) -> Path:
    """Generates a still-frame thumbnail in config.THUMBNAILS_DIR if it doesn't
    exist yet -- deliberately NOT next to `video_path`, so the Shared Drive
    output/ folder the team browses only ever contains actual generated videos.

    Called both right after a job finishes (worker.py, so dashboard loads never hit
    a burst of ffmpeg calls at once) and lazily as a fallback (main.py's thumbnail
    endpoint, for videos generated before this existed).
    """
    thumb_path = config.THUMBNAILS_DIR / f"{video_path.stem}.jpg"
    if thumb_path.is_file():
        return thumb_path
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-ss", "0.5", "-i", str(video_path), "-frames:v", "1", str(thumb_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()
    return thumb_path


async def _has_audio_stream(file_path: str) -> bool:
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "quiet", "-select_streams", "a",
        "-show_entries", "stream=codec_type", "-of", "json",
        file_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout_b, _ = await proc.communicate()
    if proc.returncode != 0:
        return False
    try:
        info = json.loads(stdout_b)
    except json.JSONDecodeError:
        return False
    return bool(info.get("streams"))


async def strip_audio(video_path: Path) -> bool:
    """Removes the audio track from a video in place via ffmpeg, if it has one.

    Zalando product clips must be silent -- generated videos sometimes carry a
    (usually silent, but not guaranteed) audio track from the source model.
    Returns True if an audio track was actually removed.
    """
    if not await _has_audio_stream(str(video_path)):
        return False

    tmp_path = video_path.with_suffix(".noaudio.mp4")
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", str(video_path),
        "-c:v", "copy", "-an",
        str(tmp_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()
    if proc.returncode != 0 or not tmp_path.is_file():
        tmp_path.unlink(missing_ok=True)
        return False

    tmp_path.replace(video_path)
    return True


def check_against_target(result: QAResult, target_duration: float) -> tuple[bool, str]:
    if not result.passed:
        return False, result.detail
    if abs(result.duration - target_duration) > config.QA_DURATION_TOLERANCE_SECONDS:
        return False, f"duration {result.duration:.2f}s deviates from target {target_duration:.2f}s"
    return True, f"{result.duration:.2f}s, {result.width}x{result.height}, {result.codec}"
