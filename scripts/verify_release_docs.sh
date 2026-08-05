#!/usr/bin/env bash
# verify_release_docs.sh — read-only release documentation consistency checks.
#
# This script validates the approval/stop-report documents that prove the
# project is ready for human production approval. It does not deploy, create
# DNS records, change secrets, or contact production systems.

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
  grep -Fq "$pattern" "$file"
}

validate_internal_markdown_links() {
  python3 - <<'PY'
import os
import re
import sys
from pathlib import Path

repo_root = Path.cwd().resolve()
files = [
    Path("README.md"),
    Path("docs/FINAL_RELEASE_STOP_REPORT.md"),
    Path("docs/RELEASE_EVIDENCE_MATRIX.md"),
    Path("docs/PRODUCTION_APPROVAL_PACKET.md"),
    Path("docs/HANDOVER.md"),
    Path("docs/RELEASE_CHECKLIST.md"),
]
pattern = re.compile(r"\[[^\]]+\]\(<([^>]+)>\)|\[[^\]]+\]\((?!https?://|mailto:|#)([^)]+)\)")
missing: list[tuple[str, str]] = []

for file in files:
    text = file.read_text(encoding="utf-8")
    for match in pattern.finditer(text):
        target = (match.group(1) or match.group(2)).split("#", 1)[0]
        if not target:
            continue
        resolved = (file.parent / target).resolve()
        try:
            in_repo = resolved.is_relative_to(repo_root)
        except AttributeError:
            in_repo = str(resolved).startswith(str(repo_root) + os.sep) or resolved == repo_root
        if not in_repo or not resolved.exists():
            missing.append((str(file), target))

for file, target in missing:
    print(f"{file}|{target}", file=sys.stderr)

raise SystemExit(1 if missing else 0)
PY
}

echo "================================================"
echo "📄 Release Documentation Preflight"
echo "================================================"

CURRENT_LOOP="$(
  python3 - <<'PY'
import json
with open("state.json", encoding="utf-8") as fh:
    state = json.load(fh)
print(state["project"]["last_loop_completed"])
PY
)"
CURRENT_MARKER="Loop ${CURRENT_LOOP}"

required_files=(
  "README.md"
  "CHANGELOG.md"
  "state.json"
  "docs/HANDOVER.md"
  "docs/PRODUCTION_APPROVAL_PACKET.md"
  "docs/RELEASE_CHECKLIST.md"
  "docs/RELEASE_EVIDENCE_MATRIX.md"
  "docs/FINAL_RELEASE_STOP_REPORT.md"
  "docs/CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK.md"
  "scripts/apply_cloudflare_legalops_after_approval.sh"
  "docs/Construction-LegalOps-DX (Standalone).html"
  "scripts/verify_goal_completion_evidence.sh"
  "scripts/verify_review_evidence.sh"
  "scripts/verify_dependency_audit_evidence.sh"
  "scripts/verify_monitoring_config.sh"
  "scripts/verify_backup_restore_docs.sh"
  "scripts/verify_local_workspace_state.sh"
  "backend/app/services/sharepoint_service.py"
  "backend/tests/unit/test_sharepoint_service.py"
  "backend/app/services/notification_service.py"
  "backend/tests/unit/test_notification_service.py"
  "backend/app/services/contract_service.py"
  "backend/tests/unit/test_contract_service.py"
  "backend/tests/integration/test_contracts_crud.py"
  "frontend/components/templates/create-template-button.tsx"
  "frontend/hooks/use-templates.ts"
  "backend/app/services/compliance_service.py"
  "backend/app/api/v1/compliance.py"
  "backend/tests/unit/test_compliance_service.py"
  "backend/tests/integration/test_risks_compliance.py"
  "backend/tests/integration/test_audit_logs.py"
  "backend/tests/unit/test_user_service.py"
  "backend/app/api/v1/users.py"
  "backend/app/services/user_service.py"
  "backend/app/services/file_parser.py"
  "backend/tests/unit/test_file_parser.py"
  "backend/app/services/upload_service.py"
  "backend/app/api/v1/uploads.py"
  "backend/tests/integration/test_uploads_flow.py"
  "backend/app/services/cloudflare_access.py"
  "backend/tests/unit/test_cloudflare_access.py"
  "backend/tests/integration/test_cloudflare_access_auth.py"
  "frontend/lib/api/endpoints.ts"
  "frontend/lib/api/schemas.ts"
  "frontend/lib/compliance/status.ts"
  "frontend/lib/compliance/__tests__/status.test.ts"
  "frontend/hooks/use-compliance.ts"
  "frontend/hooks/use-users.ts"
  "frontend/app/(authenticated)/compliance/page.tsx"
  "frontend/components/compliance/compliance-findings-table.tsx"
)

for file in "${required_files[@]}"; do
  if [ -s "$file" ]; then
    pass "Required release document exists: ${file}"
  else
    fail "Required release document missing or empty: ${file}"
  fi
done

python3 -m json.tool state.json >/dev/null && pass "state.json is valid JSON" || fail "state.json is invalid JSON"
[ -n "${CURRENT_LOOP}" ] && pass "Current loop marker loaded from state.json: ${CURRENT_MARKER}" || fail "Could not load current loop marker from state.json"

contains "README.md" "docs/FINAL_RELEASE_STOP_REPORT.md" && pass "README links final stop report" || fail "README missing final stop report link"
contains "README.md" "${CURRENT_MARKER}" && pass "README current marker is ${CURRENT_MARKER}" || fail "README current marker is not ${CURRENT_MARKER}"
contains "README.md" "本番リリース / deploy" && pass "README states production release/deploy status" || fail "README missing production release/deploy status"
contains "README.md" "未実行" && pass "README records production deploy not executed" || fail "README missing deploy-not-executed statement"
contains "README.md" "legalops.mirai-dx-platform.com" && pass "README includes Cloudflare legalops hostname" || fail "README missing Cloudflare legalops hostname"
contains "README.md" "Cloudflare Access 302" && pass "README records Cloudflare Access challenge" || fail "README missing Cloudflare Access challenge"
if contains "README.md" "http://192.168.0.185:38100/"; then
  fail "README exposes fixed internal Standalone WebUI URL"
else
  pass "README avoids fixed internal Standalone WebUI URL"
fi
contains "README.md" "](<docs/Construction-LegalOps-DX (Standalone).html>)" && pass "README Standalone HTML link handles spaces and parentheses" || fail "README Standalone HTML link is missing or malformed"
if grep -Fq "Construction-LegalOps-DX%20(Standalone).html" README.md; then
  fail "README Standalone HTML link uses fragile encoded parentheses form"
else
  pass "README Standalone HTML link avoids fragile encoded parentheses form"
