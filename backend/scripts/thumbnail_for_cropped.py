"""One-off: generate+upload a thumbnail for the just-finalized cropped videos
in the 11 article folders where the original (pre-crop) video still sits
under the SAME filename (rename already happened, delete is pending manual
cleanup -- see finalize_cropped_outputs.py). Since both files now share one
name, picks the one with the more recent modifiedTime as "the cropped one"
(renaming just now necessarily bumped it -- verified 2026-09-24 against the
one folder with a known-good DB-confirmed file id: 16:06 vs 09:25, and it's
also the much smaller file, both signals agreeing).

Once the leftover originals are manually deleted, this script becomes
unnecessary -- ordinary new videos should use backfill_thumbnails.py instead
(no ambiguity there since it doesn't rely on a duplicate-name heuristic).

Run as a module:

    python -m backend.scripts.thumbnail_for_cropped            # dry run (default)
    python -m backend.scripts.thumbnail_for_cropped --apply     # actually uploads
"""

import argparse
import asyncio
import tempfile
from pathlib import Path

from .. import gdrive

_FOLDERS = [
    ("Unterteil", "26722-A-shorts"),
    ("Unterteil", "SCTW26-3-SC-A-sctw26-2"),
    ("Unterteil", "26721-A-schlagleggings"),
    ("Unterteil", "26729-A---Capri-Leggings"),
    ("Unterteil", "26730-schlagleggings-2"),
    ("Unterteil", "26709-shorts-2"),
    ("Oberteil", "85064-A-T-shirt"),
    ("Oberteil", "26731-A T-shirt"),
    ("Oberteil", "26732---Jacke"),
    ("Oberteil", "26732 - Jacke"),
    ("Oberteil", "26725 - Sport BH"),
]


async def _make_thumbnail(video_path: Path, thumb_path: Path) -> bool:
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-ss", "0.5", "-i", str(video_path), "-frames:v", "1", str(thumb_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()
    return proc.returncode == 0 and thumb_path.is_file()


async def main(apply: bool):
    root_id = await asyncio.to_thread(gdrive.find_root_folder, "output")

    created, already_present, failed = [], [], []

    for subdir_name, article_name in _FOLDERS:
        subdir = await asyncio.to_thread(gdrive.find_child, root_id, subdir_name)
        folder = await asyncio.to_thread(gdrive.find_child, subdir["id"], article_name)
        children = await asyncio.to_thread(gdrive.list_children, folder["id"])

        mp4s = [c for c in children if c["name"].lower().endswith(".mp4")]
        if not mp4s:
            failed.append(f"{subdir_name}/{article_name}: no mp4 found")
            continue
        target = max(mp4s, key=lambda c: c.get("modifiedTime") or "")

        stem = target["name"][: -len(".mp4")]
        thumb_name = f"{stem}.jpg"
        label = f"{subdir_name}/{article_name} / {thumb_name} (from '{target['name']}', id={target['id']})"

        if any(c["name"] == thumb_name for c in children):
            already_present.append(label)
            continue

        if not apply:
            created.append(label)
            continue

        with tempfile.TemporaryDirectory() as tmp:
            local_video = Path(tmp) / target["name"]
            local_thumb = Path(tmp) / thumb_name
            await asyncio.to_thread(gdrive.download_to_path, target["id"], local_video)
            ok = await _make_thumbnail(local_video, local_thumb)
            if not ok:
                failed.append(label)
                continue
            await asyncio.to_thread(gdrive.upload_file, folder["id"], local_thumb, thumb_name, "image/jpeg")
            created.append(label)

    verb = "Created" if apply else "Would create"
    print(f"{verb} thumbnails: {len(created)}")
    for c in created:
        print(f"  - {c}")
    print(f"Already present: {len(already_present)}")
    for c in already_present:
        print(f"  - {c}")
    print(f"Failed: {len(failed)}")
    for f in failed:
        print(f"  - {f}")
    if not apply and created:
        print("\nDry run only -- re-run with --apply to actually upload thumbnails.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="actually upload thumbnails (default: dry run)")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
