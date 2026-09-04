# 📌 ポート割当 — Construction-LegalOps-DX

> マルチプロジェクト共存ホストにおけるポート衝突回避のための**専用ポート割当**仕様。
> 本ドキュメントは `.env.example` / `infra/docker/docker-compose.yml` / `frontend/package.json` /
> `frontend/.env.local.example` / `README.md` から参照される**単一の真実 (single source of truth)** です。

---

## 📊 背景 — なぜ専用ポートが必要か

本リポジトリは、`CivilPDF-DX` をはじめとする 20+ のプロジェクトと**同一ホストを共有**しています。
各プロジェクトが既定ポート（`8000` / `3000` / `5432` / `6379` 等）をそのまま使うと、
**ホスト公開ポートが衝突**し、以下の事故が発生します。

| リスク        | 内容                                                                                |
| ------------- | ----------------------------------------------------------------------------------- |
| 🔴 API 誤接続 | ブラウザバンドルが**別プロジェクトのバックエンド**を叩く（トークン漏洩・CORS 混線） |
| 🔴 起動失敗   | `bind: address already in use` でコンテナ / dev サーバが起動しない                  |
| 🟠 データ混線 | 別プロジェクトの PostgreSQL / Redis に誤接続する                                    |

> **実例**: ホストポート `8000` は `CivilPDF-DX` のバックエンド (`uvicorn ... --port 8000`) が占有。
> 本プロジェクトが `NEXT_PUBLIC_API_URL=http://<host>:8000/api/v1` のままだと、
> WebUI が CivilPDF-DX の API を呼んでしまう。**→ 専用ポート 8010 へ移行して解消。**

---

## 🖥️ Native systemd 構成のポート（2026-09-04 以降の現行）

Docker 廃止後は以下がホストで稼働する（すべて 127.0.0.1 bind。公開は cloudflared 経由のみ）。

| 用途 | prod | mvp |
|---|---|---|
| backend (uvicorn) | 8011 | 8013 |
| frontend (Next standalone) | 3011 | 3013 |
| nginx (`legalops-nginx`) | 8410 | 8412 |
| Redis (`legalops-redis`, DB 0-2 / 4-6) | 6390 | 6390 |
| PostgreSQL (host cluster) | 5432 `legalops_prod` | 5432 `legalops_mvp` |

設定の正: `infra/native/systemd/*.service`、`infra/native/nginx/legalops-main.conf`、`/etc/legalops/*.env`。

## 📋 専用ポート割当表（ホスト公開ポート）（Compose 時代の記録）

> **重要原則**: 専用化するのは **ホスト公開ポート（`HOST:CONTAINER` の左側）のみ**。
> コンテナ内部ポートと `legalops-net` ブリッジ上のサービス間通信は**不変**（衝突しない）。

| サービス                         | ホスト公開ポート | コンテナ内部ポート | 環境変数         | 備考                                      |
| -------------------------------- | ---------------- | ------------------ | ---------------- | ----------------------------------------- |
| 🖥️ Frontend (Next.js)            | **3010**         | 3000               | `FRONTEND_PORT`  | 本番想定 WebUI                            |
| 🖼️ Standalone WebUI (検証用HTML) | **38100-38999**  | なし               | 自動選択         | SSH先Linux / systemd。status JSON を正とする |
| ⚙️ Backend (FastAPI)             | **8010**         | 8000               | `BACKEND_PORT`   | REST API                                  |
| 🐘 PostgreSQL 16                 | **5442**         | 5432               | `POSTGRES_PORT`  | ホスト直結デバッグ用                      |
| 🔴 Redis 7                       | **6392**         | 6379               | `REDIS_PORT`     | cache / Celery broker                     |
| 🌐 Nginx (HTTP)                  | **8410**         | 80                 | `NGINX_PORT`     | リバースプロキシ                          |
| 🔐 Nginx (HTTPS)                 | **8453**         | 443                | `NGINX_TLS_PORT` | TLS termination                           |
| 📊 Prometheus                    | **9090**         | 9090               | `PROMETHEUS_PORT`| `--profile monitoring`                    |
| 🚨 Alertmanager                  | **9093**         | 9093               | `ALERTMANAGER_PORT` | `--profile monitoring`                 |
| 📈 Grafana                       | **3000**         | 3000               | `GRAFANA_PORT`   | `--profile monitoring`。共存時は変更推奨 |
| 📝 Loki                          | **3100**         | 3100               | `LOKI_PORT`      | `--profile logging`                       |

> 🖼️ Standalone WebUI の現在URL、PID、停止コマンドは
> `reports/webui/standalone-webui.json` を参照する。起動は
> SSH先Linux上で `bash scripts/install_standalone_webui_systemd.sh --user install`。
> systemd unit 名は `construction-legalops-standalone-webui.service`。
> Windows 端末から SSH 越しに操作する場合は
> `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/Invoke-StandaloneWebUILinux.ps1 -HostName <linux-host> -RemoteRepo /path/to/Construction-LegalOps-DX -Action status`。
> 変更前確認は同コマンドに `-DryRun` を付ける。
> HTTP health は `-Action health` で確認する。