fi
validate_internal_markdown_links && pass "Release docs internal Markdown links resolve" || fail "Release docs contain broken internal Markdown links"
contains "README.md" "status JSON の \`stop_command\`" && pass "README points to status JSON stop command" || fail "README missing status JSON stop command reference"
contains "README.md" "docs/PRODUCTION_APPROVAL_PACKET.md" && pass "README links production approval packet" || fail "README missing production approval packet link"
contains "README.md" "Project #30" && pass "README includes GitHub Project #30 release gate" || fail "README missing GitHub Project #30 release gate"
contains "README.md" "SharePoint Graph real mode" && pass "README records SharePoint Graph real mode" || fail "README missing SharePoint Graph real mode evidence"
contains "README.md" "Notification real mode" && pass "README records Notification real mode" || fail "README missing Notification real mode evidence"
contains "README.md" "Contract submit" && pass "README records contract submit evidence" || fail "README missing contract submit evidence"
contains "README.md" "Contract subresources" && pass "README records contract subresource evidence" || fail "README missing contract subresource evidence"
contains "README.md" "Compliance run" && pass "README records compliance run evidence" || fail "README missing compliance run evidence"
contains "README.md" "Local workspace" && pass "README records local workspace state" || fail "README missing local workspace state"
contains "README.md" "本番直前の承認待ち" && pass "README records production stop line" || fail "README missing production stop line"
contains "docs/HANDOVER.md" "FINAL_RELEASE_STOP_REPORT.md" && pass "HANDOVER links final stop report" || fail "HANDOVER missing final stop report link"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "FINAL_RELEASE_STOP_REPORT.md" && pass "Approval packet links final stop report" || fail "Approval packet missing final stop report link"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "FINAL_RELEASE_STOP_REPORT.md" && pass "Evidence matrix links final stop report" || fail "Evidence matrix missing final stop report link"
contains "docs/RELEASE_CHECKLIST.md" "${CURRENT_MARKER}" && pass "Release checklist current marker is ${CURRENT_MARKER}" || fail "Release checklist current marker is not ${CURRENT_MARKER}"
contains "docs/HANDOVER.md" "${CURRENT_MARKER}" && pass "HANDOVER current marker is ${CURRENT_MARKER}" || fail "HANDOVER current marker is not ${CURRENT_MARKER}"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "${CURRENT_MARKER}" && pass "Approval packet current marker is ${CURRENT_MARKER}" || fail "Approval packet current marker is not ${CURRENT_MARKER}"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "${CURRENT_MARKER}" && pass "Evidence matrix current marker is ${CURRENT_MARKER}" || fail "Evidence matrix current marker is not ${CURRENT_MARKER}"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "${CURRENT_MARKER}" && pass "Final stop report current marker is ${CURRENT_MARKER}" || fail "Final stop report current marker is not ${CURRENT_MARKER}"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "GitHub Project #30" && pass "Approval packet includes GitHub Project #30 release gate" || fail "Approval packet missing GitHub Project #30 release gate"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "GitHub Project #30" && pass "Evidence matrix includes GitHub Project #30 release gate" || fail "Evidence matrix missing GitHub Project #30 release gate"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "GitHub Project" && pass "Final report includes GitHub Project release gate" || fail "Final report missing GitHub Project release gate"

contains "docs/FINAL_RELEASE_STOP_REPORT.md" "## 🧩 2. 変更内容サマリ" && pass "Final report includes change summary" || fail "Final report missing change summary"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "## 🧪 3. 実行したレビュー" && pass "Final report includes review results" || fail "Final report missing review results"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "## ✅ 4. テスト結果" && pass "Final report includes test results" || fail "Final report missing test results"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "Release docs preflight           | Passed 352 / Failed 0" && pass "Final report records current release docs 352/0" || fail "Final report missing current release docs 352/0"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "Review evidence                  | Passed 44 / Failed 0" && pass "Final report records current review evidence 44/0" || fail "Final report missing current review evidence 44/0"
contains "README.md" "未チェック75件" && pass "README records current release checklist unchecked count" || fail "README missing current release checklist unchecked count"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "未チェック75件" && pass "Evidence matrix records current release checklist unchecked count" || fail "Evidence matrix missing current release checklist unchecked count"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "未チェック75件" && pass "Final report records current release checklist unchecked count" || fail "Final report missing current release checklist unchecked count"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "未チェック75件" && pass "Approval packet records current release checklist unchecked count" || fail "Approval packet missing current release checklist unchecked count"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "## 🖥️ 5. WebUI 確認方法" && pass "Final report includes WebUI instructions" || fail "Final report missing WebUI instructions"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "## 🚧 6. 残課題" && pass "Final report includes remaining issues" || fail "Final report missing remaining issues"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "## ⚠️ 7. リスク" && pass "Final report includes risks" || fail "Final report missing risks"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "## 🚀 8. 本番デプロイ手順" && pass "Final report includes production deployment steps" || fail "Final report missing production deployment steps"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "## 🛑 9. ロールバック手順" && pass "Final report includes rollback steps" || fail "Final report missing rollback steps"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "## 🧯 10. Stop Line" && pass "Final report includes stop line" || fail "Final report missing stop line"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "SharePoint Graph real mode" && pass "Final report includes SharePoint Graph real mode" || fail "Final report missing SharePoint Graph real mode"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "Notification real mode" && pass "Final report includes Notification real mode" || fail "Final report missing Notification real mode"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "Contract submit" && pass "Final report includes contract submit evidence" || fail "Final report missing contract submit evidence"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "Contract subresources" && pass "Final report includes contract subresource evidence" || fail "Final report missing contract subresource evidence"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "Compliance run" && pass "Final report includes compliance run evidence" || fail "Final report missing compliance run evidence"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "Local workspace" && pass "Final report records local workspace state" || fail "Final report missing local workspace state"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "PR #59 で正本化済み" && pass "Final report records PR #59 canonicalization" || fail "Final report missing PR #59 canonicalization"

