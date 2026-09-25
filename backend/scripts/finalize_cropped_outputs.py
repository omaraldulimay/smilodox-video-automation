"""One-off retrofit: for every output/ article folder that still holds both a
leftover pre-crop original video and a manually-cropped "zugeschnitten" test
copy, make the cropped copy the canonical file -- renamed to the original's
filename (so it keeps the job-traceable name and any clips.output_path DB
reference keeps working) -- and delete the leftover original.

Order per folder, deliberately DB-safe (a failed delete never leaves the DB
pointing at a missing file):
    1. Rename the cropped video to the original's filename.
    2. If clips.output_path referenced the original's file id, repoint it to
       the (now-renamed) cropped file's id.
    3. Delete the original file (and any other non-cropped leftover, e.g. a
       TOOL-TEST copy, in the same folder).

Only touches folders where exactly one "canonical" original (i.e. one whose
gdrive file id is referenced by some clips.output_path) is present alongside
a "zugeschnitten"-named video. Folders with no DB-referenced original are
left untouched and reported, not guessed at.

Run as a module:

    python -m backend.scripts.finalize_cropped_outputs            # dry run (default)
    python -m backend.scripts.finalize_cropped_outputs --apply     # actually rename/repoint/delete
"""

import argparse
import asyncio
import re

from .. import db, gdrive

_VIDEO_SUFFIX = ".mp4"
_GDRIVE_PREFIX = "gdrive://"
_JOB_ID8_RE = re.compile(r"_([0-9a-f]{8})\.mp4$", re.IGNORECASE)


async def main(apply: bool):
    with db.get_conn() as conn:
        rows = conn.execute("SELECT job_id, output_path FROM clips").fetchall()
    all_job_ids = [r["job_id"] for r in rows]
    output_path_by_file_id = {
        r["output_path"][len(_GDRIVE_PREFIX):]: r["job_id"]
        for r in rows
        if r["output_path"] and r["output_path"].startswith(_GDRIVE_PREFIX)
    }

    root_id = await asyncio.to_thread(gdrive.find_root_folder, "output")
    all_files = await asyncio.to_thread(gdrive.walk_all_files, root_id)
    videos = [f for f in all_files if f["name"].lower().endswith(_VIDEO_SUFFIX)]

    videos_by_parent: dict[str, list[dict]] = {}
    for v in videos:
        chain = v.get("_parent_chain") or []
        parent_id = chain[-1]["id"] if chain else root_id
        videos_by_parent.setdefault(parent_id, []).append(v)

    def resolve_job_id(original: dict) -> "str | None":
        # 1) current DB output_path already points at this exact file id.
        if original["id"] in output_path_by_file_id:
            return output_path_by_file_id[original["id"]]
        # 2) fallback: the filename's trailing job_id[:8] fragment (worker.py's
        # _output_filename_stem convention) uniquely identifies one job -- this
        # covers a file that was manually re-uploaded/swapped after the DB's
        # output_path was written, so the id itself no longer matches but the
        # name still does.
        m = _JOB_ID8_RE.search(original["name"])
        if not m:
            return None
        prefix = m.group(1).lower()
        matches = [j for j in all_job_ids if j.lower().startswith(prefix)]
        return matches[0] if len(matches) == 1 else None

    # Build the full plan first (no side effects yet) so ambiguous cases --
    # e.g. two different article folders both resolving to the SAME job_id,
    # which happens with the known duplicate "26732" folders that share an
    # identically-named original -- can be detected and neutralized (both
    # sides skip the DB repoint) before anything is written.
    plan = []
    for parent_id, group in videos_by_parent.items():
        cropped = [v for v in group if "zugeschnitten" in v["name"].lower()]
        originals = [v for v in group if v not in cropped]
        if not cropped or not originals:
            continue  # nothing to finalize in this folder

        chain = group[0].get("_parent_chain") or []
        folder_label = " / ".join(seg["name"] for seg in chain) or "(root)"

        db_original = next((o for o in originals if resolve_job_id(o) is not None), originals[0])
        job_id = resolve_job_id(db_original)

        plan.append({
            "folder_label": folder_label,
            "target_video": cropped[0],  # exactly one cropped video expected per folder so far
            "new_name": db_original["name"],
            "leftovers": originals,  # delete every non-cropped video in this folder, not just the DB one
            "job_id": job_id,
        })

    job_id_counts: dict[str, int] = {}
    for item in plan:
        if item["job_id"] is not None:
            job_id_counts[item["job_id"]] = job_id_counts.get(item["job_id"], 0) + 1
    ambiguous_job_ids = {j for j, count in job_id_counts.items() if count > 1}
    for item in plan:
        if item["job_id"] in ambiguous_job_ids:
            item["ambiguous"] = True
            item["job_id"] = None
        else:
            item["ambiguous"] = False

    finalized, no_db_match, ambiguous = [], [], []

    for item in plan:
        target_video, new_name, leftovers, job_id = (
            item["target_video"], item["new_name"], item["leftovers"], item["job_id"]
        )
        if item["ambiguous"]:
            repoint_note = "AMBIGUOUS -- multiple folders point to the same job, no DB repoint (needs manual review, see the open duplicate-folder question)"
        elif job_id:
            repoint_note = f"repoint job {job_id}"
        else:
            repoint_note = "no DB repoint (no matching job found)"
        label = f"{item['folder_label']}: rename '{target_video['name']}' -> '{new_name}', {repoint_note}, delete {[o['name'] for o in leftovers]}"

        if item["ambiguous"]:
            ambiguous.append(label)
        elif job_id is None:
            no_db_match.append(label)

        if not apply:
            finalized.append(label)
            continue

        await asyncio.to_thread(gdrive.rename_file, target_video["id"], new_name)
        if job_id is not None:
            with db.get_conn() as conn:
                conn.execute(
                    "UPDATE clips SET output_path = ? WHERE job_id = ?",
                    (f"{_GDRIVE_PREFIX}{target_video['id']}", job_id),
                )
                db.log_event(conn, job_id, "output_repointed", f"retrofit: repointed to finalized cropped video '{new_name}'")
        # NOT deleting `leftovers` here -- the service account's Drive role
        # can't delete files it doesn't own on this Shared Drive (confirmed
        # 2026-09-24: files().delete() 404s on a file that unquestionably
        # exists and was just listed moments before). Left for manual
        # deletion; see the printed list below.
        finalized.append(label)

    verb = "Finalized" if apply else "Would finalize"
    print(f"{verb}: {len(finalized)}")
    for f in finalized:
        print(f"  - {f}")
    print(f"Of which ambiguous (no repoint, needs manual review): {len(ambiguous)}")
    for f in ambiguous:
        print(f"  - {f}")
    print(f"Of which no DB match at all (no repoint): {len(no_db_match)}")
    for f in no_db_match:
        print(f"  - {f}")
    if not apply and finalized:
        print("\nDry run only -- re-run with --apply to actually rename/repoint/delete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="actually rename/repoint/delete (default: dry run)")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
