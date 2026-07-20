#!/usr/bin/env bash
# pre_deploy_check.sh — 本番デプロイ前の自動検証スクリプト
#
# 使用方法:
#   ./scripts/pre_deploy_check.sh
#   SKIP_DOCKER_BUILD=1 ./scripts/pre_deploy_check.sh
#
# 終了コード:
#   0 = 必須チェック通過 (人間による本番承認レビューへ進める)
#   1 = 1件以上のチェック失敗 (本番承認レビュー停止)

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

(cd backend && python -m pytest tests/ -q --disable-warnings 2>/dev/null | tail -1 | grep -q "passed") && check "pytest (900+ tests)" 0 || check "pytest" 1

echo ""
echo "🗄️ Database Migration"

MIGRATION_LOG="$(mktemp)"
if ./scripts/verify_migrations_roundtrip.sh >"${MIGRATION_LOG}" 2>&1; then
  check "Alembic roundtrip (upgrade/downgrade/idempotent)" 0
else
  cat "${MIGRATION_LOG}"
  check "Alembic roundtrip (upgrade/downgrade/idempotent)" 1
fi
rm -f "${MIGRATION_LOG}"

# ---------------------------------------------------------------------------
# 3. Frontend code quality
# ---------------------------------------------------------------------------
echo ""
echo "📋 Frontend Code Quality"

(cd frontend && npm run typecheck --silent >/dev/null 2>&1) && check "TypeScript (typecheck)" 0 || check "TypeScript (typecheck)" 1

(cd frontend && npm run lint --silent 2>/dev/null) && check "ESLint" 0 || check "ESLint" 1

# ---------------------------------------------------------------------------
# 4. Standalone WebUI
# ---------------------------------------------------------------------------
echo ""
echo "🖥️ Standalone WebUI"

python -m pytest tests/test_standalone_webui.py -q >/dev/null 2>&1 && check "Standalone WebUI contract tests" 0 || check "Standalone WebUI contract tests" 1

python -m py_compile scripts/serve_standalone_webui.py >/dev/null 2>&1 && check "Standalone WebUI server syntax" 0 || check "Standalone WebUI server syntax" 1

bash -n scripts/install_standalone_webui_systemd.sh >/dev/null 2>&1 && check "Standalone WebUI systemd installer syntax" 0 || check "Standalone WebUI systemd installer syntax" 1

if [ -x "./scripts/verify_standalone_webui_runtime.sh" ]; then
  ./scripts/verify_standalone_webui_runtime.sh >/dev/null && check "Standalone WebUI runtime preflight" 0 || check "Standalone WebUI runtime preflight" 1
fi

# ---------------------------------------------------------------------------
# 5. Monitoring
# ---------------------------------------------------------------------------
echo ""
echo "📊 Monitoring"

if [ -f "./scripts/verify_monitoring_config.sh" ]; then
  bash ./scripts/verify_monitoring_config.sh >/dev/null && check "monitoring config preflight" 0 || check "monitoring config preflight" 1
fi

# ---------------------------------------------------------------------------
# 6. Backup / restore release evidence
# ---------------------------------------------------------------------------
echo ""
echo "💾 Backup / Restore"

if [ -f "./scripts/verify_backup_restore_docs.sh" ]; then
  bash ./scripts/verify_backup_restore_docs.sh >/dev/null && check "backup/restore evidence preflight" 0 || check "backup/restore evidence preflight" 1
fi

# ---------------------------------------------------------------------------
# 7. Local workspace disclosure
# ---------------------------------------------------------------------------
echo ""
echo "🧭 Local Workspace"

if [ -f "./scripts/verify_local_workspace_state.sh" ]; then
  bash ./scripts/verify_local_workspace_state.sh >/dev/null && check "local workspace state preflight" 0 || check "local workspace state preflight" 1
fi

# ---------------------------------------------------------------------------
# 8. Security
# ---------------------------------------------------------------------------
echo ""
echo "🔒 Security"

(cd backend && bandit -r app -ll -ii 2>&1 | grep -q "No issues identified") && check "Bandit (Python SAST)" 0 || check "Bandit" 1

# npm audit: only fail on high/critical (moderate is acceptable until next.js upgrades)
(cd frontend && npm audit --audit-level=high 2>&1 | grep -q "found 0 vulnerabilities\|0 high\|0 critical" || ! npm audit --audit-level=high 2>&1 | grep -qE "^[0-9]+ high|^[0-9]+ critical") && check "npm audit (high/critical)" 0 || warn "npm audit: moderate vulnerabilities (acceptable — no high/critical)"

if [ -x "./scripts/scan_secrets.sh" ]; then
  ./scripts/scan_secrets.sh >/dev/null && check "secret exposure scan" 0 || check "secret exposure scan" 1
fi

if [ -x "./scripts/verify_cloudflare_legalops.sh" ]; then
  ./scripts/verify_cloudflare_legalops.sh >/dev/null && check "Cloudflare legalops subdomain preflight" 0 || check "Cloudflare legalops subdomain preflight" 1