contains "docs/FINAL_RELEASE_STOP_REPORT.md" "http://192.168.0.185:38100/" && pass "Final report includes Standalone WebUI URL" || fail "Final report missing Standalone WebUI URL"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "http://192.168.0.185:38100/healthz" && pass "Final report includes Standalone WebUI health URL" || fail "Final report missing Standalone WebUI health URL"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "curl -fsSI http://192.168.0.185:38100/" && pass "Final report includes Standalone WebUI HEAD check" || fail "Final report missing Standalone WebUI HEAD check"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "http://192.168.0.185:38100/standalone-source" && pass "Final report includes Standalone WebUI source endpoint" || fail "Final report missing Standalone WebUI source endpoint"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "construction-legalops-standalone-webui.service" && pass "Final report includes Standalone WebUI systemd unit" || fail "Final report missing Standalone WebUI systemd unit"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "systemctl --user stop construction-legalops-standalone-webui.service" && pass "Final report includes Standalone WebUI stop command" || fail "Final report missing Standalone WebUI stop command"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "docs/Construction-LegalOps-DX (Standalone).html" && pass "Final report includes Standalone WebUI source HTML" || fail "Final report missing Standalone WebUI source HTML"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "http://192.168.0.185:38100/" && pass "Approval packet includes Standalone WebUI URL" || fail "Approval packet missing Standalone WebUI URL"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "curl -fsSI http://192.168.0.185:38100/" && pass "Approval packet includes Standalone WebUI HEAD check" || fail "Approval packet missing Standalone WebUI HEAD check"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "systemctl --user stop construction-legalops-standalone-webui.service" && pass "Approval packet includes Standalone WebUI stop command" || fail "Approval packet missing Standalone WebUI stop command"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "http://192.168.0.185:38100/healthz" && pass "Evidence matrix includes Standalone WebUI health URL" || fail "Evidence matrix missing Standalone WebUI health URL"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "curl -fsSI http://192.168.0.185:38100/" && pass "Evidence matrix includes Standalone WebUI HEAD check" || fail "Evidence matrix missing Standalone WebUI HEAD check"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "http://192.168.0.185:38100/standalone-source" && pass "Evidence matrix includes Standalone WebUI source endpoint" || fail "Evidence matrix missing Standalone WebUI source endpoint"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "construction-legalops-standalone-webui.service" && pass "Evidence matrix includes Standalone WebUI systemd unit" || fail "Evidence matrix missing Standalone WebUI systemd unit"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "systemctl --user stop construction-legalops-standalone-webui.service" && pass "Evidence matrix includes Standalone WebUI stop command" || fail "Evidence matrix missing Standalone WebUI stop command"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "docs/Construction-LegalOps-DX (Standalone).html" && pass "Evidence matrix includes Standalone WebUI source HTML" || fail "Evidence matrix missing Standalone WebUI source HTML"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "legalops.mirai-dx-platform.com" && pass "Final report includes Cloudflare legalops hostname" || fail "Final report missing Cloudflare hostname"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "Cloudflare Access 302" && pass "Final report includes Cloudflare Access stop-line proof" || fail "Final report missing Cloudflare Access stop-line proof"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "Cloudflare Tunnel / Access application 作成" && pass "Final report includes Cloudflare Tunnel/Access stop line" || fail "Final report missing Cloudflare Tunnel/Access stop line"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "Cloudflare / Neon secret / token / connection string 投入" && pass "Final report includes Cloudflare/Neon secret stop line" || fail "Final report missing Cloudflare/Neon secret stop line"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "Cloudflare 起因" && pass "Final report includes Cloudflare rollback row" || fail "Final report missing Cloudflare rollback row"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "Tunnel connector 停止" && pass "Final report includes Tunnel connector rollback" || fail "Final report missing Tunnel connector rollback"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "本番 release / deploy" && pass "Final report forbids unapproved production release/deploy" || fail "Final report missing release/deploy stop line"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "Git push / PR merge / release tag" && pass "Final report forbids unapproved git push/merge/tag" || fail "Final report missing git stop line"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "本番 release / deploy" && pass "Evidence matrix includes production release/deploy stop line" || fail "Evidence matrix missing release/deploy stop line"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "Cloudflare Access 302" && pass "Evidence matrix records Cloudflare Access challenge" || fail "Evidence matrix missing Cloudflare Access challenge"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "Cloudflare Tunnel / Access application 作成" && pass "Evidence matrix includes Cloudflare Tunnel/Access stop line" || fail "Evidence matrix missing Cloudflare Tunnel/Access stop line"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "Cloudflare / Neon secret / token / connection string 投入" && pass "Evidence matrix includes Cloudflare/Neon secret stop line" || fail "Evidence matrix missing Cloudflare/Neon secret stop line"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "CSP enforce 切替" && pass "Evidence matrix includes CSP enforce stop line" || fail "Evidence matrix missing CSP enforce stop line"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "Git push / PR merge / release tag" && pass "Evidence matrix includes git stop line" || fail "Evidence matrix missing git stop line"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "SharePoint Graph real mode" && pass "Evidence matrix includes SharePoint Graph real mode" || fail "Evidence matrix missing SharePoint Graph real mode"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "Notification real mode" && pass "Evidence matrix includes Notification real mode" || fail "Evidence matrix missing Notification real mode"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "Contract submit" && pass "Evidence matrix includes contract submit evidence" || fail "Evidence matrix missing contract submit evidence"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "Contract subresources" && pass "Evidence matrix includes contract subresource evidence" || fail "Evidence matrix missing contract subresource evidence"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "Compliance run" && pass "Evidence matrix includes compliance run evidence" || fail "Evidence matrix missing compliance run evidence"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "ローカル作業ツリー" && pass "Evidence matrix records local workspace state" || fail "Evidence matrix missing local workspace state"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "PR #59 で正本化" && pass "Evidence matrix records PR #59 canonicalization" || fail "Evidence matrix missing PR #59 canonicalization"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "Local workspace" && pass "Approval packet records local workspace state" || fail "Approval packet missing local workspace state"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "PR #59 で正本化" && pass "Approval packet records PR #59 canonicalization" || fail "Approval packet missing PR #59 canonicalization"
contains "docs/HANDOVER.md" "ローカル作業ツリー" && pass "HANDOVER records local workspace state" || fail "HANDOVER missing local workspace state"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "Access self-hosted application を作成" && pass "Approval packet requires Cloudflare Access before DNS" || fail "Approval packet missing Cloudflare Access creation step"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "Cloudflare Tunnel を作成" && pass "Approval packet requires Cloudflare Tunnel creation" || fail "Approval packet missing Cloudflare Tunnel creation step"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "CLOUDFLARE_TUNNEL_CREDENTIALS_FILE" && pass "Approval packet includes cloudflared credentials-file human gate" || fail "Approval packet missing cloudflared credentials-file human gate"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "Cloudflare Access 302" && pass "Approval packet records Cloudflare Access challenge" || fail "Approval packet missing Cloudflare Access challenge"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "本番 deploy を自動実行しない" && pass "Approval packet forbids automatic production deploy" || fail "Approval packet missing automatic deploy prohibition"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "公開 DNS を自動変更しない" && pass "Approval packet forbids automatic public DNS changes" || fail "Approval packet missing public DNS prohibition"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "secret / token / 接続文字列を README / Issue / log に出さない" && pass "Approval packet forbids exposing secrets in docs/issues/logs" || fail "Approval packet missing secret exposure prohibition"
contains "docs/CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK.md" "Access を DNS 公開前に作成" && pass "Cloudflare runbook requires Access before DNS" || fail "Cloudflare runbook missing Access-before-DNS rule"
contains "docs/CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK.md" "Access login 302" && pass "Cloudflare runbook records Access challenge evidence" || fail "Cloudflare runbook missing Access challenge evidence"
contains "docs/CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK.md" "${CURRENT_MARKER}" && pass "Cloudflare runbook is synced to ${CURRENT_MARKER}" || fail "Cloudflare runbook missing ${CURRENT_MARKER} marker"
contains "docs/CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK.md" "親ドメイン \`mirai-dx-platform.com\` は取得済み" && pass "Cloudflare runbook records acquired parent domain" || fail "Cloudflare runbook missing acquired parent domain"
contains "docs/CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK.md" "\`legalops\` は新規作成対象" && pass "Cloudflare runbook records legalops as a new subdomain" || fail "Cloudflare runbook missing legalops new-subdomain status"
contains "docs/CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK.md" "CNAME legalops -> <TUNNEL_ID>.cfargotunnel.com" && pass "Cloudflare runbook documents legalops CNAME target" || fail "Cloudflare runbook missing legalops CNAME target"
contains "docs/CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK.md" "DNS レコードを Tunnel より先に残す" && pass "Cloudflare runbook includes DNS/Tunnel rollback warning" || fail "Cloudflare runbook missing DNS/Tunnel rollback warning"
contains "docs/CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK.md" "DNS レコードと Tunnel は独立" && pass "Cloudflare runbook documents DNS/Tunnel independence" || fail "Cloudflare runbook missing DNS/Tunnel independence"
contains "docs/CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK.md" "1016" && pass "Cloudflare runbook documents 1016 risk" || fail "Cloudflare runbook missing 1016 risk"
contains "docs/CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK.md" "apply_cloudflare_legalops_after_approval.sh" && pass "Cloudflare runbook documents approval-gated apply helper" || fail "Cloudflare runbook missing approval-gated apply helper"
contains "scripts/apply_cloudflare_legalops_after_approval.sh" "APPROVE_LEGALOPS_CLOUDFLARE" && pass "Cloudflare apply helper requires approval phrase" || fail "Cloudflare apply helper missing approval phrase"
contains "scripts/apply_cloudflare_legalops_after_approval.sh" 'EXECUTE="${EXECUTE:-0}"' && pass "Cloudflare apply helper defaults to dry-run" || fail "Cloudflare apply helper does not default to dry-run"
contains "scripts/apply_cloudflare_legalops_after_approval.sh" 'LEGALOPS_HOSTNAME="${LEGALOPS_HOSTNAME:-legalops.mirai-dx-platform.com}"' && pass "Cloudflare apply helper avoids shell HOSTNAME" || fail "Cloudflare apply helper may inherit shell HOSTNAME"
contains "scripts/apply_cloudflare_legalops_after_approval.sh" "resolve_tunnel_uuid" && pass "Cloudflare apply helper resolves tunnel names to UUIDs" || fail "Cloudflare apply helper missing tunnel UUID resolution"
contains "scripts/apply_cloudflare_legalops_after_approval.sh" "Cloudflare API CNAME post-check mismatch" && pass "Cloudflare apply helper verifies post-route CNAME through API" || fail "Cloudflare apply helper missing API CNAME verification"
contains "scripts/apply_cloudflare_legalops_after_approval.sh" "CLOUDFLARE_API_TOKEN is required" && pass "Cloudflare apply helper requires API token for proxied CNAME validation" || fail "Cloudflare apply helper missing API-token post-check requirement"
contains "scripts/apply_cloudflare_legalops_after_approval.sh" "Cloudflare-Access" && pass "Cloudflare apply helper verifies Access challenge after route" || fail "Cloudflare apply helper missing Access challenge post-check"
if grep -Fq 'cloudflared tunnel route dns "${TUNNEL_ID_OR_NAME}"' "scripts/apply_cloudflare_legalops_after_approval.sh"; then
  fail "Cloudflare apply helper still routes DNS with ambiguous tunnel name input"
