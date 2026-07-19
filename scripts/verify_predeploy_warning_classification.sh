#!/usr/bin/env bash
# verify_predeploy_warning_classification.sh — classify known approval-pending
# pre-deploy warnings from a captured pre_deploy_check.sh log.
#
# This script is read-only. It does not run deployments, write secrets, change
# DNS, build images, or mutate services. It validates that the warnings left in
# the release gate are exactly the documented human-approval warnings.

set -euo pipefail

LOG_PATH="${PREDEPLOY_LOG_PATH:-/tmp/legalops-predeploy-loop79.log}"

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

contains_file() {
  local file="$1"
  local pattern="$2"
  grep -Fq "$pattern" "$file"
}

echo "================================================"
echo "⚠️  Pre-deploy Warning Classification"
echo "================================================"

if [ -s "${LOG_PATH}" ]; then
  pass "Pre-deploy log exists: ${LOG_PATH}"
else
  fail "Pre-deploy log missing or empty: ${LOG_PATH}"
fi

contains_file "${LOG_PATH}" "✅ Passed:   22" && pass "Pre-deploy passed count is 22" || fail "Pre-deploy passed count is not 22"
contains_file "${LOG_PATH}" "❌ Failed:   0" && pass "Pre-deploy failed count is 0" || fail "Pre-deploy failed count is not 0"
contains_file "${LOG_PATH}" "⚠️  Warnings: 5" && pass "Pre-deploy warning count is 5" || fail "Pre-deploy warning count is not 5"

expected_warnings=(
  "JWT_PRIVATE_KEY not set (RS256 fallback to HS256)"
  "JWT_PUBLIC_KEY not set"
  "ENTRA_TENANT_ID not set (SSO disabled in dev)"
  "CLAUDE_API_KEY not set (AI review disabled)"
  "Docker image build skipped by SKIP_DOCKER_BUILD=1"
)

for warning in "${expected_warnings[@]}"; do
  contains_file "${LOG_PATH}" "  - ${warning}" && pass "Known warning present: ${warning}" || fail "Known warning missing: ${warning}"
done

warning_lines="$(
  awk '/^Warnings:/{flag=1; next} /^$/{if(flag){exit}} flag && /^  - /{print}' "${LOG_PATH}"
)"

unexpected_warning_lines="$(
  while IFS= read -r line; do
    [ -z "${line}" ] && continue
    matched=0
    for warning in "${expected_warnings[@]}"; do
      if [ "${line}" = "  - ${warning}" ]; then
        matched=1
        break
      fi
    done
    [ "${matched}" -eq 0 ] && printf '%s\n' "${line}"
  done <<<"${warning_lines}" || true
)"

if [ -z "${unexpected_warning_lines}" ]; then
  pass "No unexpected pre-deploy warnings are present"
else
  echo "${unexpected_warning_lines}"
  fail "Unexpected pre-deploy warnings are present"
fi

contains_file "docs/PRODUCTION_APPROVAL_PACKET.md" "Warnings は本番 secret 未投入" && pass "Approval packet explains warning classification" || fail "Approval packet missing warning classification"
contains_file "docs/FINAL_RELEASE_STOP_REPORT.md" "Warnings は本番 secret 未投入" && pass "Final stop report explains warning classification" || fail "Final stop report missing warning classification"
contains_file "docs/RELEASE_EVIDENCE_MATRIX.md" "Warnings 5" && pass "Evidence matrix records warning count" || fail "Evidence matrix missing warning count"

echo ""
echo "================================================"
echo "📊 Summary"
echo "================================================"
echo "✅ Passed: ${PASS}"
echo "❌ Failed: ${FAIL}"

if [ "${FAIL}" -gt 0 ]; then
  echo "🚨 Pre-deploy warning classification failed"
  exit 1
fi

echo "✅ Pre-deploy warning classification passed"
exit 0
