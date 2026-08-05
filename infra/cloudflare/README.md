# 🌐 infra/cloudflare — Cloudflare / Neon IaC 設定

> **ステータス: IaC コード完成 / Cloudflare edge 適用済み / 本番 deploy 承認待ち**
> このディレクトリのファイルは設定コードであり、置くだけでは何も起動・変更されません。
> `legalops.mirai-dx-platform.com` は新規サブドメイン要件として Cloudflare 側に作成済みです。親ドメイン `mirai-dx-platform.com` は取得済みで、Cloudflare zone は active です。CTO/Supervisor は DNS / Tunnel / Access の作成操作を実行していません。本番 deploy は Issue #50 の人間承認ゲートで停止します。

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

### 現在の確認結果（2026-07-20 Loop 108 / Cloudflare edge 適用後）

| 項目 | 結果 |
|---|---|
| Cloudflare zone | `mirai-dx-platform.com` は `active` |
| Zone nameservers | `kareem.ns.cloudflare.com`, `nia.ns.cloudflare.com` |
| `legalops` DNS record | Cloudflare API で `legalops.mirai-dx-platform.com` のレコード 1 件を read-only 確認済み。公開 DNS は Cloudflare proxy A/AAAA を返す |
| Cloudflare Access | 未認証 `https://legalops.mirai-dx-platform.com/healthz` は Cloudflare Access login 302 challenge で保護済み |
| `legalops` 要件 | 新規サブドメイン要件を反映済み。親ドメイン `mirai-dx-platform.com` は取得済み |
| ✅ サブドメイン | **`https://legalops.mirai-dx-platform.com` のみ** — 一本化方針により preview 用 `legalops-preview`（tunnel 459059b3-… / CNAME）は 2026-08-01 削除済み（NXDOMAIN 化・connector 停止を確認）。復元は CNAME / tunnel 再作成 |
| 🗄️ Neon | プロジェクト `Construction-LegalOps-DX` (`snowy-sound-99973684`, PG16, ap-southeast-1) 作成済み。詳細は `neon-config.md` |
| WebUI preview (LAN) | `http://192.168.0.185:38100/` |
| systemd service | `construction-legalops-standalone-webui.service` |
| ⚠️ 注意 | 本セッションでは DNS / Tunnel / Access / secret / deploy の変更操作を実行しない。secret 値はログ・文書へ出力しない |

`./scripts/verify_cloudflare_legalops.sh` は Cloudflare API token がある場合に Zone / DNS record の read-only 確認も実施します。

### 既存edge採用時（現在の `legalops.mirai-dx-platform.com`）

現在は Cloudflare API で `legalops.mirai-dx-platform.com` のレコード 1 件を read-only 確認済みで、未認証 `/healthz` は Cloudflare Access 302 challenge を返します。既存edgeを本番利用対象として採用する場合は、置換・重複作成を行わず、以下をread-onlyで確認します。

1. 対象 hostname が `legalops.mirai-dx-platform.com` であること
2. DNS record が `proxied=true` であること
3. Tunnel UUID / route / Access application の所有範囲が Issue #50 の承認範囲内であること
4. `CLOUDFLARE_ACCESS_ISSUER` / `CLOUDFLARE_ACCESS_AUD` がアプリ設定と一致すること
5. `/healthz` が Cloudflare Access login 302 に誘導され、direct origin を公開していないこと

### 未適用環境で新規作成する場合（人間が実施）

1. Cloudflare ダッシュボードで API token 発行（最小権限: Zone.DNS, Access, Tunnel, Pages）
2. Cloudflare Access self-hosted application `LegalOps-DX` を `legalops.mirai-dx-platform.com` に作成
3. Cloudflare Tunnel を作成し、Tunnel UUID / credentials JSON を取得
4. 人間承認後に DNS CNAME `legalops -> <TUNNEL_UUID>.cfargotunnel.com` を作成し、Cloudflare API post-check で一致確認
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
cloudflared tunnel route dns <TUNNEL_UUID> legalops.mirai-dx-platform.com

# 誤実行防止 helper（dry-run）。Tunnel UUID と post-check 予定を表示する
LEGALOPS_CLOUDFLARE_APPROVAL=APPROVE_LEGALOPS_CLOUDFLARE \
TUNNEL_UUID=<TUNNEL_UUID> \
./scripts/apply_cloudflare_legalops_after_approval.sh

# 誤実行防止 helper（公開 DNS 作成。人間の最終承認後のみ）
LEGALOPS_CLOUDFLARE_APPROVAL=APPROVE_LEGALOPS_CLOUDFLARE \
EXECUTE=1 \
TUNNEL_UUID=<TUNNEL_UUID> \
./scripts/apply_cloudflare_legalops_after_approval.sh

# cloudflared を compose overlay で起動（Tunnel credentials JSON は安全な host path へ配備）
docker compose \
  -f infra/docker/docker-compose.yml \
  -f infra/docker/docker-compose.prod.yml \
  -f infra/docker/docker-compose.cloudflare-tunnel.yml \
  --profile worker \
  --profile cloudflare-tunnel up -d
```

`TUNNEL_ID_OR_NAME` も使用できますが、helper は必ず UUID に解決してから `cloudflared tunnel route dns` を実行します。post-check で `legalops.mirai-dx-platform.com` の CNAME が `<UUID>.cfargotunnel.com` と一致しない場合は fail-close します。

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
- Access ポリシーを先に適用し、未認証アクセスが Cloudflare Access challenge で止まることを確認する
- DNS 変更・課金プラン変更は本計画では実行しない（人間判断・人間実行）
