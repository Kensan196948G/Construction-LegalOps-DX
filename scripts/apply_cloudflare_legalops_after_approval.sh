#!/usr/bin/env bash
# apply_cloudflare_legalops_after_approval.sh
#
# Approval-gated helper for routing legalops.mirai-dx-platform.com to an
# already-approved Cloudflare Tunnel. This script performs a public DNS change
# only when both an explicit approval phrase and EXECUTE=1 are supplied.
#
# Safety invariant:
# - Never pass a tunnel name directly to `cloudflared tunnel route dns`.
# - Resolve or require a concrete Tunnel UUID first.
# - After route creation, verify the Cloudflare API CNAME record points to that
#   UUID. A proxied CNAME can be flattened in public DNS and may not be visible
#   through `dig CNAME`.

set -euo pipefail

LEGALOPS_HOSTNAME="${LEGALOPS_HOSTNAME:-legalops.mirai-dx-platform.com}"
LEGALOPS_ZONE="${LEGALOPS_ZONE:-mirai-dx-platform.com}"
APPROVAL="${LEGALOPS_CLOUDFLARE_APPROVAL:-}"
TUNNEL_ID_OR_NAME="${TUNNEL_ID_OR_NAME:-}"
TUNNEL_UUID="${TUNNEL_UUID:-}"
EXECUTE="${EXECUTE:-0}"
CLOUDFLARE_ROUTE_OVERWRITE="${CLOUDFLARE_ROUTE_OVERWRITE:-0}"
EXPECTED_APPROVAL="APPROVE_LEGALOPS_CLOUDFLARE"

is_uuid() {
  printf '%s' "$1" | grep -Eiq '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
}

resolve_tunnel_uuid() {
  local tunnel_ref="$1"

  if is_uuid "${tunnel_ref}"; then
    printf '%s\n' "${tunnel_ref}"
    return 0
  fi

  if ! command -v cloudflared >/dev/null 2>&1; then
    echo "STOP: cloudflared is required to resolve tunnel names to UUIDs." >&2
    return 2
  fi

  local tunnel_json
  if ! tunnel_json="$(cloudflared tunnel list --output json 2>/dev/null)"; then
    echo "STOP: failed to list Cloudflare tunnels for UUID resolution." >&2
    return 2
  fi

  TUNNEL_JSON="${tunnel_json}" TUNNEL_REF="${tunnel_ref}" python3 - <<'PY'
import json
import os
import sys

ref = os.environ["TUNNEL_REF"]
try:
    tunnels = json.loads(os.environ["TUNNEL_JSON"])
except json.JSONDecodeError:
    print("STOP: cloudflared tunnel list did not return JSON.", file=sys.stderr)
    sys.exit(2)

matches = []
for tunnel in tunnels:
    tunnel_id = str(tunnel.get("id") or tunnel.get("ID") or "")
    tunnel_name = str(tunnel.get("name") or tunnel.get("NAME") or "")
    if ref in {tunnel_id, tunnel_name}:
        matches.append((tunnel_id, tunnel_name))

if len(matches) != 1:
    print(
        f"STOP: tunnel reference {ref!r} matched {len(matches)} tunnels; pass TUNNEL_UUID explicitly.",
        file=sys.stderr,
    )
    sys.exit(2)

tunnel_id, _ = matches[0]
if not tunnel_id:
    print("STOP: matched tunnel did not expose a UUID.", file=sys.stderr)
    sys.exit(2)

print(tunnel_id)
PY
}

cloudflare_dns_record_summary() {
  if [ -z "${CLOUDFLARE_API_TOKEN:-}" ]; then
    echo "STOP: CLOUDFLARE_API_TOKEN is required for Cloudflare DNS record validation." >&2
    return 2
  fi

  HOSTNAME="${LEGALOPS_HOSTNAME}" ZONE="${LEGALOPS_ZONE}" EXPECTED_CNAME="${EXPECTED_CNAME}" python3 - <<'PY'
import json
import os
import sys
import urllib.parse
import urllib.request

base = "https://api.cloudflare.com/client/v4"
token = os.environ["CLOUDFLARE_API_TOKEN"]
zone = os.environ["ZONE"]
hostname = os.environ["HOSTNAME"]
expected = os.environ["EXPECTED_CNAME"].rstrip(".")
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
        print("matching_count=0")
        print("error=zone_not_found")
        sys.exit(0)

    zone_id = zone_records[0]["id"]
    records = request_json(
        f"/zones/{zone_id}/dns_records?name={urllib.parse.quote(hostname)}"
    )
    dns_records = records.get("result") or []
    matching = [
        record
        for record in dns_records
        if record.get("type") == "CNAME"
        and str(record.get("content") or "").rstrip(".") == expected
    ]
    print("api_success=true")
    print(f"record_count={len(dns_records)}")
    print(f"matching_count={len(matching)}")
    print(
        "record_types="
        + ",".join(sorted({str(record.get("type") or "") for record in dns_records}))
    )
except Exception as exc:
    print("api_success=false")
    print("record_count=0")
    print("matching_count=0")
    print(f"error={type(exc).__name__}")
PY
}

