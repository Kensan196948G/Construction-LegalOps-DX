"""Serve the standalone Construction-LegalOps-DX WebUI bundle.

This intentionally serves the generated standalone HTML as-is instead of
running Next.js. It is useful on Windows/UNC workspaces where Next's watcher
and webpack loader resolution can fail before the UI becomes reachable.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import socket
import sys
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HTML = REPO_ROOT / "docs" / "Construction-LegalOps-DX (Standalone).html"
DEFAULT_STATUS = REPO_ROOT / "reports" / "webui" / "standalone-webui.json"


def select_host() -> str:
    """Pick a useful local IPv4 address without requiring external services."""
    candidates: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if not ip.startswith(("127.", "169.254.")):
                candidates.append(ip)
    except OSError:
        pass

    hostname = socket.gethostname()
    try:
        for item in socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM):
            ip = item[4][0]
            if ip.startswith("127.") or ip.startswith("169.254."):
                continue
            if ip not in candidates:
                candidates.append(ip)
    except socket.gaierror:
        pass

    for ip in candidates:
        if ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172."):
            return ip
    return candidates[0] if candidates else "127.0.0.1"


def find_free_port(host: str, start: int = 38100, end: int = 38999) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"no free TCP port found in range {start}-{end} for {host}")


class StandaloneHandler(BaseHTTPRequestHandler):
    server_version = "ConstructionLegalOpsStandalone/1.0"

    def do_GET(self) -> None:  # noqa: N802
        self._route(send_body=True)

    def do_HEAD(self) -> None:  # noqa: N802
        self._route(send_body=False)

    def _route(self, *, send_body: bool) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path in {"/", "/index.html"}:
            self._serve_html(send_body=send_body)
            return
        if path == "/healthz":
            self._send_bytes(b"ok\n", "text/plain; charset=utf-8", send_body=send_body)
            return
        if path == "/standalone-source":
            self._send_bytes(
                str(self.server.html_path).encode("utf-8"),
                "text/plain; charset=utf-8",
                send_body=send_body,
            )
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stdout.write(
            json.dumps(
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "client": self.address_string(),
                    "message": fmt % args,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        sys.stdout.flush()

    def _serve_html(self, *, send_body: bool) -> None:
        html_path: Path = self.server.html_path
        content = html_path.read_bytes()
        self._send_bytes(content, "text/html; charset=utf-8", send_body=send_body)

    def _send_bytes(self, content: bytes, content_type: str, *, send_body: bool) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self' blob: data:; script-src 'self' 'unsafe-inline' blob:; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:;",
        )
        self.end_headers()
        if send_body:
            self.wfile.write(content)


class StandaloneServer(ThreadingHTTPServer):
    html_path: Path


def write_status(path: Path, host: str, port: int, html_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stop_command = os.environ.get("STANDALONE_WEBUI_STOP_COMMAND")
    if not stop_command:
        stop_command = f"Stop-Process -Id {os.getpid()}" if os.name == "nt" else f"kill {os.getpid()}"
    payload = {
        "pid": os.getpid(),
        "host": host,
        "port": port,
        "url": f"http://{host}:{port}/",
        "health_url": f"http://{host}:{port}/healthz",
        "html_path": str(html_path),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "stop_command": stop_command,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--host", default="auto")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    args = parser.parse_args()

    html_path = args.html.resolve()
    if not html_path.exists():
        raise FileNotFoundError(html_path)

    host = select_host() if args.host == "auto" else args.host
    port = args.port or find_free_port(host)
    mimetypes.add_type("text/html", ".html")

    server = StandaloneServer((host, port), StandaloneHandler)
    server.html_path = html_path
    write_status(args.status.resolve(), host, port, html_path)
    print(f"Serving {html_path} at http://{host}:{port}/", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
