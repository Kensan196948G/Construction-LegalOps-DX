#!/usr/bin/env bash
# verify_local_workspace_state.sh — read-only local git state disclosure checks.
#
# This verifier makes sure the release-facing documents match the current local
# workspace reality. It does not push, merge, rebase, tag, deploy, or mutate
# files or remote systems.

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

contains() {
  local file="$1"
  local pattern="$2"
  grep -Fq -- "$pattern" "$file"
}

echo "================================================"
echo "🧭 Local Workspace State Preflight"
echo "================================================"

BRANCH="$(git branch --show-current)"
HEAD_SHA="$(git rev-parse --short HEAD)"
ORIGIN_MAIN_SHA="$(git rev-parse --short origin/main)"
DIRTY_COUNT="$(git status --porcelain | wc -l | tr -d ' ')"
STATUS_LINES="$(git status --porcelain)"
DIFF_NAMES="$(git diff --name-only | sort)"

[ "${BRANCH}" = "feat/phase1-neon-cf-preview" ] && pass "Local branch is feat/phase1-neon-cf-preview" || fail "Local branch is ${BRANCH}"
[ "${HEAD_SHA}" != "${ORIGIN_MAIN_SHA}" ] && pass "Local HEAD differs from origin/main (${HEAD_SHA} != ${ORIGIN_MAIN_SHA})" || fail "Local HEAD unexpectedly equals origin/main"
[ "${DIRTY_COUNT}" -gt 0 ] && pass "Local workspace has uncommitted changes (${DIRTY_COUNT} files)" || fail "Local workspace has no uncommitted changes"

for file in \
  "README.md" \
  "docs/CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK.md" \
  "docs/FINAL_RELEASE_STOP_REPORT.md" \
  "docs/HANDOVER.md" \
  "docs/PRODUCTION_APPROVAL_PACKET.md" \
  "docs/RELEASE_CHECKLIST.md" \
  "docs/RELEASE_EVIDENCE_MATRIX.md" \
  "docs/api_design.md" \
  "backend/app/api/v1/compliance.py" \
  "backend/app/schemas/compliance.py" \
  "backend/app/services/compliance_service.py" \
  "backend/tests/integration/test_risks_compliance.py" \
  "backend/tests/unit/test_compliance_service.py" \
  "backend/app/api/v1/users.py" \
  "backend/app/services/user_service.py" \
  "backend/tests/integration/test_audit_logs.py" \
  "backend/tests/unit/test_user_service.py" \
  "backend/app/services/file_parser.py" \
  "backend/tests/unit/test_file_parser.py" \
  "backend/app/api/v1/uploads.py" \
  "backend/app/schemas/upload.py" \
  "backend/app/services/upload_service.py" \
  "backend/tests/integration/test_uploads_flow.py" \
  "frontend/components/templates/create-template-button.tsx" \
  "frontend/app/(authenticated)/compliance/page.tsx" \
  "frontend/hooks/use-compliance.ts" \
  "frontend/hooks/use-users.ts" \
  "frontend/lib/api/endpoints.ts" \
  "frontend/lib/api/schemas.ts" \
  "infra/cloudflare/README.md" \
  "scripts/pre_deploy_check.sh" \
  "scripts/verify_cloudflare_legalops.sh" \
  "scripts/verify_github_release_gate.sh" \
  "scripts/verify_goal_completion_evidence.sh" \
  "scripts/verify_predeploy_warning_classification.sh" \
  "scripts/verify_release_docs.sh" \
  "state.json"; do
  if grep -Fxq "${file}" <<<"${DIFF_NAMES}"; then
    pass "Expected Loop sync file is dirty: ${file}"
  else
    fail "Expected Loop sync file is not dirty: ${file}"
  fi
done

if grep -Fq "?? scripts/verify_local_workspace_state.sh" <<<"${STATUS_LINES}"; then
  pass "Expected Loop sync file is untracked: scripts/verify_local_workspace_state.sh"
else
  fail "Expected untracked Loop sync file is missing: scripts/verify_local_workspace_state.sh"
fi

contains "README.md" "Local workspace" && pass "README discloses local workspace state" || fail "README missing local workspace disclosure"
contains "README.md" "push / rebase / merge は未実行" && pass "README discloses no push/rebase/merge" || fail "README missing no push/rebase/merge disclosure"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "Local workspace" && pass "Final report discloses local workspace state" || fail "Final report missing local workspace disclosure"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "push・rebase・merge未実行" && pass "Final report discloses no push/rebase/merge" || fail "Final report missing no push/rebase/merge disclosure"
contains "docs/HANDOVER.md" "ローカル作業ツリー" && pass "HANDOVER discloses local workspace state" || fail "HANDOVER missing local workspace disclosure"
contains "docs/HANDOVER.md" "push / rebase / merge は未実行" && pass "HANDOVER discloses no push/rebase/merge" || fail "HANDOVER missing no push/rebase/merge disclosure"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "Local workspace" && pass "Approval packet discloses local workspace state" || fail "Approval packet missing local workspace disclosure"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "push / rebase / merge は未実行" && pass "Approval packet discloses no push/rebase/merge" || fail "Approval packet missing no push/rebase/merge disclosure"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "ローカル作業ツリー" && pass "Evidence matrix discloses local workspace state" || fail "Evidence matrix missing local workspace disclosure"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "push / rebase / merge は未実行" && pass "Evidence matrix discloses no push/rebase/merge" || fail "Evidence matrix missing no push/rebase/merge disclosure"

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
