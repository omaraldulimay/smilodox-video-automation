"""One-off connectivity check for the direct Gemini API (bypassing Higgsfield).

Run manually: .venv/bin/python scripts/test_gemini_api_connection.py

Sends a single trivial text prompt to a cheap Gemini model to confirm the API
key + billing are actually wired up correctly, before we touch anything video-
or money-related. Does NOT call Omni Flash and does NOT generate video --
this is deliberately the smallest possible real request.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("GEMINI_API_KEY not found in .env -- aborting.")
    sys.exit(1)

from google import genai

client = genai.Client(api_key=api_key)

print("Sending a minimal test request to Gemini...")
response = client.models.generate_content(
    model="gemini-3.6-flash",
    contents="Reply with exactly: connection ok",
)

print()
print("Response:", response.text)
print()
print("If you see 'connection ok' above, the API key and billing are working.")
