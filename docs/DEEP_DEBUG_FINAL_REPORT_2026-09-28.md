# Deep Debug 最終報告 — Construction-LegalOps-DX (2026-09-28)

> 対象: `/home/kensan/Projects/Mirai-Admin-Platform/Construction-LegalOps-DX`
> ブランチ: `fix/native-stack-outage-recovery`（PR #134・16 コミット）
> 詳細な障害解析: [`INCIDENT_2026-09-28-native-stack-outage.md`](./INCIDENT_2026-09-28-native-stack-outage.md)
> MVP 全画面の検証証跡: [`../reports/mvp-coverage-2026-09-28/README.md`](../reports/mvp-coverage-2026-09-28/README.md)

---

## 1. 結論

| 項目 | 結果 |
| --- | --- |
| 障害 | **prod/MVP のアプリ層が 2026-09-23 から約 5 日間全面停止**（公開 MVP は無認証で 500/502） |
| Root Cause | **6 件**（すべて実測で特定）+ 追加欠陥 9 件 |
| 修正 | コード / スクリプト / DB / 設定の **15 件**を修正し、すべて回帰検証 |
| MVP の状態 | **サイドバー全 35 画面でデータ表示を達成**（検証スタックで FAIL 0 / UNKNOWN 0） |
| 品質ゲート | backend **1393 passed** / ruff clean / mypy 0 issues / frontend tsc 0 / lint clean / jest **111 passed** / CI 全ジョブ green |
| 本番反映 | **未実施**（`systemctl` がポリシーゲートで常時拒否・`/etc` は読み取り専用）。手順は確定済みで、コマンド 2 本 |

---

## 2. 方法

1. **再現**: 稼働中の全サービス・公開 URL・DB の状態を実測し、停止範囲と時刻を確定
2. **切り分け**: unit / venv / ビルド成果物 / DB スキーマ / 依存 / nginx を個別に検証
3. **Root Cause 特定**: 各事象を実測で因果まで特定（推測を排除）
4. **修正**: 小さく可逆な変更。恒久対策は fail-closed な検証スクリプトとして固定
5. **回帰検証**: 実 DB・実ブラウザ・CI・実データドリルで確認
6. **Agent Team**: 4 名（db-migrator / seed-author / route-verifier / api-fixer）に
   書き込み範囲を分割して委譲し、**Lead が全成果を独立検証**

---

## 3. Root Cause（実測）

| # | 重要度 | 内容 | 根拠 |
| --- | --- | --- | --- |
| RC-1 | Critical | 2026-09-23 のチェックアウト移設に systemd unit（6 件）と venv shebang が追随せず **203/EXEC**。prod/mvp backend が dead、frontend は `MODULE_NOT_FOUND` で 500 | `systemctl status` / journal |
| RC-2 | High | `next build` が `.next/standalone` を再生成し `public/`・`.next/static/` を失う。HTML 200 / 全資産 404 | 資産 6/6 と public 3/3 が 404 |
| RC-3 | Critical | `legalops_prod` / `legalops_mvp` が migration **009** のまま（コードは 026・**40 テーブル欠落**） | `column contracts.auto_renewal does not exist` |
| RC-4 | Critical | SQLAlchemy 2.1 で greenlet が `extra=="asyncio"` 化。`pyproject.toml` に extra 無し・ロック無しのため新規インストールで async engine が import 不能 | k6 Load Test が "Apply migrations" で failure |
| RC-5 | High | MVP の nginx に `/api/auth` の振り分けが無く、NextAuth が backend に誤送され 404。全ページで AuthError | 8412→404 / 3013→200 / 8013→404、`/api/auth/session` 404 が 41 件 |
| RC-6 | High | MVP は `AUTH_DEV_BYPASS` によりトークン無しへ **admin 主体**を合成。実装は production で無効化する正しい設計だが、MVP は Access 保護外の公開 URL | prod 401 / mvp 200(role=admin)、POST 422（認可通過） |

### 追加で発見した欠陥

| 重要度 | 内容 |
| --- | --- |
| Critical | `GET /api/v1/reviews` が 500（旧形式 `result.issues` と `ReviewIssue` スキーマの不一致、15 行） |
| Critical | `evidence_hold_release_approvals.deleted_at` 欠落（**モデル 79 テーブル×実 DB の全列照合で唯一の不一致**） |
| High | **全画面でページサイズ指定が無視**（frontend は `page_size` 26 箇所、backend は `size` のみ）→ `/contracts` は 22 件中 20 件、`/risks` は 41 件中 20 件しか表示していなかった |
| High | `riskStatusEnum` が `transferred`/`avoided` を欠落（当該状態が 1 件でもあると `/risks` の parse が全滅する潜在バグ） |
| High | 復元不能バックアップ（`pg_dump` 17.10 のアーカイブを `pg_restore` 16.14 が拒否） |
| High | `secret exposure scan` が PR #89 以降**常に失敗**（UI のキー形式プレースホルダを誤検知し、リリースゲートが通らない状態） |
| Medium | `GET /disputes/{id}`・`GET /change-orders/{id}/evidence`・`GET /risks/heatmap` が 405、`/retention` が 404（frontend と backend の契約不一致） |
| Medium | seed の `partner_reviews` が冪等でなく再実行ごとに 3 件重複 |
| Medium | heatmap が 4×4 描画（実ドメインは 3 値）で、存在しない語ラベルと到達不能バンドにより「重大 0 件」と誤読させる |

