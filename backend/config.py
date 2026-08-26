import os
from pathlib import Path

# Points at the local data directory by default. Once Google Drive Desktop is
# installed and a team folder is synced, set DATA_ROOT to that folder's path
# (e.g. via the DATA_ROOT env var) so state.db, uploads/, and output/ sync
# to the team's shared Drive automatically.
DATA_ROOT = Path(os.environ.get("DATA_ROOT", Path(__file__).resolve().parent.parent / "data"))

# Internal/technical folders the team never needs to browse -- kept in their own
# subfolder so the Shared Drive root only shows reference-images/ and output/.
INTERNAL_DIR = DATA_ROOT / "Datenbank"

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
# Currently unused by the pipeline (the per-product logo-reference-image feature
# this was built for was reverted) -- kept in case that gets revisited later.
BRAND_ASSETS_DIR = DATA_ROOT / "brand_assets"

for d in (UPLOADS_DIR, OUTPUT_DIR, MANIFESTS_DIR, THUMBNAILS_DIR, BRAND_ASSETS_DIR, *OUTPUT_SUBDIRS.values()):
    d.mkdir(parents=True, exist_ok=True)

WORKER_CONCURRENCY = int(os.environ.get("WORKER_CONCURRENCY", "3"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))
RETRY_BACKOFF_BASE_SECONDS = int(os.environ.get("RETRY_BACKOFF_BASE_SECONDS", "30"))
GENERATE_WAIT_TIMEOUT = os.environ.get("GENERATE_WAIT_TIMEOUT", "20m")
WORKER_POLL_INTERVAL_SECONDS = int(os.environ.get("WORKER_POLL_INTERVAL_SECONDS", "5"))

QA_DURATION_TOLERANCE_SECONDS = float(os.environ.get("QA_DURATION_TOLERANCE_SECONDS", "0.75"))

DEFAULT_ASPECT_RATIO = "9:16"
DEFAULT_RESOLUTION = "1080p"

SUPPORTED_MODELS = ["kling3_0", "gemini_omni"]
