"""One-off retrofit: remove the audio track from already-generated clips.

Run as a module so the `backend.*` relative imports resolve:

    python -m backend.scripts.strip_audio_existing            # dry run (default)
    python -m backend.scripts.strip_audio_existing --apply     # actually strips audio

Dry run only reports which files have an audio track; nothing is written
until --apply is passed, since this mutates files in place on the shared
Drive output/ folder.
"""

import argparse
import asyncio
from pathlib import Path

from .. import config, db, qa


async def main(apply: bool):
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT job_id, output_path FROM clips WHERE output_path IS NOT NULL"
        ).fetchall()

    stripped, already_silent, missing = [], [], []

    for row in rows:
        job_id, output_path = row["job_id"], row["output_path"]
        path = Path(output_path)
        if not path.is_file():
            missing.append(job_id)
            continue

        has_audio = await qa._has_audio_stream(str(path))
        if not has_audio:
            already_silent.append(job_id)
            continue

        if apply:
            ok = await qa.strip_audio(path)
            if ok:
                stripped.append(job_id)
                with db.get_conn() as conn:
                    db.log_event(conn, job_id, "audio_stripped", "retrofit: audio track removed")
            else:
                missing.append(job_id)  # ffmpeg failed
        else:
            stripped.append(job_id)  # "would strip"

    verb = "Stripped" if apply else "Would strip"
    print(f"{verb} audio: {len(stripped)}")
    for j in stripped:
        print(f"  - {j}")
    print(f"Already silent: {len(already_silent)}")
    print(f"Missing/failed: {len(missing)}")
    for j in missing:
        print(f"  - {j}")
    if not apply and stripped:
        print("\nDry run only -- re-run with --apply to actually strip audio.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="actually strip audio (default: dry run)")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