else
  pass "Cloudflare apply helper avoids ambiguous tunnel name route input"
fi
contains "scripts/verify_cloudflare_legalops.sh" "Apply helper dry-run resolves tunnel names before route dns" && pass "Cloudflare preflight executes helper UUID dry-run proof" || fail "Cloudflare preflight missing helper UUID dry-run proof"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "Cloudflare edge / Access challenge" && pass "Evidence matrix records current Cloudflare Access evidence" || fail "Evidence matrix missing current Cloudflare Access evidence"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "Cloudflare edge / Access challenge" && pass "Approval packet records current Cloudflare Access evidence" || fail "Approval packet missing current Cloudflare Access evidence"
contains "scripts/verify_cloudflare_legalops.sh" "Runbook documents DNS/Tunnel independence" && pass "Cloudflare preflight validates DNS/Tunnel independence docs" || fail "Cloudflare preflight missing DNS/Tunnel independence validation"
contains "scripts/verify_cloudflare_legalops.sh" "Runbook documents Cloudflare 1016 rollback risk" && pass "Cloudflare preflight validates 1016 rollback risk docs" || fail "Cloudflare preflight missing 1016 rollback risk validation"
contains "scripts/pre_deploy_check.sh" "./scripts/verify_release_docs.sh" && pass "Pre-deploy gate invokes release documentation preflight" || fail "Pre-deploy gate does not invoke release documentation preflight"
contains "scripts/pre_deploy_check.sh" "release documentation preflight" && pass "Pre-deploy gate reports release documentation preflight" || fail "Pre-deploy gate missing release documentation preflight label"
contains "scripts/pre_deploy_check.sh" "./scripts/verify_goal_completion_evidence.sh" && pass "Pre-deploy gate invokes goal completion evidence preflight" || fail "Pre-deploy gate missing goal completion evidence preflight"
contains "scripts/pre_deploy_check.sh" "goal completion evidence preflight" && pass "Pre-deploy gate reports goal completion evidence preflight" || fail "Pre-deploy gate missing goal completion evidence label"
contains "scripts/verify_goal_completion_evidence.sh" "Goal criterion covered: lint/type/test/build" && pass "Goal evidence preflight validates lint/type/test/build criterion" || fail "Goal evidence preflight missing lint/type/test/build criterion validation"
contains "scripts/pre_deploy_check.sh" "./scripts/verify_review_evidence.sh" && pass "Pre-deploy gate invokes review evidence preflight" || fail "Pre-deploy gate missing review evidence preflight"
contains "scripts/pre_deploy_check.sh" "review evidence preflight" && pass "Pre-deploy gate reports review evidence preflight" || fail "Pre-deploy gate missing review evidence label"
contains "scripts/verify_review_evidence.sh" "Final report avoids unsupported Critical/High zero claim" && pass "Review evidence preflight validates Critical/High limitation" || fail "Review evidence preflight missing Critical/High limitation validation"
contains "scripts/pre_deploy_check.sh" "./scripts/verify_dependency_audit_evidence.sh" && pass "Pre-deploy gate invokes dependency audit evidence preflight" || fail "Pre-deploy gate missing dependency audit evidence preflight"
contains "scripts/pre_deploy_check.sh" "dependency audit evidence preflight" && pass "Pre-deploy gate reports dependency audit evidence preflight" || fail "Pre-deploy gate missing dependency audit evidence label"
contains "scripts/verify_dependency_audit_evidence.sh" "npm audit high vulnerabilities are 0" && pass "Dependency audit evidence preflight validates npm high result" || fail "Dependency audit evidence preflight missing npm high validation"
contains "scripts/verify_dependency_audit_evidence.sh" "strict project-scoped pip-audit" && pass "Dependency audit evidence preflight validates pip-audit configuration" || fail "Dependency audit evidence preflight missing pip-audit validation"
contains "scripts/pre_deploy_check.sh" "monitoring config preflight" && pass "Pre-deploy gate invokes monitoring config preflight" || fail "Pre-deploy gate missing monitoring config preflight"
contains "scripts/verify_monitoring_config.sh" "Prometheus uses DNS service discovery for backend" && pass "Monitoring preflight validates backend DNS discovery" || fail "Monitoring preflight missing backend DNS discovery validation"
contains "scripts/verify_monitoring_config.sh" "Monitoring YAML/JSON files parse" && pass "Monitoring preflight validates config syntax" || fail "Monitoring preflight missing syntax validation"
contains "infra/monitoring/prometheus.yml" "dns_sd_configs:" && pass "Prometheus config uses dns_sd_configs" || fail "Prometheus config missing dns_sd_configs"
contains "docs/MONITORING.md" "Docker DNS service discovery" && pass "Monitoring docs record Docker DNS discovery" || fail "Monitoring docs missing Docker DNS discovery"
contains "scripts/pre_deploy_check.sh" "backup/restore evidence preflight" && pass "Pre-deploy gate invokes backup/restore evidence preflight" || fail "Pre-deploy gate missing backup/restore evidence preflight"
contains "scripts/verify_backup_restore_docs.sh" "Backup guide documents pg_dump" && pass "Backup/restore preflight validates pg_dump documentation" || fail "Backup/restore preflight missing pg_dump validation"
contains "scripts/verify_backup_restore_docs.sh" "Backup guide documents pg_restore" && pass "Backup/restore preflight validates pg_restore documentation" || fail "Backup/restore preflight missing pg_restore validation"
contains "scripts/verify_backup_restore_docs.sh" "Release docs do not claim PITR is fully complete" && pass "Backup/restore preflight guards PITR completion claims" || fail "Backup/restore preflight missing PITR completion guard"
contains "docs/BACKUP_RESTORE.md" "本番データ PITR 実演は未実施" && pass "Backup guide records PITR drill as incomplete" || fail "Backup guide missing PITR incomplete statement"
contains "docs/BACKUP_RESTORE.md" "本番 backup / WAL / Neon 承認後" && pass "Backup guide keeps PITR behind approval" || fail "Backup guide missing PITR approval boundary"
contains "scripts/pre_deploy_check.sh" "local workspace state preflight" && pass "Pre-deploy gate invokes local workspace state preflight" || fail "Pre-deploy gate missing local workspace state preflight"
# The workspace preflight is state-agnostic by design: it asserts timeless
# fail-closed conditions and only DISCLOSES point-in-time facts. Asserting a
# specific branch / dirty-file snapshot here would break the gate the moment
# that work is committed.
contains "scripts/verify_local_workspace_state.sh" "Timeless fail-closed checks" && pass "Local workspace preflight is state-agnostic (timeless checks)" || fail "Local workspace preflight missing timeless-check design"
contains "scripts/verify_local_workspace_state.sh" "No secret-bearing file" && pass "Local workspace preflight validates secret-file absence" || fail "Local workspace preflight missing secret-file validation"
contains "scripts/verify_local_workspace_state.sh" "executable bit" && pass "Local workspace preflight validates script executable bits" || fail "Local workspace preflight missing executable-bit validation"
contains "scripts/verify_local_workspace_state.sh" "origin/main resolvable" && pass "Local workspace preflight validates origin/main resolvability" || fail "Local workspace preflight missing origin/main validation"
contains "scripts/verify_local_workspace_state.sh" "Workspace disclosure (informational)" && pass "Local workspace preflight discloses workspace state" || fail "Local workspace preflight missing workspace disclosure"
contains "scripts/verify_local_workspace_state.sh" "scripts/verify_github_release_gate.sh" && pass "Local workspace preflight validates verifier presence" || fail "Local workspace preflight missing verifier-presence validation"
contains "backend/app/services/sharepoint_service.py" "grant_type\": \"client_credentials\"" && pass "SharePoint service uses client-credentials Graph token flow" || fail "SharePoint service missing client-credentials Graph token flow"
contains "backend/app/services/sharepoint_service.py" "Graph upload response missing item id" && pass "SharePoint service fails closed on missing Graph item id" || fail "SharePoint service missing Graph upload fail-closed guard"
contains "backend/tests/unit/test_sharepoint_service.py" "test_real_upload_uses_graph_drive_content_endpoint" && pass "SharePoint real upload contract test exists" || fail "SharePoint real upload contract test missing"
contains "backend/tests/unit/test_sharepoint_service.py" "test_real_get_url_returns_graph_web_url" && pass "SharePoint real get_url contract test exists" || fail "SharePoint real get_url contract test missing"
contains "backend/app/services/notification_service.py" "EXCHANGE_SENDER_UPN is required for real email notifications" && pass "Notification service fails closed without Exchange sender" || fail "Notification service missing Exchange sender fail-closed guard"
contains "backend/app/services/notification_service.py" "TEAMS_WEBHOOK_URL is required for real Teams notifications" && pass "Notification service fails closed without Teams webhook" || fail "Notification service missing Teams webhook fail-closed guard"
contains "backend/app/services/notification_service.py" "DESKNETS_WEBHOOK_URL is required for real DeskNet's notifications" && pass "Notification service fails closed without DeskNet's webhook" || fail "Notification service missing DeskNet's webhook fail-closed guard"
contains "backend/tests/unit/test_notification_service.py" "test_send_email_real_mode_calls_graph_send_mail" && pass "Notification real email contract test exists" || fail "Notification real email contract test missing"
contains "backend/tests/unit/test_notification_service.py" "test_send_teams_card_real_mode_posts_adaptive_card" && pass "Notification real Teams contract test exists" || fail "Notification real Teams contract test missing"
contains "backend/tests/unit/test_notification_service.py" "test_send_desknets_real_mode_posts_webhook_payload" && pass "Notification real DeskNet's contract test exists" || fail "Notification real DeskNet's contract test missing"
contains "backend/app/services/contract_service.py" "async def submit_for_review" && pass "Contract service implements submit_for_review" || fail "Contract service missing submit_for_review"
contains "backend/app/services/contract_service.py" "ContractStatus.IN_REVIEW.value" && pass "Contract submit transitions to in_review" || fail "Contract submit missing in_review transition"
contains "backend/tests/unit/test_contract_service.py" "test_moves_draft_contract_to_in_review" && pass "Contract submit unit test exists" || fail "Contract submit unit test missing"
contains "backend/tests/integration/test_contracts_crud.py" "test_submit_contract_moves_draft_to_review" && pass "Contract submit integration test exists" || fail "Contract submit integration test missing"
contains "backend/app/services/contract_service.py" "async def list_versions" && pass "Contract service implements list_versions" || fail "Contract service missing list_versions"
contains "backend/app/services/contract_service.py" "async def list_clauses" && pass "Contract service implements list_clauses" || fail "Contract service missing list_clauses"
contains "backend/tests/integration/test_contracts_crud.py" "test_contract_versions_returns_current_snapshot" && pass "Contract versions integration test exists" || fail "Contract versions integration test missing"
contains "backend/tests/integration/test_contracts_crud.py" "test_contract_clauses_returns_db_rows" && pass "Contract clauses integration test exists" || fail "Contract clauses integration test missing"
contains "backend/app/services/compliance_service.py" "status\": \"done\"" && pass "Compliance run returns completed job status" || fail "Compliance run does not return completed job status"
contains "backend/app/services/compliance_service.py" "callers do not receive a false queued state" && pass "Compliance service documents false-queued guard" || fail "Compliance service missing false-queued guard"
contains "backend/tests/unit/test_compliance_service.py" "test_returns_completed_job_handle_when_contract_found" && pass "Compliance run unit test covers completed job handle" || fail "Compliance run unit test missing completed job handle"
contains "backend/tests/integration/test_risks_compliance.py" "completed job handle" && pass "Compliance run integration test covers completed job handle" || fail "Compliance run integration test missing completed job handle"
contains "frontend/lib/api/endpoints.ts" "/compliance/checks/\${contractId}/run" && pass "Frontend compliance run endpoint matches backend route" || fail "Frontend compliance run endpoint mismatch"
contains "frontend/lib/api/endpoints.ts" "z.array(complianceChecklistSchema)" && pass "Frontend compliance checklists expect backend list response" || fail "Frontend compliance checklists still expect paginated response"
contains "frontend/lib/api/schemas.ts" "job_id: z.string().min(1)" && pass "Frontend compliance run schema matches backend job_id" || fail "Frontend compliance run schema missing job_id"
contains "frontend/lib/api/schemas.ts" "\"done\"" && pass "Frontend compliance run schema accepts done status" || fail "Frontend compliance run schema missing done status"
contains "frontend/app/(authenticated)/compliance/page.tsx" "const checklists = await complianceApi.checklists" && pass "Compliance page consumes checklist list response" || fail "Compliance page not aligned with checklist list response"
contains "frontend/lib/compliance/status.ts" '"not_run"' && pass "Compliance status mapper supports neutral not_run state" || fail "Compliance status mapper missing neutral not_run state"
contains "frontend/lib/compliance/status.ts" 'return "not_run"' && pass "Compliance status mapper keeps missing severity neutral" || fail "Compliance status mapper maps missing severity to warning"
contains "frontend/components/compliance/compliance-findings-table.tsx" "未実施" && pass "Compliance findings table labels not_run as 未実施" || fail "Compliance findings table missing 未実施 label"
contains "frontend/components/compliance/compliance-findings-table.tsx" "CircleDashed" && pass "Compliance findings table uses neutral icon for not_run" || fail "Compliance findings table missing neutral not_run icon"
contains "frontend/lib/compliance/__tests__/status.test.ts" "missing severities to not_run" && pass "Compliance status mapper unit test covers missing severity" || fail "Compliance status mapper test missing null severity case"
contains "backend/app/api/v1/users.py" "action=\"user.sync\"" && pass "User sync route writes user.sync audit action" || fail "User sync route missing user.sync audit action"
contains "backend/app/api/v1/users.py" "\"external_write\": False" && pass "User sync audit payload records no external write" || fail "User sync audit payload missing external_write false"
contains "backend/app/services/user_service.py" "never contacts" && pass "User sync service documents no external Graph call" || fail "User sync service missing no-external-Graph guard"
contains "backend/tests/integration/test_audit_logs.py" "test_user_sync_returns_queued_job_and_audit_log" && pass "User sync integration test covers audit log" || fail "User sync integration test missing audit log coverage"
contains "backend/tests/unit/test_user_service.py" "auditable queued job" && pass "User sync unit test covers auditable queued job" || fail "User sync unit test missing auditable queued job"
if rg -n "get_user_by_id|get_user_by_sub|create_or_update_user" backend/app --glob '!services/user_service.py' >/tmp/legalops-user-legacy-refs.txt; then
  fail "Production app references legacy user_service 501 helper names"
