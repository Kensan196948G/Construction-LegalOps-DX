from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_unhealthy_services.sh"


def _fake_docker(tmp_path: Path, payload: str) -> Path:
    docker = tmp_path / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        "if [ \"$1\" = \"compose\" ] && [ \"$4\" = \"ps\" ]; then\n"
        f"  printf '%s\\n' '{payload}'\n"
        "  exit 0\n"
        "fi\n"
        "if [ \"$1\" = \"compose\" ] && [ \"$4\" = \"restart\" ]; then\n"
        "  echo restart-called ${@:5}\n"
        "  exit 0\n"
        "fi\n"
        "echo unexpected docker args: $* >&2\n"
        "exit 2\n",
        encoding="utf-8",
    )
    docker.chmod(docker.stat().st_mode | stat.S_IXUSR)
    return docker


def _env_with_fake_docker(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}:{env['PATH']}"
    return env


def test_unhealthy_watchdog_report_ok_when_no_unhealthy(tmp_path: Path) -> None:
    _fake_docker(
        tmp_path,
        '[{"Service":"backend","State":"running","Health":"healthy"}]',
    )

    result = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        env=_env_with_fake_docker(tmp_path),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "OK: no unhealthy services detected" in result.stdout


def test_unhealthy_watchdog_report_fails_when_unhealthy(tmp_path: Path) -> None:
    _fake_docker(
        tmp_path,
        '[{"Service":"backend","State":"running","Health":"unhealthy"}]',
    )

    result = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        env=_env_with_fake_docker(tmp_path),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    assert "UNHEALTHY services detected" in result.stdout
    assert "backend" in result.stdout


def test_unhealthy_watchdog_restarts_only_requested_unhealthy_service(tmp_path: Path) -> None:
    _fake_docker(
        tmp_path,
        '[{"Service":"backend","State":"running","Health":"unhealthy"}]',
    )

    result = subprocess.run(
        [str(SCRIPT), "--restart", "backend"],
        cwd=ROOT,
        env=_env_with_fake_docker(tmp_path),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Restarting approved unhealthy service: backend" in result.stdout
    assert "restart-called backend" in result.stdout
