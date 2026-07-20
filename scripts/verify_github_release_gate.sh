#!/usr/bin/env bash
# verify_github_release_gate.sh — read-only GitHub release gate checks.
#
# Validates that GitHub Issues, PRs, and Project #30 still reflect the
# production-approval-pending state. This script does not create, edit, close,
# merge, push, tag, deploy, or mutate GitHub state.

set -euo pipefail

OWNER="${GITHUB_OWNER:-Kensan196948G}"
PROJECT_NUMBER="${GITHUB_PROJECT_NUMBER:-30}"
REQUIRED_OPEN_ISSUES="${REQUIRED_OPEN_ISSUES:-23,24,50}"
REQUIRED_OPEN_PRS="${REQUIRED_OPEN_PRS:-}"
REQUIRED_CI_WORKFLOW="${REQUIRED_CI_WORKFLOW:-CI}"
REQUIRED_CI_BRANCH="${REQUIRED_CI_BRANCH:-main}"
REQUIRED_OPEN_PRS_LABEL="${REQUIRED_OPEN_PRS:-none}"

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
  local haystack="$1"
  local needle="$2"
  grep -Fq "$needle" <<<"${haystack}"
}

echo "================================================"
echo "🐙 GitHub Release Gate Preflight"
echo "================================================"

if ! command -v gh >/dev/null 2>&1; then
  fail "GitHub CLI is installed"
else
  pass "GitHub CLI is installed"
fi

if gh auth status >/dev/null 2>&1; then
  pass "GitHub CLI is authenticated"
else
  fail "GitHub CLI is authenticated"
fi

CURRENT_LOOP="$(
  python3 - <<'PY'
import json
with open("state.json", encoding="utf-8") as fh:
    state = json.load(fh)
print(state["project"]["last_loop_completed"])
PY
)"
CURRENT_MARKER="Loop ${CURRENT_LOOP}"
[ -n "${CURRENT_LOOP}" ] && pass "Current loop marker loaded from state.json: ${CURRENT_MARKER}" || fail "Could not load current loop marker from state.json"

OPEN_PR_NUMBERS="$(gh pr list --state open --json number --jq '[.[].number | tostring] | sort | join(",")')"
OPEN_PR_NUMBERS_LABEL="${OPEN_PR_NUMBERS:-none}"
if [ "${OPEN_PR_NUMBERS}" = "${REQUIRED_OPEN_PRS}" ]; then
  pass "Open PRs are exactly ${REQUIRED_OPEN_PRS_LABEL}"
else
  fail "Open PRs are ${OPEN_PR_NUMBERS_LABEL}; expected ${REQUIRED_OPEN_PRS_LABEL}"
fi

PR_58="$(gh pr view 58 --json number,isDraft,baseRefName,headRefName,mergeStateStatus,state,statusCheckRollup,url)"
PR_58_BASE="$(jq -r '.baseRefName' <<<"${PR_58}")"
PR_58_HEAD="$(jq -r '.headRefName' <<<"${PR_58}")"
PR_58_STATE="$(jq -r '.state' <<<"${PR_58}")"
PR_58_CHECKS="$(jq -r '[.statusCheckRollup[]? | select(.conclusion != null) | .conclusion] | unique | join(",")' <<<"${PR_58}")"

[ "${PR_58_BASE}" = "main" ] && pass "PR #58 targets main" || fail "PR #58 base is ${PR_58_BASE}; expected main"
[ "${PR_58_HEAD}" = "feat/phase1-neon-cf-preview" ] && pass "PR #58 head branch is feat/phase1-neon-cf-preview" || fail "PR #58 head is ${PR_58_HEAD}"
[ "${PR_58_STATE}" = "MERGED" ] && pass "PR #58 is merged" || fail "PR #58 state is ${PR_58_STATE}; expected MERGED"
if [ "${PR_58_CHECKS}" = "SUCCESS" ]; then
  pass "PR #58 status checks are all success"
else
  fail "PR #58 status check conclusions are ${PR_58_CHECKS}; expected SUCCESS"
fi

LATEST_CI="$(
  gh run list \
    --workflow "${REQUIRED_CI_WORKFLOW}" \
    --branch "${REQUIRED_CI_BRANCH}" \
    --limit 1 \
    --json databaseId,workflowName,status,conclusion,headBranch,event,createdAt,url \
    --jq '.[0] // empty'
)"

if [ -n "${LATEST_CI}" ]; then
  pass "Latest ${REQUIRED_CI_WORKFLOW} run on ${REQUIRED_CI_BRANCH} exists"
else
  fail "Latest ${REQUIRED_CI_WORKFLOW} run on ${REQUIRED_CI_BRANCH} is missing"
fi

LATEST_CI_STATUS="$(jq -r '.status // ""' <<<"${LATEST_CI}")"
LATEST_CI_CONCLUSION="$(jq -r '.conclusion // ""' <<<"${LATEST_CI}")"
LATEST_CI_BRANCH="$(jq -r '.headBranch // ""' <<<"${LATEST_CI}")"
LATEST_CI_URL="$(jq -r '.url // ""' <<<"${LATEST_CI}")"

if [ "${LATEST_CI_STATUS}" = "completed" ]; then
  pass "Latest ${REQUIRED_CI_WORKFLOW} run is completed"
else
  fail "Latest ${REQUIRED_CI_WORKFLOW} run status is ${LATEST_CI_STATUS}; expected completed"
