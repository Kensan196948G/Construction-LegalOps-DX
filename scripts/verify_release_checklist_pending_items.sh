#!/usr/bin/env bash
# verify_release_checklist_pending_items.sh — classify unchecked release
# checklist items as human approval, production execution, or post-release gates.
#
# This script is read-only. It does not mark checklist items complete. It fails
# if an unchecked item looks like unresolved local engineering work rather than
# a documented human/production/post-release gate.

set -euo pipefail

CHECKLIST="${RELEASE_CHECKLIST_PATH:-docs/RELEASE_CHECKLIST.md}"

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
echo "📋 Release Checklist Pending Item Classification"
echo "================================================"

if [ -s "${CHECKLIST}" ]; then
  pass "Release checklist exists: ${CHECKLIST}"
else
  fail "Release checklist missing or empty: ${CHECKLIST}"
fi

unchecked_lines="$(grep -n '^- \[ \]' "${CHECKLIST}" || true)"
unchecked_count="$(printf '%s\n' "${unchecked_lines}" | sed '/^$/d' | wc -l | tr -d ' ')"

if [ "${unchecked_count}" -gt 0 ]; then
  pass "Unchecked release checklist items are present for approval classification (${unchecked_count})"
else
  fail "No unchecked checklist items found; expected human approval gates before production"
fi

allowed_patterns=(
  "GitHub Projects の Production Release"
  "CHANGELOG.md.*0.1.0"
  "state.json.*project.status"
  "CodeRabbit / Codex review"
  "docs/HANDOVER.md.*未解決事項"
  "docs/PRODUCTION_APPROVAL_PACKET.md.*責任者"
  "Standalone WebUI"
  "JWT_PRIVATE_KEY"
  "JWT_PUBLIC_KEY"
  "ENTRA_"
  "CLAUDE_API_KEY"
  "SHAREPOINT_"
  "DESKNET_"
  "HENNGE_"
  "POSTGRES_PASSWORD"
  "REDIS_PASSWORD"
  "HASH_CHAIN_SECRET"
  "シークレットローテーション"
  "Cloudflare Tunnel 採用時"
  "非 Tunnel / 直接公開時のみ"
  "HSTS"
  "TLS 1.2 / 1.3"
  "SSL Labs"
  "postgresql.conf"
  "pg_hba.conf"
  "自動バックアップ"
  "Alembic rollback drill"
  "PITR"
  "audit_logs.*パーティショニング"
  "本番 DB"
  "バックアップ取得後"
  "alembic current"
  "ロールバック手順"
  "audit_logs.*トリガー"
  "AI 呼び出し"
  "法定保存期間"
  "REVOKE UPDATE"
  "Report-Only"
  "レポートで検出"
  "Content-Security-Policy-Report-Only"
  "段階的ロールアウト"
  "違反発生時"
  "Login"
  "Upload"
  "Review"
  "Workflow"
  "Audit"
  "Healthz / Readyz"
  "負荷確認"
  "CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK"
  "mirai-dx-platform.com"
  "legalops.mirai-dx-platform.com"
  "Cloudflare Access"
  "CLOUDFLARE_ACCESS_AUD"
  "CLOUDFLARE_ACCESS_ISSUER"
  "Access policy"
  "Tunnel ID"
  "Tunnel UUID"
  "Tunnel UUID 解決"
  "CLOUDFLARE_TUNNEL_CREDENTIALS_FILE"
  "verify_cloudflare_legalops.sh"
  "Cloudflare Tunnel compose overlay"
  "cloudflared tunnel ingress validate"
  "DNS 作成後"
  "systemd user service"
  "URL:"
  "Health:"
  "HEAD:"
  "待受:"
  "起動:"
  "停止:"
  "配信元:"
  "Trivy"
  "Bandit / npm audit"
  "scan_secrets.sh"
  "OWASP ZAP"
  "git log -p"
  "secrets を環境変数"
  "法務担当者"
  "ai_disclaimer_policy"
  "弁護士法"
  "個人情報保護法"
  "監査ログ保管期間"
  "障害検知"
  "nginx の upstream"
  "DB マイグレーション"
  "バックアップから PITR"
  "CSP 違反"
  "Cloudflare 起因"
  "事後対応"
  "24 時間以内"
  "72 時間以内"
  "7 日以内"
  "GitHub Release"
)

unexpected_lines=()
while IFS= read -r line; do
  [ -z "${line}" ] && continue
  matched=0
  for pattern in "${allowed_patterns[@]}"; do
    if grep -Eq "${pattern}" <<<"${line}"; then
      matched=1
      break
    fi
  done
  if [ "${matched}" -eq 0 ]; then
    unexpected_lines+=("${line}")
  fi
done <<<"${unchecked_lines}"

if [ "${#unexpected_lines[@]}" -eq 0 ]; then
  pass "All unchecked checklist items are classified as approval/production/post-release gates"
else
  printf '%s\n' "${unexpected_lines[@]}"
  fail "Unclassified unchecked checklist items are present"
fi

grep -Fq "本番 deploy / DNS / secrets は人間承認後に実行" "${CHECKLIST}" \
  && pass "Release checklist records human approval boundary" \
  || fail "Release checklist missing human approval boundary"

grep -Fq "docs/PRODUCTION_APPROVAL_PACKET.md" "${CHECKLIST}" \
  && pass "Release checklist links production approval packet" \
  || fail "Release checklist missing approval packet link"

echo ""
echo "================================================"
echo "📊 Summary"
echo "================================================"
echo "✅ Passed: ${PASS}"
echo "❌ Failed: ${FAIL}"

if [ "${FAIL}" -gt 0 ]; then
  echo "🚨 Release checklist pending item classification failed"
  exit 1
fi

echo "✅ Release checklist pending item classification passed"
exit 0
