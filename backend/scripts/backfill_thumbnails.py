"""One-off retrofit: add a matching high-resolution thumbnail (.jpg) next to
every already-uploaded video in the Shared Drive's output/ folder tree.

Zalando's own template folders pair each video with a same-named preview
image in the same folder -- our own output/ tree never had that, since
qa.ensure_thumbnail() deliberately writes thumbnails to a separate local
cache dir instead. This backfills the missing sibling image for every video
that doesn't already have one, using a still frame from the video itself
(same resolution as the video, no downscaling) -- same ffmpeg invocation as
qa.ensure_thumbnail(), just written next to the video instead of into
config.THUMBNAILS_DIR.

Run as a module so the `backend.*` relative imports resolve:

    python -m backend.scripts.backfill_thumbnails            # dry run (default)
    python -m backend.scripts.backfill_thumbnails --apply    # actually uploads thumbnails

Dry run only reports which videos are missing a thumbnail; nothing is
uploaded until --apply is passed, since this writes new files onto the
shared Drive output/ folder.
"""

import argparse
import asyncio
import tempfile
from pathlib import Path

from .. import gdrive

_VIDEO_SUFFIX = ".mp4"
_THUMB_SUFFIX = ".jpg"


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
    all_files = await asyncio.to_thread(gdrive.walk_all_files, root_id)

    videos = [f for f in all_files if f["name"].lower().endswith(_VIDEO_SUFFIX)]
    existing_names_by_parent: dict[str, set] = {}
    for f in all_files:
        chain = f.get("_parent_chain") or []
        parent_id = chain[-1]["id"] if chain else root_id
        existing_names_by_parent.setdefault(parent_id, set()).add(f["name"])

    # Some article folders still hold a leftover, pre-crop original alongside
    # the final "zugeschnitten" (cropped-to-portrait) copy from the manual
    # crop-tool testing phase -- only the cropped one is the real deliverable,
    # so when a folder has a "zugeschnitten" video, skip every other video in
    # that same folder rather than thumbnailing the leftover original too.
    videos_by_parent: dict[str, list[dict]] = {}
    for video in videos:
        chain = video.get("_parent_chain") or []
        parent_id = chain[-1]["id"] if chain else root_id
        videos_by_parent.setdefault(parent_id, []).append(video)

    selected_videos = []
    skipped_leftovers = []
    for parent_id, group in videos_by_parent.items():
        cropped = [v for v in group if "zugeschnitten" in v["name"].lower()]
        if cropped:
            selected_videos.extend(cropped)
            skipped_leftovers.extend(v for v in group if v not in cropped)
        else:
            selected_videos.extend(group)

    created, already_present, failed = [], [], []

    for video in selected_videos:
        chain = video.get("_parent_chain") or []
        parent_id = chain[-1]["id"] if chain else root_id
        folder_label = " / ".join(seg["name"] for seg in chain) or "(root)"
        stem = video["name"][: -len(_VIDEO_SUFFIX)]
        thumb_name = f"{stem}{_THUMB_SUFFIX}"

        if thumb_name in existing_names_by_parent.get(parent_id, set()):
            already_present.append(f"{folder_label} / {video['name']}")
            continue

        label = f"{folder_label} / {thumb_name}"
        if not apply:
            created.append(label)
            continue

        with tempfile.TemporaryDirectory() as tmp:
            local_video = Path(tmp) / video["name"]
            local_thumb = Path(tmp) / thumb_name
            await asyncio.to_thread(gdrive.download_to_path, video["id"], local_video)
            ok = await _make_thumbnail(local_video, local_thumb)
            if not ok:
                failed.append(label)
                continue
            await asyncio.to_thread(gdrive.upload_file, parent_id, local_thumb, thumb_name, "image/jpeg")
            created.append(label)

    verb = "Created" if apply else "Would create"
    print(f"{verb} thumbnails: {len(created)}")
    for c in created:
        print(f"  - {c}")
    print(f"Already present: {len(already_present)}")
    print(f"Failed: {len(failed)}")
    for f in failed:
        print(f"  - {f}")
    print(f"Skipped (leftover original next to a cropped version): {len(skipped_leftovers)}")
    for v in skipped_leftovers:
        chain = v.get("_parent_chain") or []
        folder_label = " / ".join(seg["name"] for seg in chain) or "(root)"
        print(f"  - {folder_label} / {v['name']}")
    if not apply and created:
        print("\nDry run only -- re-run with --apply to actually upload thumbnails.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="actually upload thumbnails (default: dry run)")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