else
  pass "Production app does not reference legacy user_service 501 helper names"
fi
contains "frontend/lib/api/schemas.ts" "userSyncJobSchema" && pass "Frontend user sync schema exists" || fail "Frontend user sync schema missing"
contains "frontend/lib/api/endpoints.ts" "postParsed(apiResponse(userSyncJobSchema), \"/users/sync\")" && pass "Frontend users sync parses backend job response" || fail "Frontend users sync does not parse backend job response"
contains "frontend/hooks/use-users.ts" "UserSyncJob" && pass "Frontend users hook exposes UserSyncJob mutation result" || fail "Frontend users hook missing UserSyncJob result"
contains "backend/app/services/file_parser.py" "Image-only PDFs fail closed" && pass "File parser documents image-only PDF fail-closed behavior" || fail "File parser missing image-only PDF fail-closed documentation"
contains "backend/app/services/file_parser.py" "placeholder OCR text must never flow" && pass "File parser rejects placeholder OCR legal-review evidence" || fail "File parser missing placeholder OCR guard"
contains "backend/app/services/file_parser.py" "OCR backend is not configured" && pass "File parser raises when OCR backend is unavailable" || fail "File parser missing OCR unavailable error"
contains "backend/tests/unit/test_file_parser.py" "test_parse_pdf_image_only_fails_closed_without_ocr_backend" && pass "File parser unit test covers image-only PDF fail-closed" || fail "File parser missing image-only PDF fail-closed test"
contains "backend/tests/unit/test_file_parser.py" "must not return placeholder OCR text" && pass "File parser test documents placeholder OCR prohibition" || fail "File parser tests missing placeholder OCR prohibition"
if grep -Fq "sharepoint-stub://items" backend/app/services/upload_service.py; then
  fail "Upload download URL falls back to sharepoint-stub"
