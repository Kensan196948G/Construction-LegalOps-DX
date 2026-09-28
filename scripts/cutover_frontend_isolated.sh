#!/usr/bin/env bash
# ============================================================
# Construction-LegalOps-DX — cut an isolated frontend build into the checkout
#
# Companion to scripts/build_frontend_isolated.sh. That script builds and stages
# a production bundle OUTSIDE the checkout so the running frontend unit is never
# disturbed. This script performs the (short) cutover window:
#
#   1. verify the isolated build is complete (staged assets, BUILD_ID, chunks)
#   2. replace <repo>/frontend/.next with the isolated .next
#   3. re-run the staging authority against the checkout
#   4. restart the frontend units so they re-register static routes at boot
#
# Steps 2-4 must happen together: while the old process is alive it resolves
# chunks from the directory being replaced, so a partial cutover serves a mix of
# old and new assets. This is why restart is part of this script rather than a
# separate step the operator might forget.
#
# Requires root for step 4 (systemctl). Use --no-restart to stop after step 3.
#
# Usage:
#   sudo bash scripts/cutover_frontend_isolated.sh                  # default isolated dir
#   sudo bash scripts/cutover_frontend_isolated.sh /path/to/build
#   bash scripts/cutover_frontend_isolated.sh --check               # verify only, no writes
#   sudo bash scripts/cutover_frontend_isolated.sh --no-restart
#
# Exit: 0 ok / 1 precondition / 3 isolated build unverified / 4 restart failed
# ============================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DST="${REPO_ROOT}/frontend"
SRC="${HOME}/.cache/legalops-fe-build"
RESTART=1
CHECK=0
FRONTEND_UNITS="legalops-prod-frontend legalops-mvp-frontend"

while [ $# -gt 0 ]; do
  case "$1" in
    --check) CHECK=1; shift ;;
    --no-restart) RESTART=0; shift ;;
    -h | --help) sed -n '2,26p' "${BASH_SOURCE[0]}"; exit 0 ;;
    -*) echo "unknown arg $1" >&2; exit 64 ;;
    *) SRC="$1"; shift ;;
  esac
done

log() { printf '[cutover-frontend] %s\n' "$*"; }

[ -f "${SRC}/.next/standalone/server.js" ] || {
  log "ERROR: ${SRC}/.next/standalone/server.js not found — run scripts/build_frontend_isolated.sh first"
  exit 1
}

# --- 1. Verify the isolated build before touching anything -------------------
log "verifying isolated build at ${SRC}"
if ! bash "${REPO_ROOT}/scripts/stage_frontend_standalone.sh" --verify --frontend "$SRC"; then
  log "REFUSING: isolated build is not verified (missing/stale staged assets)"
  exit 3
fi
src_build_id="$(cat "${SRC}/.next/BUILD_ID")"
log "isolated BUILD_ID=${src_build_id}"

if [ "$CHECK" = 1 ]; then
  log "check-only: no files were written"
  exit 0
fi

[ "$(id -u)" -eq 0 ] || { log "run with sudo (or pass --no-restart to only copy files)"; exit 1; }

# --- 2. Replace the checkout's .next ----------------------------------------
# Build output only: the previous .next is moved aside (not deleted) so the
# cutover is reversible without a rebuild.
backup="${DST}/.next.pre-cutover.$(date -u +%Y%m%dT%H%M%SZ)"
log "moving current .next aside -> ${backup}"
mv "${DST}/.next" "$backup"
if ! cp -a "${SRC}/.next" "${DST}/.next"; then
  log "copy failed — restoring the previous build"
  rm -rf "${DST}/.next"
  mv "$backup" "${DST}/.next"
  exit 1
fi
dst_build_id="$(cat "${DST}/.next/BUILD_ID")"
[ "$dst_build_id" = "$src_build_id" ] || { log "BUILD_ID mismatch after copy (${dst_build_id} != ${src_build_id})"; exit 1; }
log "checkout .next updated (BUILD_ID ${dst_build_id})"

# --- 3. Re-stage in the checkout (single staging authority) ------------------
bash "${REPO_ROOT}/scripts/stage_frontend_standalone.sh"

# --- 4. Restart so static routes are registered against the new build --------
if [ "$RESTART" = 0 ]; then
  log "--no-restart: files are in place but the running units still serve the old build."
  log "run: systemctl restart ${FRONTEND_UNITS}"
  log "previous build kept at ${backup} for rollback"
  exit 0
fi

log "restarting frontend units: ${FRONTEND_UNITS}"
# shellcheck disable=SC2086
systemctl restart ${FRONTEND_UNITS}

ok=1
for i in $(seq 1 30); do
  ok=1
  for p in 3011 3013; do
    curl -fsS --max-time 3 -o /dev/null "http://127.0.0.1:${p}/" 2>/dev/null || curl -fsS --max-time 3 -o /dev/null -w '' "http://127.0.0.1:${p}/login" 2>/dev/null || ok=0
  done
  [ "$ok" = 1 ] && break
  sleep 2
done

if [ "$ok" != 1 ]; then
  log "frontend did not become healthy; rolling back to ${backup}"
  rm -rf "${DST}/.next" && mv "$backup" "${DST}/.next"
  # shellcheck disable=SC2086
  systemctl restart ${FRONTEND_UNITS}
  exit 4
fi

# Verify the assets the new HTML references are actually served.
css="$(curl -fsS --max-time 5 "http://127.0.0.1:3013/" | grep -oE '/_next/static/css/[a-z0-9]+\.css' | head -1 || true)"
if [ -n "$css" ]; then
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:3013${css}")"
  [ "$code" = "200" ] || { log "static asset ${css} returned ${code} — staging regression"; exit 4; }
  log "static asset check OK (${css} -> 200)"
fi

log "cutover complete. previous build kept at ${backup}"
