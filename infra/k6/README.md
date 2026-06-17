# k6 負荷テスト — Construction LegalOps DX

## 📌 概要

[k6](https://k6.io/) を使った負荷テストスイート。3 つのシナリオでバックエンド API の SLO を検証します。

**SLO 目標:** `p(95) < 500ms` / エラー率 `< 1%`

## 📊 シナリオ一覧

| シナリオ | VU | 期間 | 用途 |
|---|---|---|---|
| `smoke` | 5 VU | 30s | リリース前の基本動作確認 |
| `load` | 最大 20 VU | 約 5min（ramp/hold/down）| SLO ゲート（目標 50+ req/s） |
| `soak` | 10 VU | 10min | メモリリーク・経時劣化の検出 |

## 🔧 ローカル実行手順

### 前提

```bash
# k6 のインストール（macOS）
brew install k6

# k6 のインストール（Ubuntu）
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
  | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install k6
```

### バックエンドを起動

```bash
cd backend
APP_ENV=test uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### テスト実行

```bash
# smoke（最速確認）
k6 run -e SCENARIO=smoke infra/k6/load-test.js

# load（SLO 検証）
k6 run -e SCENARIO=load infra/k6/load-test.js

# soak（安定性検証）
k6 run -e SCENARIO=soak infra/k6/load-test.js
```

### 認証付きエンドポイントをテストする場合

```bash
# JWT_TOKEN を設定すると /api/v1/contracts などの認証エンドポイントも検証する
k6 run -e SCENARIO=load -e JWT_TOKEN="<bearer_token>" infra/k6/load-test.js
```

### 別のターゲットに向ける

```bash
# ステージング環境など
k6 run -e SCENARIO=smoke -e BASE_URL=https://staging.example.com infra/k6/load-test.js
```

## ⚙️ CI（GitHub Actions）

`.github/workflows/load-test.yml` で定義：

| トリガー | シナリオ | 説明 |
|---|---|---|
| `workflow_dispatch` | 任意選択 | 手動実行（リリース前検証など） |
| weekly schedule（月曜 02:00 JST）| smoke | 定期ヘルスチェック |

**手動実行:**
1. Actions → "Load Test (k6)" → "Run workflow"
2. `scenario` = `smoke` / `load` / `soak` を選択
3. `base_url` を指定（省略時 `http://localhost:8000`）

## 📈 計測エンドポイント

| エンドポイント | 認証 | 計測対象 |
|---|---|---|
| `GET /healthz` | 不要 | liveness（プロセス応答のみ） |
| `GET /ping` | 不要 | 疎通確認（最軽量） |
| `GET /readyz` | 不要 | DB SELECT 1 + Redis ping |
| `GET /api/v1/contracts` | 必要 | DB 一覧クエリ |
| `GET /api/v1/reviews` | 必要 | DB 一覧クエリ |
| `GET /api/v1/risks` | 必要 | DB 一覧クエリ |
| `GET /api/v1/knowledge` | 必要 | ハイブリッド検索 |

## 🔁 結果の読み方

k6 は実行終了時に自動でサマリーを出力します：

```
=============================================================
[k6] Scenario: SMOKE
[k6] p(95): 42.3ms
[k6] Error rate: 0.00%
[k6] ✅ PASS — SLO 達成 (p95 < 500ms, error < 1%)
=============================================================
```

詳細な JSON 結果は `k6-results.json`（CI では Artifact としてダウンロード可能）。