else
  pass "Upload download URL avoids sharepoint-stub fallback"
fi
contains "backend/app/api/v1/uploads.py" "sharepoint url unavailable" && pass "Upload download route fails closed when SharePoint URL is unavailable" || fail "Upload download route missing SharePoint URL fail-closed response"
contains "backend/tests/integration/test_uploads_flow.py" "sharepoint url unavailable" && pass "Upload integration test covers SharePoint URL fail-closed response" || fail "Upload integration test missing SharePoint URL fail-closed coverage"
contains "backend/app/services/upload_service.py" "upload_url=None" && pass "Upload init avoids pseudo external upload URL" || fail "Upload init still exposes a pseudo external upload URL"
contains "backend/tests/integration/test_uploads_flow.py" 'init.json()["upload_url"] is None' && pass "Upload integration test covers null upload_url" || fail "Upload integration test missing null upload_url coverage"
contains "docs/api_design.md" '"upload_url": null' && pass "API design documents null upload_url before external route approval" || fail "API design still documents a pseudo upload URL"
contains "backend/app/services/sso_service.py" "SSO_MODE=stub is disabled when APP_ENV=production" && pass "SSO production stub guard fails closed unless Cloudflare Access boundary is explicit" || fail "SSO production stub guard missing"
contains "backend/app/services/sso_service.py" "EDGE_AUTH_BOUNDARY=cloudflare-access" && pass "SSO production stub exception requires explicit Cloudflare Access boundary" || fail "SSO Cloudflare Access boundary exception missing"
contains "backend/app/services/cloudflare_access.py" "Cf-Access-Jwt-Assertion" && pass "Cloudflare Access verifier documents origin JWT header" || fail "Cloudflare Access verifier missing origin JWT header"
contains "backend/app/services/cloudflare_access.py" "CLOUDFLARE_ACCESS_AUD" && pass "Cloudflare Access verifier requires AUD configuration" || fail "Cloudflare Access verifier missing AUD configuration"
contains "backend/app/deps.py" "Cf-Access-Authenticated-User-Email" && pass "Auth dependency consumes Cloudflare Access email header" || fail "Auth dependency missing Access email header"
contains "backend/app/deps.py" "Cloudflare Access email header does not match JWT" && pass "Auth dependency rejects Access email spoofing" || fail "Auth dependency missing Access email mismatch guard"
contains "backend/tests/unit/test_cloudflare_access.py" "test_verify_access_jwt_validates_signature_issuer_and_audience" && pass "Cloudflare Access unit test covers signature/issuer/audience" || fail "Cloudflare Access unit test missing signature coverage"
contains "backend/tests/integration/test_cloudflare_access_auth.py" "test_access_only_mode_derives_real_email_and_jit_provisions_user" && pass "Cloudflare Access integration test covers real email JIT path" || fail "Cloudflare Access integration test missing real email JIT coverage"
contains "infra/docker/docker-compose.prod.yml" "CLOUDFLARE_ACCESS_ISSUER" && pass "Production compose requires Cloudflare Access issuer" || fail "Production compose missing Cloudflare Access issuer"
contains "infra/docker/docker-compose.prod.yml" "CLOUDFLARE_ACCESS_AUD" && pass "Production compose requires Cloudflare Access AUD" || fail "Production compose missing Cloudflare Access AUD"
contains "scripts/pre_deploy_check.sh" "CLOUDFLARE_ACCESS_AUD=dummy-access-aud" && pass "Pre-deploy Cloudflare overlay config includes Access AUD placeholder" || fail "Pre-deploy overlay config missing Access AUD placeholder"
contains "scripts/pre_deploy_check.sh" "CLOUDFLARE_TUNNEL_CREDENTIALS_FILE=" && pass "Pre-deploy Cloudflare overlay config uses credentials file placeholder" || fail "Pre-deploy overlay config missing credentials file placeholder"
nginx_auth_route_count="$(grep -Fc 'location ~* ^/api/auth(/|$)' infra/nginx/default.conf)"
if [ "${nginx_auth_route_count}" -eq 2 ]; then
  pass "Nginx routes NextAuth /api/auth only in both HTTP and HTTPS server blocks"
else
  fail "Nginx NextAuth /api/auth route count is ${nginx_auth_route_count}; expected 2"
fi
if grep -Fq '^/api/(auth|login|token)' infra/nginx/default.conf; then
  fail "Nginx auth route still captures /api/login or /api/token"
else
  pass "Nginx auth route does not capture /api/login or /api/token"
fi
contains "infra/nginx/default.conf" "Backend auth APIs" && pass "Nginx documents backend auth APIs stay on backend route" || fail "Nginx missing backend auth API route note"
contains "backend/app/services/sharepoint_service.py" "SHAREPOINT_MODE=stub is disabled when APP_ENV=production" && pass "SharePoint production stub guard fails closed" || fail "SharePoint production stub guard missing"
contains "backend/app/services/ai_review.py" "AI_REVIEW_MODE=stub is disabled when APP_ENV=production" && pass "AI review production stub guard fails closed" || fail "AI review production stub guard missing"
contains "backend/app/services/ai_review.py" "CLAUDE_API_KEY must be configured when APP_ENV=production" && pass "AI review production sentinel key guard fails closed" || fail "AI review production sentinel key guard missing"
contains "backend/app/services/notification_service.py" "NOTIFY_MODE=stub is disabled when APP_ENV=production" && pass "Notification production stub guard fails closed" || fail "Notification production stub guard missing"
contains "backend/tests/unit/test_production_stub_guards.py" "test_sso_stub_mode_is_disabled_in_production" && pass "Production stub guard tests cover SSO rejection" || fail "Production stub guard tests missing SSO rejection"
contains "backend/tests/unit/test_production_stub_guards.py" "test_sso_stub_mode_allowed_behind_cloudflare_access_boundary" && pass "Production stub guard tests cover Cloudflare Access boundary exception" || fail "Production stub guard tests missing Cloudflare Access boundary exception"
contains "backend/tests/unit/test_production_stub_guards.py" "test_sharepoint_stub_mode_is_disabled_in_production" && pass "Production stub guard tests cover SharePoint rejection" || fail "Production stub guard tests missing SharePoint rejection"
contains "backend/tests/unit/test_production_stub_guards.py" "test_ai_review_requires_real_key_in_production" && pass "Production stub guard tests cover Claude sentinel key rejection" || fail "Production stub guard tests missing Claude sentinel key rejection"
contains "backend/tests/unit/test_production_stub_guards.py" "test_notification_stub_mode_is_disabled_in_production" && pass "Production stub guard tests cover notification rejection" || fail "Production stub guard tests missing notification rejection"
contains "backend/app/api/v1/uploads.py" "\"external_url_resolved\": True" && pass "Upload download audit records external URL resolution" || fail "Upload download audit missing external URL resolution flag"
contains "backend/app/api/v1/uploads.py" "\"external_write\": False" && pass "Upload download audit records no external write" || fail "Upload download audit missing external_write false"
contains "backend/tests/integration/test_uploads_flow.py" "external_url_resolved" && pass "Upload integration test covers download audit payload" || fail "Upload integration test missing download audit payload coverage"
contains "frontend/components/templates/create-template-button.tsx" "useCreateTemplate" && pass "Template creation UI uses create mutation hook" || fail "Template creation UI missing create mutation hook"
contains "frontend/components/templates/create-template-button.tsx" "templatesApi" && fail "Template creation UI bypasses hook with direct API call" || pass "Template creation UI avoids direct API bypass"
contains "frontend/components/templates/create-template-button.tsx" "DialogTrigger asChild" && pass "Template creation UI opens a dialog from the page button" || fail "Template creation UI missing dialog trigger"
contains "frontend/components/templates/create-template-button.tsx" "router.refresh()" && pass "Template creation UI refreshes the server-rendered list" || fail "Template creation UI missing list refresh"
UNIMPL_SCAN="$(mktemp)"
trap 'rm -f "${UNIMPL_SCAN}"' EXIT
if grep -RIn --include='*.ts' --include='*.tsx' --include='*.py' --include='*.md' "ひな形作成機能は実装予定です" frontend backend docs README.md >"${UNIMPL_SCAN}"; then
  cat "${UNIMPL_SCAN}"
  fail "Template creation unimplemented alert is absent"
