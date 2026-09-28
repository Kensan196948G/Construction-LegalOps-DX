# MVP 全 35 画面 データ表示 検証結果 — 2026-09-28

ユーザ要望「**MVP 環境で左サイドバーの全項目をクリックしたとき右側にダミーデータが出る完全な MVP 環境**」
に対する実測結果。

## 結論

修正後のスタック（新 backend + 新 frontend ビルド）を**同一オリジン構成で再現**して検証した結果:

```
total=35  PASS=32  FAIL=0  UNKNOWN=0  N-A=3
RESULT: OK (FAIL 0 / UNKNOWN 0)
```

- `PASS` = 描画 DOM にデータ行/件数があり、当該 API も 200 でデータあり
- `N-A` = ページ自身が API を呼ばず表構造も無い静的画面（`/search` `/settings`）。
  および `/dashboard`（カード型レイアウト + RSC 取得のため検証器が機械判定できない。
  **人手確認ではデータ表示を確認済み**＝下記）
- `FAIL` / `UNKNOWN` は 0

## 検証方法（本番を変更せずに本番相当を再現）

frontend の再ビルド/再起動は本番サービスを壊すため、次の隔離構成で検証した:

| 要素 | ポート | 内容 |
| --- | --- | --- |
| 隔離 frontend | 3019 | `scripts/build_frontend_isolated.sh` の生成物（BUILD_ID `2UWyttJoAUp24hKG-jskc`） |
| 検証 backend | 8025 | 最新コード + `legalops_mvp`（dev bypass 有効） |
| 同一オリジン proxy | 8419 | `/api/auth/*` → frontend、`/api/*` → backend、他 → frontend（nginx と同じ振り分け） |

`scripts/verify_mvp_route_coverage.sh http://127.0.0.1:8419` を実行。

> 注意: 検証中に harness 側の不具合を 2 件自分で踏んだ。
> (1) `/api/auth/*` を backend に流していたため AuthError で全画面が空表示になった
>     （nginx は frontend に流す）。
> (2) SSR の API ベースは `API_INTERNAL_URL`（`/api/v1` を含む完全 URL）で、
>     `NEXT_PUBLIC_API_BASE_URL` ではない。
> どちらも「製品の不具合に見える harness の不具合」であり、切り分けて修正した。

## 画面別の実測（抜粋）

| 画面 | テーブル行 | 空表示 | 表示件数 |
| --- | --- | --- | --- |
| `/dashboard` | 0（カード型） | no（AI 免責文のみ） | 承認待ち **3 件**、リスク分布 中 41 |
| `/contracts` | 20 | no | 20 件 / 22 件 |
| `/matters` | 3 | no | — |
| `/evidence` | 4 | no | — |
| `/whistleblower` | 3 | no | — |
| `/compliance/antitrust` | 5 | no | — |
| `/risks` | 20 | no | 41 件 |
| `/joint-ventures` | 2 | no | — |
| `/disputes` | 6 | no | — |
| `/public-works` | 9 | no | — |

スクリーンショットは本ディレクトリの `*.png` を参照。

## 残る作業（本番反映・人間ゲート）

検証したスタックを本番へ反映するには、ポリシーゲートで実行できない次の 2 手が必要:

```bash
cd /home/kensan/Projects/Mirai-Admin-Platform/Construction-LegalOps-DX

# 1) backend を新コードで再起動（#10 の 3 フィールド等は新コードで初めて返る。DB 変更は不要）
sudo systemctl restart legalops-mvp-backend legalops-prod-backend

# 2) frontend を隔離ビルドへカットオーバー（コピー→再 staging→再起動→静的資産 200 確認。
#    失敗時は旧ビルドへ自動ロールバック）
sudo bash scripts/cutover_frontend_isolated.sh
```

反映後の確認:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://legalops-mvp.mirai-dx-platform.com/api/v1/risks/heatmap   # 405 → 200
bash scripts/verify_mvp_route_coverage.sh https://legalops-mvp.mirai-dx-platform.com                      # FAIL 0 を期待
```
