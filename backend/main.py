import csv
import io
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, db, worker, templates, drive_scan, qa
from . import higgsfield_adapter as hf

app = FastAPI(title="Smilodox Video Automation")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _now_iso() -> str:
    # Millisecond precision + trailing "Z" (not "+00:00" with 6-digit microseconds)
    # -- the latter parses inconsistently across browsers (notably Safari), which
    # showed up as wrong "time ago" values in the dashboard.
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@app.on_event("startup")
async def on_startup():
    db.init_db()
    templates.seed_templates()
    worker.start_workers()


@app.on_event("shutdown")
async def on_shutdown():
    await worker.stop_workers()


class JobOut(BaseModel):
    job_id: str


def _save_upload(upload: UploadFile, dest_dir: Path) -> str:
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(upload.filename or "").suffix
    dest = dest_dir / f"{uuid.uuid4().hex}{suffix}"
    with open(dest, "wb") as f:
        f.write(upload.file.read())
    return str(dest)


def _insert_job(
    product_id: Optional[str],
    template_key: Optional[str],
    prompt: str,
    model: str,
    duration: float,
    aspect_ratio: str,
    resolution: Optional[str],
    reference_paths: list,
    dry_run: bool,
    mode: Optional[str] = None,
) -> str:
    if model not in config.SUPPORTED_MODELS:
        raise HTTPException(400, f"unsupported model '{model}', expected one of {config.SUPPORTED_MODELS}")

    job_id = uuid.uuid4().hex
    now = _now_iso()
    with db.get_conn() as conn:
        conn.execute(
            """
            INSERT INTO clips (
                job_id, product_id, template_key, prompt, model, duration, aspect_ratio, resolution,
                mode, reference_paths_json, dry_run, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (
                job_id,
                product_id,
                template_key,
                prompt,
                model,
                duration,
                aspect_ratio,
                resolution,
                mode,
                json.dumps(reference_paths) if reference_paths else None,
                1 if dry_run else 0,
                now,
                now,
            ),
        )
        db.log_event(conn, job_id, "pending", "job created")
    return job_id


def _get_template(template_key: str) -> dict:
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM prompt_templates WHERE template_key = ?", (template_key,)
        ).fetchone()
    if row is None:
        raise HTTPException(400, f"unknown template_key '{template_key}'")
    return dict(row)


@app.get("/templates")
async def list_templates():
    with db.get_conn() as conn:
        rows = conn.execute("SELECT * FROM prompt_templates ORDER BY garment_type").fetchall()
    return [dict(row) for row in rows]


@app.post("/jobs", response_model=JobOut)
async def create_job(
    model: str = Form(...),
    prompt: Optional[str] = Form(None),
    template_key: Optional[str] = Form(None),
    duration: Optional[float] = Form(None),
    aspect_ratio: Optional[str] = Form(None),
    resolution: Optional[str] = Form(None),
    mode: Optional[str] = Form(None),
    product_id: Optional[str] = Form(None),
    dry_run: bool = Form(False),
    references: list[UploadFile] = File(default=[]),
):
    """Either `prompt` or `template_key` must be given. When `template_key` is set,
    its prompt/duration/aspect_ratio/resolution are used as defaults and can still
    be overridden by explicitly passing the other fields."""
    if template_key:
        t = _get_template(template_key)
        prompt = prompt or templates.resolve_prompt_text(template_key, model)
        duration = duration if duration is not None else t["duration"]
        aspect_ratio = aspect_ratio or t["aspect_ratio"]
        resolution = resolution or t["resolution"]
    if not prompt:
        raise HTTPException(400, "either 'prompt' or 'template_key' is required")

    reference_paths = [_save_upload(f, config.UPLOADS_DIR) for f in references if f is not None and f.filename]
    job_id = _insert_job(
        product_id,
        template_key,
        prompt,
        model,
        duration if duration is not None else 9.0,
        aspect_ratio or config.DEFAULT_ASPECT_RATIO,
        resolution or config.DEFAULT_RESOLUTION,
        reference_paths,
        dry_run,
        mode,
    )
    return JobOut(job_id=job_id)


@app.post("/jobs/batch")
async def create_batch(
    manifest: UploadFile = File(...),
    images: list[UploadFile] = File(default=[]),
    dry_run: bool = Form(False),
):
    """CSV columns: product_id, template_key, prompt, model, duration, aspect_ratio,
    resolution, reference_images.

    `reference_images` holds one or more filenames separated by `;`, each matching
    the filename of one of the uploaded `images`. Either `template_key` or `prompt`
    must be set per row (template_key fills in prompt/duration/aspect_ratio/resolution
    defaults, `prompt`/other columns override them when also present).
    """
    image_by_name = {}
    for img in images:
        saved_path = _save_upload(img, config.UPLOADS_DIR)
        image_by_name[img.filename] = saved_path

    raw = (await manifest.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))

    created, errors = [], []
    for i, row in enumerate(reader):
        try:
            ref_names = [n.strip() for n in (row.get("reference_images") or "").split(";") if n.strip()]
            reference_paths = []
            for name in ref_names:
                path = image_by_name.get(name)
                if path is None:
                    raise ValueError(f"reference_images entry '{name}' not found among uploaded images")
                reference_paths.append(path)

            template_key = (row.get("template_key") or "").strip() or None
            prompt = (row.get("prompt") or "").strip() or None
            duration = float(row["duration"]) if row.get("duration") else None
            aspect_ratio = (row.get("aspect_ratio") or "").strip() or None
            resolution = (row.get("resolution") or "").strip() or None
            model = (row.get("model") or "").strip() or config.SUPPORTED_MODELS[0]

            if template_key:
                t = _get_template(template_key)
                prompt = prompt or templates.resolve_prompt_text(template_key, model)
                duration = duration if duration is not None else t["duration"]
                aspect_ratio = aspect_ratio or t["aspect_ratio"]
                resolution = resolution or t["resolution"]
            if not prompt:
                raise ValueError("row has neither 'template_key' nor 'prompt'")

            job_id = _insert_job(
                product_id=row.get("product_id"),
                template_key=template_key,
                prompt=prompt,
                model=model,
                duration=duration if duration is not None else 9.0,
                aspect_ratio=aspect_ratio or config.DEFAULT_ASPECT_RATIO,
                resolution=resolution or config.DEFAULT_RESOLUTION,
                reference_paths=reference_paths,
                dry_run=dry_run,
            )
            created.append(job_id)
        except Exception as exc:  # noqa: BLE001 - collected per-row, batch keeps going
            errors.append({"row": i + 1, "error": str(exc)})

    return {"created": created, "errors": errors}


class DriveScanIn(BaseModel):
    folder_path: str
    default_template_key: Optional[str] = None
    model: Optional[str] = None


@app.post("/jobs/batch/drive-scan/preview")
async def preview_drive_scan(body: DriveScanIn):
    """Scans the folder and reports what would be created, without creating anything."""
    try:
        groups = drive_scan.scan_folder(body.folder_path, model=body.model)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    for g in groups:
        g["template_key"] = g["template_key"] or body.default_template_key

    unresolved = [g["variant_number"] for g in groups if not g["template_key"]]
    return {
        "groups": groups,
        "total": len(groups),
        "incomplete": sum(1 for g in groups if not g["complete"]),
        "missing_template": unresolved,
    }


@app.get("/jobs/batch/drive-scan/image")
async def drive_scan_image(path: str):
    """Serves a single reference-image file by absolute path for scan-preview thumbnails.

    no-store because the team edits/replaces these files on disk directly (e.g.
    swapping a bad reference photo) -- the URL (same path) never changes when they
    do, so browsers must never cache this response or a stale image lingers in the
    preview after a real, on-disk swap.
    """
    file_path = Path(path)
    if file_path.suffix.lower() not in drive_scan.IMAGE_EXTENSIONS:
        raise HTTPException(400, "not a recognized image file")
    if not file_path.is_file():
        raise HTTPException(404, "file not found")
    return FileResponse(file_path, headers={"Cache-Control": "no-store"})


class DriveScanCommitIn(BaseModel):
    folder_path: str
    default_template_key: Optional[str] = None
    model: str
    resolution: Optional[str] = None
    mode: Optional[str] = None
    dry_run: bool = False
    include_folders: Optional[list[str]] = None


@app.post("/jobs/batch/drive-scan/commit")
async def commit_drive_scan(body: DriveScanCommitIn):
    """Scans the folder and creates one job per detected (complete or not) variant group.

    If `include_folders` is given, only groups whose folder is in that list are
    committed -- lets the UI let people deselect products they already generated.
    """
    try:
        groups = drive_scan.scan_folder(body.folder_path, model=body.model)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    if body.include_folders is not None:
        include_set = set(body.include_folders)
        groups = [g for g in groups if g["folder"] in include_set]

    created, errors = [], []
    for g in groups:
        template_key = g["template_key"] or body.default_template_key
        try:
            if not template_key:
                raise ValueError("no template_key detected from folder name and none given as default")
            t = _get_template(template_key)
            reference_paths = drive_scan.reference_paths_for_model(g["images"], body.model)
            job_id = _insert_job(
                product_id=g["variant_number"],
                template_key=template_key,
                prompt=templates.resolve_prompt_text(template_key, body.model),
                model=body.model,
                duration=t["duration"],
                aspect_ratio=t["aspect_ratio"],
                resolution=body.resolution or t["resolution"],
                reference_paths=reference_paths,
                dry_run=body.dry_run,
                mode=body.mode,
            )
            created.append(job_id)
        except Exception as exc:  # noqa: BLE001 - collected per-variant, scan keeps going
            errors.append({"variant_number": g["variant_number"], "error": str(exc)})

    return {"created": created, "errors": errors}


# The dashboard only offers these 4 simplified statuses; "completed"/"failed" each
# expand to the finer-grained statuses the worker actually uses internally.
STATUS_GROUPS = {
    "completed": ("completed", "completed_dry_run"),
    "failed": ("failed_transient", "failed_permanent", "qa_failed"),
}


@app.get("/jobs")
async def list_jobs(
    status: Optional[str] = None,
    model: Optional[str] = None,
    dry_run: Optional[int] = None,
    limit: int = 200,
):
    query = "SELECT * FROM clips WHERE 1=1"
    params: list = []
    if status:
        statuses = STATUS_GROUPS.get(status, (status,))
        query += f" AND status IN ({','.join('?' for _ in statuses)})"
        params.extend(statuses)
    if model:
        query += " AND model = ?"
        params.append(model)
    if dry_run is not None:
        query += " AND dry_run = ?"
        params.append(dry_run)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with db.get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    with db.get_conn() as conn:
        row = conn.execute("SELECT * FROM clips WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "job not found")
        events = conn.execute(
            "SELECT * FROM events WHERE job_id = ? ORDER BY created_at ASC", (job_id,)
        ).fetchall()
    return {"job": dict(row), "events": [dict(e) for e in events]}


def _get_output_path(job_id: str) -> Path:
    with db.get_conn() as conn:
        row = conn.execute("SELECT output_path FROM clips WHERE job_id = ?", (job_id,)).fetchone()
    if row is None or not row["output_path"]:
        raise HTTPException(404, "no video for this job")
    path = Path(row["output_path"])
    if not path.is_file():
        raise HTTPException(404, "video file not found")
    return path


@app.get("/jobs/{job_id}/video")
async def get_job_video(job_id: str):
    """Streams the finished video for hover-preview / playback in the dashboard."""
    return FileResponse(_get_output_path(job_id), media_type="video/mp4")


@app.get("/jobs/{job_id}/thumbnail")
async def get_job_thumbnail(job_id: str):
    """Serves a still frame from the finished video. Normally already generated
    proactively by the worker right after the job finishes (see worker.py) --
    this lazily generates it only as a fallback for videos made before that
    existed, so it never re-runs ffmpeg once cached."""
    video_path = _get_output_path(job_id)
    thumb_path = await qa.ensure_thumbnail(video_path)
    if not thumb_path.is_file():
        raise HTTPException(500, "thumbnail generation failed")
    return FileResponse(thumb_path, media_type="image/jpeg")


@app.post("/jobs/{job_id}/retry")
async def retry_job(job_id: str):
    with db.get_conn() as conn:
        row = conn.execute("SELECT * FROM clips WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "job not found")

        # Re-resolve the prompt from the current template on every retry -- the
        # stored `prompt` is a frozen snapshot from whenever the job was first
        # created, so without this a retry after editing templates.py (e.g. a
        # wording fix) would silently keep resubmitting the old, pre-fix prompt.
        # Only template-backed jobs can be refreshed this way; a manually
        # supplied prompt (no template_key) has no template to re-resolve from.
        prompt = row["prompt"]
        if row["template_key"]:
            try:
                prompt = templates.resolve_prompt_text(row["template_key"], row["model"])
            except KeyError:
                pass

        conn.execute(
            """
            UPDATE clips
            SET status = 'pending', prompt = ?, retry_count = 0, next_retry_at = NULL, error_message = NULL, updated_at = ?
            WHERE job_id = ?
            """,
            (prompt, _now_iso(), job_id),
        )
        db.log_event(conn, job_id, "pending", "manual retry")
    return {"ok": True}


@app.get("/models")
async def get_models():
    return await hf.list_models(config.SUPPORTED_MODELS)


class CostEstimateIn(BaseModel):
    model: str
    duration: float
    aspect_ratio: str = config.DEFAULT_ASPECT_RATIO
    resolution: Optional[str] = config.DEFAULT_RESOLUTION
    mode: Optional[str] = None
    prompt: str = "estimate"


@app.post("/cost-estimate")
async def cost_estimate(body: CostEstimateIn):
    """Live cost lookup for the UI -- no job is created, nothing touches the DB."""
    try:
        credits = await hf.estimate_cost(
            body.model, body.prompt, body.duration, body.aspect_ratio, body.resolution, body.mode
        )
    except hf.GenerationError as exc:
        raise HTTPException(400, str(exc))
    return {"credits": credits}


@app.get("/stats")
async def get_stats():
    with db.get_conn() as conn:
        rows = conn.execute("SELECT status, COUNT(*) as n FROM clips GROUP BY status").fetchall()
    counts = {row["status"]: row["n"] for row in rows}

    account = None
    try:
        account = await hf.account_status()
    except Exception as exc:  # noqa: BLE001 - surfaced as null so the dashboard still renders
        account = {"error": str(exc)}

    return {"counts": counts, "account": account}


# Serve the built frontend (npm run build -> frontend/dist) if present.
_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
