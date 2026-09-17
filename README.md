# Smilodox Video Automation

Interne Web-App zur automatisierten Erstellung von Zalando-Produktvideos aus Referenzfotos. Statt jedes Clip einzeln manuell zu generieren, werden Produktordner aus Google Drive gescannt, in Jobs umgewandelt und über die Higgsfield-API als Video gerendert. Die fertigen Videos landen automatisch wieder im Drive.

## Stack

- **Backend:** FastAPI (Python 3.11), Worker-Loop für Job-Abarbeitung
- **Frontend:** React + Vite
- **Datenbank:** SQLite lokal, Postgres (Neon) im Hosting
- **Storage:** Google Drive, lokal per Drive Desktop oder per Drive API v3 (Service Account)
- **Generierung:** Higgsfield CLI (Kling 3.0, Gemini Omni Flash)
- **Hosting:** Render (siehe `render.yaml`)

## Video-Spezifikation

| Einstellung | Wert |
|---|---|
| Dauer | 10 Sekunden |
| Format | 9:16, 1080p |
| Schnitt | harte Schnitte, keine Kamerafahrten |
| Ton/Text | keiner |
| Modelle | `kling3_0`, `gemini_omni`, `gemini_omni_flash_1_1` |

Kling 3.0 akzeptiert nur 2 Referenzbilder (vorne + hinten) und nutzt dafür eigene Prompt-Varianten. Gemini nutzt bis zu 4 Bilder.

## Ordnerstruktur im Drive

```
reference-images/
  oberteil/   |  unterteil/
    <Produkt-SKU>/
      <sku>_full.jpg        Ganzkörper vorne
      <sku>_front.jpg       Nahaufnahme
      <sku>_fullback.jpg    Ganzkörper hinten
      <sku>_detail_one.jpg  Detailaufnahme
output/
  Oberteil/  |  Unterteil/   fertige Videos, sortiert nach Kleidungstyp
```

## Projektstruktur

```
backend/
  main.py               FastAPI-Endpunkte, Basic Auth, Job-Erstellung
  worker.py             Job-Queue, Retries, Statusverwaltung
  drive_scan.py         Scannt Produktordner, gruppiert Bilder nach Shot-Typ
  gdrive.py             Google Drive API v3 (Service Account)
  templates.py          Prompt-Templates je Kleidungstyp
  higgsfield_adapter.py Anbindung an die Higgsfield CLI
  qa.py, logo_check.py  Qualitätsprüfung, Logo-Kontrolle
  image_classify.py     Automatische Erkennung des Shot-Typs
frontend/src/views/
  Dashboard.jsx         Job-Übersicht, Status, Videovorschau
  BatchUpload.jsx       Drive-Scan und Batch-Erstellung
  Prompts.jsx           Prompt-Bearbeitung (Code-geschützt)
```

## Lokal starten

```bash
./start_backend.sh                    # Backend auf Port 8000
cd frontend && npm install && npm run dev
```

Voraussetzung: `.env` im Projektroot (nicht im Git) und eine eingerichtete Higgsfield CLI.

## Wichtige Umgebungsvariablen

| Variable | Zweck |
|---|---|
| `DATA_ROOT` | Pfad zum Drive-Ordner (lokaler Modus) |
| `USE_GDRIVE_API` | `true` schaltet auf Drive API statt lokalem Ordner |
| `GDRIVE_KEY_JSON` | Service-Account-JSON (Hosting) |
| `DATABASE_URL` | Postgres-Verbindung, leer = lokales SQLite |
| `PORTAL_USERNAME` / `PORTAL_PASSWORD` | Gemeinsamer Portal-Login |
| `PROMPT_EDIT_CODE` | Code zum Speichern von Prompt-Änderungen |
| `MAX_CREDITS_PER_BATCH` | Limit pro Batch, Standard 300 |
| `MAX_CREDITS_PER_MONTH` | Limit pro Monat, Standard 1500 |

## Kosten

15 Credits pro Video (Kling 3.0, 10s, 9:16) entsprechen etwa 0,63 EUR. Beide Credit-Limits werden geprüft, bevor ein Job angelegt wird. Der aktuelle Verbrauch ist über `GET /budget` und im Dashboard sichtbar.
