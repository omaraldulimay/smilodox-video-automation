"""Thin synchronous Google Drive API v3 helper, used to replace the local
Drive-Desktop-synced filesystem access once the app runs on a server instead
of the user's Mac (Drive Desktop doesn't run headless on a server at all).

Runs on the service-account key at config.GDRIVE_KEY_PATH -- the account must
already be a member of the target Shared Drive (or reachable via domain-wide
delegation), see memory/project_hosted_deployment_plan.md for the setup.

Deliberately synchronous (googleapiclient has no native asyncio support) --
callers from async code (main.py routes, worker.py) must wrap calls in
asyncio.to_thread(...) so a slow Drive request doesn't block the event loop.

Every folder-scoped call passes corpora="drive" + driveId + supportsAllDrives
+ includeItemsFromAllDrives -- omitting any of these silently returns empty
results against a Shared Drive instead of an error, the single most common
mistake when working against Shared Drives specifically (confirmed against
this exact Shared Drive on 2026-09-02).
"""

import io
import threading
import time
from functools import lru_cache
from pathlib import Path
from typing import Optional

from . import config

_FOLDER_MIME = "application/vnd.google-apps.folder"

_thread_local = threading.local()

# Short-lived cache for list_children() -- the per-colorway folder layout
# (introduced 2026-09-24) added a whole extra tree level, so walk_all_files()
# now makes roughly one API round-trip per PRODUCT VARIANT (~75 of them, not
# ~16 product folders as before) just to list each color folder's contents.
# A 30s TTL doesn't help a cold first scan, but makes every scan repeated
# within that window (re-checking after uploading a few more images, retrying
# after a hiccup) return near-instantly instead of re-walking the whole tree.
# 30s is short enough that newly added folders still show up on the very next
# natural re-scan.
_list_children_cache: dict[str, tuple[float, list[dict]]] = {}
_LIST_CHILDREN_CACHE_TTL_SECONDS = 30


@lru_cache(maxsize=1)
def _credentials():
    import json

    from google.oauth2 import service_account

    scopes = ["https://www.googleapis.com/auth/drive"]
    # Prefer the raw JSON in an env var when set -- most hosts (Render etc.)
    # handle a secret env var more simply than mounting a secret file at a
    # specific path. Falls back to the file path (config.GDRIVE_KEY_PATH,
    # used locally) when the env var isn't set, so local Mac use is unchanged.
    if config.GDRIVE_KEY_JSON:
        info = json.loads(config.GDRIVE_KEY_JSON)
        return service_account.Credentials.from_service_account_info(info, scopes=scopes)
    return service_account.Credentials.from_service_account_file(str(config.GDRIVE_KEY_PATH), scopes=scopes)


def _service():
    # One googleapiclient Resource (and its underlying httplib2.Http/socket)
    # PER THREAD, not shared -- walk_all_files() below calls this concurrently
    # from a ThreadPoolExecutor, and a single shared httplib2 connection is
    # not safe for concurrent use (confirmed 2026-09-02: sharing one via
    # @lru_cache caused "ssl.SSLError: [SSL: WRONG_VERSION_NUMBER]" under
    # concurrent requests). The credentials object itself is safe to share.
    service = getattr(_thread_local, "service", None)
    if service is None:
        from googleapiclient.discovery import build

        service = build("drive", "v3", credentials=_credentials(), cache_discovery=False)
        _thread_local.service = service
    return service


@lru_cache(maxsize=1)
def get_shared_drive_id() -> str:
    drives = _service().drives().list(pageSize=50).execute().get("drives", [])
    match = next((d for d in drives if d["name"] == config.GDRIVE_SHARED_DRIVE_NAME), None)
    if match is None:
        raise RuntimeError(
            f'Shared Drive "{config.GDRIVE_SHARED_DRIVE_NAME}" not visible to the service account -- '
            "check its membership."
        )
    return match["id"]


