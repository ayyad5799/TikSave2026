"""
POST /api/upload
Body JSON: { video_url, filename, drop_folder, app_key, app_secret, refresh_token }

Strategy:
  1. Check if file exists (duplicate check)
  2. Try Dropbox "save URL" API first (Dropbox downloads directly — no timeout risk)
  3. Fallback: download video → upload bytes (for URLs Dropbox can't access)
"""
import json, requests, time
from http.server import BaseHTTPRequestHandler


def get_access_token(app_key, app_secret, refresh_token):
    r = requests.post(
        "https://api.dropbox.com/oauth2/token",
        data={"grant_type": "refresh_token", "refresh_token": refresh_token,
              "client_id": app_key, "client_secret": app_secret},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def file_exists(path, token):
    r = requests.post(
        "https://api.dropbox.com/2/files/get_metadata",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"path": path}, timeout=10,
    )
    return r.status_code == 200


def save_url_to_dropbox(video_url, path, token):
    """
    Ask Dropbox to download the URL itself — much faster, no timeout issues.
    Returns job_id for async job.
    """
    r = requests.post(
        "https://api.dropbox.com/2/files/save_url",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"path": path, "url": video_url},
        timeout=15,
    )
    r.raise_for_status()
    result = r.json()
    # Can return {"async_job_id": "..."} or {"complete": {...}}
    return result


def check_save_url_job(job_id, token, max_wait=55):
    """Poll until Dropbox finishes downloading the URL."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        r = requests.post(
            "https://api.dropbox.com/2/files/save_url/check_job_status",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"async_job_id": job_id},
            timeout=10,
        )
        r.raise_for_status()
        d = r.json()
        tag = d.get(".tag") or d.get("tag", "")
        if tag == "complete":
            return True, d
        if tag == "failed":
            return False, d
        time.sleep(2)
    return False, {"error": "timeout waiting for Dropbox"}


def upload_bytes_to_dropbox(video_bytes, path, token):
    """Fallback: upload raw bytes."""
    r = requests.post(
        "https://content.dropboxapi.com/2/files/upload",
        headers={
            "Authorization": f"Bearer {token}",
            "Dropbox-API-Arg": json.dumps({"path": path, "mode": "overwrite",
                                            "autorename": False, "mute": True}),
            "Content-Type": "application/octet-stream",
        },
        data=video_bytes, timeout=55,
    )
    if r.status_code == 507 or "storage" in r.text.lower() or "insufficient" in r.text.lower():
        raise Exception("storage_full: Dropbox امتلأت المساحة")
    r.raise_for_status()
    return r.json()


class handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = json.loads(self.rfile.read(length) or b"{}")

        video_url     = body.get("video_url",     "").strip()
        filename      = body.get("filename",      "video.mp4").strip()
        drop_folder   = body.get("drop_folder",   "/videos").strip()
        app_key       = body.get("app_key",       "").strip()
        app_secret    = body.get("app_secret",    "").strip()
        refresh_token = body.get("refresh_token", "").strip()

        if not video_url:
            self._respond(400, {"error": "video_url مطلوب"}); return
        if not all([app_key, app_secret, refresh_token]):
            self._respond(400, {"error": "Dropbox credentials ناقصة"}); return

        try:
            token = get_access_token(app_key, app_secret, refresh_token)
        except Exception as e:
            self._respond(401, {"error": f"Dropbox token فشل: {e}"}); return

        dropbox_path = f"{drop_folder.rstrip('/')}/{filename}"

        # ── Duplicate check ──
        try:
            if file_exists(dropbox_path, token):
                self._respond(200, {"ok": True, "skipped": True,
                                    "path": dropbox_path, "reason": "already_exists"})
                return
        except Exception:
            pass  # non-fatal

        # ── Strategy 1: Dropbox saves the URL itself ──
        try:
            result = save_url_to_dropbox(video_url, dropbox_path, token)
            tag    = result.get(".tag") or result.get("tag", "")

            if tag == "complete":
                self._respond(200, {"ok": True, "skipped": False,
                                    "path": dropbox_path, "method": "save_url"})
                return

            job_id = result.get("async_job_id")
            if job_id:
                ok, info = check_save_url_job(job_id, token)
                if ok:
                    self._respond(200, {"ok": True, "skipped": False,
                                        "path": dropbox_path, "method": "save_url_async"})
                    return
                # Job failed — fall through to bytes upload

        except Exception:
            pass  # fall through to bytes upload

        # ── Strategy 2: Download then upload bytes ──
        try:
            vr = requests.get(video_url, timeout=50,
                              headers={"User-Agent": "Mozilla/5.0"})
            vr.raise_for_status()
            upload_bytes_to_dropbox(vr.content, dropbox_path, token)
            self._respond(200, {"ok": True, "skipped": False,
                                "path": dropbox_path, "method": "bytes"})
        except Exception as e:
            err = str(e)
            if "storage_full" in err or "507" in err:
                self._respond(507, {"error": err})
            else:
                self._respond(500, {"error": err})

    def _respond(self, status, body):
        raw = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