### 内部通信（不変・専用化しない）

| 接続                     | URL                                               | 理由                  |
| ------------------------ | ------------------------------------------------- | --------------------- |
| backend → postgres       | `postgresql+asyncpg://...@postgres:5432/legalops` | コンテナ間は内部 5432 |
| backend → redis          | `redis://redis:6379/0`                            | コンテナ間は内部 6379 |
| frontend → backend (SSR) | `http://backend:8000`（`BACKEND_INTERNAL_URL`）   | コンテナ間は内部 8000 |

---

## 🔧 フロントエンド API URL の 3 変数モデル（混同注意）

Next.js フロントは API ベース URL を **3 つの異なる変数**で扱います。**用途が異なるため統合不可**。

| 変数                       | 参照箇所                                             | `/api/v1` 付与                 | 値の例                               |
| -------------------------- | ---------------------------------------------------- | ------------------------------ | ------------------------------------ |
| `NEXT_PUBLIC_API_URL`      | ブラウザ axios (`lib/api/client.ts`)                 | **含む**                       | `http://localhost:8010/api/v1`       |
| `NEXT_PUBLIC_API_BASE_URL` | サーバー認証 (`auth.config.ts` / `refresh-token.ts`) | **含まない**（コード側で付与） | `http://localhost:8010`              |
| `BACKEND_INTERNAL_URL`     | サーバーサイド最優先オーバーライド                   | コード側で付与                 | `http://backend:8000`（Docker 内部） |

> ⚠️ `NEXT_PUBLIC_*` は**ビルド時にブラウザバンドルへ焼き込まれる**。
> よってビルド時点で**ホスト公開ポート (`8010`) を指す**必要がある（実行時の `environment:` では再焼き込みされない）。

優先順位（サーバーサイド）: `BACKEND_INTERNAL_URL` > `NEXT_PUBLIC_API_BASE_URL`

---

## 🛠️ 設定の反映先（変更時はすべて同期すること）

| ファイル                          | 役割                                              | 同期対象                                        |
| --------------------------------- | ------------------------------------------------- | ----------------------------------------------- |
| `.env.example`                    | コミット対象の env テンプレート                   | 全ポート変数・両 `NEXT_PUBLIC_*`                |
| `infra/docker/docker-compose.yml` | compose フォールバック既定値（`${VAR:-default}`） | 全 `ports:` マッピング・frontend `environment:` |
| `frontend/package.json`           | `dev` / `start` の `-p` ポート                    | `3010`                                          |
| `frontend/.env.local.example`     | ローカル開発 env テンプレート                     | 両 `NEXT_PUBLIC_*`                              |
| `README.md`                       | 外向けアクセス URL 表・dev コマンド               | `3010` / `8010` / `8410`                        |

> **補足**: `docker compose -f infra/docker/docker-compose.yml` はプロジェクトディレクトリを
> `infra/docker/` に設定するため、`${VAR:-default}` の補間は `infra/docker/.env`（通常不在）を見る。
> したがって**compose 側フォールバック既定値**と**`.env.example` 既定値の両方**を専用ポートに揃える必要がある。
> `env_file: - ../../.env` は別機構で、リポジトリルートの `.env` をコンテナ環境変数へ注入する。

---

## 📈 ホスト稼働ポートの確認方法

```bash
# 特定ポートが空いているか（出力が空なら FREE）
ss -tlnH '( sport = :8010 )'

# ポート占有プロセスの所有プロジェクト特定
pid=$(ss -tlnpH '( sport = :8000 )' | grep -oP 'pid=\K[0-9]+' | head -1)
readlink -f /proc/$pid/cwd      # → 所有プロジェクトのパス
tr '\0' ' ' < /proc/$pid/cmdline # → 起動コマンド
```

---

## 🗺️ 他プロジェクトとの棲み分け（参考）

ホスト上の代表的な占有状況（2026-06 時点）:

| ポート帯                                                | 用途                    | 例                                  |
| ------------------------------------------------------- | ----------------------- | ----------------------------------- |
| `8000`                                                  | 他プロジェクト backend  | CivilPDF-DX (`uvicorn --port 8000`) |
| `8001`–`8003`, `8020`, `8400`                           | 他プロジェクト各種 API  | —                                   |
| `3000`, `3001`, `3003`                                  | 他プロジェクト frontend | —                                   |
| `5432`–`5436`                                           | 各種 PostgreSQL         | —                                   |
| `6379`, `6380`                                          | 各種 Redis              | —                                   |
| **`8010` / `3010` / `5442` / `6392` / `8410` / `8453` / `9090` / `9093` / `3100`** | **本プロジェクト専用**  | Construction-LegalOps-DX            |

> 新しいポートを追加する場合は、必ず本表に追記し、上記「設定の反映先」をすべて同期すること。
