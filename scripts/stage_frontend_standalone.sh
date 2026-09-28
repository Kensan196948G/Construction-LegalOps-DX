#!/usr/bin/env bash
# ============================================================
# Construction-LegalOps-DX — Next.js standalone staging + verification
#
# `next build` emits `.next/standalone/` containing server.js and a pruned
# node_modules, but it deliberately does NOT copy `public/` or `.next/static/`
# next to it (see the Next.js self-hosting docs; `npm run start:standalone`
# performs the copy). The systemd units run `node .next/standalone/server.js`
# directly, so without this step the server boots, answers `/` with 200, and
# 404s every `/_next/static/**` and `/public` asset — a site that looks up but
# is unusable in a browser.
#
# Because a bare `npm run build` silently re-creates `.next/standalone` without
# the staged assets, this script is the single staging authority. Run it after
# EVERY frontend build, before (re)starting the frontend units.
#
# Usage:
#   scripts/stage_frontend_standalone.sh            # stage + verify
#   scripts/stage_frontend_standalone.sh --verify    # verify only (no writes)
#
# Exit codes:
#   0  staged assets present and complete
#   1  build output missing
#   2  staging incomplete after the copy (fail closed)
# ============================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND="${REPO_ROOT}/frontend"

MODE="stage"
while [ $# -gt 0 ]; do
  case "$1" in
    --verify) MODE="verify"; shift ;;
    # Stage an isolated build tree instead of the repo checkout. The live
    # frontend unit serves .next/standalone from the checkout, so a rebuild
    # there corrupts what the running process is serving; isolated builds
    # (scripts/build_frontend_isolated.sh) live elsewhere and are staged with this.
    --frontend) FRONTEND="${2:?--frontend needs a directory}"; shift 2 ;;
    -h | --help) sed -n '2,22p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown arg $1" >&2; exit 64 ;;
  esac
done
STANDALONE="${FRONTEND}/.next/standalone"

log() { printf '[stage-standalone] %s\n' "$*"; }

if [ ! -f "${STANDALONE}/server.js" ]; then
  log "ERROR: ${STANDALONE}/server.js not found — run \`npm run build\` first"
  exit 1
fi

if [ "$MODE" = "stage" ]; then
  log "staging public/ and .next/static into .next/standalone"
  rm -rf "${STANDALONE}/public" "${STANDALONE}/.next/static"
  cp -r "${FRONTEND}/public" "${STANDALONE}/public"
  cp -r "${FRONTEND}/.next/static" "${STANDALONE}/.next/static"
fi

# ---- Verification (fail closed) -------------------------------------------
rc=0

if [ ! -d "${STANDALONE}/public" ]; then
  log "FAIL: .next/standalone/public missing (all /public assets will 404)"
  rc=2
fi
if [ ! -d "${STANDALONE}/.next/static" ]; then
  log "FAIL: .next/standalone/.next/static missing (all /_next/static assets will 404)"
  rc=2
fi

if [ "$rc" = 0 ]; then
  # The build the server runs must be the build we staged.
  top_build_id="$(cat "${FRONTEND}/.next/BUILD_ID" 2>/dev/null || echo '')"
  standalone_build_id="$(cat "${STANDALONE}/.next/BUILD_ID" 2>/dev/null || echo '')"
  if [ -z "$top_build_id" ] || [ "$top_build_id" != "$standalone_build_id" ]; then
    log "FAIL: BUILD_ID mismatch (top='${top_build_id}' standalone='${standalone_build_id}')"
    log "      .next/standalone is stale relative to .next — rebuild, then re-run this script"
    rc=2
  fi

  # Every chunk the build references must be reachable from the staged copy.
  missing=0
  while IFS= read -r chunk; do
    [ -n "$chunk" ] || continue
    [ -f "${STANDALONE}/.next/static/${chunk}" ] || { log "FAIL: missing staged chunk ${chunk}"; missing=1; }
  done < <(cd "${FRONTEND}/.next/static" && find . -name '*.js' -printf '%P\n')
  [ "$missing" = 0 ] || rc=2

  # public/ must be staged too (favicon / manifest etc. are referenced by the shell).
  if [ -d "${FRONTEND}/public" ]; then
    pub_missing=0
    while IFS= read -r f; do
      [ -n "$f" ] || continue
      [ -f "${STANDALONE}/public/${f}" ] || { log "FAIL: missing staged public file ${f}"; pub_missing=1; }
    done < <(cd "${FRONTEND}/public" && find . -type f -printf '%P\n')
    [ "$pub_missing" = 0 ] || rc=2
  fi
fi

if [ "$rc" = 0 ]; then
  staged_js="$(find "${STANDALONE}/.next/static" -name '*.js' | wc -l)"
  log "OK: staged ${staged_js} js chunks (BUILD_ID ${standalone_build_id})"
  log "note: a RUNNING frontend registers static routes at boot — restart the unit to serve newly staged assets"
else
  log "staging verification FAILED (rc=${rc})"
fi
exit "$rc"
