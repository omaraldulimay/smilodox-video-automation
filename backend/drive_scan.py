"""Scans a (Google Drive-synced) folder for per-variant reference image sets.

One folder per product/variant: the team drops exactly 4 plainly-named images
(no number prefix needed) into a folder named however they like, e.g.
".../oberteil/some-product/full.jpg" -- the folder name itself is the variant
identifier. Folders may be nested arbitrarily deep under the scan root (in which
case any ancestor folder literally named "oberteil"/"unterteil" auto-selects that
template for everything inside it; otherwise the caller-supplied default applies).

Shot types (team's own naming, matches their existing photography workflow):
  full        - full body, front view
  front       - close-up of the garment, front
  fullback    - full body, back view
  detail_one  - product detail close-up (team shoots detail_one/detail_two but only
                detail_one is ever used here)

Images don't strictly need these names -- anything not recognized by filename
is classified by Gemini vision instead (see image_classify.py), so the team
can drop in images without renaming them. If that's unavailable (no API key,
request failed), falls back to upload-order (oldest file first) into whichever
shot types are still missing -- silent and only correct if the images were
actually added in the full -> front -> fullback -> detail_one sequence.
"""

import asyncio
import hashlib
from pathlib import Path
from typing import Optional

from . import config, gdrive, image_classify

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

# Marker prefix for a Drive file id standing in for what used to be a local
# path string everywhere in this module (images dict values, reference_paths,
# output_path). Lets every downstream consumer (image_classify, worker.py,
# main.py's image/video endpoints) tell "Drive reference" from "local path"
# with a plain string check instead of a second parallel type throughout.
GDRIVE_PREFIX = "gdrive://"


def is_gdrive_ref(value: str) -> bool:
    return value.startswith(GDRIVE_PREFIX)


def gdrive_file_id(value: str) -> str:
    return value[len(GDRIVE_PREFIX):]

_THUMB_MAX_SIDE = 240