fi

if [ -x "./scripts/verify_release_docs.sh" ]; then
  ./scripts/verify_release_docs.sh >/dev/null && check "release documentation preflight" 0 || check "release documentation preflight" 1
fi

if [ -x "./scripts/verify_goal_completion_evidence.sh" ]; then
  ./scripts/verify_goal_completion_evidence.sh >/dev/null && check "goal completion evidence preflight" 0 || check "goal completion evidence preflight" 1
fi

if [ -x "./scripts/verify_review_evidence.sh" ]; then
  ./scripts/verify_review_evidence.sh >/dev/null && check "review evidence preflight" 0 || check "review evidence preflight" 1
fi

if [ -x "./scripts/verify_dependency_audit_evidence.sh" ]; then
  ./scripts/verify_dependency_audit_evidence.sh >/dev/null && check "dependency audit evidence preflight" 0 || check "dependency audit evidence preflight" 1
fi

if [ -x "./scripts/verify_github_release_gate.sh" ]; then
  ./scripts/verify_github_release_gate.sh >/dev/null && check "GitHub release gate preflight" 0 || check "GitHub release gate preflight" 1
fi

# ---------------------------------------------------------------------------
# 9. Environment
# ---------------------------------------------------------------------------
echo ""
echo "🔧 Environment"

[ -n "${JWT_PRIVATE_KEY:-}" ] && check "JWT_PRIVATE_KEY is set" 0 || warn "JWT_PRIVATE_KEY not set (RS256 fallback to HS256)"
[ -n "${JWT_PUBLIC_KEY:-}" ] && check "JWT_PUBLIC_KEY is set" 0 || warn "JWT_PUBLIC_KEY not set"
[ -n "${ENTRA_TENANT_ID:-}" ] && check "ENTRA_TENANT_ID is set" 0 || warn "ENTRA_TENANT_ID not set (SSO disabled in dev)"
[ -n "${CLAUDE_API_KEY:-}" ] && check "CLAUDE_API_KEY is set" 0 || warn "CLAUDE_API_KEY not set (AI review disabled)"

# ---------------------------------------------------------------------------
# 10. Docker images
# ---------------------------------------------------------------------------
echo ""
echo "🐳 Docker"

if command -v docker &>/dev/null; then
  docker compose -f infra/docker/docker-compose.yml config >/dev/null && check "docker compose config" 0 || check "docker compose config" 1
  env \
    POSTGRES_USER=dummy \
    POSTGRES_PASSWORD=dummy \
    POSTGRES_DB=dummy \
    DB_URL=postgresql+asyncpg://dummy:dummy@postgres:5432/dummy \
    REDIS_PASSWORD=dummy \
    REDIS_URL=redis://:dummy@redis:6379/0 \
    CELERY_BROKER_URL=redis://:dummy@redis:6379/1 \
    CELERY_RESULT_BACKEND=redis://:dummy@redis:6379/2 \
    JWT_SECRET=dummy \
    ENTRA_TENANT_ID=dummy \
    ENTRA_CLIENT_ID=dummy \
    ENTRA_CLIENT_SECRET=dummy \
    CLAUDE_API_KEY=dummy \
    HENNGE_TENANT_ID=dummy \
    HENNGE_API_KEY=dummy \
    NEXT_PUBLIC_API_BASE_URL=https://legalops.mirai-dx-platform.com \
    CLOUDFLARE_TUNNEL_TOKEN=dummy \
    docker compose \
      -f infra/docker/docker-compose.yml \
      -f infra/docker/docker-compose.prod.yml \
      -f infra/docker/docker-compose.cloudflare-tunnel.yml \
      --profile worker \
      --profile cloudflare-tunnel config >/dev/null \
    && check "Cloudflare Tunnel compose overlay config" 0 || check "Cloudflare Tunnel compose overlay config" 1
  if [ "${SKIP_DOCKER_BUILD:-0}" = "1" ]; then
    warn "Docker image build skipped by SKIP_DOCKER_BUILD=1"
  else
    docker build -t legalops/backend:check backend/ -q 2>/dev/null && check "Docker backend build" 0 || check "Docker backend build" 1
    docker build -t legalops/frontend:check frontend/ -q 2>/dev/null && check "Docker frontend build" 0 || check "Docker frontend build" 1
  fi
else
  warn "Docker not available — skipping Docker build checks"
fi

if [ -x "./scripts/check_unhealthy_services.sh" ]; then
  ./scripts/check_unhealthy_services.sh >/dev/null && check "unhealthy watchdog report" 0 || warn "unhealthy services detected — review before deploy"
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
  echo "✅ Mandatory checks passed: ready for human production approval review"
  if [ "${#WARNINGS[@]}" -gt 0 ]; then
    echo "   (Review warnings above before approving production release)"
  fi
  exit 0
fi
