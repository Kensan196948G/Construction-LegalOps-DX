#!/usr/bin/env bash
# verify_local_workspace_state.sh — read-only local git state preflight.
#
# Timeless fail-closed checks only: assertions must stay true for any session,
# branch, or point in the release lifecycle. Point-in-time workspace facts
# (branch name, dirty files, ahead/behind) are DISCLOSED as evidence output,
# never asserted, so committing or merging work can not break this gate.
# The script does not push, merge, rebase, tag, deploy, or mutate anything.

set -euo pipefail

PASS=0
FAIL=0

pass() {
  echo "✅ $1"
  PASS=$((PASS + 1))
}

fail() {
  echo "❌ $1"
  FAIL=$((FAIL + 1))
}

echo "================================================"
echo "🧭 Local Workspace State Preflight"
echo "================================================"

# --- 1. Git sanity -------------------------------------------------------
git rev-parse --is-inside-work-tree >/dev/null 2>&1 && pass "Inside a git work tree" || fail "Not inside a git work tree"

BRANCH="$(git branch --show-current || true)"
HEAD_SHA="$(git rev-parse --short HEAD 2>/dev/null || true)"
[ -n "${HEAD_SHA}" ] && pass "HEAD resolvable (${HEAD_SHA})" || fail "HEAD is not resolvable"

if git rev-parse --verify --quiet origin/main >/dev/null; then
  ORIGIN_MAIN_SHA="$(git rev-parse --short origin/main)"
  pass "origin/main resolvable (${ORIGIN_MAIN_SHA})"
else
  ORIGIN_MAIN_SHA=""
  fail "origin/main is not resolvable"
fi

# --- 2. Timeless fail-closed checks --------------------------------------
STATUS_LINES="$(git status --porcelain)"

# Secret-bearing files must never appear in the working tree status.
if grep -E '(^|/)\.env(\.|$| )' <<<"${STATUS_LINES}" | grep -v '\.env\.example' >/dev/null 2>&1; then
  fail "Secret-bearing file (.env*) appears in git status"
else
  pass "No secret-bearing file (.env*) in git status"
fi

# Tracked shell scripts must carry the executable bit in the index
# (core.filemode=false environments silently commit 100644 otherwise).
NONEXEC="$(git ls-files -s -- 'scripts/*.sh' | awk '$1 == "100644" {print $4}')"
if [ -n "${NONEXEC}" ]; then
  fail "Tracked scripts missing executable bit: $(tr '\n' ' ' <<<"${NONEXEC}")"
else
  pass "All tracked scripts/*.sh carry the executable bit"
fi

# Release-facing verifier scripts referenced by pre_deploy_check must exist.
for f in \
  "scripts/verify_release_docs.sh" \
  "scripts/verify_github_release_gate.sh" \
  "scripts/verify_goal_completion_evidence.sh"; do
  [ -f "${f}" ] && pass "Verifier present: ${f}" || fail "Verifier missing: ${f}"
done

# --- 3. Point-in-time disclosure (evidence output, never asserted) --------
DIRTY_COUNT="$(printf '%s' "${STATUS_LINES}" | grep -c . || true)"
echo ""
echo "📋 Workspace disclosure (informational)"
echo "  - branch: ${BRANCH:-<detached>}"
echo "  - HEAD: ${HEAD_SHA} / origin/main: ${ORIGIN_MAIN_SHA:-<unknown>}"
echo "  - uncommitted entries: ${DIRTY_COUNT}"
if [ "${DIRTY_COUNT}" -gt 0 ]; then
  printf '%s\n' "${STATUS_LINES}" | sed 's/^/    /' | head -50
fi

echo ""
echo "================================================"
echo "📊 Summary"
echo "================================================"
echo "✅ Passed: ${PASS}"
echo "❌ Failed: ${FAIL}"

if [ "${FAIL}" -gt 0 ]; then
  echo "🚨 Local workspace state preflight failed"
  exit 1
fi

echo "✅ Local workspace state preflight passed"
exit 0
