from __future__ import annotations

import importlib.util
import json
import socket
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_MODULE = REPO_ROOT / "scripts" / "serve_standalone_webui.py"


def load_server_module():
    spec = importlib.util.spec_from_file_location("serve_standalone_webui", SERVER_MODULE)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fetch(url: str) -> tuple[int, bytes, dict[str, str]]:
    with urlopen(url, timeout=5) as response:  # noqa: S310
        headers = {key.lower(): value for key, value in response.headers.items()}
        return response.status, response.read(), headers


def head(url: str) -> tuple[int, bytes, dict[str, str]]:
    request = Request(url, method="HEAD")
    with urlopen(request, timeout=5) as response:  # noqa: S310
        headers = {key.lower(): value for key, value in response.headers.items()}
        return response.status, response.read(), headers


def test_serves_html_exactly_and_exposes_health(tmp_path: Path) -> None:
    module = load_server_module()
    html = tmp_path / "Construction-LegalOps-DX (Standalone).html"
    expected = b"<!doctype html><html><body>Standalone WebUI 100%</body></html>"
    html.write_bytes(expected)

    server = module.StandaloneServer(("127.0.0.1", 0), module.StandaloneHandler)
    server.html_path = html
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base_url = f"http://{host}:{port}"

    try:
        status, body, headers = fetch(f"{base_url}/")
        assert status == 200
        assert body == expected
        assert headers["content-type"] == "text/html; charset=utf-8"
        assert headers["cache-control"] == "no-store"
        assert headers["x-content-type-options"] == "nosniff"

        status, body, headers = head(f"{base_url}/")
        assert status == 200
        assert body == b""
        assert headers["content-type"] == "text/html; charset=utf-8"
        assert headers["content-length"] == str(len(expected))

        status, body, _ = fetch(f"{base_url}/index.html")
        assert status == 200
        assert body == expected

        status, body, _ = fetch(f"{base_url}/healthz")
        assert status == 200
        assert body == b"ok\n"

        status, body, _ = fetch(f"{base_url}/standalone-source")
        assert status == 200
        assert body.decode("utf-8") == str(html)

        try:
            fetch(f"{base_url}/missing")
        except HTTPError as exc:
            assert exc.code == 404
        else:
            raise AssertionError("missing route should return 404")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_find_free_port_skips_occupied_port() -> None:
    module = load_server_module()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        occupied_port = occupied.getsockname()[1]

        free_port = module.find_free_port("127.0.0.1", occupied_port, occupied_port + 1)

    assert free_port == occupied_port + 1


def test_write_status_honors_systemd_stop_command(tmp_path: Path, monkeypatch) -> None:
    module = load_server_module()
    status_path = tmp_path / "status" / "standalone-webui.json"
    html_path = tmp_path / "Construction-LegalOps-DX (Standalone).html"
    html_path.write_text("<html></html>", encoding="utf-8")
    monkeypatch.setenv(
        "STANDALONE_WEBUI_STOP_COMMAND",
        "systemctl --user stop construction-legalops-standalone-webui.service",
    )

    module.write_status(status_path, "192.168.0.10", 38100, html_path)

    payload = json.loads(status_path.read_text(encoding="utf-8"))
    assert payload["url"] == "http://192.168.0.10:38100/"
    assert payload["health_url"] == "http://192.168.0.10:38100/healthz"
    assert payload["html_path"] == str(html_path)
    assert payload["stop_command"] == (
        "systemctl --user stop construction-legalops-standalone-webui.service"
    )
