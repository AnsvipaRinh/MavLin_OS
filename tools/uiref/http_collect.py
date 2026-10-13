#!/usr/bin/env python3
"""http_collect.py - move files between the Linux host and the macOS guest.

QEMU's user-mode networking (slirp) exposes the host at 10.0.2.2 from the guest,
so the host can serve the probe dylib and receive the JSON the guest produces:

    host:  python3 tools/uiref/http_collect.py 8000
    guest: curl -o /tmp/p.dylib http://10.0.2.2:8000/mvprobe.dylib
           DYLD_INSERT_LIBRARIES=/tmp/p.dylib MVPROBE_OUT=/tmp/probe.json /usr/bin/true
           curl --data-binary @/tmp/probe.json http://10.0.2.2:8000/probe.json

This keeps the extraction one-directional and scriptable: the agent never has to
read a screenshot to obtain data.
"""
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

DIR = os.environ.get("MVPROBE_DIR", "/home/builder/vmwork/probe-in")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
os.makedirs(DIR, exist_ok=True)


class Handler(BaseHTTPRequestHandler):
    def _target(self):
        return os.path.join(DIR, os.path.basename(self.path.lstrip("/")) or "index")

    def do_GET(self):
        p = self._target()
        if os.path.exists(p):
            data = open(p, "rb").read()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n)
        p = self._target()
        open(p, "wb").write(body)
        print(f"stored {p} ({len(body)} bytes)", flush=True)
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"serving {DIR} on 0.0.0.0:{PORT}", flush=True)
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()