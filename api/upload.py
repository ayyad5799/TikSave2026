"""
POST /api/upload
Body JSON: { video_url, filename, drop_token, drop_folder, app_key, app_secret, refresh_token }
Downloads video server-side (bypasses CORS) then uploads to Dropbox.
Supports both:
  - Long-lived access token (drop_token)
  - OAuth refresh flow (app_key + app_secret + refresh_token)
"""
import json
import requests
from http.server import BaseHTTPRequestHandler


def get_access_token(app_key, app_secret, refresh_token):
    """Exchange refresh token for short-lived access token."""
    r = requests.post(
        "https://api.dropbox.com/oauth2/token",
        data={
            "grant_type":    "refresh_token",
            "refresh_token": refresh_token,
            "client_id":     app_key,
            "client_secret": app_secret,
        },
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def upload_to_dropbox(video_bytes, filename, folder, access_token):
    path = f"{folder.rstrip('/')}/{filename}"
    r = requests.post(
        "https://content.dropboxapi.com/2/files/upload",
        headers={
            "Authorization":   f"Bearer {access_token}",
            "Dropbox-API-Arg": json.dumps({
                "path":        path,
                "mode":        "overwrite",
                "autorename":  False,
                "mute":        True,
            }),
            "Content-Type": "application/octet-stream",
        },
        data=video_bytes,
        timeout=120,
    )
    r.raise_for_status()
    return r.json()


class handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = json.loads(self.rfile.read(length) or b"{}")

        video_url     = body.get("video_url",     "").strip()
        filename      = body.get("filename",      "video.mp4").strip()
        drop_folder   = body.get("drop_folder",   "/videos").strip()
        drop_token    = body.get("drop_token",    "").strip()
        app_key       = body.get("app_key",       "").strip()
        app_secret    = body.get("app_secret",    "").strip()
        refresh_token = body.get("refresh_token", "").strip()

        if not video_url:
            self._respond(400, {"error": "video_url مطلوب"})
            return

        # Resolve access token
        access_token = ""
        if drop_token:
            access_token = drop_token
        elif app_key and app_secret and refresh_token:
            try:
                access_token = get_access_token(app_key, app_secret, refresh_token)
            except Exception as e:
                self._respond(401, {"error": f"Dropbox token refresh failed: {e}"})
                return
        else:
            self._respond(400, {"error": "Dropbox credentials ناقصة"})
            return

        try:
            # Download video server-side (no CORS issues)
            vr = requests.get(video_url, timeout=60,
                              headers={"User-Agent": "Mozilla/5.0"},
                              stream=False)
            vr.raise_for_status()
            video_bytes = vr.content

            # Upload to Dropbox
            result = upload_to_dropbox(video_bytes, filename, drop_folder, access_token)
            self._respond(200, {"ok": True, "path": result.get("path_display", "")})

        except requests.HTTPError as e:
            self._respond(e.response.status_code,
                          {"error": f"HTTP {e.response.status_code}: {e.response.text[:300]}"})
        except Exception as e:
            self._respond(500, {"error": str(e)})

    def _respond(self, status, body):
        raw = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
