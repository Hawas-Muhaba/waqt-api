"""
A local stand-in for AlAdhan's `GET /v1/gToH/DD-MM-YYYY`, on a real TCP socket, so the
real urllib transport (timeouts, redirects, size cap, status handling) is exercised in
CI without the internet. Also used by verification/live_stack_check.py and the browser
smoke test. It mimics the documented response shape; it is NOT evidence about the live
service (see SPRINT-14-REPORT.md, "What was not verified").

    srv = FakeAlAdhan().start(); srv.base_url  # http://127.0.0.1:PORT/v1
    srv.mode = "500" | "429" | "garbage" | "404" | "redirect" | "huge" | "wrongdate" | "ok"
    srv.day_offset = 1      # answer N days later than the arithmetic calendar
    srv.delay = 5.0         # seconds to stall before answering (timeout tests)
    srv.calls               # request paths received
"""
import json
import re
import threading
import time
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from waqt_core.hijri import ArithmeticTabularProvider


class FakeAlAdhan:
    def __init__(self):
        self.mode, self.day_offset, self.delay, self.retry_after = "ok", 0, 0.0, 60
        self.calls = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body, headers=None):
                try:
                    self.send_response(code)
                    for k, v in (headers or {}).items():
                        self.send_header(k, v)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def do_GET(self):
                outer.calls.append(self.path)
                if outer.delay:
                    time.sleep(outer.delay)
                m = re.match(r"/v1/gToH/(\d\d)-(\d\d)-(\d{4})", self.path)
                mode = outer.mode
                if mode == "500":
                    return self._send(500, b"boom")
                if mode == "429":
                    return self._send(429, b"slow down", {"Retry-After": str(outer.retry_after)})
                if mode == "garbage":
                    return self._send(200, b"<html>not json</html>")
                if mode == "404":
                    return self._send(404, b"{}")
                if mode == "redirect":
                    return self._send(302, b"", {"Location": "http://evil.invalid/"})
                if mode == "huge":
                    return self._send(200, b"x" * 200_000)
                if not m:
                    return self._send(404, b"{}")
                dd, mm, yy = m.group(1), m.group(2), m.group(3)
                h = ArithmeticTabularProvider().from_gregorian(date(int(yy), int(mm), int(dd)))
                day = h.day + outer.day_offset
                body = {"code": 200, "status": "OK", "data": {
                    "hijri": {"date": f"{day:02d}-{h.month:02d}-{h.year}", "day": str(day),
                              "month": {"number": h.month, "en": "fake"}, "year": str(h.year), "method": "UAQ"},
                    "gregorian": {"date": "01-01-2000" if mode == "wrongdate" else f"{dd}-{mm}-{yy}"}}}
                self._send(200, json.dumps(body).encode(), {"Content-Type": "application/json"})

        self._Handler = Handler
        self._srv = None

    def start(self):
        self._srv = ThreadingHTTPServer(("127.0.0.1", 0), self._Handler)
        self._srv.daemon_threads = True
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()
        return self

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self._srv.server_port}/v1"

    def stop(self):
        if self._srv:
            self._srv.shutdown()
            self._srv.server_close()


if __name__ == "__main__":  # run standalone: python verification/fake_aladhan.py
    s = FakeAlAdhan().start()
    print(s.base_url, flush=True)
    threading.Event().wait()
