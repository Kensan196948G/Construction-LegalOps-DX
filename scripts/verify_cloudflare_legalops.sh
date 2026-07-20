#!/usr/bin/env bash
# verify_cloudflare_legalops.sh — preflight for legalops.mirai-dx-platform.com.
#
# This script is intentionally read-only. It does not create DNS records,
# tunnels, Access applications, secrets, or deployments.

set -euo pipefail

HOSTNAME="legalops.mirai-dx-platform.com"
ZONE="mirai-dx-platform.com"
TUNNEL_CONFIG="infra/cloudflare/tunnel-config.example.yml"
DNS_EXAMPLE="infra/cloudflare/dns-records.legalops.example.json"
ACCESS_POLICY="infra/cloudflare/access-policy.yml"
COMPOSE_OVERLAY="infra/docker/docker-compose.cloudflare-tunnel.yml"
RUNBOOK="docs/CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK.md"
APPLY_HELPER="scripts/apply_cloudflare_legalops_after_approval.sh"

PASS=0
FAIL=0
WARN=0

pass() {
  echo "✅ $1"
  PASS=$((PASS + 1))
}

fail() {
  echo "❌ $1"
  FAIL=$((FAIL + 1))
}

warn() {
  echo "⚠️  $1"
  WARN=$((WARN + 1))
}

contains() {
  local file="$1"
  local pattern="$2"
  grep -Fq "$pattern" "$file"
}

echo "================================================"
echo "☁️  Cloudflare LegalOps Subdomain Preflight"
echo "================================================"
echo "Hostname: ${HOSTNAME}"
echo "Zone:     ${ZONE}"
echo ""

[ -f "${TUNNEL_CONFIG}" ] && pass "Tunnel config exists" || fail "Tunnel config missing: ${TUNNEL_CONFIG}"
[ -f "${DNS_EXAMPLE}" ] && pass "DNS record example exists" || fail "DNS record example missing: ${DNS_EXAMPLE}"
[ -f "${ACCESS_POLICY}" ] && pass "Access policy example exists" || fail "Access policy missing: ${ACCESS_POLICY}"
[ -f "${COMPOSE_OVERLAY}" ] && pass "Cloudflare Tunnel compose overlay exists" || fail "Compose overlay missing: ${COMPOSE_OVERLAY}"
[ -f "${RUNBOOK}" ] && pass "Cloudflare legalops runbook exists" || fail "Cloudflare runbook missing: ${RUNBOOK}"
[ -f "${APPLY_HELPER}" ] && pass "Approval-gated Cloudflare apply helper exists" || fail "Apply helper missing: ${APPLY_HELPER}"

if [ -f "${TUNNEL_CONFIG}" ]; then
  contains "${TUNNEL_CONFIG}" "hostname: ${HOSTNAME}" && pass "Tunnel hostname is ${HOSTNAME}" || fail "Tunnel hostname is not ${HOSTNAME}"
  contains "${TUNNEL_CONFIG}" "service: http://nginx:80" && pass "Tunnel routes to nginx:80" || fail "Tunnel service is not nginx:80"
  contains "${TUNNEL_CONFIG}" "http_status:404" && pass "Tunnel ingress fails closed for unknown hosts" || fail "Tunnel ingress does not fail closed"
fi

if [ -f "${DNS_EXAMPLE}" ]; then
  contains "${DNS_EXAMPLE}" '"name": "legalops"' && pass "DNS example uses legalops label" || fail "DNS example does not use legalops label"
  contains "${DNS_EXAMPLE}" "cfargotunnel.com" && pass "DNS example targets cfargotunnel.com" || fail "DNS example does not target cfargotunnel.com"
  contains "${DNS_EXAMPLE}" '"proxied": true' && pass "DNS example is proxied" || fail "DNS example is not proxied"
fi