echo "================================================"
echo "Cloudflare LegalOps Approval-Gated Apply"
echo "================================================"
echo "Hostname: ${LEGALOPS_HOSTNAME}"
echo "Zone:     ${LEGALOPS_ZONE}"
echo ""

if [ "${APPROVAL}" != "${EXPECTED_APPROVAL}" ]; then
  echo "STOP: set LEGALOPS_CLOUDFLARE_APPROVAL=${EXPECTED_APPROVAL} after human approval."
  exit 2
fi

if [ -z "${TUNNEL_UUID}" ] && [ -z "${TUNNEL_ID_OR_NAME}" ]; then
  echo "STOP: TUNNEL_UUID or TUNNEL_ID_OR_NAME is required."
  exit 2
fi

if [ -z "${TUNNEL_UUID}" ]; then
  TUNNEL_UUID="$(resolve_tunnel_uuid "${TUNNEL_ID_OR_NAME}")"
elif ! is_uuid "${TUNNEL_UUID}"; then
  echo "STOP: TUNNEL_UUID must be a full UUID."
  exit 2
fi

EXPECTED_CNAME="${TUNNEL_UUID}.cfargotunnel.com"

if [ "${EXECUTE}" != "1" ]; then
  echo "DRY RUN: set EXECUTE=1 after final human approval to create the DNS route."
  echo "Resolved tunnel UUID: ${TUNNEL_UUID}"
  echo "Would run: cloudflared tunnel route dns ${TUNNEL_UUID} ${LEGALOPS_HOSTNAME}"
  echo "Would verify: Cloudflare API CNAME ${LEGALOPS_HOSTNAME} == ${EXPECTED_CNAME}"
  echo "Would verify: public HTTPS endpoint returns a Cloudflare Access challenge"
  exit 0
fi

if [ ! -x "./scripts/verify_cloudflare_legalops.sh" ]; then
  echo "STOP: run from repository root; preflight script is missing."
  exit 2
fi

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "STOP: cloudflared is not installed or not on PATH."
  exit 2
fi

./scripts/verify_cloudflare_legalops.sh

record_summary_before="$(cloudflare_dns_record_summary)"
record_count_before="$(echo "${record_summary_before}" | awk -F= '/^record_count=/{print $2; exit}')"
if [ "${record_count_before:-0}" != "0" ] && [ "${CLOUDFLARE_ROUTE_OVERWRITE}" != "1" ]; then
  echo "STOP: ${LEGALOPS_HOSTNAME} already has ${record_count_before} Cloudflare DNS record(s)."
  echo "Set CLOUDFLARE_ROUTE_OVERWRITE=1 only after explicit human approval to replace the route."
  exit 2
fi

route_args=("tunnel" "route" "dns" "${TUNNEL_UUID}" "${LEGALOPS_HOSTNAME}")
if [ "${CLOUDFLARE_ROUTE_OVERWRITE}" = "1" ]; then
  route_args+=("--overwrite-dns")
fi

echo "Creating Cloudflare Tunnel DNS route..."
cloudflared "${route_args[@]}"

echo "Post-check Cloudflare DNS record:"
record_summary_after="$(cloudflare_dns_record_summary)"
echo "${record_summary_after}" | grep -E '^(api_success|record_count|matching_count|record_types)='
api_success="$(echo "${record_summary_after}" | awk -F= '/^api_success=/{print $2; exit}')"
matching_count="$(echo "${record_summary_after}" | awk -F= '/^matching_count=/{print $2; exit}')"
if [ "${api_success}" != "true" ] || [ "${matching_count:-0}" = "0" ]; then
  echo "STOP: Cloudflare API CNAME post-check mismatch."
  echo "Expected: ${LEGALOPS_HOSTNAME} CNAME ${EXPECTED_CNAME}"
  exit 2
fi

if command -v dig >/dev/null 2>&1; then
  public_dns="$(dig +short A "${LEGALOPS_HOSTNAME}" || true)"
  public_dns="${public_dns:-$(dig +short AAAA "${LEGALOPS_HOSTNAME}" || true)}"
  if [ -z "${public_dns}" ]; then
    echo "STOP: public DNS A/AAAA lookup returned no result."
    exit 2
  fi
fi

if command -v curl >/dev/null 2>&1; then
  access_headers="$(curl -fsSI --max-time 20 "https://${LEGALOPS_HOSTNAME}/healthz" || true)"
  if echo "${access_headers}" | grep -Eq '^HTTP/[0-9.]+ 302' && echo "${access_headers}" | grep -Fq "Cloudflare-Access"; then
    echo "Post-check OK: public endpoint is protected by Cloudflare Access."
  else
    echo "STOP: public endpoint did not return a Cloudflare Access challenge."
    exit 2
  fi
fi

echo "Done. Continue with Access login, /healthz, RBAC, audit, and rollback smoke checks."
