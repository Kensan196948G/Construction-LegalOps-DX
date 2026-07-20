#!/usr/bin/env bash
# verify_goal_completion_evidence.sh — read-only proof map for the active
# release goal completion criteria.
#
# This script validates that release-facing documents contain concrete evidence
# for every explicit goal completion criterion, while preserving the human
# approval stop-line. It does not deploy, create DNS records, inject secrets,
# create releases/tags, or mutate external systems.

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

# Match a verifier evidence row by script name + "Failed 0" without pinning the
# Passed count — pinned counts drift every time a verifier gains a check.
records_green_run() {
  local file="$1"
  local script_name="$2"
  grep -Eq "${script_name}.*Passed [0-9]+ / Failed 0" "$file"
}

echo "================================================"
echo "🎯 Goal Completion Evidence Preflight"
echo "================================================"

EVIDENCE="docs/RELEASE_EVIDENCE_MATRIX.md"
REPORT="docs/FINAL_RELEASE_STOP_REPORT.md"
APPROVAL="docs/PRODUCTION_APPROVAL_PACKET.md"
CHECKLIST="docs/RELEASE_CHECKLIST.md"

for file in "${EVIDENCE}" "${REPORT}" "${APPROVAL}" "${CHECKLIST}" "README.md" "state.json"; do
  [ -s "${file}" ] && pass "Goal evidence source exists: ${file}" || fail "Goal evidence source missing or empty: ${file}"
done

python3 -m json.tool state.json >/dev/null 2>&1 && pass "state.json is valid JSON" || fail "state.json is invalid JSON"

CURRENT_LOOP="$(
  python3 - <<'PY'
import json
with open("state.json", encoding="utf-8") as fh:
    state = json.load(fh)
print(state["project"]["last_loop_completed"])
PY
)"
CURRENT_MARKER="Loop ${CURRENT_LOOP}"
contains_file "${EVIDENCE}" "${CURRENT_MARKER}" && pass "Evidence matrix is current: ${CURRENT_MARKER}" || fail "Evidence matrix missing ${CURRENT_MARKER}"
contains_file "${REPORT}" "${CURRENT_MARKER}" && pass "Final report is current: ${CURRENT_MARKER}" || fail "Final report missing ${CURRENT_MARKER}"
contains_file "${APPROVAL}" "${CURRENT_MARKER}" && pass "Approval packet is current: ${CURRENT_MARKER}" || fail "Approval packet missing ${CURRENT_MARKER}"
contains_file "${CHECKLIST}" "${CURRENT_MARKER}" && pass "Release checklist is current: ${CURRENT_MARKER}" || fail "Release checklist missing ${CURRENT_MARKER}"

contains_file "${EVIDENCE}" "必須機能が実装済み" && pass "Goal criterion covered: required features implemented" || fail "Missing required-features criterion"
contains_file "${EVIDENCE}" "Lint / 型チェック / テスト / ビルドが成功" && pass "Goal criterion covered: lint/type/test/build" || fail "Missing lint/type/test/build criterion"
contains_file "${EVIDENCE}" "重大または高危険度の脆弱性なし" && pass "Goal criterion covered: critical/high security" || fail "Missing security criterion"
contains_file "${EVIDENCE}" "DB migration と rollback 手順を検証" && pass "Goal criterion covered: DB migration and rollback" || fail "Missing DB migration/rollback criterion"
contains_file "${EVIDENCE}" "リリース前チェックリストが完成" && pass "Goal criterion covered: release checklist" || fail "Missing release checklist criterion"
contains_file "${EVIDENCE}" "WebUI を提示できる" && pass "Goal criterion covered: WebUI URL" || fail "Missing WebUI criterion"
contains_file "${EVIDENCE}" "GitHub Projects / Issue / CI / 進捗が最新" && pass "Goal criterion covered: GitHub Project/Issue/CI" || fail "Missing GitHub Project/Issue/CI criterion"
contains_file "${EVIDENCE}" "本番 deploy だけを残した承認待ち" && pass "Goal criterion covered: approval-pending stop line" || fail "Missing approval-pending criterion"

