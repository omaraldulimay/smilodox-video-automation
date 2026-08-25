import sqlite3
import threading
from contextlib import contextmanager

from . import config

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS clips (
    job_id TEXT PRIMARY KEY,
    product_id TEXT,
    template_key TEXT,
    prompt TEXT NOT NULL,
    model TEXT NOT NULL,
    duration REAL NOT NULL,
    aspect_ratio TEXT NOT NULL,
    resolution TEXT,
    mode TEXT,
    reference_paths_json TEXT,
    dry_run INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    higgsfield_job_id TEXT,
    output_path TEXT,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    next_retry_at TEXT,
    credits_estimate REAL,
    qa_status TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prompt_templates (
    template_key TEXT PRIMARY KEY,
    garment_type TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    duration REAL NOT NULL,
    aspect_ratio TEXT NOT NULL,
    resolution TEXT,
    shot_count INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_clips_status ON clips(status);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(config.DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        with _lock:
            yield conn
            conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        # CREATE TABLE IF NOT EXISTS above only applies to a fresh DB -- add
        # columns introduced after the table already existed in production here.
        existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(clips)")}
        if "mode" not in existing_cols:
            conn.execute("ALTER TABLE clips ADD COLUMN mode TEXT")


def log_event(conn, job_id: str, status: str, message: str = None):
    from datetime import datetime, timezone

    # Millisecond precision + trailing "Z" (not "+00:00" with 6-digit microseconds)
    # -- the latter parses inconsistently across browsers (notably Safari).
    now_iso = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    conn.execute(
        "INSERT INTO events (job_id, status, message, created_at) VALUES (?, ?, ?, ?)",
        (job_id, status, message, now_iso),
    )
