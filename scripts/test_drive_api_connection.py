"""Verifies the Google Drive API connection before any pipeline code depends on it.

Run:  .venv/bin/python -m scripts.test_drive_api_connection

Checks, in order:
  1. the service-account key file exists and parses
  2. the credentials authenticate against the Drive API
  3. the Shared Drive is actually visible to the service account
  4. reference-images/ and output/ can be listed, with a sample of what's inside

Note on Shared Drives: every call needs supportsAllDrives/includeItemsFromAllDrives,
otherwise the API silently returns only My Drive content and everything looks empty
even when access is fine -- the single most common false negative here.
"""

import json
import sys
from pathlib import Path

KEY_PATH = Path(__file__).resolve().parent.parent / "internal_data" / "gdrive-service-account.json"
SHARED_DRIVE_NAME = "Smilodox Video Automation"
SCOPES = ["https://www.googleapis.com/auth/drive"]


def fail(msg: str) -> None:
    print(f"\n  FEHLER: {msg}")
    sys.exit(1)


def main() -> None:
    print("1. Schlüsseldatei prüfen ...")
    if not KEY_PATH.is_file():
        fail(f"nicht gefunden: {KEY_PATH}\n  Bitte die JSON-Datei genau dorthin verschieben.")
    try:
        key_data = json.loads(KEY_PATH.read_text())
    except json.JSONDecodeError as exc:
        fail(f"JSON ungültig: {exc}")
    client_email = key_data.get("client_email", "?")
    print(f"   OK -- Dienstkonto: {client_email}")

    print("2. Authentifizieren ...")
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(str(KEY_PATH), scopes=SCOPES)
        service = build("drive", "v3", credentials=creds, cache_discovery=False)
    except Exception as exc:  # noqa: BLE001 - surface whatever went wrong verbatim
        fail(f"Authentifizierung fehlgeschlagen: {exc}")
    print("   OK")

    print("3. Shared Drive suchen ...")
    try:
        drives = service.drives().list(pageSize=50).execute().get("drives", [])
    except Exception as exc:  # noqa: BLE001
        fail(f"Konnte geteilte Ablagen nicht auflisten: {exc}")

    if not drives:
        fail(
            "Das Dienstkonto sieht keine geteilte Ablage.\n"
            "  Ist die Dienstkonto-E-Mail wirklich als Mitglied der Ablage eingetragen?"
        )
    print(f"   Sichtbare Ablagen: {[d['name'] for d in drives]}")

    target = next((d for d in drives if d["name"] == SHARED_DRIVE_NAME), None)
    if target is None:
        fail(f'"{SHARED_DRIVE_NAME}" ist nicht dabei -- Mitgliedschaft prüfen.')
    drive_id = target["id"]
    print(f'   OK -- "{SHARED_DRIVE_NAME}" gefunden (id: {drive_id})')

    print("4. Inhalt auflisten ...")
    top = (
        service.files()
        .list(
            q=f"'{drive_id}' in parents and trashed = false",
            corpora="drive",
            driveId=drive_id,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            fields="files(id, name, mimeType)",
            pageSize=50,
        )
        .execute()
        .get("files", [])
    )
    print(f"   Oberste Ebene: {[f['name'] for f in top] or '(leer)'}")

    for folder_name in ("reference-images", "output"):
        folder = next((f for f in top if f["name"] == folder_name), None)
        if folder is None:
            print(f"   WARNUNG: '{folder_name}/' nicht gefunden")
            continue
        children = (
            service.files()
            .list(
                q=f"'{folder['id']}' in parents and trashed = false",
                corpora="drive",
                driveId=drive_id,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                fields="files(id, name, mimeType)",
                pageSize=10,
            )
            .execute()
            .get("files", [])
        )
        sample = [f["name"] for f in children[:5]]
        print(f"   {folder_name}/ -> {len(children)} Einträge, z.B. {sample or '(leer)'}")

    print("\n  ALLES OK -- die Drive-API-Verbindung funktioniert.")


if __name__ == "__main__":
    main()
