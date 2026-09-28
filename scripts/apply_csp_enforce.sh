#!/usr/bin/env bash
# ============================================================
# Construction-LegalOps-DX — CSP enforce 適用ヘルパー (#24)
#
# 前提:
#   - #24 の 7 日間 Report-Only データ確認と人間承認が完了していること
#   - nginx 設定の検証に Docker を使用（無い場合は nginx -t を直接実行）
#
# 実行:
#   ./scripts/apply_csp_enforce.sh
#
# 行うこと:
#   1. security-headers.conf の Report-Only ヘッダを enforce へ置換（冪等）
#   2. nginx -t で設定検証
#   3. 適用後のヘッダ確認コマンドを表示
#   4. 本番 reload は人間が実行（このスクリプトは config 変更と検証のみ）
# ============================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONF="${REPO_ROOT}/infra/nginx/security-headers.conf"
ENFORCE_CONF="${REPO_ROOT}/infra/nginx/security-headers.enforce.conf"
NGINX_IMAGE="${NGINX_IMAGE:-nginx:1.27-alpine}"

log() { printf '[csp-enforce %s] %s\n' "$(date -u +%FT%TZ)" "$*"; }

if [ ! -f "$ENFORCE_CONF" ]; then
  log "ERROR: enforce conf not found: $ENFORCE_CONF"
  exit 1
fi

# ---- 1. 置換（冪等） ----
if grep -q 'Content-Security-Policy-Report-Only' "$CONF"; then
  cp "$CONF" "${CONF}.bak-$(date -u +%Y%m%dT%H%M%SZ)"
  perl -0pi -e 's/Content-Security-Policy-Report-Only/Content-Security-Policy/g' "$CONF"
  log "Replaced Report-Only header with enforce header (backup created)."
else
  log "security-headers.conf already uses enforce header — nothing to do."
fi

if grep -q 'Content-Security-Policy-Report-Only' "$CONF"; then
  log "ERROR: Report-Only header still present after replacement."
  exit 1
fi

# ---- 2. 設定検証 ----
if command -v docker >/dev/null 2>&1; then
  docker run --rm -v "${REPO_ROOT}/infra/nginx:/etc/nginx/conf.d:ro" "$NGINX_IMAGE" nginx -t
else
  nginx -t -c "${REPO_ROOT}/infra/nginx/nginx.conf" 2>/dev/null \
    || log "WARNING: docker/nginx unavailable — run nginx -t on the target host."
fi

log "Apply complete (config only)."
cat <<'EOF'

次の人間操作を実施してください（本番 reload）:
  1. 適用差分をレビュー: git diff infra/nginx/security-headers.conf
  2. 本番ホストへ反映（例: docker compose cp または config 再生成）
  3. nginx -t && nginx -s reload
  4. 確認:
     curl -sI https://legalops.mirai-dx-platform.com/ | grep -i content-security-policy
     → "Content-Security-Policy: ..." が返ること（Report-Only でないこと）
  5. 主要画面（ダッシュボード/契約/レビュー/法務相談/設定）の表示確認
EOF
