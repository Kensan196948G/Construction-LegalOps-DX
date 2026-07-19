# 🌐 infra/cloudflare — Cloudflare / Neon IaC 設定

> **ステータス: IaC コード完成（本番適用は人間による Tunnel / Access / DNS 作成承認後）**
> このディレクトリのファイルは設定コードであり、置くだけでは何も起動・変更されません。
> `legalops.mirai-dx-platform.com` は新規サブドメイン作成対象です。親ドメイン `mirai-dx-platform.com` は取得済みで、Cloudflare zone は active です。本番適用には人間による以下の前提作業が必要です（Issue #50 参照）。

## 📌 構成

| ファイル | 役割 | 状態 |
|---|---|---|
| `wrangler.toml` | Cloudflare Pages 設定（Next.js デプロイ） | ✅ IaC 完成 |
| `tunnel-config.example.yml` | cloudflared Tunnel ルーティング設定テンプレート | ✅ 雛形 |
| `access-policy.yml` | Cloudflare Access ポリシー定義（Entra ID IdP 連携） | ✅ IaC 完成 |
| `../docker/docker-compose.cloudflare-tunnel.yml` | Cloudflare Tunnel connector overlay（nginx host ports を閉じる） | ✅ 雛形 |
| `neon-config.md` | Neon PostgreSQL 接続設定・マイグレーション手順 | ✅ 文書完成 |
| `README.md` | 本ファイル | ✅ |

## 🚀 適用手順（人間 + CTO 協働、Issue #50 解除後）

### 現在の確認結果（2026-07-19）

| 項目 | 結果 |
|---|---|
| Cloudflare zone | `mirai-dx-platform.com` は `active` |
| Zone nameservers | `kareem.ns.cloudflare.com`, `nia.ns.cloudflare.com` |
| `legalops` DNS record | Cloudflare API / public resolver ともに未作成 |
| WebUI preview | `http://192.168.0.185:38100/` |
| systemd service | `construction-legalops-standalone-webui.service` |

`./scripts/verify_cloudflare_legalops.sh` は Cloudflare API token がある場合に Zone / DNS record の read-only 確認も実施します。

### 前提（人間が実施）

1. Cloudflare ダッシュボードで API token 発行（最小権限: Zone.DNS, Access, Tunnel, Pages）
2. Cloudflare Access self-hosted application `LegalOps-DX` を `legalops.mirai-dx-platform.com` に作成
3. Cloudflare Tunnel を作成し、Tunnel ID / token を取得
4. 人間承認後に DNS CNAME `legalops -> <TUNNEL_ID>.cfargotunnel.com` を作成
5. Neon プロジェクト作成・接続文字列発行
6. GitHub Secrets に以下を登録:
   - `CLOUDFLARE_API_TOKEN`
   - `CLOUDFLARE_ACCOUNT_ID`
   - `NEON_DATABASE_URL`
   - `NEON_PROJECT_ID`
   - `NEON_API_KEY`

### Phase 1: Cloudflare Tunnel（アプリ無改修・最速）

```bash
# DNS 作成（公開 DNS 変更のため、人間承認後のみ）
cloudflared tunnel route dns <TUNNEL_ID_OR_NAME> legalops.mirai-dx-platform.com

# cloudflared を compose overlay で起動（Tunnel token は Vault / secret manager から注入）
docker compose \
  -f infra/docker/docker-compose.yml \
  -f infra/docker/docker-compose.prod.yml \
  -f infra/docker/docker-compose.cloudflare-tunnel.yml \
  --profile worker \
  --profile cloudflare-tunnel up -d
```

DNS レコード案は `dns-records.legalops.example.json`、詳細手順は
`docs/CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK.md` を参照。

### Phase 2: Neon DB 移行

```bash
# データ移行
pg_dump $OLD_DB_URL | pg_restore -d $NEON_DATABASE_URL
# マイグレーション
alembic upgrade head
```

### Phase 3: Cloudflare Pages（フロントエンド）

```bash
# OpenNext adapter 導入後に有効化
npx wrangler pages deploy .next --project-name=legalops-dx
```

## 🔒 安全メモ

- Tunnel はアウトバウンド接続のみ（インバウンドポート開放不要）
- Tunnel overlay は nginx の host 公開ポートを閉じ、cloudflared が Docker network 内の `nginx:80` に接続する
- 全トークン・接続文字列は Vault / GitHub Secrets で管理、リポジトリへコミットしない
- Access ポリシー適用までは Tunnel URL を有効化しない（認証境界の先行確立）
- DNS 変更・課金プラン変更は本計画では実行しない（人間判断・人間実行）
