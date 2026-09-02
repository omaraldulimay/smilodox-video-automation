import re
import sqlite3
import threading
from contextlib import contextmanager

from . import config

_lock = threading.Lock()

USE_POSTGRES = bool(config.DATABASE_URL)

SCHEMA_SQLITE = """
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
    logo_check TEXT,
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

# NOTE: the shot-classification cache (image_classify.py) is deliberately NOT
# in the SQLite schema -- locally it stays a plain JSON file, unchanged. It
# only needs a table in Postgres, where it exists specifically to survive a
# hosted instance's ephemeral disk being wiped on restart/deploy.

# Same schema, Postgres dialect: SERIAL instead of AUTOINCREMENT, INTEGER
# stays INTEGER (dry_run is stored 0/1 same as SQLite, not BOOLEAN, so no
# call-site changes needed anywhere that reads/writes it).
SCHEMA_POSTGRES = """
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
    logo_check TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
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

-- Vision shot-type classifications (see image_classify.py). Postgres-only:
-- on a hosted instance the local disk is wiped on every restart/deploy, so a
-- JSON-file cache there meant re-classifying every unmatched reference image
-- through the Gemini API on every single folder scan -- the actual reason
-- scanning stayed slow after the other fixes (confirmed 2026-09-02: 19 of 63
-- images needed vision, each a full download + API call).
CREATE TABLE IF NOT EXISTS shot_classifications (
    cache_key TEXT PRIMARY KEY,
    shot_type TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_clips_status ON clips(status);
"""

_PLACEHOLDER_RE = re.compile(r"\?")


class _PgConnWrapper:
    """Makes a psycopg connection behave enough like a sqlite3 connection that
    every existing `conn.execute("... ? ...", (params,))` call site across the
    app (main.py, worker.py, this file) works completely unchanged: SQLite-
    style '?' placeholders are rewritten to psycopg's '%s' on the fly, and
    dict_row gives back dict-like rows so `row["col"]` keeps working exactly
    like sqlite3.Row did. This is the only reason a from-scratch Postgres
    rewrite of every call site wasn't needed.
    """

    def __init__(self, conn):
        self._conn = conn

    def execute(self, query: str, params=()):
        cur = self._conn.cursor()
        cur.execute(_PLACEHOLDER_RE.sub("%s", query), params)
        return cur

    def executescript(self, script: str):
        cur = self._conn.cursor()
        cur.execute(script)
        return cur

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


@contextmanager
def get_conn():
    if USE_POSTGRES:
        import psycopg
        from psycopg.rows import dict_row

        conn = psycopg.connect(config.DATABASE_URL, row_factory=dict_row, autocommit=False)
        wrapped = _PgConnWrapper(conn)
        try:
            with _lock:
                yield wrapped
                wrapped.commit()
        finally:
            wrapped.close()
        return

    conn = sqlite3.connect(config.DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        with _lock:
            yield conn
            conn.commit()
    finally:
        conn.close()


def _existing_columns(conn, table: str) -> set:
    if USE_POSTGRES:
        rows = conn.execute(
            "SELECT column_name AS name FROM information_schema.columns WHERE table_name = ?", (table,)
        ).fetchall()
    else:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA_POSTGRES if USE_POSTGRES else SCHEMA_SQLITE)
        # CREATE TABLE IF NOT EXISTS above only applies to a fresh DB -- add
        # columns introduced after the table already existed in production here.
        existing_cols = _existing_columns(conn, "clips")
        if "mode" not in existing_cols:
            conn.execute("ALTER TABLE clips ADD COLUMN mode TEXT")
        if "logo_check" not in existing_cols:
            conn.execute("ALTER TABLE clips ADD COLUMN logo_check TEXT")


def log_event(conn, job_id: str, status: str, message: str = None):
    from datetime import datetime, timezone

    # Millisecond precision + trailing "Z" (not "+00:00" with 6-digit microseconds)
    # -- the latter parses inconsistently across browsers (notably Safari).
    now_iso = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    conn.execute(
        "INSERT INTO events (job_id, status, message, created_at) VALUES (?, ?, ?, ?)",
        (job_id, status, message, now_iso),
    )