if [ -f "${ACCESS_POLICY}" ]; then
  contains "${ACCESS_POLICY}" "domain: \"${HOSTNAME}\"" && pass "Access policy domain is ${HOSTNAME}" || fail "Access policy domain mismatch"
  contains "${ACCESS_POLICY}" "LegalOps-Users" && pass "Access policy includes LegalOps-Users" || fail "Access policy missing LegalOps-Users"
  contains "${ACCESS_POLICY}" "LegalOps-Admins" && pass "Access policy includes LegalOps-Admins" || fail "Access policy missing LegalOps-Admins"
  contains "${ACCESS_POLICY}" "value: \"mfa\"" && pass "Access policy requires MFA" || fail "Access policy does not require MFA"
fi

if [ -f "${COMPOSE_OVERLAY}" ]; then
  contains "${COMPOSE_OVERLAY}" "CLOUDFLARE_TUNNEL_TOKEN" && pass "Compose overlay expects CLOUDFLARE_TUNNEL_TOKEN" || fail "Compose overlay missing CLOUDFLARE_TUNNEL_TOKEN"
  contains "${COMPOSE_OVERLAY}" "cloudflare/cloudflared" && pass "Compose overlay uses official cloudflared image" || fail "Compose overlay image is not cloudflare/cloudflared"
fi

if [ -f "${RUNBOOK}" ]; then
  contains "${RUNBOOK}" "2026-07-20 Loop 106" && pass "Runbook records current Loop 106 Cloudflare status" || fail "Runbook is not synced to Loop 106"
  contains "${RUNBOOK}" "親ドメイン \`mirai-dx-platform.com\` は取得済み" && pass "Runbook records acquired parent domain requirement" || fail "Runbook missing acquired parent domain requirement"
  contains "${RUNBOOK}" "\`legalops\` は新規作成対象" && pass "Runbook records legalops as new subdomain" || fail "Runbook missing legalops new-subdomain requirement"
  contains "${RUNBOOK}" "\`legalops.mirai-dx-platform.com\` | Cloudflare API / DNS ともに未登録。新規サブドメインとして承認後に作成" && pass "Runbook records legalops DNS/API absence before approval" || fail "Runbook missing legalops pre-approval absence"
  contains "${RUNBOOK}" "DNS レコードと Tunnel は独立" && pass "Runbook documents DNS/Tunnel independence" || fail "Runbook missing DNS/Tunnel independence warning"
  contains "${RUNBOOK}" "1016" && pass "Runbook documents Cloudflare 1016 rollback risk" || fail "Runbook missing Cloudflare 1016 risk"
  contains "${RUNBOOK}" "Access を DNS 公開前に作成" && pass "Runbook requires Access before DNS publication" || fail "Runbook missing Access-before-DNS rule"
  contains "${RUNBOOK}" "DNS 作成、Access 作成、Tunnel 作成、本番デプロイはこのセッションでは実行していません" && pass "Runbook preserves no-production-change stop line" || fail "Runbook missing no-production-change stop line"
  contains "${RUNBOOK}" "apply_cloudflare_legalops_after_approval.sh" && pass "Runbook references approval-gated apply helper" || fail "Runbook missing approval-gated apply helper"
fi

if [ -f "${APPLY_HELPER}" ]; then
  contains "${APPLY_HELPER}" "APPROVE_LEGALOPS_CLOUDFLARE" && pass "Apply helper requires explicit approval phrase" || fail "Apply helper missing approval phrase"
  contains "${APPLY_HELPER}" 'EXECUTE="${EXECUTE:-0}"' && pass "Apply helper defaults to dry-run mode" || fail "Apply helper does not default to dry-run"
  contains "${APPLY_HELPER}" 'LEGALOPS_HOSTNAME="${LEGALOPS_HOSTNAME:-legalops.mirai-dx-platform.com}"' && pass "Apply helper does not inherit shell HOSTNAME" || fail "Apply helper may inherit shell HOSTNAME"
  contains "${APPLY_HELPER}" "cloudflared tunnel route dns" && pass "Apply helper routes DNS via cloudflared only after approval" || fail "Apply helper missing cloudflared DNS route"
fi

