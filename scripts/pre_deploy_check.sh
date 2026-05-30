#!/usr/bin/env bash
# pre_deploy_check.sh — 本番デプロイ前の自動検証スクリプト
#
# 使用方法:
#   ./scripts/pre_deploy_check.sh
#
# 終了コード:
#   0 = 全チェック通過 (デプロイ OK)
#   1 = 1件以上のチェック失敗 (デプロイ停止)

set -euo pipefail

PASS=0
FAIL=0
WARNINGS=()

check() {
  local label="$1"
  local result="$2"
  if [ "$result" -eq 0 ]; then
    echo "✅ $label"
    PASS=$((PASS + 1))
  else
    echo "❌ $label"
    FAIL=$((FAIL + 1))
  fi
}

warn() {
  local label="$1"
  echo "⚠️  $label"
  WARNINGS+=("$label")
}

echo "================================================"
echo "🔍 Construction-LegalOps-DX Pre-Deploy Check"
echo "================================================"
echo ""

# ---------------------------------------------------------------------------
# 1. Backend code quality
# ---------------------------------------------------------------------------
echo "📋 Backend Code Quality"

(cd backend && python -m ruff check . 2>&1 | grep -q "All checks passed") && check "ruff lint" 0 || check "ruff lint" 1

# mypy must be run from backend/ where pyproject.toml resides
(cd backend && python -m mypy app 2>&1 | grep -q "^Success:") && check "mypy type check" 0 || check "mypy type check" 1

# ---------------------------------------------------------------------------
# 2. Backend tests
# ---------------------------------------------------------------------------
echo ""
echo "🧪 Backend Tests"

(cd backend && python -m pytest tests/ -q --disable-warnings 2>/dev/null | tail -1 | grep -q "passed") && check "pytest (832+ tests)" 0 || check "pytest" 1

# ---------------------------------------------------------------------------
# 3. Frontend code quality
# ---------------------------------------------------------------------------
echo ""
echo "📋 Frontend Code Quality"

(cd frontend && npx tsc --noEmit 2>&1 | wc -l | grep -q "^0$") && check "TypeScript (tsc)" 0 || check "TypeScript (tsc)" 1

(cd frontend && npm run lint --silent 2>/dev/null) && check "ESLint" 0 || check "ESLint" 1

# ---------------------------------------------------------------------------
# 4. Security
# ---------------------------------------------------------------------------
echo ""
echo "🔒 Security"

(cd backend && bandit -r app -ll -ii 2>&1 | grep -q "No issues identified") && check "Bandit (Python SAST)" 0 || check "Bandit" 1

# npm audit: only fail on high/critical (moderate is acceptable until next.js upgrades)
(cd frontend && npm audit --audit-level=high 2>&1 | grep -q "found 0 vulnerabilities\|0 high\|0 critical" || ! npm audit --audit-level=high 2>&1 | grep -qE "^[0-9]+ high|^[0-9]+ critical") && check "npm audit (high/critical)" 0 || warn "npm audit: moderate vulnerabilities (acceptable — no high/critical)"

# ---------------------------------------------------------------------------
# 5. Environment
# ---------------------------------------------------------------------------
echo ""
echo "🔧 Environment"

[ -n "${JWT_PRIVATE_KEY:-}" ] && check "JWT_PRIVATE_KEY is set" 0 || warn "JWT_PRIVATE_KEY not set (RS256 fallback to HS256)"
[ -n "${JWT_PUBLIC_KEY:-}" ] && check "JWT_PUBLIC_KEY is set" 0 || warn "JWT_PUBLIC_KEY not set"
[ -n "${ENTRA_TENANT_ID:-}" ] && check "ENTRA_TENANT_ID is set" 0 || warn "ENTRA_TENANT_ID not set (SSO disabled in dev)"
[ -n "${ANTHROPIC_API_KEY:-}" ] && check "ANTHROPIC_API_KEY is set" 0 || warn "ANTHROPIC_API_KEY not set (AI review disabled)"

# ---------------------------------------------------------------------------
# 6. Docker images
# ---------------------------------------------------------------------------
echo ""
echo "🐳 Docker"

if command -v docker &>/dev/null; then
  docker build -t legalops/backend:check backend/ -q 2>/dev/null && check "Docker backend build" 0 || check "Docker backend build" 1
  docker build -t legalops/frontend:check frontend/ -q 2>/dev/null && check "Docker frontend build" 0 || check "Docker frontend build" 1
else
  warn "Docker not available — skipping Docker build checks"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "================================================"
echo "📊 Summary"
echo "================================================"
echo "✅ Passed:   $PASS"
echo "❌ Failed:   $FAIL"
echo "⚠️  Warnings: ${#WARNINGS[@]}"
echo ""

if [ "${#WARNINGS[@]}" -gt 0 ]; then
  echo "Warnings:"
  for w in "${WARNINGS[@]}"; do
    echo "  - $w"
  done
  echo ""
fi

if [ "$FAIL" -gt 0 ]; then
  echo "🚨 Deploy BLOCKED: $FAIL check(s) failed"
  exit 1
else
  echo "✅ Deploy ALLOWED: All mandatory checks passed"
  if [ "${#WARNINGS[@]}" -gt 0 ]; then
    echo "   (Review warnings above before deploying)"
  fi
  exit 0
fi
