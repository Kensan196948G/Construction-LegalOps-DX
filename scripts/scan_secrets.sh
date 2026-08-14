#!/usr/bin/env bash
# ============================================================
# Construction-LegalOps-DX — lightweight secret exposure scanner
#
# This is a repo-local guard for release readiness. It intentionally scans
# source/docs/config diffs for common accidental secret formats while ignoring
# generated caches and the embedded standalone HTML bundle.
# ============================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

PATTERN='AKIA[0-9A-Z]{16}|-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----|postgresql://[^[:space:]]+:[^[:space:]@]+@|postgresql\+asyncpg://[^[:space:]]+:[^[:space:]@]+@|mysql://[^[:space:]]+:[^[:space:]@]+@|mongodb(\+srv)?://[^[:space:]]+:[^[:space:]@]+@|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|CLOUDFLARE_TUNNEL_TOKEN=[^[:space:]]+'
ALLOW_PATTERN='legalops:legalops_dev|legalops:legalops_mvp|ci:ci|dummy:dummy|user:password|<user>:<password>|<NEON_USER>:<NEON_PASSWORD>|\$\{POSTGRES_USER:-legalops\}:\$\{POSTGRES_PASSWORD:-legalops_dev\}|\$\{POSTGRES_USER\}:\$\{POSTGRES_PASSWORD\}|\$\{CLOUDFLARE_TUNNEL_TOKEN:\?required after human approval\}|CLOUDFLARE_TUNNEL_TOKEN=dummy|PATTERN='

EXCLUDES=(
  --glob '!.git/**'
  --glob '!**/__pycache__/**'
  --glob '!**/.pytest_cache/**'
  --glob '!frontend/.next/**'
  --glob '!node_modules/**'
  --glob '!docs/Construction-LegalOps-DX (Standalone).html'
)

if rg -n --hidden "${EXCLUDES[@]}" "${PATTERN}" . | rg -v "${ALLOW_PATTERN}"; then
  echo "Potential secret material detected. Review findings before production approval." >&2
  exit 1
fi

echo "No high-confidence secret patterns detected."