def list_children(folder_id: str) -> list[dict]:
    """Returns [{id, name, mimeType, modifiedTime}] for direct children of a
    folder. Cached for _LIST_CHILDREN_CACHE_TTL_SECONDS -- see that constant's
    comment. Safe to call concurrently from multiple threads (walk_all_files'
    thread pool does exactly that): a plain dict read/write is enough here,
    since the only race is two threads both missing an expired/absent entry
    and both re-fetching it, which just costs one redundant API call, never
    inconsistent data.
    """
    now = time.monotonic()
    cached = _list_children_cache.get(folder_id)
    if cached is not None and (now - cached[0]) < _LIST_CHILDREN_CACHE_TTL_SECONDS:
        return cached[1]

    drive_id = get_shared_drive_id()
    files: list[dict] = []
    page_token = None
    while True:
        resp = (
            _service()
            .files()
            .list(
                q=f"'{folder_id}' in parents and trashed = false",
                corpora="drive",
                driveId=drive_id,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, size, thumbnailLink)",
                pageSize=200,
                pageToken=page_token,
            )
            .execute()
        )
        files.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    _list_children_cache[folder_id] = (now, files)
    return files


def find_child(folder_id: str, name: str) -> Optional[dict]:
    return next((f for f in list_children(folder_id) if f["name"] == name), None)


@lru_cache(maxsize=8)
def find_root_folder(name: str) -> str:
    """Finds a top-level folder by name directly under the Shared Drive root."""
    drive_id = get_shared_drive_id()
    match = find_child(drive_id, name)
    if match is None:
        raise RuntimeError(f'"{name}" not found at the Shared Drive root.')
    return match["id"]


def find_or_create_folder(parent_id: str, name: str) -> str:
    existing = find_child(parent_id, name)
    if existing and existing["mimeType"] == _FOLDER_MIME:
        return existing["id"]
    created = (
        _service()
        .files()
        .create(
            body={"name": name, "mimeType": _FOLDER_MIME, "parents": [parent_id]},
            supportsAllDrives=True,
            fields="id",
        )
        .execute()
    )
    return created["id"]


def walk_all_files(root_folder_id: str) -> list[dict]:
    """Recursively lists every non-folder file under root_folder_id, each with
    an added "_parent_chain" (list of ancestor folder dicts, root-relative) so
    callers can reconstruct nesting without repeated API round-trips.

    Lists one tree level at a time, fetching every folder at that level
    concurrently (thread pool -- the Drive API client is synchronous) instead
    of one folder at a time. For our layout (root -> oberteil/unterteil ->
    ~16 product folders) that's the difference between ~18 sequential round-
    trips and ~3 batches of parallel ones -- confirmed as the main contributor
    to the multi-second scan time on a hosted instance (2026-09-02).

    max_workers raised 8 -> 24 on 2026-09-24: the per-colorway folder layout
    added a whole extra tree level (article -> color -> images), so the
    widest level now has ~75 folders to list (one per product variant, not
    ~16 product folders as before) -- with 8 workers that was ~10 sequential
    batches of round-trips; with 24 it's ~4. Purely I/O-bound (waiting on
    Drive API responses), so this is safe against Drive's per-user rate limit
    (far below it for a single scan's short burst) and doesn't meaningfully
    add CPU load.
    """
    from concurrent.futures import ThreadPoolExecutor

    results: list[dict] = []
    frontier: list[tuple[str, list[dict]]] = [(root_folder_id, [])]
    with ThreadPoolExecutor(max_workers=24) as executor:
        while frontier:
            futures = [(fid, ancestors, executor.submit(list_children, fid)) for fid, ancestors in frontier]
            next_frontier: list[tuple[str, list[dict]]] = []
            for _fid, ancestors, future in futures:
                for child in future.result():
                    if child["mimeType"] == _FOLDER_MIME:
                        next_frontier.append((child["id"], ancestors + [child]))
                    else:
                        child["_parent_chain"] = ancestors
                        results.append(child)
            frontier = next_frontier
    return results


def get_file_metadata(file_id: str) -> dict:
    return (
        _service()
        .files()
        .get(fileId=file_id, supportsAllDrives=True, fields="id, name, mimeType")
        .execute()
    )


