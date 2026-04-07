"""
Unified HTTP server for Render deployment.
Routes all /api/* requests to the appropriate handler.
"""
import os, sys, json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# Import all handlers
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))
import profile  as profile_mod
import download as download_mod
import upload   as upload_mod
import token    as token_mod
import storage  as storage_mod
import test_keys as test_keys_mod
import settings as settings_mod

ROUTES = {
    "/api/profile":   profile_mod.handler,
    "/api/download":  download_mod.handler,
    "/api/upload":    upload_mod.handler,
    "/api/token":     token_mod.handler,
    "/api/storage":   storage_mod.handler,
    "/api/test_keys": test_keys_mod.handler,
    "/api/settings":  settings_mod.handler,
}

PUBLIC_DIR = os.path.join(os.path.dirname(__file__), 'public')

class MainHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress logs

    def _route(self):
        path = urlparse(self.path).path.rstrip('/')
        # API routes
        if path in ROUTES:
            h = ROUTES[path](self.request, self.client_address, self.server)
            h.rfile  = self.rfile
            h.wfile  = self.wfile
            h.headers = self.headers
            h.path   = self.path
            h.command = self.command
            method = getattr(h, f'do_{self.command}', None)
            if method:
                method()
                return True
        return False

    def _serve_file(self, filepath, content_type):
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()

    def _handle_static(self):
        path = urlparse(self.path).path
        if path == '/auth-callback':
            self._serve_file(os.path.join(PUBLIC_DIR, 'auth-callback.html'), 'text/html')
            return
        # Serve index.html for everything else
        self._serve_file(os.path.join(PUBLIC_DIR, 'index.html'), 'text/html')

    def do_GET(self):
        if not self._route():
            self._handle_static()

    def do_POST(self):
        if not self._route():
            self.send_response(404); self.end_headers()

    def do_OPTIONS(self):
        if not self._route():
            self.send_response(200); self.end_headers()

    def do_DELETE(self):
        if not self._route():
            self.send_response(404); self.end_headers()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print(f"🚀 TikSave running on port {port}")
    server = HTTPServer(('0.0.0.0', port), MainHandler)
    server.serve_forever()
