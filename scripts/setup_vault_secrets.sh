#!/usr/bin/env bash
# setup_vault_secrets.sh — Vault / Azure Key Vault へのシークレット投入スクリプト
#
# 使用方法:
#   1. RS256 鍵ペアを生成: ./scripts/generate_rsa_keys.sh /tmp/keys
#   2. 本スクリプトで Vault に投入: ./scripts/setup_vault_secrets.sh
#
# 前提:
#   - HashiCorp Vault または Azure CLI がインストール済み
#   - VAULT_ADDR / VAULT_TOKEN 環境変数が設定済み
#   - または: az login 済み + AZURE_KEY_VAULT_NAME 設定済み
#
# 環境変数例 (.env.production 参照):
#   JWT_PRIVATE_KEY  = RSA-2048+ 秘密鍵 (PEM)
#   JWT_PUBLIC_KEY   = RSA 公開鍵 (PEM)
#   JWT_ALGORITHM    = RS256
#   ENTRA_TENANT_ID  = Microsoft Entra ID テナント ID
#   ENTRA_CLIENT_ID  = アプリ登録 クライアント ID
#   ENTRA_CLIENT_SECRET = アプリ登録 クライアントシークレット
#   CLAUDE_API_KEY = Claude API キー
#   POSTGRES_PASSWORD = PostgreSQL 本番パスワード
#   REDIS_PASSWORD   = Redis 本番パスワード
#
# ⚠️ このスクリプトは実際のシークレット値を含まないこと！
# ⚠️ .gitignore に *.pem, .env.production が含まれていることを確認してください

set -euo pipefail

VAULT_MODE="${VAULT_MODE:-hashicorp}"  # hashicorp | azure
KEY_DIR="${KEY_DIR:-/tmp/legalops-keys}"

# ---------------------------------------------------------------------------
# HashiCorp Vault 投入
# ---------------------------------------------------------------------------
_vault_put() {
  local path="$1"
  shift
  echo "📤 Writing to Vault: $path"
  vault kv put "secret/legalops/$path" "$@"
}

setup_hashicorp() {
  if ! command -v vault &>/dev/null; then
    echo "❌ vault CLI not found. Install from https://developer.hashicorp.com/vault/install"
    exit 1
  fi
  if [ -z "${VAULT_ADDR:-}" ] || [ -z "${VAULT_TOKEN:-}" ]; then
    echo "❌ VAULT_ADDR and VAULT_TOKEN must be set."
    exit 1
  fi

  echo "🔑 Setting up HashiCorp Vault secrets..."

  # JWT RS256
  if [ -f "$KEY_DIR/jwt_private.pem" ] && [ -f "$KEY_DIR/jwt_public.pem" ]; then
    _vault_put jwt \
      private_key=@"$KEY_DIR/jwt_private.pem" \
      public_key=@"$KEY_DIR/jwt_public.pem" \
      algorithm=RS256
  else
    echo "⚠️  JWT keys not found at $KEY_DIR. Run ./scripts/generate_rsa_keys.sh $KEY_DIR first."
  fi

  # Entra ID
  echo "ℹ️  Set ENTRA_TENANT_ID, ENTRA_CLIENT_ID, ENTRA_CLIENT_SECRET manually:"
  echo "   vault kv put secret/legalops/entra tenant_id=<> client_id=<> client_secret=<>"

  # Claude API
  echo "ℹ️  Set CLAUDE_API_KEY manually:"
  echo "   vault kv put secret/legalops/claude api_key=<>"

  echo "✅ HashiCorp Vault setup complete (partial). Complete manual steps above."
}

# ---------------------------------------------------------------------------
# Azure Key Vault 投入
# ---------------------------------------------------------------------------
setup_azure() {
  if ! command -v az &>/dev/null; then
    echo "❌ Azure CLI not found. Install from https://learn.microsoft.com/cli/azure/install-azure-cli"
    exit 1
  fi
  if [ -z "${AZURE_KEY_VAULT_NAME:-}" ]; then
    echo "❌ AZURE_KEY_VAULT_NAME must be set."
    exit 1
  fi

  echo "🔑 Setting up Azure Key Vault: $AZURE_KEY_VAULT_NAME"

  if [ -f "$KEY_DIR/jwt_private.pem" ]; then
    az keyvault secret set \
      --vault-name "$AZURE_KEY_VAULT_NAME" \
      --name "jwt-private-key" \
      --file "$KEY_DIR/jwt_private.pem"
    echo "✅ JWT private key uploaded."
  fi

  if [ -f "$KEY_DIR/jwt_public.pem" ]; then
    az keyvault secret set \
      --vault-name "$AZURE_KEY_VAULT_NAME" \
      --name "jwt-public-key" \
      --file "$KEY_DIR/jwt_public.pem"
    echo "✅ JWT public key uploaded."
  fi

  az keyvault secret set \
    --vault-name "$AZURE_KEY_VAULT_NAME" \
    --name "jwt-algorithm" \
    --value "RS256"

  echo ""
  echo "📋 Remaining secrets to set manually in Azure Key Vault:"
  echo "   az keyvault secret set --vault-name $AZURE_KEY_VAULT_NAME --name entra-tenant-id --value <>"
  echo "   az keyvault secret set --vault-name $AZURE_KEY_VAULT_NAME --name entra-client-id --value <>"
  echo "   az keyvault secret set --vault-name $AZURE_KEY_VAULT_NAME --name entra-client-secret --value <>"
  echo "   az keyvault secret set --vault-name $AZURE_KEY_VAULT_NAME --name claude-api-key --value <>"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
case "$VAULT_MODE" in
  hashicorp) setup_hashicorp ;;
  azure)     setup_azure ;;
  *)         echo "❌ Unknown VAULT_MODE: $VAULT_MODE (use 'hashicorp' or 'azure')"; exit 1 ;;
esac

echo ""
echo "🔍 Post-setup verification:"
echo "   Ensure backend .env.production references Vault/Key Vault paths:"
echo "   JWT_PRIVATE_KEY=@vault:secret/legalops/jwt#private_key"
echo "   JWT_PUBLIC_KEY=@vault:secret/legalops/jwt#public_key"
echo "   JWT_ALGORITHM=RS256"
