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
from functools import lru_cache
from pathlib import Path
from typing import Optional

from . import config

_FOLDER_MIME = "application/vnd.google-apps.folder"

_thread_local = threading.local()


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
    """Returns [{id, name, mimeType, modifiedTime}] for direct children of a folder."""
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
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, size)",
                pageSize=200,
                pageToken=page_token,
            )
            .execute()
        )
        files.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
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
    """
    from concurrent.futures import ThreadPoolExecutor

    results: list[dict] = []
    frontier: list[tuple[str, list[dict]]] = [(root_folder_id, [])]
    with ThreadPoolExecutor(max_workers=8) as executor:
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


def download_bytes(file_id: str) -> bytes:
    from googleapiclient.http import MediaIoBaseDownload

    request = _service().files().get_media(fileId=file_id, supportsAllDrives=True)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()


def download_to_path(file_id: str, dest: Path) -> Path:
    dest.write_bytes(download_bytes(file_id))
    return dest


def upload_file(parent_id: str, local_path: Path, name: Optional[str] = None, mime_type: Optional[str] = None) -> str:
    from googleapiclient.http import MediaFileUpload

    media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=False)
    created = (
        _service()
        .files()
        .create(
            body={"name": name or local_path.name, "parents": [parent_id]},
            media_body=media,
            supportsAllDrives=True,
            fields="id",
        )
        .execute()
    )
    return created["id"]