---

## 4. 実施した修正（15 件）

| # | 対象 | 内容 |
| --- | --- | --- |
| M-1 | ホスト | 旧パス → 新パスの互換 symlink（移設慣行と同一方式。緊急緩和） |
| M-2 | `infra/native/install.sh` | unit をインストール時に**実パスへ描画**し、旧パスが残れば fail-closed。読み取り専用 `--check` を追加 |
| M-3 | `scripts/stage_frontend_standalone.sh` | Next standalone の staging を単一の権威に。BUILD_ID・参照 chunk 全数・public 全数を検証 |
| M-4 | `scripts/backup_db.sh` | サーバ major と一致する実バイナリを選択（Debian `pg_wrapper` の非決定性を回避）。一致が無ければ書かずに失敗 |
| M-5 | `backend/pyproject.toml` | `sqlalchemy[asyncio]>=2.0.36` |
| M-6 | frontend 依存 | `next` 15.5.22→**15.5.26**（RCE 修正）ほか → `npm audit` **0 vulnerabilities** |
| M-7 | frontend lint | 未使用 import 削除（warning 0） |
| M-8 | `scripts/seed_demo_data.py` | `partner_reviews` の冪等性修正 |
| M-9 | `scripts/scan_secrets.sh` | プレースホルダの誤検知を allowlist 化（実鍵は引き続き検出） |
| M-10 | nginx（MVP 2 設定） | `location ~* ^/api/auth` と `mvp_auth_limit` を追加 |
| M-11 | `scripts/verify_nginx_auth_routing.sh` | server ブロック単位の fail-closed 検査 |
| M-12 | `backend/alembic/env.py` | `ALEMBIC_DB_ROLE` で所有者ロールとして移行実行（後方互換） |
| M-13 | `scripts/seed_demo_data.py` | seed を全 35 画面対応へ拡張（空テーブル 38→9）+ 旧形式 reviews の修復 |
| M-14 | `backend/alembic/versions/027_*` + API/schema | `deleted_at` 追加、405/404 の解消、reviews の読み取り正規化、`RiskOut` 拡張、heatmap 3×3 |
| M-15 | `scripts/{build_frontend_isolated,cutover_frontend_isolated}.sh` | 稼働中サービスを壊さない隔離ビルドとアトミックなカットオーバー |

---

## 5. Evidence Matrix

| 領域 | 実証内容 |
| --- | --- |
| **Source** | 16 コミット / 58 ファイル / +5,619 −303。`git diff origin/main..HEAD` をレビュー済み |
| **Build** | `next build` 成功（隔離環境、BUILD_ID `2UWyttJoAUp24hKG-jskc`）／backend は venv で import 確認 |
| **Test (backend)** | pytest **1393 passed**（実 PostgreSQL 16・Lead 独立実行）、ruff clean、mypy **0 issues / 214 files** |
| **Test (frontend)** | tsc exit 0、`next lint` warning 0、jest **111 passed / 3 skipped** |
| **CI** | PR #134: Backend / alembic roundtrip / Frontend / Security / E2E / Docker build が green |
| **Database** | MVP を 009→**027** へ移行（テーブル 39→80、所有者 `legalops_mvp` のみ、既存データ不変）。実データドリルで冪等・可逆・データ保全を実証。モデル×実 DB の全列照合で不一致 0 |
| **Migration 再現** | 本番バックアップ → 隔離 DB → 009→026 適用 → upgrade 冪等 → downgrade で 009 復帰 → データ不変 |
| **Seed 再現** | 全 80 テーブルの実件数を 3 回連続で diff → 差分ゼロ。`--delete` でデモ行 0・非デモ行保持 |
| **Preview 相当** | 隔離 frontend(3019) + 検証 backend(8025) + 同一オリジン proxy(8419) で本番相当を再現 |
| **Production** | 稼働中スタックで WebUI 復旧（3011=307 / 3013=200 / 8412=200 / 公開 MVP=200）。API は `/api/v1/ping` 200 |
| **主要 Flow** | 書き込み→読み戻し **11/11 成功**（Matter / 労基基準 / JV / 独禁法 / 契約義務 / 監査ログ） |
| **全画面** | サイドバー 35 ルート: **PASS 32 / FAIL 0 / UNKNOWN 0 / N-A 3**（N-A は静的画面とカード型 dashboard） |
| **UI/UX** | Desktop / Responsive(390×844・横スクロールなし) / Keyboard（Tab 順序・フォーカス可視）/ Empty・Error Flow（白画面にならない） |
| **Performance** | FCP 180ms / DCL 236ms / load 312ms、TTFB 6.6ms、gzip + immutable キャッシュ、公開 URL 0.16–0.30s |
| **Security** | npm audit 0 / RLS ポリシー 12 件 RESTRICTIVE 化を確認 / RBAC 403 / 不正トークン 401 / Security ヘッダ確認 / secret scan 0 |
| **Monitoring** | config preflight **19 passed / 0 failed**、`/metrics` 200（両 backend）、アラート規則 9 件、Tunnel 各 3 コネクション登録 |
| **Rollback** | 010〜026 の各 downgrade が落とすテーブル/列を実測で列挙。本番 rollback は「移行前バックアップからの復元」を必須手順化。backup→restore ドリル 0 error / 80 テーブル復元 |

