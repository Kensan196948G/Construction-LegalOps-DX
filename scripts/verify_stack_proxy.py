#!/usr/bin/env python3
"""Verification harness: frontend (isolated build) + API, same-origin.

Purpose
-------
The MVP frontend is a Next.js standalone server that calls the backend on the
same origin (`/api/v1/*`); in production nginx joins the two. When we want to
verify a *rebuilt* frontend without touching the running production units, we
need that same join somewhere else. This script runs a tiny HTTP proxy that

  * forwards `/api/*`           -> the verification backend (default :8025)
  * forwards everything else    -> the isolated frontend build (default :3019)

so a browser (or scripts/verify_mvp_route_coverage.sh) sees exactly the
same-origin layout as production, on spare ports, with production untouched.

Not a production component: verification only.
"""

from __future__ import annotations

import argparse
import http.client
import socketserver
import sys
from http.server import BaseHTTPRequestHandler

HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    frontend: tuple[str, int] = ("127.0.0.1", 3019)
    backend: tuple[str, int] = ("127.0.0.1", 8025)

    def log_message(self, fmt: str, *args: object) -> None:  # quieter
        if self.path.startswith("/api/"):
            sys.stderr.write("[proxy] %s %s\n" % (self.command, self.path))

    def _target(self) -> tuple[str, int]:
        # Mirror the production nginx routing exactly:
        #   /api/auth/*  -> NextAuth lives on the frontend
        #   /api/*       -> FastAPI backend
        #   everything   -> frontend
        # Getting this wrong makes the SPA throw AuthError and render empty
        # states, which would look like a product bug instead of a harness bug.
        if self.path.startswith("/api/auth/"):
            return self.frontend
        if self.path.startswith("/api/"):
            return self.backend
        return self.frontend

    def _relay(self, method: str) -> None:
        host, port = self._target()
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None

        conn = http.client.HTTPConnection(host, port, timeout=30)
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP_BY_HOP}
        headers["Host"] = f"{host}:{port}"
        try:
            conn.request(method, self.path, body=body, headers=headers)
            resp = conn.getresponse()
            payload = resp.read()
        except Exception as exc:  # surface, don't mask
            self.send_response(502)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(str(exc))))
            self.end_headers()
            self.wfile.write(str(exc).encode())
            return

        self.send_response(resp.status)
        for key, value in resp.getheaders():
            if key.lower() in HOP_BY_HOP or key.lower() == "content-length":
                continue
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if method != "HEAD":
            self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        self._relay("GET")

    def do_HEAD(self) -> None:  # noqa: N802
        self._relay("HEAD")

    def do_POST(self) -> None:  # noqa: N802
        self._relay("POST")

    def do_PATCH(self) -> None:  # noqa: N802
        self._relay("PATCH")

    def do_PUT(self) -> None:  # noqa: N802
        self._relay("PUT")

    def do_DELETE(self) -> None:  # noqa: N802
        self._relay("DELETE")


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8419)
    ap.add_argument("--frontend-port", type=int, default=3019)
    ap.add_argument("--backend-port", type=int, default=8025)
    args = ap.parse_args()

    Handler.frontend = ("127.0.0.1", args.frontend_port)
    Handler.backend = ("127.0.0.1", args.backend_port)

    with Server(("127.0.0.1", args.port), Handler) as httpd:
        print(
            f"[proxy] http://127.0.0.1:{args.port}  "
            f"(/api/* -> :{args.backend_port}, else -> :{args.frontend_port})",
            flush=True,
        )
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
