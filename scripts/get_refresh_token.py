"""
Get Google OAuth refresh token — works in Cloud Shell (no local browser needed).

Steps:
  1. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your environment
  2. Run: python scripts/get_refresh_token.py
  3. Open the printed URL in YOUR local browser
  4. Authorize → browser redirects to http://localhost/?code=xxx (page won't load, that's fine)
  5. Copy the FULL redirect URL from your browser address bar
  6. Paste it back into the terminal when prompted
  7. Copy the printed GOOGLE_REFRESH_TOKEN into your .env
"""

from __future__ import annotations

import os

from google_auth_oauthlib.flow import Flow

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

if not CLIENT_ID or CLIENT_ID == "paste-your-client-id":
    CLIENT_ID = input("Enter your GOOGLE_CLIENT_ID: ").strip()
if not CLIENT_SECRET or CLIENT_SECRET == "paste-your-client-secret":
    CLIENT_SECRET = input("Enter your GOOGLE_CLIENT_SECRET: ").strip()

flow = Flow.from_client_config(
    {
        "installed": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uris": ["http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    },
    scopes=["https://www.googleapis.com/auth/calendar"],
    redirect_uri="http://localhost",
)

auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")

print("\n" + "=" * 60)
print("STEP 1 — Open this URL in your local browser:")
print("=" * 60)
print(auth_url)
print("=" * 60)
print("\nSTEP 2 — After authorizing, your browser will try to load")
print("http://localhost/?code=...  (it will fail to load — that's OK)")
print("\nSTEP 3 — Copy the FULL URL from your browser address bar and paste below.")
print()

redirect_response = input("Paste the full redirect URL here: ").strip()

flow.fetch_token(authorization_response=redirect_response)
creds = flow.credentials

print("\n" + "=" * 60)
print("SUCCESS — add this to your .env file:")
print("=" * 60)
print(f"GOOGLE_CLIENT_ID={CLIENT_ID}")
print(f"GOOGLE_CLIENT_SECRET={CLIENT_SECRET}")
print(f"GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
print("=" * 60)
