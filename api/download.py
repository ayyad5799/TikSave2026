"""
GET /api/download?video_id=xxx&rapid_key=yyy
Returns { url: "https://..." }
"""
import json
import requests
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


def get_nowm_url(video_id, rapid_key):
    # Try endpoint 1 — analysis
    url = (
        "https://tiktok-video-no-watermark2.p.rapidapi.com/"
        f"?url=https%3A%2F%2Fwww.tiktok.com%2Fvideo%2F{video_id}&hd=1"
    )
    headers = {
        "x-rapidapi-key":  rapid_key,
        "x-rapidapi-host": "tiktok-video-no-watermark2.p.rapidapi.com",
    }
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    d = r.json()
    data = d.get("data") or {}
    link = (
        data.get("play") or data.get("wmplay") or
        data.get("hdplay") or data.get("nwm_video_url") or
        data.get("nwm_video_url_HQ") or ""
    )
    if not link:
        raise ValueError(f"No download URL in response: {json.dumps(d)[:300]}")
    return link


class handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        def p(k, d=""): return (qs.get(k, [d])[0]).strip()

        video_id  = p("video_id")
        rapid_key = p("rapid_key")

        if not video_id or not rapid_key:
            self._respond(400, {"error": "video_id و rapid_key مطلوبان"})
            return

        try:
            url = get_nowm_url(video_id, rapid_key)
            self._respond(200, {"url": url})
        except requests.HTTPError as e:
            self._respond(e.response.status_code,
                          {"error": f"RapidAPI: {e.response.text[:300]}"})
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