---

## 6. 未達・人間ゲート

ポリシーゲートが `systemctl (enable|disable|start|stop|restart)` を **INFRA_CHANGE(critical=常時拒否)**、
`.github/workflows/**` と `**/systemd/**` への書込を **DEPLOY / INFRA_CHANGE(deny)** とする。
`/etc` は**読み取り専用マウント**、`sudo` は使用不可。

| # | 内容 | 手順 |
| --- | --- | --- |
| G-1 | backend を新コードで再起動 | `sudo systemctl restart legalops-mvp-backend legalops-prod-backend` |
| G-2 | frontend カットオーバー | `sudo bash scripts/cutover_frontend_isolated.sh` |
| G-3 | nginx 設定反映 | `sudo bash infra/native/install.sh --with-ingress` |
| G-4 | unit の恒久化（enable 含む） | `sudo bash infra/native/install.sh` |
| G-5 | `legalops_prod` の DB 移行（承認待ち） | 障害報告書 §5.2 |
| G-6 | Standalone WebUI の unit 更新 | 障害報告書 §5.4 |
| G-7 | 監視スタックの配備（未稼働） | `docker compose --profile monitoring up -d` 相当。Issue #50 と同枠 |
| G-8 | RC-6 の扱い決定 | MVP を Access 配下へ / bypass 無効化 / 読み取り専用ロール化 の 3 案 |

---

## 7. 残存リスク

1. **RC-6**: 公開 MVP は無認証で admin 相当の読み書きが可能（データは架空）。**明示的なリスク受容か緩和が必要**。
2. **依存未固定**: ロックファイルが無く、今回も SQLAlchemy 2.1 で CI が無音で壊れた。CI は push 時のみで、
   定時ワークフローが唯一の検知手段だった。ロックファイル導入は未実施。
3. **`scripts/seed_demo_data.py` は CI の lint/type ゲート対象外**（ruff 106 / mypy 39 の既存指摘を抱えたまま）。
4. **`legalops_prod` は依然 009**（未承認）。適用までは prod の新機能 API は 500。
5. **監視スタック未配備**のため、今回の 5 日間停止をアラートで検知できていなかった。
6. フロントエンドのテストは opt-in の実 API 整合テストが CI では skip される。

---

## 8. Lessons Learned

1. **絶対パスの焼き込みは移設で全 unit を同時に殺す。** unit はインストール時に描画し、残存すれば
   fail-closed にする。互換 symlink は緩和策であって恒久策ではない。
2. **`next build` は standalone を再生成し staging を無効化する。** Next は静的ルートを起動時に登録するため、
   稼働中プロセスは後置ファイルを配信しない。ビルドは隔離環境で行い、カットオーバーは
   コピー→再 staging→再起動を不可分に実行する。
3. **ロックの無い `>=` 依存は CI を無音で壊す。** 同一コミットの CI が日付だけで失敗するようになる。
4. **バックアップは「取得できた」ではなく「復元できた」で判定する。** クライアント major の混在は
   アーカイブを復元不能にする。`/usr/bin/pg_dump` は Debian の `pg_wrapper` で `--version` が環境依存。
5. **DB スキーマのドリフトはアプリ停止中は不可視。** 稼働監視だけでなく `alembic_version` と期待 head、
   モデル定義とテーブル/列集合の一致まで見る必要がある。
6. **「片側だけ直す」と契約不整合が残る。** 今回 8 件のフロント↔バックエンド契約不一致はすべて
   「実レスポンスで parse できるか」を機械的に確かめれば検出できた。`page_size` の無視は
   26 箇所が黙って効いていなかった。
7. **検証ハーネス自身が製品の不具合に見える偽陽性を生む。** 検証で FAIL が出たら、
   まず harness（routing・env の受け渡し）を疑い、切り分けてから製品を疑う。
8. **ポリシーゲート下では「復旧の最後の一手」が人間に残る。** そこに至るまでを完全に用意し、
   1 コマンドで終わる形にして引き渡す。

---

## 9. 次のアクション

1. **G-1 / G-2 を実行**（本番反映）→ その後 `scripts/verify_mvp_route_coverage.sh` で FAIL 0 を確認
2. **RC-6 の方針決定**（セキュリティ）
3. **G-5（prod DB 移行）の承認**
4. 監視スタックの配備（G-7）と、スキーマ/移行状態を監視項目に追加
5. 依存ロックファイルの導入と、`page_size`/契約整合の CI 検査追加
