"""
GET /api/profile?username=xxx&rapid_key=yyy&max_dur=120&cursor=0
Returns list of videos with id, duration, title
"""
import json
import requests
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


def fetch_page(username, rapid_key, cursor):
    url = (
        "https://tiktok-video-no-watermark2.p.rapidapi.com/user/posts"
        f"?unique_id={username}&count=20&cursor={cursor}"
    )
    headers = {
        "x-rapidapi-key":  rapid_key,
        "x-rapidapi-host": "tiktok-video-no-watermark2.p.rapidapi.com",
    }
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()


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

        username  = p("username")
        rapid_key = p("rapid_key")
        max_dur   = int(p("max_dur", "120"))
        cursor    = int(p("cursor",  "0"))

        if not username or not rapid_key:
            self._respond(400, {"error": "username و rapid_key مطلوبان"})
            return

        try:
            data  = fetch_page(username, rapid_key, cursor)
            raw   = (data.get("data") or {})
            items = raw.get("videos") or raw.get("aweme_list") or []

            videos = []
            for v in items:
                dur = v.get("duration") or v.get("video", {}).get("duration", 0)
                if isinstance(dur, str):
                    try: dur = float(dur)
                    except: dur = 0
                if dur <= 0 or dur > max_dur:
                    continue
                vid_id = (
                    v.get("video_id") or v.get("aweme_id") or
                    v.get("id") or ""
                )
                title = (
                    v.get("title") or v.get("desc") or
                    v.get("video", {}).get("desc") or vid_id
                )[:80]
                videos.append({"id": str(vid_id), "duration": dur, "title": title})

            has_more = raw.get("hasMore") or raw.get("has_more") or False
            next_cur = raw.get("cursor") or (cursor + 20)

            self._respond(200, {
                "videos":   videos,
                "has_more": bool(has_more),
                "cursor":   next_cur,
            })

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