else
  pass "Template creation unimplemented alert is absent"
fi
contains "scripts/pre_deploy_check.sh" "Standalone WebUI contract tests" && pass "Pre-deploy gate reports Standalone WebUI contract tests" || fail "Pre-deploy gate missing Standalone WebUI contract tests"
contains "scripts/pre_deploy_check.sh" "tests/test_standalone_webui.py" && pass "Pre-deploy gate invokes Standalone WebUI contract tests" || fail "Pre-deploy gate missing Standalone WebUI contract test path"
contains "scripts/pre_deploy_check.sh" "Standalone WebUI server syntax" && pass "Pre-deploy gate reports Standalone WebUI server syntax" || fail "Pre-deploy gate missing Standalone WebUI server syntax"
contains "scripts/pre_deploy_check.sh" "scripts/serve_standalone_webui.py" && pass "Pre-deploy gate checks Standalone WebUI server file" || fail "Pre-deploy gate missing Standalone WebUI server file path"
contains "scripts/pre_deploy_check.sh" "Standalone WebUI systemd installer syntax" && pass "Pre-deploy gate reports Standalone WebUI systemd installer syntax" || fail "Pre-deploy gate missing Standalone WebUI systemd installer syntax"
contains "scripts/pre_deploy_check.sh" "scripts/install_standalone_webui_systemd.sh" && pass "Pre-deploy gate checks Standalone WebUI systemd installer file" || fail "Pre-deploy gate missing Standalone WebUI systemd installer path"
contains "scripts/pre_deploy_check.sh" "./scripts/verify_standalone_webui_runtime.sh" && pass "Pre-deploy gate invokes Standalone WebUI runtime preflight" || fail "Pre-deploy gate missing Standalone WebUI runtime preflight"
contains "scripts/pre_deploy_check.sh" "Standalone WebUI runtime preflight" && pass "Pre-deploy gate reports Standalone WebUI runtime preflight" || fail "Pre-deploy gate missing Standalone WebUI runtime label"
contains "scripts/verify_standalone_webui_runtime.sh" "systemctl --user is-active" && pass "Standalone WebUI runtime preflight validates systemd active state" || fail "Standalone WebUI runtime preflight missing systemd validation"
contains "scripts/verify_standalone_webui_runtime.sh" "systemctl --user is-enabled" && pass "Standalone WebUI runtime preflight validates systemd enabled state" || fail "Standalone WebUI runtime preflight missing systemd enabled validation"
contains "scripts/verify_standalone_webui_runtime.sh" "Standalone WebUI status JSON is valid" && pass "Standalone WebUI runtime preflight validates status JSON" || fail "Standalone WebUI runtime preflight missing status JSON validation"
contains "scripts/verify_standalone_webui_runtime.sh" "Standalone WebUI status port is within auto allocation range" && pass "Standalone WebUI runtime preflight validates auto port range" || fail "Standalone WebUI runtime preflight missing auto port range validation"
contains "scripts/verify_standalone_webui_runtime.sh" "Standalone WebUI status host is assigned to this Linux host" && pass "Standalone WebUI runtime preflight validates selected host address" || fail "Standalone WebUI runtime preflight missing selected host validation"
contains "scripts/verify_standalone_webui_runtime.sh" "Standalone WebUI process is listening on status host and port" && pass "Standalone WebUI runtime preflight validates listening socket" || fail "Standalone WebUI runtime preflight missing listening socket validation"
contains "scripts/verify_standalone_webui_runtime.sh" "Standalone WebUI systemd unit starts serve_standalone_webui.py" && pass "Standalone WebUI runtime preflight validates systemd ExecStart" || fail "Standalone WebUI runtime preflight missing systemd ExecStart validation"
contains "scripts/verify_standalone_webui_runtime.sh" "Content-Length: \${EXPECTED_SIZE}" && pass "Standalone WebUI runtime preflight validates content length" || fail "Standalone WebUI runtime preflight missing content length validation"
contains "scripts/verify_standalone_webui_runtime.sh" "Standalone WebUI source endpoint matches expected HTML path" && pass "Standalone WebUI runtime preflight validates source endpoint" || fail "Standalone WebUI runtime preflight missing source endpoint validation"
contains "scripts/pre_deploy_check.sh" "./scripts/verify_github_release_gate.sh" && pass "Pre-deploy gate invokes GitHub release gate preflight" || fail "Pre-deploy gate missing GitHub release gate preflight"
contains "scripts/pre_deploy_check.sh" "GitHub release gate preflight" && pass "Pre-deploy gate reports GitHub release gate preflight" || fail "Pre-deploy gate missing GitHub release gate label"
contains "scripts/verify_github_release_gate.sh" "Open P0 issues are exactly" && pass "GitHub release gate validates open Issue set" || fail "GitHub release gate missing open Issue set validation"
contains "scripts/verify_github_release_gate.sh" "PR #62 is merged" && pass "GitHub release gate validates PR #62 merged approval state" || fail "GitHub release gate missing PR #62 merged validation"
contains "scripts/verify_github_release_gate.sh" "PR #66 | merged" && pass "GitHub release gate validates PR #66 merged Project readme state" || fail "GitHub release gate missing PR #66 Project readme validation"
contains "scripts/verify_github_release_gate.sh" "PR #58 is merged" && pass "GitHub release gate validates PR #58 merged state" || fail "GitHub release gate missing PR #58 merged validation"
contains "scripts/verify_github_release_gate.sh" "PR #58 concluded status checks are all success" && pass "GitHub release gate validates PR #58 status checks" || fail "GitHub release gate missing PR #58 status validation"
contains "scripts/verify_github_release_gate.sh" "PR #70 is open for human merge approval" && pass "GitHub release gate validates PR #70 open approval state" || fail "GitHub release gate missing PR #70 open validation"
contains "scripts/verify_github_release_gate.sh" "PR #70 is mergeable" && pass "GitHub release gate validates PR #70 mergeable state" || fail "GitHub release gate missing PR #70 mergeable validation"
contains "scripts/verify_github_release_gate.sh" "PR #70 merge state is CLEAN" && pass "GitHub release gate validates PR #70 clean merge state" || fail "GitHub release gate missing PR #70 clean validation"
contains "scripts/verify_github_release_gate.sh" "PR #70 status checks are all success" && pass "GitHub release gate validates PR #70 status checks" || fail "GitHub release gate missing PR #70 status validation"
contains "scripts/verify_github_release_gate.sh" "Project #\${PROJECT_NUMBER} item #50 carries blocked label" && pass "GitHub release gate validates #50 blocked Project label" || fail "GitHub release gate missing #50 blocked Project label validation"
contains "scripts/verify_github_release_gate.sh" "PR #65 | merged" && pass "GitHub release gate validates PR #65 merged state in Project readme" || fail "GitHub release gate missing PR #65 Project readme validation"
contains "scripts/verify_github_release_gate.sh" "Latest \${REQUIRED_CI_WORKFLOW} run conclusion is success" && pass "GitHub release gate validates latest CI success" || fail "GitHub release gate missing latest CI success validation"
contains "scripts/verify_github_release_gate.sh" "Latest \${REQUIRED_CI_WORKFLOW} run branch is \${REQUIRED_CI_BRANCH}" && pass "GitHub release gate validates latest CI branch" || fail "GitHub release gate missing latest CI branch validation"
contains "scripts/verify_github_release_gate.sh" "Latest \${REQUIRED_CI_WORKFLOW} run is completed" && pass "GitHub release gate validates latest CI completed status" || fail "GitHub release gate missing latest CI completed validation"
contains "scripts/verify_github_release_gate.sh" "Cloudflare legalops preflight | Passed 46 / Failed 0 / Warnings 0" && pass "GitHub release gate validates Project Cloudflare 46/0 evidence" || fail "GitHub release gate missing Project Cloudflare 46/0 validation"
contains "scripts/verify_github_release_gate.sh" "Release docs | Passed 352 / Failed 0" && pass "GitHub release gate validates Project release docs 352/0 evidence" || fail "GitHub release gate missing Project release docs 352/0 validation"
contains "scripts/verify_github_release_gate.sh" "deploy_ready=false" && pass "GitHub release gate validates Project deploy_ready=false evidence" || fail "GitHub release gate missing Project deploy_ready=false validation"
contains "scripts/verify_github_release_gate.sh" "Cloudflare DNS API proxied=true + Access login redirect verified" && pass "GitHub release gate validates Project proxied DNS/Access login evidence" || fail "GitHub release gate missing Project proxied DNS/Access login validation"
contains "scripts/verify_github_release_gate.sh" "LATEST_ISSUE_50_URL" && pass "GitHub release gate validates latest Issue #50 evidence link" || fail "GitHub release gate missing latest Issue #50 link validation"
contains "scripts/verify_github_release_gate.sh" "readme formats latest Issue #50 evidence row" && pass "GitHub release gate validates latest Issue #50 evidence row formatting" || fail "GitHub release gate missing latest Issue #50 evidence row formatting validation"
contains "scripts/verify_github_release_gate.sh" "state.json records latest Issue #50 evidence URL" && pass "GitHub release gate validates state latest Issue #50 evidence URL" || fail "GitHub release gate missing state latest Issue #50 evidence URL validation"
contains "scripts/verify_github_release_gate.sh" "Release docs: Passed 352 / Failed 0" && pass "GitHub release gate validates latest Issue #50 release-doc count" || fail "GitHub release gate missing latest Issue #50 release-doc count validation"
contains "scripts/verify_github_release_gate.sh" "No production deploy or production release executed by this session" && pass "GitHub release gate validates latest Issue #50 production stop-line" || fail "GitHub release gate missing latest Issue #50 production stop-line validation"
contains "scripts/verify_predeploy_warning_classification.sh" "Pre-deploy warning count is 5" && pass "Warning classification validates expected warning count" || fail "Warning classification missing expected warning count validation"
contains "scripts/verify_predeploy_warning_classification.sh" "No unexpected pre-deploy warnings are present" && pass "Warning classification rejects unexpected warnings" || fail "Warning classification missing unexpected warning guard"
contains "scripts/verify_predeploy_warning_classification.sh" "Approval packet explains warning classification" && pass "Warning classification validates approval packet explanation" || fail "Warning classification missing approval packet explanation validation"
contains "scripts/verify_predeploy_warning_classification.sh" "Final stop report explains warning classification" && pass "Warning classification validates final report explanation" || fail "Warning classification missing final report explanation validation"
contains "scripts/verify_release_checklist_pending_items.sh" "All unchecked checklist items are classified as approval/production/post-release gates" && pass "Release checklist classifier rejects unclassified unchecked items" || fail "Release checklist classifier missing unchecked item guard"
contains "scripts/verify_release_checklist_pending_items.sh" "Release checklist records human approval boundary" && pass "Release checklist classifier validates human approval boundary" || fail "Release checklist classifier missing human approval boundary validation"
contains "scripts/verify_release_checklist_pending_items.sh" "Release checklist links production approval packet" && pass "Release checklist classifier validates approval packet link" || fail "Release checklist classifier missing approval packet link validation"
contains "scripts/verify_production_stop_line.sh" "No unapproved GitHub releases" && pass "Production stop-line validates unapproved-release absence" || fail "Production stop-line missing unapproved-release validation"
contains "scripts/verify_production_stop_line.sh" "GitHub deployment count is 0" && pass "Production stop-line validates GitHub deployment absence" || fail "Production stop-line missing GitHub deployment absence validation"
contains "scripts/verify_production_stop_line.sh" "resolves through Cloudflare proxy" && pass "Production stop-line validates Cloudflare proxy resolution" || fail "Production stop-line missing Cloudflare proxy validation"
contains "scripts/verify_production_stop_line.sh" "Cloudflare DNS API record is proxied" && pass "Production stop-line validates proxied DNS through Cloudflare API" || fail "Production stop-line missing proxied DNS API validation"
contains "scripts/verify_production_stop_line.sh" "challenged by Cloudflare Access" && pass "Production stop-line validates Cloudflare Access challenge" || fail "Production stop-line missing Access challenge validation"
contains "scripts/verify_production_stop_line.sh" "\\.cloudflareaccess\\.com/cdn-cgi/access/login/" && pass "Production stop-line validates Access login destination" || fail "Production stop-line missing Access login destination validation"
contains "scripts/verify_production_stop_line.sh" "Project #\${PROJECT_NUMBER} readme records production deploy not executed" && pass "Production stop-line validates Project deploy stop line" || fail "Production stop-line missing Project deploy stop validation"
if grep -Eq 'curl[^\n]*(^|[[:space:]])(--insecure|-[A-Za-z]*k[A-Za-z]*)($|[[:space:]])' scripts/verify_production_stop_line.sh; then
  fail "Production stop-line disables TLS verification with curl insecure options"
