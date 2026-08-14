# 🧪 Construction-LegalOps-DX — MVP / Prototype 運用ガイド

> 📌 本番運用は対象外。本ドキュメントは「関係者が直ちに操作・評価できる
> MVP/Prototype 環境」の URL・構築手順・デモ手順・ダミーデータを定義する。
> 最終更新: 2026-08-14

## 🗺️ URL 構成（本番と MVP の分離）

| 🎯 用途 | 🌐 URL | 📌 状態 |
|---|---|---|
| 🏭 本番 | `https://legalops.mirai-dx-platform.com` | Cloudflare Access 保護で運用中（人間ゲート #23/#24/#50） |
| 🧪 MVP 公開 | `https://legalops-mvp.mirai-dx-platform.com` | ✅ 稼働中（Cloudflare Tunnel `legalops-mvp` + Cloudflare proxy。削除後の再作成は `scripts/apply_mvp_legalops_after_approval.sh`） |
| 🖥️ MVP 即時確認（UI + API） | `http://127.0.0.1:8412/` | `docker-compose.mvp.yml` スタック（nginx 経由。UI は `/`、API は `/api/v1/*`） |
| 🖥️ Standalone WebUI | `http://192.168.0.185:38100/` | systemd: `construction-legalops-standalone-webui.service`（単一 HTML デモ） |

⚠️ MVP コンテナ（compose プロジェクト `construction-legalops-mvp`）は
`restart: unless-stopped` で起動し、ダミーデータを保持したまま停止しない。
本番 overlay（`legalops-*` / `construction-legalops-dx-*`）とは別の compose
プロジェクト・別 Docker network（`construction-legalops-mvp_mvp-net`）で分離する。

## 🧱 MVP スタック構成（`infra/docker/docker-compose.mvp.yml`）

| 🐳 サービス | 🖼️ 内容 |
|---|---|
| `postgres` | PostgreSQL 16（`legalops` DB、volume `mvp-pgdata`） |
| `redis` | Redis 7（celery broker/result、AOF） |
| `seed` | `alembic upgrade head` → `scripts/seed_demo_data.py` を自動実行（使い捨て） |
| `backend` | FastAPI（`APP_ENV=staging`・`AUTH_DEV_BYPASS=true`） |
| `frontend` | Next.js standalone（同オリジン `/api/v1/*` を nginx 経由で backend へ） |
| `nginx` | `127.0.0.1:8412` で公開（`infra/nginx/mvp.conf`） |
| `cloudflared` | MVP 公開時に `legalops-mvp` Tunnel へ接続（creds は host から mount） |

## 🔧 起動・再構築手順

```bash
cd /home/kensan/Projects/Mirai-DX-Project/Construction-LegalOps-DX
docker compose -f infra/docker/docker-compose.mvp.yml up -d --build
# seed サービスが migration + ダミーデータ投入を自動実行する
curl -fsS http://127.0.0.1:8412/healthz   # → ok
curl -fsS http://127.0.0.1:8412/readyz    # → ok (DB/依存サービスの deep check)
```

再投入（冪等・既存行スキップ）:

```bash
docker compose -f infra/docker/docker-compose.mvp.yml run --rm seed
docker compose -f infra/docker/docker-compose.mvp.yml down   # 停止
docker compose -f infra/docker/docker-compose.mvp.yml down -v # volume 削除（データ破棄）
```

## 🎭 ダミーデータ（すべて架空・再生成可能）

`scripts/seed_demo_data.py` が投入するデータ（冪等・識別子プレフィックスで判別可能）:

| 📋 種別 | 🔢 件数 | 🔖 識別子例 |
|---|---|---|
| 契約 | 22 | `CTR-2026-0001`〜（架空企業名・架空案件名） |
| 契約レビュー / リスク | 15 / 41 | `REV-` / `RISK-` |
| 承認ワークフロー（定義・ステップ） | 1 / 30 | `DEMO-LEGAL-001` |
| 協力会社台帳 | 12 | 架空許可番号（`デモ大臣許可…` 等） |
| 紛争・クレーム | 6 | `DSP-2026-0001`〜 |
| 支払イベント | 32 | `PAY-<契約番号>-NN`（期日超過 `late`・手形 `promissory_note` の異常系を含む） |
| 変更契約 | 6 | `CHG-2026-0001`〜 |
| 契約テンプレート / ナレッジ / 通知 | 5 / 5 / 5 | `DEMO-UC-001` 等 |
| 監査ログ（デモフラグ付き） | 68 | `demo=true` payload |

