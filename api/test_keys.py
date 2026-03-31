"""
POST /api/test_keys
Body: { rapid_keys, apify_token, scraper_key, drop_app_key, drop_app_secret, drop_refresh }
Tests all keys and returns detailed status for each.
"""
import json, requests, time
from http.server import BaseHTTPRequestHandler


def test_rapid(key):
    """Test a RapidAPI key - checks quota and response."""
    start = time.time()
    try:
        r = requests.get(
            "https://tiktok-video-no-watermark2.p.rapidapi.com/user/posts",
            params={"unique_id": "tiktok", "count": 1, "cursor": 0},
            headers={
                "x-rapidapi-key":  key,
                "x-rapidapi-host": "tiktok-video-no-watermark2.p.rapidapi.com",
            },
            timeout=10,
        )
        ms = int((time.time()-start)*1000)
        if r.status_code == 200:
            return {"ok": True,  "status": "✅ شغال", "ms": ms, "code": 200}
        if r.status_code == 429:
            return {"ok": False, "status": "❌ quota خلص", "ms": ms, "code": 429}
        if r.status_code == 403:
            return {"ok": False, "status": "❌ مفتاح غير صالح", "ms": ms, "code": 403}
        return {"ok": False, "status": f"⚠️ كود {r.status_code}", "ms": ms, "code": r.status_code}
    except requests.Timeout:
        return {"ok": False, "status": "⚠️ timeout", "ms": 10000, "code": 0}
    except Exception as e:
        return {"ok": False, "status": f"❌ {str(e)[:60]}", "ms": 0, "code": 0}


def test_apify(token):
    """Test Apify token - checks balance and validity."""
    start = time.time()
    try:
        r = requests.get(
            "https://api.apify.com/v2/users/me",
            params={"token": token},
            timeout=10,
        )
        ms = int((time.time()-start)*1000)
        if r.status_code == 200:
            data     = r.json().get("data", {})
            plan     = data.get("plan", {})
            usage    = data.get("monthlyUsage", {})
            limit    = plan.get("maxActorRunMemoryGbytes", 0)
            username = data.get("username", "unknown")
            # Compute remaining credit estimate
            used_usd   = usage.get("actorComputeUnits", 0) * 0.004  # approx
            credit     = plan.get("monthlyUsageCreditsUsd", 5)
            remaining  = max(0, credit - used_usd)
            return {
                "ok": True,
                "status": "✅ شغال",
                "ms": ms, "code": 200,
                "detail": f"@{username} | رصيد متبقي ~${remaining:.2f}",
            }
        if r.status_code == 401:
            return {"ok": False, "status": "❌ token غير صالح", "ms": ms, "code": 401}
        return {"ok": False, "status": f"⚠️ كود {r.status_code}", "ms": ms, "code": r.status_code}
    except Exception as e:
        return {"ok": False, "status": f"❌ {str(e)[:60]}", "ms": 0, "code": 0}


def test_scraper(api_key):
    """Test ScraperAPI key - checks account and credits."""
    start = time.time()
    try:
        r = requests.get(
            "https://api.scraperapi.com/account",
            params={"api_key": api_key},
            timeout=10,
        )
        ms = int((time.time()-start)*1000)
        if r.status_code == 200:
            data       = r.json()
            used       = data.get("requestCount", 0)
            limit      = data.get("requestLimit", 1000)
            remaining  = max(0, limit - used)
            pct        = int(used/limit*100) if limit else 0
            return {
                "ok":     remaining > 0,
                "status": "✅ شغال" if remaining > 0 else "❌ quota خلص",
                "ms":     ms, "code": 200,
                "detail": f"مستخدم {used}/{limit} ({pct}%) | متبقي {remaining}",
            }
        if r.status_code == 403:
            return {"ok": False, "status": "❌ مفتاح غير صالح", "ms": ms, "code": 403}
        return {"ok": False, "status": f"⚠️ كود {r.status_code}", "ms": ms, "code": r.status_code}
    except Exception as e:
        return {"ok": False, "status": f"❌ {str(e)[:60]}", "ms": 0, "code": 0}


def test_dropbox(app_key, app_secret, refresh_token):
    """Test Dropbox credentials - refresh token + account info."""
    start = time.time()
    try:
        # Refresh token
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
        ms1 = int((time.time()-start)*1000)
        if r.status_code != 200:
            return {"ok": False, "status": "❌ credentials غلط", "ms": ms1, "code": r.status_code}

        access_token = r.json().get("access_token","")

        # Get account info
        r2 = requests.post(
            "https://api.dropbox.com/2/users/get_current_account",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        ms2 = int((time.time()-start)*1000)
        if r2.status_code == 200:
            acc   = r2.json()
            name  = acc.get("name",{}).get("display_name","")
            email = acc.get("email","")
            # Get space usage
            r3 = requests.post(
                "https://api.dropbox.com/2/users/get_space_usage",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            detail = f"{name} ({email})"
            if r3.status_code == 200:
                sp    = r3.json()
                used  = sp.get("used",0) / 1e9
                alloc = sp.get("allocation",{}).get("allocated",0) / 1e9
                pct   = int(used/alloc*100) if alloc else 0
                detail += f" | مساحة: {used:.1f}/{alloc:.0f} GB ({pct}%)"
            return {"ok": True, "status": "✅ متصل", "ms": ms2, "code": 200, "detail": detail}

        return {"ok": False, "status": f"⚠️ {r2.status_code}", "ms": ms2, "code": r2.status_code}
    except Exception as e:
        return {"ok": False, "status": f"❌ {str(e)[:60]}", "ms": 0, "code": 0}


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

        results = {}

        # Test all RapidAPI keys
        rapid_keys = body.get("rapid_keys", [])
        results["rapid"] = []
        for k in rapid_keys:
            if k.strip():
                res = test_rapid(k.strip())
                res["key_preview"] = k.strip()[:16] + "…"
                results["rapid"].append(res)

        # Test all Apify tokens
        apify_tokens = body.get("apify_tokens") or ([body["apify_token"]] if body.get("apify_token","").strip() else [])
        results["apify"] = []
        for t in apify_tokens:
            if t.strip():
                res = test_apify(t.strip())
                res["token_preview"] = t.strip()[:16] + "…"
                results["apify"].append(res)

        # Test all ScraperAPI keys
        scraper_keys = body.get("scraper_keys") or ([body["scraper_key"]] if body.get("scraper_key","").strip() else [])
        results["scraper"] = []
        for k in scraper_keys:
            if k.strip():
                res = test_scraper(k.strip())
                res["key_preview"] = k.strip()[:16] + "…"
                results["scraper"].append(res)

        # Test Dropbox
        if all(body.get(k,"").strip() for k in ["drop_app_key","drop_app_secret","drop_refresh"]):
            results["dropbox"] = test_dropbox(
                body["drop_app_key"].strip(),
                body["drop_app_secret"].strip(),
                body["drop_refresh"].strip(),
            )

        raw = json.dumps(results, ensure_ascii=False).encode()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
