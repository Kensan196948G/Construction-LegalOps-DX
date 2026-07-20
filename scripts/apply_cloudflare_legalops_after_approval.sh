#!/usr/bin/env bash
# apply_cloudflare_legalops_after_approval.sh
#
# Approval-gated helper for routing legalops.mirai-dx-platform.com to an
# already-approved Cloudflare Tunnel. This script performs a public DNS change
# only when both an explicit approval phrase and EXECUTE=1 are supplied.

set -euo pipefail

LEGALOPS_HOSTNAME="${LEGALOPS_HOSTNAME:-legalops.mirai-dx-platform.com}"
LEGALOPS_ZONE="${LEGALOPS_ZONE:-mirai-dx-platform.com}"
APPROVAL="${LEGALOPS_CLOUDFLARE_APPROVAL:-}"
TUNNEL_ID_OR_NAME="${TUNNEL_ID_OR_NAME:-}"
EXECUTE="${EXECUTE:-0}"
EXPECTED_APPROVAL="APPROVE_LEGALOPS_CLOUDFLARE"

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

if [ "${EXECUTE}" != "1" ]; then
  echo "DRY RUN: set EXECUTE=1 after final human approval to create the DNS route."
  echo "Would run: cloudflared tunnel route dns <TUNNEL_ID_OR_NAME> ${LEGALOPS_HOSTNAME}"
  exit 0
fi

if [ -z "${TUNNEL_ID_OR_NAME}" ]; then
  echo "STOP: TUNNEL_ID_OR_NAME is required."
  exit 2
fi

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "STOP: cloudflared is not installed or not on PATH."
  exit 2
fi

if [ ! -x "./scripts/verify_cloudflare_legalops.sh" ]; then
  echo "STOP: run from repository root; preflight script is missing."
  exit 2
fi

./scripts/verify_cloudflare_legalops.sh

if command -v dig >/dev/null 2>&1; then
  existing_cname="$(dig +short CNAME "${LEGALOPS_HOSTNAME}" || true)"
  if [ -n "${existing_cname}" ]; then
    echo "STOP: ${LEGALOPS_HOSTNAME} already has a CNAME: ${existing_cname}"
    echo "Review and remove/replace it manually if this is intentional."
    exit 2
  fi
fi

echo "Creating Cloudflare Tunnel DNS route..."
cloudflared tunnel route dns "${TUNNEL_ID_OR_NAME}" "${LEGALOPS_HOSTNAME}"

if command -v dig >/dev/null 2>&1; then
  echo "Post-check CNAME result:"
  dig +short CNAME "${LEGALOPS_HOSTNAME}" || true
else
  echo "Post-check skipped: dig is unavailable."
fi

echo "Done. Continue with Access login, /healthz, RBAC, audit, and rollback smoke checks."