if command -v dig >/dev/null 2>&1; then
  NS_RESULT="$(dig +short NS "${ZONE}" || true)"
  if echo "${NS_RESULT}" | grep -qi "cloudflare"; then
    pass "${ZONE} is delegated to Cloudflare nameservers"
  elif [ -n "${NS_RESULT}" ]; then
    warn "${ZONE} NS did not include cloudflare in this resolver response"
  else
    warn "${ZONE} NS lookup returned no result"
  fi

  CNAME_RESULT="$(dig +short CNAME "${HOSTNAME}" || true)"
  if [ -z "${CNAME_RESULT}" ]; then
    pass "${HOSTNAME} CNAME is currently absent or not visible"
  else
    warn "${HOSTNAME} CNAME already resolves to: ${CNAME_RESULT}"
  fi
else
  warn "dig is not installed; DNS read-only checks skipped"
fi

if [ -n "${CLOUDFLARE_API_TOKEN:-}" ]; then
  if command -v python3 >/dev/null 2>&1; then
    API_SUMMARY="$(
      HOSTNAME="${HOSTNAME}" ZONE="${ZONE}" python3 - <<'PY'
import json
import os
import sys
import urllib.parse
import urllib.request

base = "https://api.cloudflare.com/client/v4"
token = os.environ["CLOUDFLARE_API_TOKEN"]
zone = os.environ["ZONE"]
hostname = os.environ["HOSTNAME"]
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
        print("error=zone_not_found")
        sys.exit(0)

    selected = zone_records[0]
    zone_id = selected["id"]
    records = request_json(
        f"/zones/{zone_id}/dns_records?name={urllib.parse.quote(hostname)}"
    )
    print("api_success=true")
    print(f"zone_status={selected.get('status', '')}")
    print(f"zone_id={zone_id}")
    print(f"record_count={len(records.get('result') or [])}")
except Exception as exc:
    print("api_success=false")
    print(f"error={type(exc).__name__}")
PY
    )"

    if echo "${API_SUMMARY}" | grep -Fq "api_success=true"; then
      pass "Cloudflare API token can read the ${ZONE} zone"
      API_ZONE_STATUS="$(echo "${API_SUMMARY}" | awk -F= '/^zone_status=/{print $2; exit}')"
      [ "${API_ZONE_STATUS}" = "active" ] && pass "Cloudflare zone status is active" || warn "Cloudflare zone status is ${API_ZONE_STATUS:-unknown}"
      API_RECORD_COUNT="$(echo "${API_SUMMARY}" | awk -F= '/^record_count=/{print $2; exit}')"
      if [ "${API_RECORD_COUNT:-0}" = "0" ]; then
        pass "Cloudflare API confirms ${HOSTNAME} DNS record is absent"
      else
        warn "Cloudflare API found ${API_RECORD_COUNT} existing ${HOSTNAME} DNS record(s)"
      fi
    else
      warn "Cloudflare API read-only check failed: $(echo "${API_SUMMARY}" | awk -F= '/^error=/{print $2; exit}')"
    fi
  else
    warn "python3 is not installed; Cloudflare API read-only check skipped"
  fi
else
  warn "CLOUDFLARE_API_TOKEN is not set; Cloudflare API read-only check skipped"
fi

if command -v cloudflared >/dev/null 2>&1; then
  if cloudflared tunnel ingress validate "${TUNNEL_CONFIG}" >/dev/null 2>&1; then
    pass "cloudflared ingress validate passed"
  else
    warn "cloudflared ingress validate could not run against the placeholder template"
  fi
else
  warn "cloudflared is not installed; ingress validate skipped"
fi

echo ""
echo "================================================"
echo "📊 Summary"
echo "================================================"
echo "✅ Passed:   ${PASS}"
echo "❌ Failed:   ${FAIL}"
echo "⚠️  Warnings: ${WARN}"

if [ "${FAIL}" -gt 0 ]; then
  echo "🚨 Cloudflare legalops preflight failed"
  exit 1
fi

echo "✅ Cloudflare legalops preflight passed"
exit 0
