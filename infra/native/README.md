# 🖥️ Native (Docker-free) deployment — `infra/native/`

2026-09-04 に prod / mvp の両スタックを Docker Compose から host の systemd ユニットへ移行した（方針: Docker を今後使わない）。
Compose 定義（`infra/docker/`）と Dockerfile は履歴・参照用に残すが、運用の正は本ディレクトリ。

## 構成（すべて 127.0.0.1 bind、公開は cloudflared 経由のみ）

| ユニット | 役割 | ポート | 置き換えたコンテナ |
|---|---|---|---|
| `legalops-prod-backend` | FastAPI / uvicorn ×2 workers | 8011 | `construction-legalops-dx-backend-{1,2}` |
| `legalops-prod-celery-worker` | Celery worker (concurrency 4) | – | `construction-legalops-dx-celery-worker-{1,2}` |
| `legalops-prod-celery-beat` | Celery beat（schedule は `/run/legalops-beat/`） | – | `legalops-celery-beat` |
| `legalops-prod-frontend` | Next.js standalone (`node .next/standalone/server.js`) | 3011 | `construction-legalops-dx-frontend-{1,2}` |
| `legalops-mvp-backend` | FastAPI / uvicorn | 8013 | `construction-legalops-mvp-backend-1` |
| `legalops-mvp-frontend` | Next.js standalone | 3013 | `construction-legalops-mvp-frontend-1` |
| `legalops-nginx` | 専用 nginx master（`/etc/nginx/legalops-main.conf`） | 8410 (prod) / 8412 (mvp) | `legalops-nginx`, `construction-legalops-mvp-nginx-1` |
| `legalops-prod-cloudflared` | tunnel `legalops-prod` → 127.0.0.1:8410 | – | `legalops-cloudflared` |
| `legalops-mvp-cloudflared` | tunnel `legalops-mvp` → 127.0.0.1:8412（**remote-managed**、origin は Cloudflare 側の設定で保持） | – | `construction-legalops-mvp-cloudflared-1` |
| `legalops-redis` | 専用 Redis（`/etc/redis/legalops.conf`、requirepass、AOF） | 6390 | `legalops-redis`, `construction-legalops-mvp-redis-1` |
| host PostgreSQL 16 | DB `legalops_prod` / `legalops_mvp`（ロール同名） | 5432 | `legalops-postgres`, `construction-legalops-mvp-postgres-1` |

Redis 論理 DB: prod = 0 (cache + Celery broker/result 実体), 1, 2 / mvp = 4, 5, 6。

## 環境変数

`/etc/legalops/{prod,mvp}-{backend,frontend}.env`（root:root 0600、Git 管理外）。
初回は `migrate-env-from-docker.sh` がコンテナの env をそのまま写し、Docker 内部エンドポイントだけを書き換えた。
以後の変更はこのファイルを直接編集して `systemctl restart <unit>`。

## 日常運用

```bash
# 状態
systemctl status legalops-prod-backend legalops-prod-frontend legalops-mvp-backend legalops-mvp-frontend legalops-nginx
journalctl -u legalops-prod-backend -n 100 -f

# デプロイ（コード更新後）
git pull
sudo bash infra/native/install.sh --build     # venv 再構築 + Next build + ユニット再起動 + health 待ち
sudo systemctl reload legalops-nginx           # nginx 設定を変えた場合

# マイグレーション（DB_URL は env から）
sudo -u kensan env DB_URL="$(sudo grep -oP '^DB_URL=\K.*' /etc/legalops/prod-backend.env)" \
  bash -c 'cd backend && .venv/bin/alembic upgrade head'

# 死活
curl -s http://127.0.0.1:8410/healthz; curl -s http://127.0.0.1:8011/readyz
curl -s http://127.0.0.1:8412/readyz
```

## バックアップ / ロールバック

- DB は host PostgreSQL の通常バックアップに含める（`scripts/backup_db.sh` は Compose 前提なので `pg_dump -h 127.0.0.1 -U legalops_prod legalops_prod` を使う）。
- 移行時のダンプと最終 resync ダンプ: `~/backups/docker-exit/2026-09-04/`。
- Docker のボリューム（`legalops-pgdata`, `construction-legalops-mvp_mvp-pgdata`, `legalops-redisdata`）は削除していない。
  ロールバックは native ユニット stop → `docker start` で各コンテナを戻す → mvp tunnel の remote origin を `http://nginx:80` に戻す。

## 注意

- mvp トンネル（`e86543a8…`）は Cloudflare 側で管理される remote config。ローカル yml の `service:` は無視されるため、origin を変えるときは API / ダッシュボードで変更する。prod（`3e1bddee…`）はローカル yml 管理。
- prod は Cloudflare Access 配下（未認証は 302）。`/api/auth/*` は NextAuth なので nginx で frontend へ振り分ける（`legalops-main.conf`）。
- Next.js の browser bundle は相対 `/api/v1` を使う（同一オリジン前提）。`NEXT_PUBLIC_API_URL` を絶対 URL にしない。
