#!/usr/bin/env bash
# verify_review_evidence.sh — read-only release review evidence checks.
#
# This script validates that AI/code/security review evidence is documented
# honestly: CodeRabbit availability/timeout is recorded, no unsupported
# "Critical/High = 0" claim is made for missing findings, and fallback static
# and security reviews are tied to concrete gates.

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

contains_file() {
  local file="$1"
  local pattern="$2"
  grep -Fq "$pattern" "$file"
}

echo "================================================"
echo "🔍 Review Evidence Preflight"
echo "================================================"

REPORT="docs/FINAL_RELEASE_STOP_REPORT.md"
EVIDENCE="docs/RELEASE_EVIDENCE_MATRIX.md"
APPROVAL="docs/PRODUCTION_APPROVAL_PACKET.md"
HANDOVER="docs/HANDOVER.md"
HANDOFF="reports/handoff/2026-07-19-cto-autonomous-session.md"
TRANSCRIPT="reports/agent-transcripts/2026-07-13T23-40-43.md"

for file in "${REPORT}" "${EVIDENCE}" "${APPROVAL}" "${HANDOVER}" "${HANDOFF}" "${TRANSCRIPT}"; do
  [ -s "${file}" ] && pass "Review evidence source exists: ${file}" || fail "Review evidence source missing or empty: ${file}"
done

contains_file "${REPORT}" "## 🧪 3. 実行したレビュー" && pass "Final report has review section" || fail "Final report missing review section"
contains_file "${REPORT}" "CodeRabbit CLI" && pass "Final report records CodeRabbit CLI availability" || fail "Final report missing CodeRabbit CLI evidence"
contains_file "${REPORT}" "findings 前 timeout" && pass "Final report records CodeRabbit timeout before findings" || fail "Final report missing CodeRabbit timeout"
contains_file "${REPORT}" "Critical / High が「0 件」とは断言しない" && pass "Final report avoids unsupported Critical/High zero claim" || fail "Final report missing Critical/High limitation"
contains_file "${REPORT}" "ローカル静的検証・CI・pre-deploy" && pass "Final report records fallback static/CI/pre-deploy review" || fail "Final report missing fallback review evidence"
contains_file "${REPORT}" "Security review" && pass "Final report records security review" || fail "Final report missing security review"
contains_file "${REPORT}" "Static review" && pass "Final report records static review" || fail "Final report missing static review"
contains_file "${REPORT}" "Release review" && pass "Final report records release review" || fail "Final report missing release review"

contains_file "${EVIDENCE}" "CodeRabbit CLI" && pass "Evidence matrix records CodeRabbit CLI" || fail "Evidence matrix missing CodeRabbit CLI"
contains_file "${EVIDENCE}" "findings なし" && pass "Evidence matrix records missing CodeRabbit findings" || fail "Evidence matrix missing findings limitation"
contains_file "${EVIDENCE}" "代替レビュー" && pass "Evidence matrix records fallback review" || fail "Evidence matrix missing fallback review"
contains_file "${EVIDENCE}" "ruff / mypy / pytest / migration roundtrip / Bandit / npm audit / secret scan / Cloudflare preflight" && pass "Evidence matrix lists fallback review gates" || fail "Evidence matrix missing fallback gate list"

contains_file "${APPROVAL}" "CodeRabbit review" && pass "Approval packet records CodeRabbit review state" || fail "Approval packet missing CodeRabbit review state"
contains_file "${APPROVAL}" "findings 前タイムアウト" && pass "Approval packet records CodeRabbit timeout" || fail "Approval packet missing CodeRabbit timeout"
contains_file "${APPROVAL}" "ローカル静的検証で代替" && pass "Approval packet records fallback static verification" || fail "Approval packet missing fallback verification"

contains_file "${HANDOFF}" "CodeRabbit" && pass "Handoff records CodeRabbit attempt" || fail "Handoff missing CodeRabbit attempt"
contains_file "${HANDOFF}" "no actionable findings" && pass "Handoff records no actionable findings received" || fail "Handoff missing no-findings statement"
contains_file "${HANDOFF}" "bandit" && pass "Handoff records Bandit review result" || fail "Handoff missing Bandit evidence"
contains_file "${HANDOFF}" "npm audit" && pass "Handoff records npm audit result" || fail "Handoff missing npm audit evidence"

contains_file "${TRANSCRIPT}" "Adversarial-Reviewer" && pass "Agent transcript records adversarial reviewer" || fail "Agent transcript missing adversarial reviewer"
contains_file "${TRANSCRIPT}" "Silent-Failure-Hunter" && pass "Agent transcript records silent-failure hunter" || fail "Agent transcript missing silent-failure hunter"
contains_file "${HANDOVER}" "認証・認可・DB スキーマ・並列処理変更" && pass "Handover records future adversarial review trigger" || fail "Handover missing future review trigger"

unsupported_zero_claim="$(
  grep -F "Critical / High が「0 件」" "${REPORT}" "${EVIDENCE}" "${APPROVAL}" 2>/dev/null \
    | grep -Fv "とは断言しない" || true
)"

if [ -n "${unsupported_zero_claim}" ]; then
  echo "${unsupported_zero_claim}"
  fail "Release docs contain unsupported Critical/High zero wording"
else
  pass "Release docs do not claim unsupported Critical/High zero findings"
fi

echo ""
echo "================================================"
echo "📊 Summary"
echo "================================================"
echo "✅ Passed: ${PASS}"
echo "❌ Failed: ${FAIL}"

if [ "${FAIL}" -gt 0 ]; then
  echo "🚨 Review evidence preflight failed"
  exit 1
fi

echo "✅ Review evidence preflight passed"
exit 0
