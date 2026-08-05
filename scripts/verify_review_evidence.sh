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
CODERABBIT_REVIEW="reports/reviews/2026-07-20-coderabbit-uncommitted.md"
CODERABBIT_INITIAL_RAW="reports/reviews/coderabbit-uncommitted-2026-07-20T092639.txt"
CODERABBIT_FINAL_RAW="reports/reviews/coderabbit-uncommitted-2026-07-20T-final.txt"

for file in "${REPORT}" "${EVIDENCE}" "${APPROVAL}" "${HANDOVER}" "${HANDOFF}" "${TRANSCRIPT}" "${CODERABBIT_REVIEW}" "${CODERABBIT_INITIAL_RAW}" "${CODERABBIT_FINAL_RAW}"; do
  [ -s "${file}" ] && pass "Review evidence source exists: ${file}" || fail "Review evidence source missing or empty: ${file}"
done

contains_file "${REPORT}" "## 🧪 3. 実行したレビュー" && pass "Final report has review section" || fail "Final report missing review section"
contains_file "${REPORT}" "CodeRabbit CLI" && pass "Final report records CodeRabbit CLI availability" || fail "Final report missing CodeRabbit CLI evidence"
contains_file "${REPORT}" "major findings" && pass "Final report records CodeRabbit findings received" || fail "Final report missing CodeRabbit findings received"
contains_file "${REPORT}" "Critical / High が「0 件」とは断言しない" && pass "Final report avoids unsupported Critical/High zero claim" || fail "Final report missing Critical/High limitation"
contains_file "${REPORT}" "ローカル静的検証・CI・pre-deploy" && pass "Final report records fallback static/CI/pre-deploy review" || fail "Final report missing fallback review evidence"
contains_file "${REPORT}" "Security review" && pass "Final report records security review" || fail "Final report missing security review"
contains_file "${REPORT}" "Static review" && pass "Final report records static review" || fail "Final report missing static review"
contains_file "${REPORT}" "Release review" && pass "Final report records release review" || fail "Final report missing release review"

contains_file "${EVIDENCE}" "CodeRabbit CLI" && pass "Evidence matrix records CodeRabbit CLI" || fail "Evidence matrix missing CodeRabbit CLI"
contains_file "${EVIDENCE}" "findings を返却" && pass "Evidence matrix records CodeRabbit findings" || fail "Evidence matrix missing CodeRabbit findings"
contains_file "${EVIDENCE}" "Nginx \`/api/auth\` 境界" && pass "Evidence matrix records final CodeRabbit re-run fixes" || fail "Evidence matrix missing final CodeRabbit re-run fixes"
contains_file "${EVIDENCE}" "代替レビュー" && pass "Evidence matrix records fallback review" || fail "Evidence matrix missing fallback review"
contains_file "${EVIDENCE}" "ruff / mypy / pytest / migration roundtrip / Bandit / npm audit / secret scan / Cloudflare preflight" && pass "Evidence matrix lists fallback review gates" || fail "Evidence matrix missing fallback gate list"

contains_file "${APPROVAL}" "CodeRabbit review" && pass "Approval packet records CodeRabbit review state" || fail "Approval packet missing CodeRabbit review state"
contains_file "${APPROVAL}" "findings を返却" && pass "Approval packet records CodeRabbit findings" || fail "Approval packet missing CodeRabbit findings"
contains_file "${APPROVAL}" "Markdown内部リンクrepo外拒否" && pass "Approval packet records final CodeRabbit re-run fixes" || fail "Approval packet missing final CodeRabbit re-run fixes"
contains_file "${APPROVAL}" "ローカル静的検証で代替" && pass "Approval packet records fallback static verification" || fail "Approval packet missing fallback verification"

contains_file "${CODERABBIT_REVIEW}" "Cloudflare API CNAME content" && pass "CodeRabbit review record covers Cloudflare API CNAME fix" || fail "CodeRabbit review record missing Cloudflare API CNAME fix"
contains_file "${CODERABBIT_REVIEW}" "CLOUDFLARE_TUNNEL_CREDENTIALS_FILE" && pass "CodeRabbit review record covers credentials-file fix" || fail "CodeRabbit review record missing credentials-file fix"
contains_file "${CODERABBIT_REVIEW}" "normal TLS verification" && pass "CodeRabbit review record covers TLS verification fix" || fail "CodeRabbit review record missing TLS verification fix"
contains_file "${CODERABBIT_REVIEW}" "production deployment" && pass "CodeRabbit review record covers production deployment boundary fix" || fail "CodeRabbit review record missing deployment boundary fix"
contains_file "${CODERABBIT_REVIEW}" "README exposed fixed internal WebUI IP/port/service values" && pass "CodeRabbit review record covers README internal URL fix" || fail "CodeRabbit review record missing README internal URL fix"
contains_file "${CODERABBIT_REVIEW}" "nginx NextAuth regex" && pass "CodeRabbit review record covers nginx auth route fix" || fail "CodeRabbit review record missing nginx auth route fix"
contains_file "${CODERABBIT_REVIEW}" "internal-link validator" && pass "CodeRabbit review record covers internal link validator fix" || fail "CodeRabbit review record missing internal link validator fix"
contains_file "${CODERABBIT_INITIAL_RAW}" '"severity":"major"' && pass "Initial CodeRabbit raw artifact records major findings" || fail "Initial CodeRabbit raw artifact missing major findings"
contains_file "${CODERABBIT_FINAL_RAW}" '"severity":"major"' && pass "Final CodeRabbit raw artifact records major findings" || fail "Final CodeRabbit raw artifact missing major findings"
contains_file "${CODERABBIT_FINAL_RAW}" '"fileName":"infra/nginx/default.conf"' && pass "Final CodeRabbit raw artifact records nginx finding" || fail "Final CodeRabbit raw artifact missing nginx finding"

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
