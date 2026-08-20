import os
from pathlib import Path

# Points at the local data directory by default. Once Google Drive Desktop is
# installed and a team folder is synced, set DATA_ROOT to that folder's path
# (e.g. via the DATA_ROOT env var) so state.db, uploads/, and output/ sync
# to the team's shared Drive automatically.
DATA_ROOT = Path(os.environ.get("DATA_ROOT", Path(__file__).resolve().parent.parent / "data"))

DB_PATH = DATA_ROOT / "state.db"
UPLOADS_DIR = DATA_ROOT / "uploads"
OUTPUT_DIR = DATA_ROOT / "output"
MANIFESTS_DIR = DATA_ROOT / "manifests"

for d in (UPLOADS_DIR, OUTPUT_DIR, MANIFESTS_DIR):
    d.mkdir(parents=True, exist_ok=True)

WORKER_CONCURRENCY = int(os.environ.get("WORKER_CONCURRENCY", "3"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))
RETRY_BACKOFF_BASE_SECONDS = int(os.environ.get("RETRY_BACKOFF_BASE_SECONDS", "30"))
GENERATE_WAIT_TIMEOUT = os.environ.get("GENERATE_WAIT_TIMEOUT", "20m")
WORKER_POLL_INTERVAL_SECONDS = int(os.environ.get("WORKER_POLL_INTERVAL_SECONDS", "5"))

QA_DURATION_TOLERANCE_SECONDS = float(os.environ.get("QA_DURATION_TOLERANCE_SECONDS", "0.75"))

DEFAULT_ASPECT_RATIO = "9:16"
DEFAULT_RESOLUTION = "1080p"

SUPPORTED_MODELS = ["seedance_2_0", "kling3_0", "gemini_omni"]
