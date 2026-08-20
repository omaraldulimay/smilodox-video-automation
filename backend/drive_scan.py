"""Scans a (Google Drive-synced) folder for per-variant reference image sets.

Filenames are expected to end in one of the four shot-type suffixes below, prefixed
by the product/variant number, e.g. "12345_full_front.jpg". Images may sit in one
flat folder, or be split into per-garment-type subfolders (in which case a subfolder
named "oberteil"/"unterteil" auto-selects that template for everything inside it;
otherwise the caller-supplied default template applies).
"""

from pathlib import Path
from typing import Optional

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

# Longest-suffix-first so "front_closeup" isn't mistaken for a shorter match.
SHOT_TYPES = ["front_closeup", "detail_shot", "full_front", "full_back"]

# Fixed submission order expected by the prompt templates (image1..image4).
SHOT_ORDER = ["full_front", "front_closeup", "full_back", "detail_shot"]

GARMENT_FOLDER_NAMES = {"oberteil": "oberteil", "unterteil": "unterteil"}


def _match_shot_type(stem: str) -> Optional[tuple[str, str]]:
    """Returns (variant_number, shot_type) if `stem` ends in a known shot-type suffix."""
    for shot_type in SHOT_TYPES:
        suffix = f"_{shot_type}"
        if stem.lower().endswith(suffix):
            variant = stem[: -len(suffix)]
            if variant:
                return variant, shot_type
    return None


def scan_folder(root: str) -> list[dict]:
    """Walks `root` recursively and groups matching images by variant number.

    Returns a list of dicts: {variant_number, template_key (None if undetected),
    images: {shot_type: path}, complete: bool, folder: str}.
    """
    root_path = Path(root)
    if not root_path.is_dir():
        raise ValueError(f"'{root}' is not a directory")

    groups: dict[tuple[str, str], dict] = {}  # (folder, variant_number) -> group

    for file_path in root_path.rglob("*"):
        if not file_path.is_file() or file_path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        match = _match_shot_type(file_path.stem)
        if match is None:
            continue
        variant_number, shot_type = match

        parent_name = file_path.parent.name.strip().lower()
        detected_template = GARMENT_FOLDER_NAMES.get(parent_name)
        folder_key = str(file_path.parent)

        key = (folder_key, variant_number)
        group = groups.setdefault(
            key,
            {
                "variant_number": variant_number,
                "template_key": detected_template,
                "folder": folder_key,
                "images": {},
            },
        )
        group["images"][shot_type] = str(file_path)

    results = []
    for group in groups.values():
        images = group["images"]
        results.append(
            {
                "variant_number": group["variant_number"],
                "template_key": group["template_key"],
                "folder": group["folder"],
                "image_count": len(images),
                "complete": all(shot in images for shot in SHOT_ORDER),
                "images": images,
            }
        )
    results.sort(key=lambda g: g["variant_number"])
    return results


def ordered_reference_paths(images: dict) -> list[str]:
    """Reference paths in the fixed image1..image4 order, skipping missing shots."""
    return [images[shot] for shot in SHOT_ORDER if shot in images]


# Models limited to a start/end image pair (see higgsfield_adapter._build_flags)
# get front+back specifically -- not just "the first two of the four", which would
# otherwise silently pick front_closeup as the "end" frame.
TWO_IMAGE_MODEL_SHOT_ORDER = {
    "kling3_0": ["full_front", "full_back"],
}


def reference_paths_for_model(images: dict, model: str) -> list[str]:
    shot_order = TWO_IMAGE_MODEL_SHOT_ORDER.get(model, SHOT_ORDER)
    return [images[shot] for shot in shot_order if shot in images]
