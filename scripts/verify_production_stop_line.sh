#!/usr/bin/env bash
# verify_production_stop_line.sh — read-only proof that production release,
# deploy, public DNS changes, and release tags remain stopped.
#
# This script does not create/delete DNS records, releases, deployments, tags,
# PRs, issues, secrets, or Cloudflare resources.

set -euo pipefail

OWNER="${GITHUB_OWNER:-Kensan196948G}"
REPO="${GITHUB_REPOSITORY_NAME:-Construction-LegalOps-DX}"
PROJECT_NUMBER="${GITHUB_PROJECT_NUMBER:-30}"
HOSTNAME="${LEGALOPS_HOSTNAME:-legalops.mirai-dx-platform.com}"

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
echo "🛑 Production Stop-Line Preflight"
echo "================================================"

CNAME_RECORD="$(dig +short CNAME "${HOSTNAME}" || true)"
A_RECORD="$(dig +short A "${HOSTNAME}" || true)"

if [ -z "${CNAME_RECORD}" ]; then
  pass "${HOSTNAME} CNAME is absent"
else
  fail "${HOSTNAME} CNAME exists: ${CNAME_RECORD}"
fi

if [ -z "${A_RECORD}" ]; then
  pass "${HOSTNAME} A record is absent"
else
  fail "${HOSTNAME} A record exists: ${A_RECORD}"
fi

TAG_COUNT="$(git tag --list | wc -l | tr -d ' ')"
if [ "${TAG_COUNT}" = "0" ]; then
  pass "Local git release tag count is 0"
else
  fail "Local git release tag count is ${TAG_COUNT}; expected 0"
fi

RELEASE_COUNT="$(gh release list --limit 100 --json tagName --jq 'length')"
if [ "${RELEASE_COUNT}" = "0" ]; then
  pass "GitHub release count is 0"
else
  fail "GitHub release count is ${RELEASE_COUNT}; expected 0"
fi

DEPLOYMENT_COUNT="$(gh api "repos/${OWNER}/${REPO}/deployments" --jq 'length')"
if [ "${DEPLOYMENT_COUNT}" = "0" ]; then
  pass "GitHub deployment count is 0"
else
  fail "GitHub deployment count is ${DEPLOYMENT_COUNT}; expected 0"
fi

OPEN_PR_COUNT="$(gh pr list --state open --json number --jq 'length')"
if [ "${OPEN_PR_COUNT}" = "0" ]; then
  pass "Open PR count is 0"
else
  fail "Open PR count is ${OPEN_PR_COUNT}; expected 0"
fi

OPEN_ISSUES="$(gh issue list --state open --limit 100 --json number --jq '[.[].number | tostring] | sort | join(",")')"
if [ "${OPEN_ISSUES}" = "23,24,50" ]; then
  pass "Open issues are exactly #23/#24/#50 human gates"
else
  fail "Open issues are ${OPEN_ISSUES}; expected 23,24,50"
fi

ISSUE_50_LABELS="$(gh issue view 50 --json labels --jq '[.labels[].name] | join(",")')"
contains "${ISSUE_50_LABELS}" "blocked" && pass "Issue #50 remains blocked" || fail "Issue #50 missing blocked label"
contains "${ISSUE_50_LABELS}" "human-decision" && pass "Issue #50 remains human-decision" || fail "Issue #50 missing human-decision label"

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

contains "$(gh project view "${PROJECT_NUMBER}" --owner "${OWNER}" --format json --jq .readme)" "Production deploy | Not executed" \
  && pass "Project #${PROJECT_NUMBER} readme records production deploy not executed" \
  || fail "Project #${PROJECT_NUMBER} readme missing production deploy stop line"

echo ""
echo "================================================"
echo "📊 Summary"
echo "================================================"
echo "✅ Passed: ${PASS}"
echo "❌ Failed: ${FAIL}"

if [ "${FAIL}" -gt 0 ]; then
  echo "🚨 Production stop-line preflight failed"
  exit 1
fi

echo "✅ Production stop-line preflight passed"
exit 0