- 👤 人物名・企業名・案件名・許可番号・金額・日付はすべて架空値。
  画面には「デモ」表示を付与し、実在情報と混同しない。
- 🔁 再投入: `docker compose -f infra/docker/docker-compose.mvp.yml run --rm seed`
  🗑️ 削除: `python scripts/seed_demo_data.py --delete`（DB 接続先を MVP に設定して実行）。
  監査ログは append-only のため削除対象外。
- ✅ 正常系・境界値・異常系の例:
  許可期限 18 日後（境界）/ 反社確認 `pending` / 倒産リスク `high` の協力会社、
  支払期日超過 `late`、下請契約への手形払い（取適法違反候補）、
  回答期限経過の変更契約（失権リスク警告）など。

## 🕹️ デモシナリオ（認証不要）

`AUTH_DEV_BYPASS=true` のため、Authorization ヘッダなしで
`demo@legalops-mvp.example.invalid`（admin ロール）として動作する。

```bash
curl -fsS http://127.0.0.1:8412/healthz
curl -fsS 'http://127.0.0.1:8412/api/v1/dashboard/summary'
curl -fsS 'http://127.0.0.1:8412/api/v1/contracts?limit=5'
curl -fsS 'http://127.0.0.1:8412/api/v1/contracts?q=下請'
curl -fsS 'http://127.0.0.1:8412/api/v1/partners?size=100'
curl -fsS 'http://127.0.0.1:8412/api/v1/disputes?size=100'
curl -fsS 'http://127.0.0.1:8412/api/v1/change-orders?size=100'
curl -fsS 'http://127.0.0.1:8412/api/v1/contracts/4/payment-compliance'
curl -fsS 'http://127.0.0.1:8412/api/v1/audit-logs?limit=10'
```

画面側は `http://127.0.0.1:8412/` をブラウザで開き、ダッシュボード →
契約一覧/詳細 → 協力会社 → 紛争 → 支払コンプライアンス → 監査ログの順に確認する。

## ☁️ MVP 公開 URL の作成（人間ゲート）

公開用 `legalops-mvp.mirai-dx-platform.com` は、本番と同じ Cloudflare zone への外部
書き込みを伴うため、以下の前提が揃うまで作成しない（既存 Issue #50 の方針）:

1. 👤 Cloudflare 側で `CLOUDFLARE_API_TOKEN`（Zone DNS 編集 + 参照権限）を発行
2. 🛰️ `cloudflared tunnel create legalops-mvp` で Tunnel UUID を確定
3. ✅ 人間の明示的承認

```bash
CLOUDFLARE_API_TOKEN=<token> \
MVP_LEGALOPS_CLOUDFLARE_APPROVAL=APPROVE_MVP_LEGALOPS_CLOUDFLARE \
MVP_TUNNEL_UUID=<uuid> EXECUTE=1 \
./scripts/apply_mvp_legalops_after_approval.sh
```

このヘルパーは `apply_cloudflare_legalops_after_approval.sh` に委譲し、UUID 明示・
Cloudflare API の CNAME post-check・Access チャレンジ確認まで行う。
ロールバック: 対象 CNAME（`legalops-mvp`）を削除して Tunnel connector を停止する。

## ⚠️ 既知の制約

- 🔌 外部連携（SharePoint Graph / Exchange・Teams / desknet's / Claude API）は MVP では
  stub・disabled・fail-closed。疑似 URL や偽の成功を返さない。
- 🧠 AI レビューは `AI_REVIEW_STUB=1` のヒューリスティック出力。本物の法的判断はしない。
- 🛡️ RLS / 案件単位 ACL は PostgreSQL 限定（SQLite では無効）。
- 🔑 dev bypass は `APP_ENV=staging|development` かつ `AUTH_DEV_BYPASS=true` の両方が
  揃った時のみ有効。production では構造的に発動しない（`backend/app/deps.py`）。
- 🖥️ フロントは NextAuth を dev bypass で迂回して動作するため、SSO/Cloudflare Access の
  実運用フローは本番 URL でのみ確認できる。
