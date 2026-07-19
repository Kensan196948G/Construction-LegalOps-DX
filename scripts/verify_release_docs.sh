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
  "docs/Construction-LegalOps-DX (Standalone).html"
  "scripts/verify_goal_completion_evidence.sh"
  "scripts/verify_review_evidence.sh"
  "scripts/verify_dependency_audit_evidence.sh"
  "backend/app/services/sharepoint_service.py"
  "backend/tests/unit/test_sharepoint_service.py"
  "backend/app/services/notification_service.py"
  "backend/tests/unit/test_notification_service.py"
  "backend/app/services/contract_service.py"
  "backend/tests/unit/test_contract_service.py"
  "backend/tests/integration/test_contracts_crud.py"
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
contains "README.md" "CNAME / A は未作成" && pass "README records legalops CNAME/A absence" || fail "README missing legalops CNAME/A absence"
contains "README.md" "http://192.168.0.185:38100/" && pass "README includes Standalone WebUI URL" || fail "README missing Standalone WebUI URL"
contains "README.md" "systemctl --user stop construction-legalops-standalone-webui.service" && pass "README includes Standalone WebUI stop command" || fail "README missing Standalone WebUI stop command"
contains "README.md" "docs/PRODUCTION_APPROVAL_PACKET.md" && pass "README links production approval packet" || fail "README missing production approval packet link"
contains "README.md" "Project #30" && pass "README includes GitHub Project #30 release gate" || fail "README missing GitHub Project #30 release gate"
contains "README.md" "SharePoint Graph real mode" && pass "README records SharePoint Graph real mode" || fail "README missing SharePoint Graph real mode evidence"
contains "README.md" "Notification real mode" && pass "README records Notification real mode" || fail "README missing Notification real mode evidence"
contains "README.md" "Contract submit" && pass "README records contract submit evidence" || fail "README missing contract submit evidence"
contains "README.md" "Contract subresources" && pass "README records contract subresource evidence" || fail "README missing contract subresource evidence"
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
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "DNS CNAME 作成" && pass "Final report includes legalops CNAME stop line" || fail "Final report missing legalops CNAME stop line"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "Cloudflare Tunnel / Access application 作成" && pass "Final report includes Cloudflare Tunnel/Access stop line" || fail "Final report missing Cloudflare Tunnel/Access stop line"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "Cloudflare / Neon secret / token / connection string 投入" && pass "Final report includes Cloudflare/Neon secret stop line" || fail "Final report missing Cloudflare/Neon secret stop line"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "Cloudflare 起因" && pass "Final report includes Cloudflare rollback row" || fail "Final report missing Cloudflare rollback row"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "Tunnel connector 停止" && pass "Final report includes Tunnel connector rollback" || fail "Final report missing Tunnel connector rollback"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "本番 release / deploy" && pass "Final report forbids unapproved production release/deploy" || fail "Final report missing release/deploy stop line"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "Git push / PR merge / release tag" && pass "Final report forbids unapproved git push/merge/tag" || fail "Final report missing git stop line"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "本番 release / deploy" && pass "Evidence matrix includes production release/deploy stop line" || fail "Evidence matrix missing release/deploy stop line"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "CNAME / A は未作成" && pass "Evidence matrix records legalops CNAME/A absence" || fail "Evidence matrix missing legalops CNAME/A absence"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "Cloudflare Tunnel / Access application 作成" && pass "Evidence matrix includes Cloudflare Tunnel/Access stop line" || fail "Evidence matrix missing Cloudflare Tunnel/Access stop line"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "Cloudflare / Neon secret / token / connection string 投入" && pass "Evidence matrix includes Cloudflare/Neon secret stop line" || fail "Evidence matrix missing Cloudflare/Neon secret stop line"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "CSP enforce 切替" && pass "Evidence matrix includes CSP enforce stop line" || fail "Evidence matrix missing CSP enforce stop line"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "Git push / PR merge / release tag" && pass "Evidence matrix includes git stop line" || fail "Evidence matrix missing git stop line"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "SharePoint Graph real mode" && pass "Evidence matrix includes SharePoint Graph real mode" || fail "Evidence matrix missing SharePoint Graph real mode"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "Notification real mode" && pass "Evidence matrix includes Notification real mode" || fail "Evidence matrix missing Notification real mode"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "Contract submit" && pass "Evidence matrix includes contract submit evidence" || fail "Evidence matrix missing contract submit evidence"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "Contract subresources" && pass "Evidence matrix includes contract subresource evidence" || fail "Evidence matrix missing contract subresource evidence"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "Access self-hosted application を作成" && pass "Approval packet requires Cloudflare Access before DNS" || fail "Approval packet missing Cloudflare Access creation step"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "Cloudflare Tunnel を作成" && pass "Approval packet requires Cloudflare Tunnel creation" || fail "Approval packet missing Cloudflare Tunnel creation step"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "CLOUDFLARE_TUNNEL_TOKEN" && pass "Approval packet includes cloudflared token human gate" || fail "Approval packet missing cloudflared token human gate"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "CNAME / A 未作成" && pass "Approval packet records legalops CNAME/A absence" || fail "Approval packet missing legalops CNAME/A absence"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "本番 deploy を自動実行しない" && pass "Approval packet forbids automatic production deploy" || fail "Approval packet missing automatic deploy prohibition"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "公開 DNS を自動変更しない" && pass "Approval packet forbids automatic public DNS changes" || fail "Approval packet missing public DNS prohibition"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "secret / token / 接続文字列を README / Issue / log に出さない" && pass "Approval packet forbids exposing secrets in docs/issues/logs" || fail "Approval packet missing secret exposure prohibition"
contains "docs/CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK.md" "Access を DNS 公開前に作成" && pass "Cloudflare runbook requires Access before DNS" || fail "Cloudflare runbook missing Access-before-DNS rule"
contains "docs/CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK.md" "CNAME / A が未作成" && pass "Cloudflare runbook records legalops DNS absence" || fail "Cloudflare runbook missing legalops DNS absence evidence"
contains "docs/CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK.md" "CNAME legalops -> <TUNNEL_ID>.cfargotunnel.com" && pass "Cloudflare runbook documents legalops CNAME target" || fail "Cloudflare runbook missing legalops CNAME target"
contains "docs/CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK.md" "DNS レコードを Tunnel より先に残す" && pass "Cloudflare runbook includes DNS/Tunnel rollback warning" || fail "Cloudflare runbook missing DNS/Tunnel rollback warning"
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
contains "scripts/verify_github_release_gate.sh" "Open issues are exactly" && pass "GitHub release gate validates open Issue set" || fail "GitHub release gate missing open Issue set validation"
contains "scripts/verify_github_release_gate.sh" "Open PR count is 0" && pass "GitHub release gate validates open PR count" || fail "GitHub release gate missing open PR validation"
contains "scripts/verify_github_release_gate.sh" "Project #\${PROJECT_NUMBER} item #50 carries blocked label" && pass "GitHub release gate validates #50 blocked Project label" || fail "GitHub release gate missing #50 blocked Project label validation"
contains "scripts/verify_github_release_gate.sh" "Latest \${REQUIRED_CI_WORKFLOW} run conclusion is success" && pass "GitHub release gate validates latest CI success" || fail "GitHub release gate missing latest CI success validation"
contains "scripts/verify_github_release_gate.sh" "Latest \${REQUIRED_CI_WORKFLOW} run branch is \${REQUIRED_CI_BRANCH}" && pass "GitHub release gate validates latest CI branch" || fail "GitHub release gate missing latest CI branch validation"
contains "scripts/verify_github_release_gate.sh" "Latest \${REQUIRED_CI_WORKFLOW} run is completed" && pass "GitHub release gate validates latest CI completed status" || fail "GitHub release gate missing latest CI completed validation"
contains "scripts/verify_predeploy_warning_classification.sh" "Pre-deploy warning count is 5" && pass "Warning classification validates expected warning count" || fail "Warning classification missing expected warning count validation"
contains "scripts/verify_predeploy_warning_classification.sh" "No unexpected pre-deploy warnings are present" && pass "Warning classification rejects unexpected warnings" || fail "Warning classification missing unexpected warning guard"
contains "scripts/verify_predeploy_warning_classification.sh" "Approval packet explains warning classification" && pass "Warning classification validates approval packet explanation" || fail "Warning classification missing approval packet explanation validation"
contains "scripts/verify_predeploy_warning_classification.sh" "Final stop report explains warning classification" && pass "Warning classification validates final report explanation" || fail "Warning classification missing final report explanation validation"
contains "scripts/verify_release_checklist_pending_items.sh" "All unchecked checklist items are classified as approval/production/post-release gates" && pass "Release checklist classifier rejects unclassified unchecked items" || fail "Release checklist classifier missing unchecked item guard"
contains "scripts/verify_release_checklist_pending_items.sh" "Release checklist records human approval boundary" && pass "Release checklist classifier validates human approval boundary" || fail "Release checklist classifier missing human approval boundary validation"
contains "scripts/verify_release_checklist_pending_items.sh" "Release checklist links production approval packet" && pass "Release checklist classifier validates approval packet link" || fail "Release checklist classifier missing approval packet link validation"
contains "scripts/verify_production_stop_line.sh" "GitHub release count is 0" && pass "Production stop-line validates GitHub release absence" || fail "Production stop-line missing GitHub release absence validation"
contains "scripts/verify_production_stop_line.sh" "GitHub deployment count is 0" && pass "Production stop-line validates GitHub deployment absence" || fail "Production stop-line missing GitHub deployment absence validation"
contains "scripts/verify_production_stop_line.sh" "CNAME is absent" && pass "Production stop-line validates legalops CNAME absence" || fail "Production stop-line missing legalops CNAME absence validation"
contains "scripts/verify_production_stop_line.sh" "A record is absent" && pass "Production stop-line validates legalops A absence" || fail "Production stop-line missing legalops A absence validation"
contains "scripts/verify_production_stop_line.sh" "Project #\${PROJECT_NUMBER} readme records production deploy not executed" && pass "Production stop-line validates Project deploy stop line" || fail "Production stop-line missing Project deploy stop validation"

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
