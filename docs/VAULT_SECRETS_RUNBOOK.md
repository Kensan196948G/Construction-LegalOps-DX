# 🔐 Vault 秘密情報投入ランブック（Issue #23）

> 実行は **人間（IT/DX 管理者）** が行う。本リポジトリ・ログ・チャットに秘密値を書き込まないこと。

## 📋 投入対象一覧

| カテゴリ | キー | 用途 | 必須 |
| --- | --- | --- | --- |
| JWT | `JWT_PRIVATE_KEY` / `JWT_PUBLIC_KEY` / `JWT_ALGORITHM=RS256` | API トークン署名・検証 | ✅ |
| Entra ID | `ENTRA_TENANT_ID` / `ENTRA_CLIENT_ID` / `ENTRA_CLIENT_SECRET` | SSO・Graph 連携 | ✅ |
| AI | `ANTHROPIC_API_KEY` | AI レビュー（Claude） | ✅（無いと fail-closed） |
| AI | `PERPLEXITY_API_KEY` | 契約調査エージェント（Web 根拠） | 任意 |
| DB | `NEON_DATABASE_URL` | Neon 本番接続（#50 承認後） | 採用時 |
| Edge | `CLOUDFLARE_TUNNEL_TOKEN` / API token | Tunnel・DNS 管理（#50 承認後） | 採用時 |

## 🔧 実行手順（HashiCorp Vault）

```bash
# 1. 鍵生成（一時ディレクトリ・作業後は削除）
./scripts/generate_rsa_keys.sh /tmp/legalops-keys

# 2. Vault 環境
export VAULT_ADDR="https://vault.example.internal"
export VAULT_TOKEN="<管理者が発行>"

# 3. 投入（JWT はスクリプトが自動投入）
./scripts/setup_vault_secrets.sh

# 4. 手動投入（スクリプトは対話を避けるため echo のみ）
vault kv put secret/legalops/entra \
  tenant_id="<TENANT_ID>" client_id="<CLIENT_ID>" client_secret="<CLIENT_SECRET>"
vault kv put secret/legalops/claude api_key="<ANTHROPIC_API_KEY>"
vault kv put secret/legalops/perplexity api_key="<PERPLEXITY_API_KEY>"   # 任意

# 5. 本番 env を Vault 参照へ切替（例: 起動時 fetch + env 注入）
#    docker compose では VAULT_ADDR / VAULT_ROLE_ID / VAULT_SECRET_ID を
#    コンテナへ渡し、backend が起動時にシークレットを取得する方式を推奨
```

## 🔧 実行手順（Azure Key Vault）

```bash
az login
export AZURE_KEY_VAULT_NAME="legalops-prod-kv"
./scripts/setup_vault_secrets.sh   # VAULT_MODE=azure を env で設定

az keyvault secret set --vault-name "$AZURE_KEY_VAULT_NAME" \
  --name entra-tenant-id --value "<TENANT_ID>"
az keyvault secret set --vault-name "$AZURE_KEY_VAULT_NAME" \
  --name entra-client-id --value "<CLIENT_ID>"
az keyvault secret set --vault-name "$AZURE_KEY_VAULT_NAME" \
  --name entra-client-secret --value "<CLIENT_SECRET>"
az keyvault secret set --vault-name "$AZURE_KEY_VAULT_NAME" \
  --name claude-api-key --value "<ANTHROPIC_API_KEY>"
```

## ✅ 完了条件と検証

- [ ] 全キーが Vault に格納済み（`vault kv get secret/legalops/...` で確認）
- [ ] 本番で `JWT_ALGORITHM=RS256` のトークン検証が成功（`/api/v1/auth/me` 200）
- [ ] `./scripts/scan_secrets.sh` で高信頼秘密パターン 0
- [ ] ログ・監査・Git に秘密値が非保存であること（`rg -n "sk-ant-|client_secret" . --hidden` 相当で確認）
- [ ] AI 接続テスト（設定画面の Connection test）が成功

## ↩️ ロールバック

- 鍵ローテーション: 新鍵を Vault に追記し `JWT_PUBLIC_KEYS`（旧鍵リスト）で検証継続 → 切替 → 旧鍵削除
- 誤投入時: `vault kv delete secret/legalops/<path>` で即時削除し、アクセスログを確認
