import os
from pathlib import Path

from dotenv import load_dotenv

# Loads .env (GEMINI_API_KEY etc.) into the process environment -- config.py is
# imported before anything else that reads env vars, so this must run first.
# .env itself is gitignored; each machine running the backend needs its own.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Team-visible folder: reference images in, finished videos out. Set via the
# DATA_ROOT env var to the team's Google Drive Desktop folder so everyone sees
# the same files.
DATA_ROOT = Path(os.environ.get("DATA_ROOT", Path(__file__).resolve().parent.parent / "data"))

# Internal/technical storage -- deliberately NOT inside DATA_ROOT/Drive. Two
# reasons: (1) so the team's Shared Drive root only ever shows
# reference-images/ and output/, nothing else to accidentally click into, and
# (2) state.db is written on every single API request -- letting Google Drive
# continuously try to sync an actively-written SQLite file risks lock/sync
# conflicts. Defaults to a local-only folder next to the app.
INTERNAL_ROOT = Path(os.environ.get("INTERNAL_ROOT", Path(__file__).resolve().parent.parent / "internal_data"))
INTERNAL_DIR = INTERNAL_ROOT / "Datenbank"

DB_PATH = INTERNAL_DIR / "state.db"
UPLOADS_DIR = INTERNAL_DIR / "uploads"
OUTPUT_DIR = DATA_ROOT / "output"
# Finished videos are sorted into these by the job's template_key (oberteil/
# unterteil) so the team can find a product's video without scanning one flat
# folder of job-id-named files. A job with no recognized template_key (e.g. a
# manually supplied prompt) falls back to OUTPUT_DIR itself.
OUTPUT_SUBDIRS = {
    "oberteil": OUTPUT_DIR / "Oberteil",
    "unterteil": OUTPUT_DIR / "Unterteil",
}
MANIFESTS_DIR = INTERNAL_DIR / "manifests"
# Preview thumbnails (qa.ensure_thumbnail) -- kept out of OUTPUT_DIR so the
# Shared Drive output/ folder the team browses only ever contains the actual
# generated videos, never the internal .jpg previews the dashboard uses.
THUMBNAILS_DIR = INTERNAL_DIR / "thumbnails"
# Downsized copies of reference photos for the batch-upload scan preview (see
# drive_scan.ensure_reference_thumbnail) -- the source photos are full-res
# shoot originals (often 9-14MB), too large to serve directly for a 56x56
# on-screen thumbnail without risking browser decode failures under load.
REFERENCE_THUMBS_DIR = INTERNAL_DIR / "reference_thumbnails"
# Currently unused by the pipeline (the per-product logo-reference-image feature
# this was built for was reverted) -- kept in case that gets revisited later.
BRAND_ASSETS_DIR = INTERNAL_ROOT / "brand_assets"
# Per-job fix packages for the logo-check gate (see logo_check.py): the original
# reference logo image + a note with the failure timecode, for the manual
# DaVinci Resolve/Fusion correction step.
LOGO_FIXES_DIR = INTERNAL_ROOT / "logo_fixes"

for d in (
    UPLOADS_DIR, OUTPUT_DIR, MANIFESTS_DIR, THUMBNAILS_DIR, REFERENCE_THUMBS_DIR,
    BRAND_ASSETS_DIR, LOGO_FIXES_DIR, *OUTPUT_SUBDIRS.values(),
):
    d.mkdir(parents=True, exist_ok=True)

WORKER_CONCURRENCY = int(os.environ.get("WORKER_CONCURRENCY", "3"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))
RETRY_BACKOFF_BASE_SECONDS = int(os.environ.get("RETRY_BACKOFF_BASE_SECONDS", "30"))
GENERATE_WAIT_TIMEOUT = os.environ.get("GENERATE_WAIT_TIMEOUT", "20m")
WORKER_POLL_INTERVAL_SECONDS = int(os.environ.get("WORKER_POLL_INTERVAL_SECONDS", "5"))

QA_DURATION_TOLERANCE_SECONDS = float(os.environ.get("QA_DURATION_TOLERANCE_SECONDS", "0.75"))

DEFAULT_ASPECT_RATIO = "9:16"
DEFAULT_RESOLUTION = "1080p"

SUPPORTED_MODELS = ["kling3_0", "gemini_omni", "gemini_omni_flash_1_1"]

# Shared team login (HTTP Basic Auth, see main.py) -- gates the whole portal
# (API + frontend) behind one login prompt. Set PORTAL_PASSWORD in .env to a
# real value; the fallback here is only so the app doesn't crash if it's
# missing, not a secure default -- change it before sharing portal access.
PORTAL_USERNAME = os.environ.get("PORTAL_USERNAME", "smilodox")
PORTAL_PASSWORD = os.environ.get("PORTAL_PASSWORD", "changeme")
