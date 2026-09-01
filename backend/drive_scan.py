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

from pathlib import Path
from typing import Optional

from . import image_classify

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

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
