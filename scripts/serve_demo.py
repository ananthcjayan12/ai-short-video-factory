#!/usr/bin/env python3
from __future__ import annotations

import http.server
import socketserver
import sys
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
port = int(sys.argv[2] if len(sys.argv) > 2 else "4173")

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(root), **kwargs)

with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
    print(f"Serving {root} at http://127.0.0.1:{port}")
    httpd.serve_forever()
