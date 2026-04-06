# get_refresh_token.py  — run once locally, never commit
from google_auth_oauthlib.flow import InstalledAppFlow

CLIENT_ID = "paste-your-client-id"
CLIENT_SECRET = "paste-your-client-secret"

flow = InstalledAppFlow.from_client_config(
    {
        "installed": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    },
    scopes=["https://www.googleapis.com/auth/calendar"],
)

creds = flow.run_local_server(port=0)
print("REFRESH_TOKEN:", creds.refresh_token)