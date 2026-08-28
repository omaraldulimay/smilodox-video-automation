"""One-off test: generate a real video directly via the Gemini Interactions API
(bypassing Higgsfield entirely), using our existing Gemini prompt template and
real reference images.

COSTS REAL MONEY (~0.88 EUR estimated) -- do not run this without deliberately
deciding to. Run manually:

    .venv/bin/python scripts/test_gemini_direct_video.py

What this does NOT do: touch the main app, the worker, or the database. This
is a standalone script so we can see whether the whole flow (reference images
in, real video out) actually works before wiring it into the real pipeline.

Known unknowns (the REST API docs didn't fully specify these -- see the
2026-08-27 session notes): whether duration_seconds/negative_prompt are
settable, and whether the response is synchronous or needs polling. This
script handles both possibilities and prints the raw response either way so
we can adapt if reality differs from the docs -- it already has, twice, today.
"""

import base64
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

sys.path.insert(0, str(PROJECT_ROOT))

import httpx

from backend import templates

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("GEMINI_API_KEY not found in .env -- aborting.")
    sys.exit(1)

# A product that has generated cleanly before (t-shirt, not activewear) --
# deliberately NOT "Leggings Amaze pro" for this first test, so we're not
# mixing "does the direct API even work" with "does this NSFW-prone product
# trigger it too".
REF_DIR = (
    PROJECT_ROOT.parent
    / "Library/CloudStorage/kontakt@firma.example/Geteilte Ablagen"
    / "Smilodox Video Automation/reference-images/oberteil/26701-tshirt-hellblau-26707"
)
# Same role order as image1-image4 in OBERTEIL_PROMPT.
REF_IMAGES = [REF_DIR / "full.png", REF_DIR / "front.png", REF_DIR / "back.png", REF_DIR / "detail.png"]

for p in REF_IMAGES:
    if not p.is_file():
        print(f"Reference image not found: {p}")
        sys.exit(1)

prompt_text = templates.resolve_prompt_text("oberteil", "gemini_omni")

print(f"Loading {len(REF_IMAGES)} reference images from:\n  {REF_DIR}\n")

input_parts = []
for p in REF_IMAGES:
    data = base64.b64encode(p.read_bytes()).decode("ascii")
    input_parts.append({"type": "image", "data": data, "mime_type": "image/png"})
input_parts.append({"type": "text", "text": prompt_text})

body = {
    "model": "gemini-omni-flash-preview",
    "input": input_parts,
    "response_format": {"type": "video", "aspect_ratio": "9:16"},
    "generation_config": {"video_config": {"task": "reference_to_video"}},
}

headers = {
    "x-goog-api-key": API_KEY,
    "Content-Type": "application/json",
    "Api-Revision": "2026-05-20",
}

print("Sending request to the Interactions API (this costs real money)...")
with httpx.Client(timeout=300) as client:
    resp = client.post(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        headers=headers,
        json=body,
    )

print(f"HTTP {resp.status_code}")
if resp.status_code != 200:
    print(resp.text[:3000])
    sys.exit(1)

interaction = resp.json()
interaction_id = interaction.get("id")
status = interaction.get("status")
print(f"interaction id={interaction_id} status={status}")

# Poll if not already completed.
poll_count = 0
with httpx.Client(timeout=60) as client:
    while status not in ("completed", "failed", "error") and poll_count < 60:
        poll_count += 1
        time.sleep(10)
        r = client.get(
            f"https://generativelanguage.googleapis.com/v1beta/interactions/{interaction_id}",
            headers=headers,
        )
        interaction = r.json()
        status = interaction.get("status")
        print(f"  poll {poll_count}: status={status}")

print()
print("=== Final response (raw) ===")
print(json.dumps(interaction, indent=2)[:4000])

output_video = interaction.get("output_video") or {}
video_b64 = output_video.get("data")
video_uri = output_video.get("uri")

out_path = PROJECT_ROOT / "scripts" / "test_output.mp4"
if video_b64:
    out_path.write_bytes(base64.b64decode(video_b64))
    print(f"\nSaved video (from inline data) to {out_path}")
elif video_uri:
    with httpx.Client(timeout=120) as client:
        v = client.get(video_uri, headers=headers)
        out_path.write_bytes(v.content)
    print(f"\nSaved video (downloaded from uri) to {out_path}")
else:
    print("\nNo output_video.data or output_video.uri found in the response -- see raw JSON above.")