def get_parent_folder(file_id: str) -> Optional[dict]:
    """Returns {id, name} for `file_id`'s immediate parent folder, or None if
    it has none (Shared Drive root)."""
    meta = (
        _service()
        .files()
        .get(fileId=file_id, supportsAllDrives=True, fields="id, name, parents")
        .execute()
    )
    parents = meta.get("parents") or []
    if not parents:
        return None
    parent_id = parents[0]
    parent_meta = (
        _service()
        .files()
        .get(fileId=parent_id, supportsAllDrives=True, fields="id, name")
        .execute()
    )
    return {"id": parent_meta["id"], "name": parent_meta["name"]}


def article_folder_for_file(file_id: str, garment_folder_names: set) -> Optional[str]:
    """Walks UP from a reference image's real Drive location to find the
    article folder name directly under oberteil/unterteil -- i.e. the live-API
    equivalent of drive_scan._article_folder_name(), for a file whose
    ancestor chain isn't already known (e.g. migrating an old job that
    predates the article_name column). `garment_folder_names` is
    drive_scan.GARMENT_FOLDER_NAMES's key set (lowercased "oberteil"/
    "unterteil"). Returns None if no such ancestor is found within 10 levels
    (a sane bound -- the real layout is never that deep) or the file has no
    parent at all.
    """
    current_id = file_id
    last_name = None
    for _ in range(10):
        parent = get_parent_folder(current_id)
        if parent is None:
            return None
        if parent["name"].strip().lower() in garment_folder_names:
            return last_name
        last_name = parent["name"]
        current_id = parent["id"]
    return None


def download_bytes(file_id: str) -> bytes:
    from googleapiclient.http import MediaIoBaseDownload

    request = _service().files().get_media(fileId=file_id, supportsAllDrives=True)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        # num_retries turns on googleapiclient's own built-in exponential-
        # backoff retry for exactly the class of transient connection error
        # confirmed 2026-09-24 (see worker.py's _download docstring): a
        # dropped/reset connection mid-transfer under concurrent load. Was
        # previously 0 (the client's default) -- a single reset failed the
        # whole download outright.
        _, done = downloader.next_chunk(num_retries=5)
    return buf.getvalue()


def download_to_path(file_id: str, dest: Path) -> Path:
    dest.write_bytes(download_bytes(file_id))
    return dest


def download_thumbnail_bytes(thumbnail_link: str) -> Optional[bytes]:
    """Fetches Drive's own pre-generated small preview image (~a few KB-100KB,
    already downsized server-side by Google) instead of the full multi-MB
    original -- used for the batch-upload scan preview, where downloading the
    full shoot original just to shrink it to a 56x56 thumbnail was the actual
    bottleneck behind slow-loading previews on a hosted instance (confirmed
    2026-09-02: scanning the folder tree itself takes ~2s, but each preview
    image required a full-size download + ffmpeg resize).

    Needs an Authorization header (the file isn't public) -- reuses the same
    service-account credentials as the API client. Returns None on any
    failure so the caller can fall back to the full download.
    """
    import requests

    creds = _credentials()
    if not creds.valid:
        import google.auth.transport.requests

        creds.refresh(google.auth.transport.requests.Request())
    try:
        resp = requests.get(thumbnail_link, headers={"Authorization": f"Bearer {creds.token}"}, timeout=15)
        if resp.status_code == 200 and resp.content:
            return resp.content
    except requests.RequestException:
        pass
    return None


def upload_file(parent_id: str, local_path: Path, name: Optional[str] = None, mime_type: Optional[str] = None) -> str:
    from googleapiclient.http import MediaFileUpload

    # resumable=True + num_retries: same reasoning as download_bytes()'s
    # num_retries -- a finished video is often several MB, and previously a
    # single non-resumable upload had no protection against a transient
    # connection drop mid-transfer (the exact failure class confirmed
    # 2026-09-24). Resumable uploads let googleapiclient continue from where
    # it left off instead of restarting the whole upload on a retry.
    media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=True)
    created = (
        _service()
        .files()
        .create(
            body={"name": name or local_path.name, "parents": [parent_id]},
            media_body=media,
            supportsAllDrives=True,
            fields="id",
        )
        .execute(num_retries=5)
    )
    return created["id"]
