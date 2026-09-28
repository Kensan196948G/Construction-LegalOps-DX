#!/usr/bin/env bash
# ============================================================
# Construction-LegalOps-DX — isolated Next.js production build
#
# Why this exists
# ---------------
# The systemd frontend units run `node .next/standalone/server.js` with
# WorkingDirectory=<repo>/frontend. The running process resolves chunks and
# static routes from THAT directory, so a `next build` in the checkout mutates
# the very tree the live process is serving: requests then mix old in-memory
# state with new on-disk files, and the site breaks in ways that only a restart
# fixes. `next build` also regenerates `.next/standalone` without the staged
# `public/` and `.next/static/`, which is what caused the 2026-09-28
# "HTML 200 / every asset 404" incident.
#
# So: build somewhere else, stage there, verify there. The checkout is not
# touched. Cutover (copy into the checkout + restart the unit) stays a separate,
# human-gated step.
#
# Usage:
#   scripts/build_frontend_isolated.sh                       # ~/.cache/legalops-fe-build
#   scripts/build_frontend_isolated.sh --out /path/to/dir
#   scripts/build_frontend_isolated.sh --reuse-node-modules  # default: true
#
# Env:
#   NEXT_PUBLIC_API_BASE_URL   baked into the client bundle (default http://localhost:8000)
#   AUTH_DEV_BYPASS            baked auth bypass flag (default true, matches CI e2e)
#
# Exit: 0 = build ok and staging verified
#       1 = precondition failure  2 = build failure  3 = staging verification failure
#       4 = refuses to build inside the checkout (see above)
# ============================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${REPO_ROOT}/frontend"
OUT="${HOME}/.cache/legalops-fe-build"

while [ $# -gt 0 ]; do
  case "$1" in
    --out) OUT="${2:?--out needs a directory}"; shift 2 ;;
    -h | --help) sed -n '2,32p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown arg $1" >&2; exit 64 ;;
  esac
done

log() { printf '[fe-build-isolated] %s\n' "$*"; }

# --- Guard: never build in place -------------------------------------------
out_real="$(readlink -f "$(dirname "$OUT")")/$(basename "$OUT")"
if [ "$out_real" = "$(readlink -f "$SRC")" ] || [[ "$out_real" == "$(readlink -f "$SRC")"/* ]]; then
  log "REFUSING: --out resolves inside the checkout ($out_real)."
  log "The running frontend unit serves .next/standalone from there; an in-place"
  log "build corrupts it. Use the default isolated directory instead."
  exit 4
fi
if [ "$(stat -c %d "$(dirname "$out_real")" 2>/dev/null || echo x)" != "$(stat -c %d "$SRC" 2>/dev/null || echo y)" ]; then
  log "WARNING: $out_real is on a different filesystem than the checkout;"
  log "         node_modules will be copied instead of hardlinked (slower, more disk)."
fi

[ -f "${SRC}/package.json" ] || { log "ERROR: ${SRC}/package.json not found"; exit 1; }
[ -d "${SRC}/node_modules" ] || { log "ERROR: ${SRC}/node_modules missing — run npm install first"; exit 1; }

# --- Sync sources (keep node_modules so unchanged deps stay warm) -----------
log "syncing sources -> ${out_real}"
mkdir -p "$out_real"
# Prune first: `tar -x` overwrites but never deletes, so a file removed from the
# checkout would otherwise linger here and be built into the isolated bundle.
find "$out_real" -mindepth 1 -maxdepth 1 \
  ! -name node_modules ! -name .next -exec rm -rf {} +
( cd "$SRC" && tar -cf - \
    --exclude=./.next \
    --exclude=./node_modules \
    --exclude=./test-results \
    --exclude=./playwright-report \
    --exclude=./tsconfig.tsbuildinfo . ) | ( cd "$out_real" && tar -xf - )

# The previous .next belongs to the previous source tree; never reuse it.
rm -rf "${out_real}/.next"

if [ ! -d "${out_real}/node_modules" ]; then
  log "linking node_modules"
  cp -al "${SRC}/node_modules" "${out_real}/node_modules" 2>/dev/null \
    || cp -a "${SRC}/node_modules" "${out_real}/node_modules"
fi

# --- Build ------------------------------------------------------------------
export NEXT_TELEMETRY_DISABLED=1
export NODE_ENV=production
export NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://localhost:8000}"
export AUTH_DEV_BYPASS="${AUTH_DEV_BYPASS:-true}"
# Prefer the Node the systemd units pin, so the build and the runtime match.
if [ -x /home/kensan/.nvm/versions/node/v20.20.2/bin/node ]; then
  export PATH="/home/kensan/.nvm/versions/node/v20.20.2/bin:${PATH}"
fi

log "next build (node $(node -v), NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL})"
if ! ( cd "$out_real" && ./node_modules/.bin/next build ); then
  log "BUILD FAILED"
  exit 2
fi

# --- Stage + verify (single staging authority) ------------------------------
log "staging + verifying"
if ! bash "${REPO_ROOT}/scripts/stage_frontend_standalone.sh" --frontend "$out_real"; then
  log "STAGING VERIFICATION FAILED"
  exit 3
fi

build_id="$(cat "${out_real}/.next/BUILD_ID" 2>/dev/null || echo '?')"
log "OK: ${out_real} (BUILD_ID ${build_id})"
log "cutover (human-gated): copy .next/standalone into the checkout, then restart the frontend unit"
