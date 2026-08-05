#!/usr/bin/env bash
# verify_production_stop_line.sh — read-only proof that production release,
# deploy, unapproved release tags, and unauthenticated public origin access
# remain stopped.
#
# This script does not create/delete DNS records, releases, deployments, tags,
# PRs, issues, secrets, or Cloudflare resources.

set -euo pipefail

OWNER="${GITHUB_OWNER:-Kensan196948G}"
REPO="${GITHUB_REPOSITORY_NAME:-Construction-LegalOps-DX}"
PROJECT_NUMBER="${GITHUB_PROJECT_NUMBER:-30}"
HOSTNAME="${LEGALOPS_HOSTNAME:-legalops.mirai-dx-platform.com}"
REQUIRED_OPEN_PRS="${REQUIRED_OPEN_PRS:-}"
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
echo "🛑 Production Stop-Line Preflight"
echo "================================================"

A_RECORD="$(dig +short A "${HOSTNAME}" || true)"

if [ -n "${A_RECORD}" ]; then
  pass "${HOSTNAME} resolves through Cloudflare proxy"
else
  fail "${HOSTNAME} A record is not visible"
fi

if [ -n "${CLOUDFLARE_API_TOKEN:-}" ]; then
  DNS_API_SUMMARY="$(
    HOSTNAME="${HOSTNAME}" python3 - <<'PY'
import json
import os
import sys
import urllib.parse
import urllib.request

base = "https://api.cloudflare.com/client/v4"
token = os.environ["CLOUDFLARE_API_TOKEN"]
hostname = os.environ["HOSTNAME"]
zone = ".".join(hostname.split(".")[-2:])
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
}


def request_json(path: str) -> dict:
    request = urllib.request.Request(f"{base}{path}", headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


try:
    zones = request_json(f"/zones?name={urllib.parse.quote(zone)}&status=active")
    zone_records = zones.get("result") or []
    if not zones.get("success") or not zone_records:
        print("api_success=false")
        print("record_count=0")
        print("proxied_count=0")
        print("error=zone_not_found")
        sys.exit(0)
    zone_id = zone_records[0]["id"]
    records = request_json(
        f"/zones/{zone_id}/dns_records?name={urllib.parse.quote(hostname)}"
    )
    dns_records = records.get("result") or []
    proxied_records = [record for record in dns_records if record.get("proxied") is True]
    print("api_success=true")
    print(f"record_count={len(dns_records)}")
    print(f"proxied_count={len(proxied_records)}")
except Exception as exc:
    print("api_success=false")
    print("record_count=0")
    print("proxied_count=0")
    print(f"error={type(exc).__name__}")
PY
  )"
  DNS_API_SUCCESS="$(awk -F= '/^api_success=/{print $2; exit}' <<<"${DNS_API_SUMMARY}")"
  DNS_API_RECORD_COUNT="$(awk -F= '/^record_count=/{print $2; exit}' <<<"${DNS_API_SUMMARY}")"
  DNS_API_PROXIED_COUNT="$(awk -F= '/^proxied_count=/{print $2; exit}' <<<"${DNS_API_SUMMARY}")"
  if [ "${DNS_API_SUCCESS}" = "true" ] && [ "${DNS_API_RECORD_COUNT:-0}" -gt 0 ] && [ "${DNS_API_PROXIED_COUNT:-0}" -gt 0 ]; then
    pass "${HOSTNAME} Cloudflare DNS API record is proxied"
  else
    fail "${HOSTNAME} Cloudflare DNS API proxied record check failed"
  fi
else
  fail "CLOUDFLARE_API_TOKEN is required for proxied DNS stop-line verification"
fi

ACCESS_HEADERS="$(curl -fsSI --max-time 20 "https://${HOSTNAME}/healthz" || true)"
if echo "${ACCESS_HEADERS}" | grep -Eq '^HTTP/[0-9.]+ 302' \
  && echo "${ACCESS_HEADERS}" | grep -Eiq '^location: https://[^/]+\.cloudflareaccess\.com/cdn-cgi/access/login/' \
  && contains "${ACCESS_HEADERS}" "Cloudflare-Access"; then
  pass "${HOSTNAME} unauthenticated healthz is challenged by Cloudflare Access"
else
  fail "${HOSTNAME} unauthenticated healthz is not protected by Cloudflare Access"
fi

# The stop line forbids UNAPPROVED tags/releases. Tags approved through the
# merge gate (PR #59: v0.1.12) are allowed — pinning "count 0" would make the
# gate self-destruct the moment the approved release is cut.
APPROVED_RELEASE_TAGS="${APPROVED_RELEASE_TAGS:-v0.1.12}"

UNAPPROVED_TAGS="$(git tag --list | grep -vFx -f <(tr ',' '\n' <<<"${APPROVED_RELEASE_TAGS}") || true)"
if [ -z "${UNAPPROVED_TAGS}" ]; then
  pass "No unapproved local git release tags (approved: ${APPROVED_RELEASE_TAGS})"
else
  fail "Unapproved local git release tags exist: $(tr '\n' ' ' <<<"${UNAPPROVED_TAGS}")"
fi

UNAPPROVED_RELEASES="$(gh release list --limit 100 --json tagName --jq '.[].tagName' | grep -vFx -f <(tr ',' '\n' <<<"${APPROVED_RELEASE_TAGS}") || true)"
if [ -z "${UNAPPROVED_RELEASES}" ]; then
  pass "No unapproved GitHub releases (approved: ${APPROVED_RELEASE_TAGS})"
else
  fail "Unapproved GitHub releases exist: $(tr '\n' ' ' <<<"${UNAPPROVED_RELEASES}")"
fi

DEPLOYMENT_COUNT="$(gh api "repos/${OWNER}/${REPO}/deployments" --jq 'length')"
if [ "${DEPLOYMENT_COUNT}" = "0" ]; then
  pass "GitHub deployment count is 0"
else
  fail "GitHub deployment count is ${DEPLOYMENT_COUNT}; expected 0"
fi

OPEN_PR_NUMBERS="$(gh pr list --state open --json number --jq '[.[].number | tostring] | sort | join(",")')"
OPEN_PR_NUMBERS_LABEL="${OPEN_PR_NUMBERS:-none}"
if [ "${OPEN_PR_NUMBERS}" = "${REQUIRED_OPEN_PRS}" ]; then
  pass "Open PRs are exactly ${REQUIRED_OPEN_PRS_LABEL}"
else
  fail "Open PRs are ${OPEN_PR_NUMBERS_LABEL}; expected ${REQUIRED_OPEN_PRS_LABEL}"
fi

# Only P0 (release-blocking) issues gate the stop line; routine P2/P3 issues
# must not break it.
OPEN_ISSUES="$(gh issue list --state open --limit 100 --label P0 --json number --jq '[.[].number | tostring] | sort | join(",")')"
if [ "${OPEN_ISSUES}" = "23,24,50" ]; then
  pass "Open P0 issues are exactly #23/#24/#50 human gates"
else
  fail "Open P0 issues are ${OPEN_ISSUES}; expected 23,24,50"
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
