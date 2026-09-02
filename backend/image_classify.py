"""Vision-based fallback for identifying which shot type (full/front/fullback/
detail_one) a reference image is, when its filename doesn't already say so.

Filename matching (drive_scan._match_shot_type) stays the free, instant first
path -- this only runs for images that don't match any known name or alias, so
a well-organized folder never triggers an API call at all. Results are cached
to disk keyed by (path, mtime, size), so re-scanning the same unchanged folder
never re-classifies the same image twice.

Uses gemini-3.5-flash-lite specifically: verified live against the team's own
reference photos across two different products (2026-08-31) at 100% accuracy,
~1250 input tokens / ~2 output tokens per image, zero thinking tokens (unlike
gemini-3.6-flash's ~511) -- works out to roughly $0.0004 (~0.03 cent) per
newly-classified image at current pricing. A free classical-CV attempt (Haar
cascade + DNN face detection + background-percentage heuristics) was tried
first and discarded: only ~62% accurate across products, worse than doing
nothing.
"""

import json
import os
from pathlib import Path
from typing import Optional

from . import config

CACHE_PATH = config.INTERNAL_ROOT / "shot_classification_cache.json"

_MODEL = "gemini-3.5-flash-lite"

_VALID_SHOT_TYPES = {"full", "front", "fullback", "detail_one", "unknown"}

_PROMPT = """You are classifying a fashion product reference photo into exactly one category. Reply with ONLY one lowercase word, nothing else -- no punctuation, no explanation.

Categories:
- full: full body shot, front view, entire outfit and shoes visible
- front: moderate close-up of the garment's front -- shows a wide chunk of it
  (e.g. the whole chest/torso area), clearly cropped tighter than a full body
  shot, but NOT zoomed in tight on one small spot
- fullback: any back-facing shot of the model/garment (full body OR a closer
  torso-level back crop -- both count, back-facing is what matters, not how
  tight the crop is)
- detail_one: EXTREME close-up, zoomed in tight on one small specific spot
  (a few centimeters of fabric texture, a single seam, a logo tag, a hardware
  piece) -- the detail fills nearly the whole frame
- unknown: does not clearly match any of the above

Reply with exactly one of: full, front, fullback, detail_one, unknown"""


def _load_cache() -> dict:
    if not CACHE_PATH.is_file():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2))


def _cache_key(file_path: Path) -> str:
    stat = file_path.stat()
    return f"{file_path}|{stat.st_mtime_ns}|{stat.st_size}"


def classify_shot_type(file_path: Path) -> Optional[str]:
    """Returns one of full/front/fullback/detail_one via Gemini vision, or None
    if classification isn't possible (no API key configured, request failed, or
    the model couldn't confidently place it) -- the caller falls back to
    upload-order assignment in that case. Cached on disk -- a given image is
    only ever sent to the API once as long as it doesn't change.
    """
    key = _cache_key(file_path)
    mime_type = "image/png" if file_path.suffix.lower() == ".png" else "image/jpeg"
    return classify_shot_type_bytes(key, lambda: file_path.read_bytes(), mime_type)


def classify_shot_type_bytes(cache_key: str, data_fn, mime_type: str) -> Optional[str]:
    """Same as classify_shot_type but for callers that don't have a local file
    (e.g. a Drive-hosted image) -- `data_fn` is only invoked on a cache miss, so
    a cached result never triggers a download/read at all. `cache_key` must be
    stable across re-scans of the *same, unchanged* image and change whenever
    its content does (e.g. "gdrive:<file_id>|<modifiedTime>")."""
    cache = _load_cache()
    if cache_key in cache:
        result = cache[cache_key]
        return result if result != "unknown" else None

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=_MODEL,
            contents=[types.Part.from_bytes(data=data_fn(), mime_type=mime_type), _PROMPT],
        )
        answer = (resp.text or "").strip().lower()
    except Exception:  # noqa: BLE001 - any failure here just means "couldn't classify"
        return None

    if answer not in _VALID_SHOT_TYPES:
        answer = "unknown"

    cache[cache_key] = answer
    _save_cache(cache)
    return answer if answer != "unknown" else None
