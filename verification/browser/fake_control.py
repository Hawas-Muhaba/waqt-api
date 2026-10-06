"""Fake AlAdhan + a tiny control port so the browser script can flip failure modes: GET :8099/mode/<mode>"""
import sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fake_aladhan import FakeAlAdhan
import fake_aladhan
s = FakeAlAdhan()
srv = s.start()
class C(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        s.mode = self.path.split("/")[2]; b = s.mode.encode()
        self.send_response(200); self.send_header("Content-Length", str(len(b))); self.send_header("Access-Control-Allow-Origin", "*"); self.end_headers(); self.wfile.write(b)
print(s.base_url, flush=True)
ThreadingHTTPServer(("127.0.0.1", 8099), C).serve_forever()