records_green_run "${EVIDENCE}" "pre_deploy_check\.sh" && pass "Evidence matrix records pre-deploy gate result" || fail "Evidence matrix missing pre-deploy result"
records_green_run "${EVIDENCE}" "verify_standalone_webui_runtime\.sh" && pass "Evidence matrix records Standalone WebUI runtime result" || fail "Evidence matrix missing Standalone WebUI runtime result"
records_green_run "${EVIDENCE}" "verify_release_docs\.sh" && pass "Evidence matrix records release docs preflight result" || fail "Evidence matrix missing release docs preflight result"
records_green_run "${EVIDENCE}" "verify_github_release_gate\.sh" && pass "Evidence matrix records GitHub release gate result" || fail "Evidence matrix missing GitHub release gate result"
records_green_run "${EVIDENCE}" "verify_production_stop_line\.sh" && pass "Evidence matrix records warning/stop-line classification results" || fail "Evidence matrix missing stop-line classification evidence"
records_green_run "${EVIDENCE}" "verify_cloudflare_legalops\.sh" && pass "Evidence matrix records Cloudflare preflight result" || fail "Evidence matrix missing Cloudflare preflight result"

contains_file "${REPORT}" "## 🧩 2. 変更内容サマリ" && pass "Final report includes change summary" || fail "Final report missing change summary"
contains_file "${REPORT}" "## 🧪 3. 実行したレビュー" && pass "Final report includes review summary" || fail "Final report missing review summary"
contains_file "${REPORT}" "## ✅ 4. テスト結果" && pass "Final report includes test results" || fail "Final report missing test results"
contains_file "${REPORT}" "## 🖥️ 5. WebUI 確認方法" && pass "Final report includes WebUI instructions" || fail "Final report missing WebUI instructions"
contains_file "${REPORT}" "## 🚧 6. 残課題" && pass "Final report includes remaining work" || fail "Final report missing remaining work"
contains_file "${REPORT}" "## ⚠️ 7. リスク" && pass "Final report includes risks" || fail "Final report missing risks"
contains_file "${REPORT}" "## 🚀 8. 本番デプロイ手順" && pass "Final report includes production deploy steps" || fail "Final report missing production deploy steps"
contains_file "${REPORT}" "## 🛑 9. ロールバック手順" && pass "Final report includes rollback steps" || fail "Final report missing rollback steps"
contains_file "${REPORT}" "## 🧯 10. Stop Line" && pass "Final report includes stop line" || fail "Final report missing stop line"

contains_file "${EVIDENCE}" "#23" && contains_file "${EVIDENCE}" "#24" && contains_file "${EVIDENCE}" "#50" && pass "Evidence matrix records all human gates #23/#24/#50" || fail "Evidence matrix missing one or more human gates"
contains_file "${EVIDENCE}" "未承認 tag / Release 0" && pass "Evidence matrix records no unapproved release tags" || fail "Evidence matrix missing unapproved-tag evidence"
contains_file "${EVIDENCE}" "GitHub Deployments 0" && pass "Evidence matrix records no GitHub deployments" || fail "Evidence matrix missing no-deployment evidence"
contains_file "${EVIDENCE}" "CNAME / A は未作成" && pass "Evidence matrix records legalops DNS absence" || fail "Evidence matrix missing legalops DNS absence"

if grep -Fq "コメント予定" "${EVIDENCE}"; then
  fail "Evidence matrix still contains pending comment wording"
else
  pass "Evidence matrix has no pending comment wording"
fi

echo ""
echo "================================================"
echo "📊 Summary"
echo "================================================"
echo "✅ Passed: ${PASS}"
echo "❌ Failed: ${FAIL}"

if [ "${FAIL}" -gt 0 ]; then
  echo "🚨 Goal completion evidence preflight failed"
  exit 1
fi

echo "✅ Goal completion evidence preflight passed"
exit 0