else
  pass "Production stop-line keeps normal TLS verification"
fi

if grep -Fq "本チェックリストは Loop 57" docs/RELEASE_CHECKLIST.md; then
  fail "Release checklist still contains stale Loop 57 footer"
else
  pass "Release checklist stale Loop 57 footer absent"
fi

if grep -Fq "Loop 58 時点の CI" docs/RELEASE_CHECKLIST.md; then
  fail "Release checklist still references Loop 58 current evidence"
else
  pass "Release checklist stale Loop 58 current evidence absent"
fi

if grep -Fq "Loop 60 時点" docs/HANDOVER.md; then
  fail "HANDOVER still references Loop 60 as current state"
else
  pass "HANDOVER stale Loop 60 current-state marker absent"
fi

if grep -Fq "Loop 60 以降" docs/HANDOVER.md; then
  fail "HANDOVER still uses stale Loop 60 next-session wording"
else
  pass "HANDOVER stale Loop 60 next-session wording absent"
fi

if grep -Fq "Loop 63 まで同期" docs/RELEASE_EVIDENCE_MATRIX.md; then
  fail "Evidence matrix still claims the release checklist is synced only through Loop 63"
else
  pass "Evidence matrix stale Loop 63 checklist sync wording absent"
fi

if grep -Fq "コメント予定" docs/RELEASE_EVIDENCE_MATRIX.md; then
  fail "Evidence matrix still contains a pending Issue comment marker"
else
  pass "Evidence matrix pending Issue comment marker absent"
fi

echo ""
echo "================================================"
echo "📊 Summary"
echo "================================================"
echo "✅ Passed: ${PASS}"
echo "❌ Failed: ${FAIL}"

if [ "${FAIL}" -gt 0 ]; then
  echo "🚨 Release documentation preflight failed"
  exit 1
fi

echo "✅ Release documentation preflight passed"
exit 0