async def ensure_reference_thumbnail(source_path: Path) -> Path:
    """Generates (once) and returns a small cached JPEG copy of a reference
    photo for the batch-upload scan preview, keyed by (path, mtime, size) so a
    file the team swaps in place under the same filename is picked up
    automatically.

    These reference photos are full-resolution shoot originals (often 9-14MB
    at 2000-4000px+) -- serving them directly for a 56x56 on-screen thumbnail
    made several silently fail to render in the browser when many loaded at
    once (confirmed 2026-09-01: backend logs showed a clean 200 OK for every
    one of them, so this is a client-side decode/memory issue under
    concurrent load, not a server error). Falls back to the original file if
    ffmpeg is unavailable or the resize fails, so a broken thumbnail never
    blocks the scan preview outright.
    """
    stat = source_path.stat()
    digest = hashlib.sha1(f"{source_path}|{stat.st_mtime_ns}|{stat.st_size}".encode()).hexdigest()
    thumb_path = config.REFERENCE_THUMBS_DIR / f"{digest}.jpg"
    if thumb_path.is_file():
        return thumb_path

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", str(source_path),
        "-vf", f"scale='min({_THUMB_MAX_SIDE},iw)':'min({_THUMB_MAX_SIDE},ih)':force_original_aspect_ratio=decrease",
        "-q:v", "4",
        str(thumb_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()
    if proc.returncode != 0 or not thumb_path.is_file():
        thumb_path.unlink(missing_ok=True)
        return source_path
    return thumb_path

async def ensure_reference_thumbnail_gdrive(file_id: str) -> Path:
    """Same as ensure_reference_thumbnail() but for a Drive-hosted image --
    downloads it to a local temp file once, keyed by file_id, then reuses the
    exact same ffmpeg resize step. Keyed by id only (not modifiedTime, unlike
    the local version) to avoid an extra metadata round-trip per thumbnail
    request -- fine in practice since replacing a reference photo in Drive
    normally creates a new file id anyway."""
    digest = hashlib.sha1(f"gdrive:{file_id}".encode()).hexdigest()
    thumb_path = config.REFERENCE_THUMBS_DIR / f"{digest}.jpg"
    if thumb_path.is_file():
        return thumb_path

    raw_path = config.REFERENCE_THUMBS_DIR / f"{digest}_src"
    raw_path.write_bytes(gdrive.download_bytes(file_id))
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", str(raw_path),
            "-vf", f"scale='min({_THUMB_MAX_SIDE},iw)':'min({_THUMB_MAX_SIDE},ih)':force_original_aspect_ratio=decrease",
            "-q:v", "4",
            str(thumb_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        if proc.returncode != 0 or not thumb_path.is_file():
            thumb_path.unlink(missing_ok=True)
            return raw_path
        return thumb_path
    finally:
        if thumb_path.is_file():
            raw_path.unlink(missing_ok=True)


SHOT_TYPES = ["full", "front", "fullback", "detail_one"]

# Fixed submission order expected by the prompt templates (image1..image4).
SHOT_ORDER = ["full", "front", "fullback", "detail_one"]

GARMENT_FOLDER_NAMES = {"oberteil": "oberteil", "unterteil": "unterteil"}

# Common shorthand/alternate names (English and German) people naturally use
# instead of the canonical name -- purely alternate wording for the SAME photo,
# never a different shot content (e.g. a side-angle body shot is NOT an alias of
# "front", since that's a different photo entirely -- give it its own shot type
# instead of aliasing it). detail_two also maps to detail_one -- the team shoots
# both but only ever uses one per product, so whichever is present should work.
_SHOT_TYPE_ALIAS_GROUPS = {
    "full": ["fullfront", "front_full", "frontfull", "frontview", "front_view", "ganzkoerper", "ganzkörper", "vorne"],
    "front": ["closeup", "close_up", "frontcloseup", "front_closeup", "nahaufnahme"],
    "fullback": ["back", "backfull", "back_full", "backview", "back_view", "rueckansicht", "rückansicht", "hinten"],
    "detail_one": ["detail", "detail_two", "detailone", "detail_shot", "makro", "macro"],
}
SHOT_TYPE_ALIASES = {
    alias: canonical for canonical, aliases in _SHOT_TYPE_ALIAS_GROUPS.items() for alias in aliases
}


def _match_shot_type(stem: str) -> Optional[str]:
    """Returns the shot type if `stem` (the filename without extension) is exactly
    one of the known shot-type names or a recognized alias, case-insensitive --
    one plainly-named image per shot type, per product folder."""
    normalized = stem.strip().lower()
    normalized = SHOT_TYPE_ALIASES.get(normalized, normalized)
    return normalized if normalized in SHOT_TYPES else None


def _detect_template_from_ancestors(file_path: Path, root_path: Path) -> Optional[str]:
    """Walks up from the file's folder to `root_path`, looking for an ancestor
    literally named "oberteil"/"unterteil" -- not just the immediate parent. This
    way a per-product subfolder nested inside e.g. ".../oberteil/some-product/"
    still auto-detects, not only images placed directly in the oberteil folder.
    """
    current = file_path.parent
    root_resolved = root_path.resolve()
    while True:
        if current.name.strip().lower() in GARMENT_FOLDER_NAMES:
            return GARMENT_FOLDER_NAMES[current.name.strip().lower()]
        if current.resolve() == root_resolved or current.parent == current:
            return None
        current = current.parent


def scan_folder(root: str, model: Optional[str] = None) -> list[dict]:
    """Walks `root` recursively and groups matching images by containing folder --
    each folder holding recognized shot-type images is treated as one product/
    variant, identified by that folder's own name.

    `model`, if given, narrows what counts as "complete" to that model's actual
    required shots (e.g. kling3_0 only needs full+fullback) instead of always
    requiring all 4 canonical shots.

    Returns a list of dicts: {variant_number, template_key (None if undetected),
    images: {shot_type: path}, complete: bool, folder: str}.
    """
    root_path = Path(root)
    if not root_path.is_dir():
        raise ValueError(f"'{root}' is not a directory")

    groups: dict[str, dict] = {}  # folder -> group
    unmatched: list[Path] = []

    for file_path in root_path.rglob("*"):
        if not file_path.is_file() or file_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        shot_type = _match_shot_type(file_path.stem)
        if shot_type is None:
            unmatched.append(file_path)
            continue

        detected_template = _detect_template_from_ancestors(file_path, root_path)
        folder_key = str(file_path.parent)

        group = groups.setdefault(
            folder_key,
            {
                "variant_number": file_path.parent.name,
                "template_key": detected_template,
                "folder": folder_key,
                "images": {},
                "uncertain_shots": [],
            },
        )
        group["images"][shot_type] = str(file_path)

    # Second pass: any image whose filename didn't match a known shot type/alias
    # gets classified by Gemini vision instead (content-based, order-independent).
    # Anything vision can't place (no API key, request failed, or genuinely
    # "unknown") falls through to upload-order assignment as a last resort --
    # oldest-first, into whichever shot types are still missing, in the fixed
    # full -> front -> fullback -> detail_one sequence (only correct if the
    # images were actually added in that order; see the Batch-Upload UI hint).
    def _add_to_group(file_path: Path, shot_type: str, uncertain: bool = False) -> None:
        folder_key = str(file_path.parent)
        detected_template = _detect_template_from_ancestors(file_path, root_path)
        group = groups.setdefault(
            folder_key,
            {
                "variant_number": file_path.parent.name,
                "template_key": detected_template,
                "folder": folder_key,
                "images": {},
                "uncertain_shots": [],
            },
        )
        group.setdefault("uncertain_shots", [])
        group["images"][shot_type] = str(file_path)
        if uncertain and shot_type not in group["uncertain_shots"]:
            group["uncertain_shots"].append(shot_type)
        elif not uncertain and shot_type in group["uncertain_shots"]:
            group["uncertain_shots"].remove(shot_type)

    still_unmatched: list[Path] = []
    for file_path in unmatched:
        folder_key = str(file_path.parent)
        group = groups.get(folder_key)
        existing_shots = set(group["images"]) if group else set()
        if existing_shots == set(SHOT_TYPES):
            continue  # folder already complete, nothing left to fill

        shot_type = image_classify.classify_shot_type(file_path)
        if shot_type is None or shot_type in existing_shots:
            still_unmatched.append(file_path)
            continue
        _add_to_group(file_path, shot_type)

    unmatched_by_folder: dict[str, list[Path]] = {}
    for file_path in still_unmatched:
        unmatched_by_folder.setdefault(str(file_path.parent), []).append(file_path)

    for folder_key, files in unmatched_by_folder.items():
        files.sort(key=lambda p: p.stat().st_mtime)
        group = groups.get(folder_key)
        existing_shots = set(group["images"]) if group else set()
        missing_shots = [s for s in SHOT_ORDER if s not in existing_shots]
        for file_path, shot_type in zip(files, missing_shots):
            _add_to_group(file_path, shot_type, uncertain=True)

    required_shots = TWO_IMAGE_MODEL_SHOT_ORDER.get(model, SHOT_ORDER)

    results = []
    for group in groups.values():
        images = group["images"]
        results.append(
            {
                "variant_number": group["variant_number"],
                "template_key": group["template_key"],
                "folder": group["folder"],
                "image_count": len(images),
                "complete": all(shot in images for shot in required_shots),
                "images": images,
                # Shot types assigned by upload-order fallback rather than
                # filename or vision recognition -- the one case where the
                # assignment isn't actually content-verified, so the UI can
                # flag these for a quick manual check instead of making the
                # team look through every single thumbnail.
                "uncertain_shots": group.get("uncertain_shots", []),
            }
        )
    results.sort(key=lambda g: g["variant_number"])
    return results


def scan_drive_folder(root_folder_id: str, model: Optional[str] = None) -> list[dict]:
    """Same contract as scan_folder(), but walks a Google Drive folder via the
    API instead of the local filesystem (see gdrive.py) -- used when
    config.USE_GDRIVE_API is on. Every image reference in the returned
    "images" dict is a "gdrive://<file_id>" string instead of a local path;
    "folder" is the Drive folder id instead of a filesystem path.
    """
    all_files = gdrive.walk_all_files(root_folder_id)
    image_files = [f for f in all_files if Path(f["name"]).suffix.lower() in IMAGE_EXTENSIONS]

    groups: dict[str, dict] = {}

    def _group_for(f: dict) -> dict:
        chain = f["_parent_chain"]
        parent_id = chain[-1]["id"] if chain else root_folder_id
        variant_name = chain[-1]["name"] if chain else "root"
        detected_template = None
        for anc in chain:
            name = anc["name"].strip().lower()
            if name in GARMENT_FOLDER_NAMES:
                detected_template = GARMENT_FOLDER_NAMES[name]
        return groups.setdefault(
            parent_id,
            {
                "variant_number": variant_name,
                "template_key": detected_template,
                "folder": parent_id,
                "images": {},
                "uncertain_shots": [],
            },
        )

    unmatched: list[dict] = []
    for f in image_files:
        shot_type = _match_shot_type(Path(f["name"]).stem)
        if shot_type is None:
            unmatched.append(f)
            continue
        _group_for(f)["images"][shot_type] = GDRIVE_PREFIX + f["id"]

    still_unmatched: list[dict] = []
    for f in unmatched:
        group = _group_for(f)
        if set(group["images"]) == set(SHOT_TYPES):
            continue
        cache_key = f"gdrive:{f['id']}|{f.get('modifiedTime', '')}"
        mime_type = "image/png" if f["name"].lower().endswith(".png") else "image/jpeg"
        file_id = f["id"]
        shot_type = image_classify.classify_shot_type_bytes(
            cache_key, lambda fid=file_id: gdrive.download_bytes(fid), mime_type
        )
        if shot_type is None or shot_type in group["images"]:
            still_unmatched.append(f)
            continue
        group["images"][shot_type] = GDRIVE_PREFIX + f["id"]

    unmatched_by_folder: dict[str, list[dict]] = {}
    for f in still_unmatched:
        chain = f["_parent_chain"]
        parent_id = chain[-1]["id"] if chain else root_folder_id
        unmatched_by_folder.setdefault(parent_id, []).append(f)

    for parent_id, files in unmatched_by_folder.items():
        files.sort(key=lambda f: f.get("modifiedTime", ""))
        group = groups.get(parent_id)
        if group is None:
            continue
        missing_shots = [s for s in SHOT_ORDER if s not in group["images"]]
        for f, shot_type in zip(files, missing_shots):
            group["images"][shot_type] = GDRIVE_PREFIX + f["id"]
            group["uncertain_shots"].append(shot_type)

    required_shots = TWO_IMAGE_MODEL_SHOT_ORDER.get(model, SHOT_ORDER)
    results = []
    for group in groups.values():
        images = group["images"]
        results.append(
            {
                "variant_number": group["variant_number"],
                "template_key": group["template_key"],
                "folder": group["folder"],
                "image_count": len(images),
                "complete": all(shot in images for shot in required_shots),
                "images": images,
                "uncertain_shots": group.get("uncertain_shots", []),
            }
        )
    results.sort(key=lambda g: g["variant_number"])
    return results


def ordered_reference_paths(images: dict) -> list[str]:
    """Reference paths in the fixed image1..image4 order, skipping missing shots."""
    return [images[shot] for shot in SHOT_ORDER if shot in images]


# Models limited to a start/end image pair (see higgsfield_adapter._build_flags)
# get full+fullback specifically -- not just "the first two of the four", which
# would otherwise silently pick "front" (the close-up) as the "end" frame.
TWO_IMAGE_MODEL_SHOT_ORDER = {
    "kling3_0": ["full", "fullback"],
}


def reference_paths_for_model(images: dict, model: str) -> list[str]:
    if model in TWO_IMAGE_MODEL_SHOT_ORDER:
        shot_order = TWO_IMAGE_MODEL_SHOT_ORDER[model]
        return [images[shot] for shot in shot_order if shot in images]
    return ordered_reference_paths(images)
