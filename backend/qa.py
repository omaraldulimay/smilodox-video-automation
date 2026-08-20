import asyncio
import json
from dataclasses import dataclass
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


def check_against_target(result: QAResult, target_duration: float) -> tuple[bool, str]:
    if not result.passed:
        return False, result.detail
    if abs(result.duration - target_duration) > config.QA_DURATION_TOLERANCE_SECONDS:
        return False, f"duration {result.duration:.2f}s deviates from target {target_duration:.2f}s"
    return True, f"{result.duration:.2f}s, {result.width}x{result.height}, {result.codec}"
