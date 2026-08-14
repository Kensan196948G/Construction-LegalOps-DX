#!/usr/bin/env bash
# apply_mvp_legalops_after_approval.sh
#
# Approval-gated helper for routing the MVP/Prototype subdomain
# legalops-mvp.mirai-dx-platform.com to an already-approved Cloudflare Tunnel.
#
# Safety:
# - All DNS mutation is delegated to apply_cloudflare_legalops_after_approval.sh,
#   which resolves a concrete Tunnel UUID and post-checks the Cloudflare API
#   CNAME target before declaring success.
# - This wrapper requires its own approval phrase (different from the
#   production one) so a production approval token can never activate the
#   MVP route by accident.
#
# Usage (only after explicit human approval):
#   MVP_LEGALOPS_CLOUDFLARE_APPROVAL=APPROVE_MVP_LEGALOPS_CLOUDFLARE \
#   MVP_TUNNEL_UUID=<tunnel-uuid> EXECUTE=1 \
#   ./scripts/apply_mvp_legalops_after_approval.sh

set -euo pipefail

export LEGALOPS_HOSTNAME="${MVP_LEGALOPS_HOSTNAME:-legalops-mvp.mirai-dx-platform.com}"
export LEGALOPS_ZONE="${LEGALOPS_ZONE:-mirai-dx-platform.com}"

EXPECTED_APPROVAL="APPROVE_MVP_LEGALOPS_CLOUDFLARE"
APPROVAL="${MVP_LEGALOPS_CLOUDFLARE_APPROVAL:-}"
if [ "${APPROVAL}" != "${EXPECTED_APPROVAL}" ]; then
  echo "STOP: set MVP_LEGALOPS_CLOUDFLARE_APPROVAL=${EXPECTED_APPROVAL} after human approval." >&2
  exit 2
fi

export TUNNEL_UUID="${MVP_TUNNEL_UUID:-${TUNNEL_UUID:-}}"
export TUNNEL_ID_OR_NAME="${MVP_TUNNEL_ID_OR_NAME:-${TUNNEL_ID_OR_NAME:-}}"
# The inner script requires its own phrase; the MVP-specific gate above is the
# actual human approval and the inner check is a fail-closed invariant.
export LEGALOPS_CLOUDFLARE_APPROVAL="APPROVE_LEGALOPS_CLOUDFLARE"

exec ./scripts/apply_cloudflare_legalops_after_approval.sh