fi

if [ "${LATEST_CI_CONCLUSION}" = "success" ]; then
  pass "Latest ${REQUIRED_CI_WORKFLOW} run conclusion is success"
else
  fail "Latest ${REQUIRED_CI_WORKFLOW} run conclusion is ${LATEST_CI_CONCLUSION}; expected success"
fi

if [ "${LATEST_CI_BRANCH}" = "${REQUIRED_CI_BRANCH}" ]; then
  pass "Latest ${REQUIRED_CI_WORKFLOW} run branch is ${REQUIRED_CI_BRANCH}"
else
  fail "Latest ${REQUIRED_CI_WORKFLOW} run branch is ${LATEST_CI_BRANCH}; expected ${REQUIRED_CI_BRANCH}"
fi

contains "${LATEST_CI_URL}" "/actions/runs/" && pass "Latest ${REQUIRED_CI_WORKFLOW} run URL is recorded" || fail "Latest ${REQUIRED_CI_WORKFLOW} run URL is missing"

OPEN_ISSUES="$(gh issue list --state open --limit 100 --json number --jq '[.[].number | tostring] | sort | join(",")')"
if [ "${OPEN_ISSUES}" = "${REQUIRED_OPEN_ISSUES}" ]; then
  pass "Open issues are exactly ${REQUIRED_OPEN_ISSUES}"
else
  fail "Open issues are ${OPEN_ISSUES}; expected ${REQUIRED_OPEN_ISSUES}"
fi

ISSUE_50_LABELS="$(gh issue view 50 --json labels --jq '[.labels[].name] | join(",")')"
contains "${ISSUE_50_LABELS}" "blocked" && pass "Issue #50 has blocked label" || fail "Issue #50 missing blocked label"
contains "${ISSUE_50_LABELS}" "human-decision" && pass "Issue #50 has human-decision label" || fail "Issue #50 missing human-decision label"
contains "${ISSUE_50_LABELS}" "infra" && pass "Issue #50 has infra label" || fail "Issue #50 missing infra label"

PROJECT_README="$(gh project view "${PROJECT_NUMBER}" --owner "${OWNER}" --format json --jq .readme)"
contains "${PROJECT_README}" "${CURRENT_MARKER}" && pass "Project #${PROJECT_NUMBER} readme current marker is ${CURRENT_MARKER}" || fail "Project #${PROJECT_NUMBER} readme missing ${CURRENT_MARKER}"
contains "${PROJECT_README}" "Open PRs | 0" && pass "Project #${PROJECT_NUMBER} readme records open PR 0" || fail "Project #${PROJECT_NUMBER} readme missing open PR 0"
contains "${PROJECT_README}" "PR #58 | merged" && pass "Project #${PROJECT_NUMBER} readme records PR #58 merged state" || fail "Project #${PROJECT_NUMBER} readme missing PR #58 merged state"
contains "${PROJECT_README}" "#23 / #24 / #50 only" && pass "Project #${PROJECT_NUMBER} readme records only #23/#24/#50 open" || fail "Project #${PROJECT_NUMBER} readme missing open issue gate"
contains "${PROJECT_README}" "legalops.mirai-dx-platform.com CNAME/A remains absent" && pass "Project #${PROJECT_NUMBER} readme records legalops DNS absence" || fail "Project #${PROJECT_NUMBER} readme missing legalops DNS absence"
contains "${PROJECT_README}" "http://192.168.0.185:38100/" && pass "Project #${PROJECT_NUMBER} readme records WebUI URL" || fail "Project #${PROJECT_NUMBER} readme missing WebUI URL"
contains "${PROJECT_README}" "production release / deploy" && pass "Project #${PROJECT_NUMBER} readme records production deploy stop line" || fail "Project #${PROJECT_NUMBER} readme missing deploy stop line"
contains "${PROJECT_README}" "Issue #50 Loop" && pass "Project #${PROJECT_NUMBER} readme links Issue #50 evidence" || fail "Project #${PROJECT_NUMBER} readme missing Issue #50 evidence link"

PROJECT_ITEMS="$(
  gh project item-list "${PROJECT_NUMBER}" --owner "${OWNER}" --limit 100 --format json \
    --jq '.items[] | select(.content.number==23 or .content.number==24 or .content.number==50) | "\(.content.number)\t\(.status)\t\(.labels | join(","))"'
)"

for issue in 23 24 50; do
  if grep -Eq "^${issue}[[:space:]]+Todo[[:space:]]" <<<"${PROJECT_ITEMS}"; then
    pass "Project #${PROJECT_NUMBER} item #${issue} status is Todo"
  else
    fail "Project #${PROJECT_NUMBER} item #${issue} status is not Todo"
  fi
done

if grep -Eq "^50[[:space:]]+Todo[[:space:]].*blocked" <<<"${PROJECT_ITEMS}"; then
  pass "Project #${PROJECT_NUMBER} item #50 carries blocked label"
else
  fail "Project #${PROJECT_NUMBER} item #50 missing blocked label"
fi

echo ""
echo "================================================"
echo "📊 Summary"
echo "================================================"
echo "✅ Passed: ${PASS}"
echo "❌ Failed: ${FAIL}"

if [ "${FAIL}" -gt 0 ]; then
  echo "🚨 GitHub release gate preflight failed"
  exit 1
fi

echo "✅ GitHub release gate preflight passed"
exit 0
