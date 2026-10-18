"""Isolated stand-in for the backend admin endpoints (test only; never deployed).

Accepts POST /ingestion/run and /index/run only with the expected X-Admin-Key (constant-time compare, like the
backend): 200 with the fields workflow 01's "Run summary" reads, otherwise 401 (403 when no key is configured).
Logs whether the header was present and matched, never its value. Nothing is downloaded or indexed.
"""

import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

_key_file = os.environ.get("ADMIN_API_KEY_FILE")
EXPECTED = open(_key_file, encoding="utf-8").read().strip() if _key_file else os.environ.get("ADMIN_API_KEY", "")
BODIES = {"/ingestion/run": {"counts": {"downloaded": 0, "unchanged": 12}, "results": []},
          "/index/run": {"documents_indexed": ["fixture"], "documents_skipped": {}, "collection_points": {"structure": 0, "recursive": 0},
                         "chunks_per_strategy": {}}}


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        got = self.headers.get("X-Admin-Key")
        ok = bool(EXPECTED) and got is not None and hmac.compare_digest(got.encode(), EXPECTED.encode())
        code = 200 if ok and self.path in BODIES else (403 if not EXPECTED else 401)
        print(json.dumps({"path": self.path, "x_admin_key_present": got is not None, "matches": ok, "status": code}), flush=True)
        body = json.dumps(BODIES.get(self.path, {}) if code == 200 else {"detail": "denied"}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


HTTPServer(("0.0.0.0", 8000), H).serve_forever()
