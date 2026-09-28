#!/usr/bin/env bash
# ============================================================
# Construction-LegalOps-DX — nginx /api/auth routing preflight
#
# Why this exists
# ---------------
# `/api/auth/*` belongs to NextAuth and is served by the **frontend** (Next.js).
# The backend owns `/api/v1/auth/*`. Any nginx **server block** that forwards
# `location /api/` to a backend must therefore also carry a regex location
#
#     location ~* ^/api/auth(/|$) { proxy_pass http://<frontend upstream>; }
#
# because a regex location wins over the `/api/` prefix location. Without it,
# /api/auth/* is proxied to FastAPI, which answers 404 with a problem+json body;
# the browser then throws AuthError on every page and the user menu falls back
# to a generic label.
#
# 2026-09-28: the rule existed in infra/nginx/default.conf (prod) and in the prod
# server block of infra/native/nginx/legalops-main.conf, but was MISSING from
# infra/nginx/mvp.conf and from the mvp server block of the native config.
# Measured on the running host: nginx 8412 /api/auth/session = 404,
# frontend 3013 = 200, backend 8013 = 404, AuthError on every page.
#
# The check is per server block (not a file-wide count): a file may legitimately
# contain several server blocks, each needing its own /api/auth rule.
#
# Usage:
#   scripts/verify_nginx_auth_routing.sh            # check all known configs
#   scripts/verify_nginx_auth_routing.sh <file>...  # check specific files
#
# Exit: 0 = every backend-facing /api/ block has a matching /api/auth block
#       1 = at least one gap, or nothing was checked (fail closed)
# ============================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

exec python3 - "$REPO_ROOT" "$@" <<'PY'
"""Per-server-block check that /api/auth is routed to the frontend."""
from __future__ import annotations

import os
import re
import sys

repo_root = sys.argv[1]
args = sys.argv[2:]

defaults = [
    "infra/nginx/default.conf",
    "infra/nginx/mvp.conf",
    "infra/native/nginx/legalops-main.conf",
]
configs = args or [os.path.join(repo_root, p) for p in defaults]


def strip_comments(text: str) -> str:
    """Drop `#` comments so words like "location" inside prose are not parsed.

    Without this, the comment above the /api/auth block (which mentions the word
    "location") is matched as a location header and the real block is swallowed.
    """
    out = []
    for line in text.splitlines():
        in_single = in_double = False
        cut = len(line)
        for idx, ch in enumerate(line):
            if ch == "'" and not in_double:
                in_single = not in_single
            elif ch == '"' and not in_single:
                in_double = not in_double
            elif ch == "#" and not in_single and not in_double:
                cut = idx
                break
        out.append(line[:cut])
    return "\n".join(out)


def blocks_of(text: str, keyword: str) -> list[tuple[str, str]]:
    """Return (header, body) for each `keyword { ... }` block, brace-balanced."""
    found: list[tuple[str, str]] = []
    pos = 0
    while True:
        m = re.search(rf"(?m)^[ \t]*{keyword}\s*\{{", text[pos:])
        if not m:
            break
        start = pos + m.start()
        i = pos + m.end()
        depth = 1
        while i < len(text) and depth > 0:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        body = text[start:i]
        head_match = re.search(rf"{keyword}\s*([^{{]*)\{{", body)
        found.append((head_match.group(1).strip() if head_match else "", body))
        pos = i
    return found


def locations(body: str) -> list[tuple[str, str]]:
    """Return (modifier, body) for each `location ... { ... }` inside body."""
    out: list[tuple[str, str]] = []
    pos = 0
    while True:
        m = re.search(r"location\s+([^{]*?)\{", body[pos:])
        if not m:
            break
        modifier = m.group(1).strip()
        i = pos + m.end()
        depth = 1
        while i < len(body) and depth > 0:
            if body[i] == "{":
                depth += 1
            elif body[i] == "}":
                depth -= 1
            i += 1
        out.append((modifier, body[pos + m.end() : i - 1]))
        pos = i
    return out


def proxied_upstream(loc_body: str) -> str | None:
    m = re.search(r"proxy_pass\s+http://([A-Za-z0-9_.\-]+)", loc_body)
    return m.group(1) if m else None


checked = 0
failures = 0

for cfg in configs:
    rel = os.path.relpath(cfg, repo_root) if cfg.startswith(repo_root) else cfg
    if not os.path.isfile(cfg):
        print(f"❌ {rel} (not found)")
        failures += 1
        continue

    text = strip_comments(open(cfg, encoding="utf-8").read())
    servers = blocks_of(text, "server")
    if not servers:
        print(f"➖ {rel} (no server block — n/a)")
        continue

    for header, sbody in servers:
        checked += 1
        label = header or "<no server_name>"
        api_backend = False
        auth_frontend = False

        for modifier, lb in locations(sbody):
            upstream = proxied_upstream(lb)
            if upstream is None:
                continue
            is_api_prefix = re.fullmatch(r"(?:\^~|=)?\s*/api/\S*", modifier) is not None
            is_auth_regex = modifier.startswith("~") and "^/api/auth" in modifier
            if is_api_prefix and "backend" in upstream:
                api_backend = True
            if is_auth_regex and "frontend" in upstream:
                auth_frontend = True

        if not api_backend:
            print(f"➖ {rel} [{label}] (no backend /api/ proxy — n/a)")
            continue

        if auth_frontend:
            print(f"✅ {rel} [{label}] /api/auth -> frontend")
        else:
            print(f"❌ {rel} [{label}] /api/ -> backend but /api/auth is NOT routed to a frontend")
            print("     fix: add 'location ~* ^/api/auth(/|$) { limit_req ...; proxy_pass http://<frontend>; ... }'")
            failures += 1

if checked == 0:
    print("❌ no nginx server block was checked (fail closed)")
    sys.exit(1)

print()
if failures == 0:
    print(f"✅ nginx /api/auth routing preflight passed ({checked} server block(s))")
    sys.exit(0)
print(f"❌ nginx /api/auth routing preflight failed ({failures} server block(s))")
sys.exit(1)
PY
