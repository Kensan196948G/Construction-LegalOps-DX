# 🌐 infra/cloudflare — Cloudflare / Neon IaC 設定

> **ステータス: IaC コード完成（本番適用は人間による API token 発行・リソース作成後）**
> このディレクトリのファイルは設定コードであり、置くだけでは何も起動・変更されません。
> 本番適用には人間による以下の前提作業が必要です（Issue #50 参照）。

## 📌 構成

| ファイル | 役割 | 状態 |
|---|---|---|
| `wrangler.toml` | Cloudflare Pages 設定（Next.js デプロイ） | ✅ IaC 完成 |
| `tunnel-config.example.yml` | cloudflared Tunnel ルーティング設定テンプレート | ✅ 雛形 |
| `access-policy.yml` | Cloudflare Access ポリシー定義（Entra ID IdP 連携） | ✅ IaC 完成 |
| `neon-config.md` | Neon PostgreSQL 接続設定・マイグレーション手順 | ✅ 文書完成 |
| `README.md` | 本ファイル | ✅ |

## 🚀 適用手順（人間 + CTO 協働、Issue #50 解除後）

### 前提（人間が実施）

1. Cloudflare ダッシュボードで API token 発行（最小権限: Zone.DNS, Access, Tunnel, Pages）
2. `legalops.mirai-dx-platform.com` の DNS CNAME 作成
3. Neon プロジェクト作成・接続文字列発行
4. GitHub Secrets に以下を登録:
   - `CLOUDFLARE_API_TOKEN`
   - `CLOUDFLARE_ACCOUNT_ID`
   - `NEON_DATABASE_URL`
   - `NEON_PROJECT_ID`
   - `NEON_API_KEY`

### Phase 1: Cloudflare Tunnel（アプリ無改修・最速）

```bash
# cloudflared をサイドカー起動（Tunnel トークンは Vault 管理）
docker run -d --name cloudflared --network legalops-net \
  cloudflare/cloudflared:latest tunnel --no-autoupdate run --token <TUNNEL_TOKEN>
```

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
- 全トークン・接続文字列は Vault / GitHub Secrets で管理、リポジトリへコミットしない
- Access ポリシー適用までは Tunnel URL を有効化しない（認証境界の先行確立）
- DNS 変更・課金プラン変更は本計画では実行しない（人間判断・人間実行）