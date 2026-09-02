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
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from . import config, db

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
    if db.USE_POSTGRES:
        # Hosted: the local disk is ephemeral (wiped on restart/deploy), so the
        # cache lives in the database instead -- otherwise every scan re-sent
        # every unmatched image to the API. Read in one query, not per image.
        try:
            with db.get_conn() as conn:
                rows = conn.execute("SELECT cache_key, shot_type FROM shot_classifications").fetchall()
            return {row["cache_key"]: row["shot_type"] for row in rows}
        except Exception:  # noqa: BLE001 - an unreachable cache just means "classify again"
            return {}

    if not CACHE_PATH.is_file():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2))


def _store_results(entries: dict) -> None:
    """Persists newly classified results -- one batched write, not one per image."""
    if not entries:
        return

    if db.USE_POSTGRES:
        from datetime import datetime, timezone

        now_iso = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        try:
            with db.get_conn() as conn:
                for key, shot_type in entries.items():
                    conn.execute(
                        "INSERT INTO shot_classifications (cache_key, shot_type, created_at) VALUES (?, ?, ?) "
                        "ON CONFLICT (cache_key) DO UPDATE SET shot_type = excluded.shot_type",
                        (key, shot_type, now_iso),
                    )
        except Exception:  # noqa: BLE001 - failing to cache must not fail the scan
            pass
        return

    cache = _load_cache()
    cache.update(entries)
    _save_cache(cache)


def _classify_one(api_key: str, data_fn, mime_type: str) -> Optional[str]:
    """Single API call. Returns a valid shot type, "unknown", or None when the
    call itself failed -- None is deliberately NOT cached, so a transient
    failure (rate limit, network) doesn't permanently poison the result.
    Retries once, since a rate-limited image would otherwise silently fall
    through to upload-order assignment, which can assign the wrong shot type.
    """
    from google import genai
    from google.genai import types

    try:
        data = data_fn()
    except Exception:  # noqa: BLE001 - couldn't even fetch the image
        return None

    for attempt in range(2):
        try:
            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(
                model=_MODEL,
                contents=[types.Part.from_bytes(data=data, mime_type=mime_type), _PROMPT],
            )
            answer = (resp.text or "").strip().lower()
            return answer if answer in _VALID_SHOT_TYPES else "unknown"
        except Exception:  # noqa: BLE001
            if attempt == 0:
                time.sleep(2)
    return None


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
    return classify_shot_types_batch([(cache_key, data_fn, mime_type)]).get(cache_key)


def classify_shot_types_batch(items: list) -> dict:
    """Classifies many images at once, returning {cache_key: shot_type or None}.

    `items` is a list of (cache_key, data_fn, mime_type) tuples, same meaning
    as in classify_shot_type_bytes.

    Exists because classifying one image at a time was the dominant cost of a
    folder scan: each miss is a full image download plus an API round-trip
    (~1-2s), and doing 19 of them sequentially accounted for essentially all
    of the ~30s scan time seen on the hosted instance (2026-09-02). Cache
    misses are now fetched and classified concurrently, the cache is read once
    up front, and all new results are written back in a single batch (the
    per-image read-modify-write of the old cache file would also have raced
    against itself once parallelized).
    """
    cache = _load_cache()
    results: dict = {}
    misses = []
    for cache_key, data_fn, mime_type in items:
        if cache_key in cache:
            cached = cache[cache_key]
            results[cache_key] = cached if cached != "unknown" else None
        else:
            misses.append((cache_key, data_fn, mime_type))

    if not misses:
        return results

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        for cache_key, _, _ in misses:
            results[cache_key] = None
        return results

    # Capped well below the API's rate limit -- a rate-limited image returns
    # None and falls through to upload-order assignment, which can be silently
    # wrong, so throughput here is deliberately not maximized.
    max_workers = min(4, len(misses))
    new_entries: dict = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_classify_one, api_key, data_fn, mime_type): cache_key
            for cache_key, data_fn, mime_type in misses
        }
        for future in as_completed(futures):
            cache_key = futures[future]
            answer = future.result()
            if answer is None:  # call failed -- don't cache, retry next scan
                results[cache_key] = None
                continue
            new_entries[cache_key] = answer
            results[cache_key] = answer if answer != "unknown" else None

    _store_results(new_entries)
    return results
