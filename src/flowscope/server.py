"""A small local web server for the viewer. Standard library only.

It runs the project's tests on request, so it listens on localhost and every request
needs the random token printed at startup. Without that, any web page you open could
make your browser ask it to run tests.
"""
from __future__ import annotations

import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from urllib.parse import parse_qs, urlparse

from . import modules, runner

LOCAL_HOSTS = ("localhost", "127.0.0.1")


def make_server(root, port: int = 0):
    token = secrets.token_urlsafe(9)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:       # keep the terminal quiet
            pass

        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, data, status: int = 200) -> None:
            self._send(status, json.dumps(data).encode(), "application/json")

        def do_GET(self) -> None:
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
            url = urlparse(self.path)
            q = parse_qs(url.query)
            if host not in LOCAL_HOSTS or q.get("t", [""])[0] != token:
                return self._json({"error": "forbidden"}, 403)   # wrong host or token
            try:
                if url.path in ("/", "/index.html"):
                    page = resources.files("flowscope").joinpath("static/viewer.html")
                    return self._send(200, page.read_bytes(), "text/html; charset=utf-8")
                if url.path == "/api/modules":
                    return self._json({"modules": ["entry"] + modules.all_names()})
                if url.path == "/api/usecases":
                    return self._json({"usecases": runner.discover(root)})
                if url.path == "/api/run":
                    nid = q.get("id", [""])[0]
                    if nid not in {u["id"] for u in runner.discover(root)}:
                        return self._json({"error": "unknown use case"}, 404)
                    return self._json(runner.run_use_case(root, nid))
                self._json({"error": "not found"}, 404)
            except Exception as e:                    # report it to the page, keep serving
                self._json({"error": f"{type(e).__name__}: {e}"}, 500)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.token = token
    return server
