# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added / Changed (2026-09-05: 労務費基準マスタ・乖離率判定 Issue #111)

- **💰 労務費基準マスタ（Phase 2 起点・ロードマップ #16〜#20 / Issue #111）**:
  - `labor_wage_standards`: 工種（土木/とび・土工/舗装/解体/鉄筋/コンクリート等）×
    都道府県 × 適用開始日（effective_from/to）の基準日額を**履歴蓄積**（#16 更新型）
  - as-of 日時点の最新値解決（#17 工種別・#18 都道府県別）
  - **乖離率判定（#20）**: 見積単価 vs 基準値で ratio / shortage_rate / status
    （ok・below=ダンピング確認入力 #21 に接続予定）を決定論的に算出（AI 不使用）
  - API: `GET/POST /labor-wage/standards`・`GET /standards/latest`・`GET /discrepancy`
    （登録は監査ログへ）
  - Alembic `015_labor_wage`（down_revision=014_outside_counsel）
  - 検証: backend pytest 1208 passed / 2 skipped（+6 件）・PG モード 6 passed・
    ruff / mypy clean・ローカル PG 適用＋デモ基準 5 件投入

### Added / Changed (2026-09-05: 顧問弁護士依頼・回答管理 Issue #102)

- **👨‍⚖️ 顧問弁護士・外部法律事務所管理を実装（Phase 1 完結・ロードマップ #85〜#96 / Issue #102）**:
  - 台帳: `law_firms`（#86）・`counsel_lawyers`（#87・事務所帰属検証付き）
  - `legal_engagements`: 依頼起票（#85/#88・LEG-YYYY-NNNNNN 採番）・質問/回答（#89・
    open→answered→confirmed/cancelled）・回答期限（#90）・利益相反（#91）・
    Confidential 分類（#92）・費用見込み（#93）・Matter 連携
  - API: `/outside-counsel/firms`・`/firms/{id}/lawyers`・`/lawyers`・`/engagements`
    （CRUD・answer/confirm/cancel・全変更を監査ログへ）
  - ルール: 回答は open のみ・確認は answered のみ・確定/取消後は更新不可（409）・
    他事務所弁護士指定 422・不明 firm/matter/lawyer 404
  - Alembic `014_outside_counsel`（down_revision=013_matters）
  - 検証: backend pytest 1202 passed / 2 skipped（+5 件）・PG モード 5 passed・
    ruff / mypy clean・ローカル PG（legalops / legalops_test）へ 014 適用済み

### Added / Changed (2026-09-05: Legal Matter Management Issue #101)

- **⚖️ Legal Matter Management を実装（Phase 1・ロードマップ #71〜#84 / Issue #101）**:
  - `legal_matters`: Matter 台帳・**ID 採番 MT-YYYY-NNNNNN（#72）**・種別/状態/優先度・
    担当アサイン（#74）・昇格元記録（#73 source_type/source_id・dispute 存在検証）・
    Legal Hold 連動（#82）・opened/closed 管理
  - `matter_events`: 案件タイムライン（#78・追記専用: created/assigned/status_changed/
    contract_linked/unlinked/legal_hold_linked/unlinked/note）
  - `matter_contracts`: 関係契約リンク（#79・M2M・async 安全に Core 操作）
  - 状態遷移ルール: 同一 409・CLOSED は OPEN（再開）のみ・CLOSED 中は担当変更/更新不可
  - API: `GET/POST /matters`・`PATCH /matters/{id}`・`/status`・`/assign`・`/contracts`(GET/POST/DELETE)・
    `/legal-hold`・`/events`・`/notes`（全変更を監査ログへ）
  - Alembic `013_matters`（down_revision=012_obligations）
  - 検証: backend pytest 1197 passed / 2 skipped（+9 件）・PG モード 8 passed・
    ruff / mypy clean・ローカル PG（legalops / legalops_test）へ 013 適用済み

### Added / Changed (2026-09-05: 契約書全文検索・類似検索の製品化 Issue #100)

- **🔍 契約書全文検索 API を新設（Phase 1・ロードマップ #5 / Issue #100）**:
  - `GET /search?q=&scope=contracts|clauses|documents|all&contract_id=&limit=`
  - 対象: 契約メタデータ（title/counterparty/contract_no）・**条項本文（clauses.body）**・
    **契約文書（contract_documents.content）**（既存 /knowledge/search・/knowledge/similar と住み分け）
  - ヒット位置スニペット（前後 60 文字）＋文字バイグラム Dice 類似度スコア降順
    （AI 不使用・決定論的・trgm 非依存の DB ポータブル実装）
- **🐛 契約一覧の決定論的ソートを実装**: `contract_service.list_contracts` が sort 引数を
  無視し無順序だったため、同時刻更新が多数あるとページング（20 件）が不安定になる問題を修正。
  許可列のみ受け付け id DESC タイブレークを必ず付与（Integration スイート安定化）

### Added / Changed (2026-09-05: 契約義務・Obligations Calendar Issue #99)

- **🗓️ 契約義務管理（Phase 1・ロードマップ #9〜#13 / Issue #99）**:
  - `contract_obligations`（報告/通知/提出/保険/更新/条件/終了チェック等・
    open/in_progress/completed/waived）を追加
  - **Obligations Calendar（#10）**: due_date 基準の期限バケット
    （overdue / within_30 / within_60 / future）をルールエンジンで動的判定
  - **自動更新判定（#12）**: `contracts` に `auto_renewal` / `renewal_notice_days` を追加し、
    解約通知期限（end_date - notice_days）と状態（notice_overdue/upcoming/ok/expired）を導出
  - API: `GET/PATCH /obligations`・`POST /obligations/{id}/complete|waive`・
    `GET /obligations/renewal-check`・`POST /contracts/{id}/obligations`
    （全変更を監査ログへ・二重完了/完了後更新は 409・不明 assignee 404・不正種別 422）
  - Alembic `012_obligations`（down_revision=011_negotiation）
  - 検証: backend pytest 1181 passed / 2 skipped（+9 件）・PG モード 8 passed・
    ruff / mypy clean・ローカル PG（legalops / legalops_test）へ 012 適用済み

### Added / Changed (2026-09-05: 契約交渉・Redline 管理 Issue #98)

- **📝 契約交渉・Redline 管理を実装（Phase 1・ロードマップ #5〜#8 / Issue #98）**:
  - `clauses` に `negotiation_status`（accepted / rejected / negotiating）・
    `clause_owner`（法務/工事/営業/購買/その他）・`negotiated_text`（最新修正案）を追加
  - `clause_negotiation_events`（追記専用）で交渉履歴を証跡化:
    redline（proposed_text）・demand / concession / comment・status_change・owner_change
  - API: `POST/GET /contracts/{id}/negotiations`・
    `POST /contracts/{id}/clauses/{clause_id}/status`・`/owner`
    （全変更を監査ログへ記録・同一状態/オーナーは 409・未所属条項は 404）
  - Alembic `011_negotiation`（down_revision=010_signing）
  - 検証: backend pytest 1172 passed / 2 skipped（+11 件）・PG モード 9 passed・
    ruff / mypy clean・ローカル PG（legalops / legalops_test）へ 011 適用済み

### Added / Changed (2026-09-05: DB をローカル PostgreSQL へ変更・移行)

- **🐘 DB 既定をローカル PostgreSQL（127.0.0.1:5432 / legalops / legalops_dev）へ変更**:
  `backend/app/core/config.py` の `db_url` 既定値が `@postgres`（旧 Docker Compose サービス名）→
  `@127.0.0.1` へ。Docker Compose 実行時は compose ファイルが DB_URL を上書き、
  systemd 運用は `/etc/legalops/*.env` が上書きするため実環境への影響なし
- **移行手順・ドキュメント整備**: `.env.example`（ローカル/Compose の使い分けコメント）・
  README「🐘 DB をローカル PostgreSQL で使う（既定・DB 移行）」を追加
  （role/DB 作成 → `alembic upgrade head` → `scripts/seed_demo_data.py` → PG 統合テスト）
- **実績（ローカル PG 16.14）**: role `legalops` / DB `legalops`・`legalops_test` 作成。
  `legalops` へ Alembic 001→010 適用＋デモデータ投入（契約 22・条項 108 等）。
  `legalops_test` で `PYTEST_USE_POSTGRES=1` の RLS 統合 2 件 pass（従来 SQLite でスキップ分）。

### Added / Changed (2026-09-05: 電子契約・電子署名ステータス管理 Issue #97)

- **✍️ 電子契約・電子署名ステータス管理を実装（Phase 1・ロードマップ #1〜#4 / Issue #97）**:
  締結プロセスを `draft → sent → viewed → signed → completed（+ cancelled）` の
  ルールエンジンで管理する `esignature_envelopes` / `esignature_events` を追加。
  - API: `POST /signing`（作成）・send / consent / view / sign / complete / cancel・
    証跡イベント一覧 `GET /signing/{id}/events`（追記専用・読み取りのみ）
  - **承諾証跡（建設業法 19 条）**: `electronic` 方式は署名前に相手方の承諾記録
    （consent_received・consent_* 列）を必須化（422 fail-closed）
  - **プロバイダアダプタ IF（#1）**: CloudSign / DocuSign は資格情報未設定なら 503
    （fail-closed）。既定 demo（外部送信なし）・manual 対応
  - **締結済み正本取込（#4）**: `complete` 時の `attachment_id` 指定で
    `contract_documents`（doc_type=`signed_original`）へ正本登録
  - 全遷移を監査ログ（hash chain）＋イベントへ記録。Alembic `010_signing`
    （down_revision=009_ip_management）・ローカル PG で upgrade/downgrade roundtrip 検証済み
  - 検証: backend pytest 1161 passed / 2 skipped（SQLite 全件）、PG 統合（RLS 2 件）pass、
    ruff / mypy clean（署名テスト 12 件追加）

### Added / Changed (2026-09-04: 業務OS拡張ロードマップ策定)

- **📋 法務部門の業務 OS 化ロードマップを策定**: `docs/LEGALOPS_BUSINESS_OS_ROADMAP_2026-09.md` を新設。
  既存 22 メニュー・20 API ルーター・Alembic 009 を実測した現状インベントリ（§2）と、
  272 候補の追加機能カタログ（§5・固定番号 1〜272）を重複除去の上 P0/P1/P2 に優先度付けし、
  Phase 1〜5 の開発順序（§8）と GitHub Issue 化計画（§9）を定義。
  Phase 1 = 電子契約 → Redline → Obligations → 全文/類似検索 → Matter → 顧問弁護士管理。

### Added / Changed (2026-08-14: MVP / Prototype 自律完成 Loop 113)

- **🧪 MVP 公開環境を本番と分離して構築**: `https://legalops-mvp.mirai-dx-platform.com`
  （Cloudflare Tunnel `legalops-mvp` + 独立 Compose プロジェクト `construction-legalops-mvp`）。
  本番の DNS・Neon DB・Secrets・コンテナには未着手。
  - `infra/docker/docker-compose.mvp.yml`（postgres/redis/backend/seed/frontend/nginx/cloudflared）
  - `infra/nginx/mvp.conf` / `infra/cloudflare/tunnel-mvp-config.example.yml`
  - `scripts/apply_mvp_legalops_after_approval.sh`（UUID 明示 + CNAME post-check の再作成ゲート）
- **🔑 MVP 用開発認証バイパス（fail-closed）**: `AUTH_DEV_BYPASS=true` かつ
  `APP_ENV ∈ {development, staging}` の時のみ有効。production では構造的に発動しない。
  `backend/tests/unit/test_dev_bypass.py`（5 件）で保護条件を担保。
- **🎭 ダミーデータを全主要テーブルへ拡充・架空値へ統一**: 契約 22 / レビュー 15 / リスク 41 /
  ワークフロー 30 ステップ / 協力会社 12 / 紛争 6 / 支払 32 / 変更契約 6 / テンプレート 10 /
  ナレッジ 5 / 通知 5。企業名・案件名・許可番号はすべて架空（例: みらい建設工業(株)・
  みらい北幹線道路補修工事）。監査ログは `demo=true` フラグで実監査と分離。
- **🎫 Issue クローズ**: #60（compliance 未実行チェックの neutral 表示）と
  #64（Cloudflare 適用スクリプトの tunnel UUID 解決）を検証の上クローズ。
- **🔧 依存・ビルド健全化**: `js-yaml@3` を 3.15.1 に override、backend Dockerfile の
  Trivy SBOM 誤検知ガード、MVP 用クレデンシャルの環境変数上書き対応、scan_secrets 許可リスト更新。
- **🧪 検証**: backend pytest 1113 passed / 2 skipped（SQLite・PG 専用 RLS のみスキップ）、
  ruff 0.16.1 / mypy 2.3.0 clean、frontend typecheck/lint/Jest 43 passed、
  Docker ビルド成功（node:20.18.0-alpine）、公開 URL smoke（healthz/root/API 一覧・詳細・
  支払コンプライアンス 200）。

### Added / Changed (2026-08-12: 本番ゲート準備 Loop 112)

- **🧩 PR #85 マージ**（Loop 111 の実装を main へ反映）
- **🛡️ CSP enforce 適用ヘルパー**: `scripts/apply_csp_enforce.sh`（Report-Only → enforce 置換・nginx -t 検証・冪等）と
  `scripts/verify_csp_enforce.sh`（適用状態検証）を追加（#24 の人間実行を 1 コマンド化）
- **🔐 Vault 秘密情報投入ランブック**: `docs/VAULT_SECRETS_RUNBOOK.md`（HashiCorp / Azure Key Vault・投入対象・完了条件・ロールバック）
- **💾 PITR ドリル手順書**: `docs/PITR_DRILL_RUNBOOK.md`（Neon PITR 手順 + ローカル論理バックアップ復旧ドリル）
- **👥 Entra ID パイロットグループ作成手順書**: `docs/ENTRA_PILOT_GROUPS_RUNBOOK.md`（Graph PowerShell・ロール割当・検証）
- **🧪 パイロットスモークテストチェックリスト**: `docs/PILOT_SMOKE_TEST_CHECKLIST.md`（11 項目・2 週間スケジュール・KPI）
- **🐛 backup_db.sh 修正**: 復旧時の alembic 実行を backend ディレクトリ + PYTHONPATH 設定で解決
  （ローカル復旧ドリルで `ModuleNotFoundError: No module named 'app'` を検出して修正）
- **🧪 検証**: ローカル PostgreSQL 16 でバックアップ→DROP→リストア→データ検証→migration 001→008 適用を成功。
  verify_backup_restore_docs.sh 36 passed。

### Added / Changed (2026-08-12: フォローアップ実装 Loop 111)

- **📝 契約申請・稟議画面を実データ化**: `GET /workflows/applications` を新設し、
  承認ワークフロー（workflow_step × contract × drafter）を稟議として表示。
  モック（CONTRACT_APPLICATIONS）を廃止。
- **🏗️ 建設業法務チェック画面を実データ化**: チェックリスト定義（正本マスタ）と
  契約単位の機械チェック実行・結果表示（`/compliance/checklists`・`/checks/{id}`）に接続。
  モック（CONSTRUCTION_CHECKS）を廃止。
- **📊 レポート・分析画面を実データ化**: ダッシュボード集計（summary/trends）・
  リスク分布・コンプライアンス定義数から表示。固定値（QUARTERLY_STATS 等）を廃止。
- **🗂️ 契約種別マスタ統合**: 正準値（工事請負契約 / 業務委託契約 / 資材購入契約 /
  下請契約 / 設計監理契約 / 賃貸借契約 / 秘密保持契約 / 売買契約 / 覚書 / JV / その他）を
  `app.models.enums.ContractType` と `app.services.contract_type` に定義し、
  API 境界で旧名称（`ukeoi` / `itaku` / `請負` / `委託` 等）を正規化。
  migration 008 で既存データを正準値へ更新。frontend enum・UI 選択肢も統一。
- **🧪 検証**: 種別正規化 unit 5 件 + 稟議 API integration 3 件を追加。
  backend pytest 全件 green（件数は最終確認）、ruff/mypy clean、frontend 43 passed。

### Added / Changed (2026-08-12: 総合評価・改善 Loop 110)

- **✏️ 契約編集フォーム実装**: `contracts/[id]/edit` のスタブ（notFound）を解消し、
  楽観ロック（version）付き PATCH `/contracts/{id}` へ接続。編集内容は監査ログに記録。
- **🔍 法務相談を一次情報 RAG に置換**: 疑似キーワード応答を廃止し、`GET /ai/evidence` の
  根拠検索（一次情報確認済みバッジ・引用リンク・関連度表示）へ接続。
- **📅 契約期限・更新管理を実データ化**: モックを廃止し、契約台帳の `end_date` から
  期限切れ/30 日以内/60 日以内を算出表示。
- **🛡️ アプリ層レート制限追加**: nginx に加え、ASGI ミドルウェアでクライアント IP 単位の
  スライディングウィンドウ制限（認証系 60 req/min・一般 600 req/min、環境変数で変更可）。
  429 + Retry-After 応答。単体テスト 5 件追加（ADR 0006）。
- **🔧 evidence API 契約統一**: フロントエンドの誤った `POST /ai/evidence` 呼び出しを
  `GET /ai/evidence?q=&limit=` に修正し、API 契約の回帰テスト 3 件を追加。
- **👥 ユーザー設定パネル・通知・ユーザーメニューを実 API 化**: `GET /users`・
  `GET/POST /notifications`・`GET /auth/me` に接続し、モック表示を廃止。
- **📱 モバイルナビ + PWA manifest**: ハンバーガーメニューによるドロワーと
  `manifest.webmanifest` を追加（オフライン対応は今後のロードマップ）。
- **📚 ADR 台帳新設**: 6 件（Web スタック / AI 人間承認 / 監査ハッシュチェーン /
  RLS+ACL / Cloudflare Access / レート制限）を `docs/adr/` に追加。
- **📄 文書更新**: `docs/api_design.md` の実装乖離（evidence・レート制限）を修正し、
  総合評価・改善報告書 `docs/EVALUATION_IMPROVEMENT_REPORT_2026-08-12.md` を新規作成。
- **🧪 検証**: backend pytest 1,089 passed / 2 skipped（RLS は PG 限定）、ruff/mypy clean、
  frontend lint/typecheck clean、Jest 40 passed。

### Added / Changed (2026-08-05: 外部評価 67/100 への最終対応)

- **🔐 P0-6 内部統制の実装完了（DB RLS / ACL / Legal Hold / Retention / WORM / Sentinel）**:
  - PostgreSQL ROW LEVEL SECURITY: `contracts` ほか 13 テーブルに
    `app.actor_id` / `app.role` / `app.actor_email` ベースのポリシーを適用
    （`006_security_rls` / `007_business_domain`）。倫理壁（人事・談合・内部通報）案件は
    明示許可ユーザー or admin/auditor のみ可視。
  - 案件単位 ACL（外部顧問弁護士のメール単位アクセス含む）、Legal Hold の
    発動・解除・自動削除停止、AI 入出力の保存期間ポリシー（`/security` `/legal-holds`
    `/retention` `/contracts/{id}/access-control` API）。
  - 監査ログの日次アンカー（HMAC-SHA256 署名）と WORM 相当の JSONL 外部出力
    （`/audit/anchor` `/security/audit-exports`）、Microsoft Sentinel 転送
    アウトボックス（設定不足時は blocked / fail-closed）。
- **📑 変更契約・追加工事・クレーム管理**: 設計変更 / 追加工事 / 口頭指示追認 /
  工期延長 / スライド請求の正本管理。通知期限 14 日の自動計算、失権リスク警告、
  原契約＋承認済み変更の累積影響分析、日報・写真・メール等の証拠紐付け
  （`/change-orders` + `/impact/{contract_id}`）。
- **📚 契約パッケージ文書管理**: 契約書・約款・特記仕様書・設計図書・見積書・工程表等を
  優先順位付きで一元管理し、金額乖離（20% 超）・工期逆転・責任帰属の矛盾を自動検出
  （`/contracts/{id}/documents` + `/consistency`）。
- **💰 支払・出来高・検収コンプライアンス**: 発注/受領/検収/支払日から取適法 60 日・
  公共工事 50 日基準を実日計算、遅延利息概算（年 14.6%）、手形等禁止・不当減額・
  保留金の判定（`/contracts/{id}/payment-compliance`、支払イベント正本
  `/payments` + `payment_records` テーブル）。
- **🏢 協力会社コンプライアンス台帳**: 建設業許可（特定/一般・期限）・社会保険・CCUS・
  監理技術者資格・経営事項審査・反社確認・倒産リスク・再下請関係を正本化し、
  リスクレベルを理由付きで自動判定（`/partners` + `/summary`）。
- **⚔️ 紛争・事故・債権管理**: 案件台帳・事実経過タイムライン・証拠保全（preserved）・
  消滅時効/通知期限・経営層向けエクスポージャー集計（`/disputes` + `/exposure`）。
- **⚖️ 適用法令自動判定（AI 機能 #3）**: 契約類型・資本金・従業員数・発注日・公共/民間から
  建設業法・取適法・品確法・個人情報保護法等の適用を根拠付きで提示
  （`/compliance/applicable-laws`）。
- **📖 一次情報限定 RAG（AI 機能 #1）**: ナレッジベース限定検索＋公的機関 URL 許可リスト
  検証（`/ai/evidence` + `/verify`）。
- **📅 法令改正影響分析（AI 機能 #2）**: 取適法施行日を軸に既存契約の影響（従業員数基準・
  手形禁止・60 日超・労務費内訳欠落）を抽出（`/compliance/law-change-impact`）。
- **🧪 検証**: バックエンド pytest 1,083 passed（SQLite 全件）＋ PostgreSQL 16 実 DB /
  マイグレーション 001→007 は CI 全ジョブ GREEN、ruff / mypy クリーン、
  フロントエンド typecheck / lint / Jest 40 passed。

### Added / Changed (2026-08-04: 外部評価 P0 対応)

- **⚖️ 取適法（中小受託取引適正化法）対応**: 2026-01-01 施行の新旧法切替（発注日基準）、
  資本金＋従業員数による適用マトリクス（製造委託等 3 億円/300 人、役務提供委託 1 億円/100 人）、
  受領日から 60 日支払期日の実日付計算、手形払い禁止・電子記録債権/ファクタリング判定、
  一方的な代金決定の禁止、特定運送委託、書面交付事項、取引記録保存を
  `compliance_checker.py` に実装（`toritekihou_*` ルール群）。
- **🧱 改正建設業法・労務費基準**: 労務費・材料費・安全衛生経費・法定福利費・建退共の内訳確認、
  著しく低い見積り／短工期の検知、契約前通知、価格変更協議（スライド）条項を追加
  （`construction_law_labor_breakdown` ほか）。
- **📄 建設業法 19 条チェックを拡充**: 法定記載事項を 11 項目へ拡大、約款・特記仕様書等の
  文書横断判定、台帳金額と書面金額の乖離（20% 超）・日付順序の妥当性検証を追加。
- **🔍 AI レビューの根拠保証（P0-4）**: 指摘ごとに原文抜粋・法令名・条番号・法令バージョン・
  施行日・一次情報 URL（公的機関ホスト限定）・社内規程 ID/版数・ルール ID・AI 信頼度・
  verdict を必須化。根拠不足は `needs_human_review` へ降格、根拠なき回答は `unverifiable`。
- **🛡️ プロンプトインジェクション対策（P0-5）**: 契約原文を非信頼データマーカーで分離、
  文書内命令の無視指示、JSON Schema 検証、URL 許可リスト、攻撃文書の回帰テストを追加。
- **🧪 テスト拡充**: compliance_checker / ai_review の新ルール 33 件追加（ユニット 823 件 PASS）。

### Changed (2026-08-01: サブドメイン一本化)

- **🌐 サブドメイン一本化**: 公開 URL を `https://legalops.mirai-dx-platform.com` に統一し、
  preview 用 `legalops-preview.mirai-dx-platform.com`（tunnel `legalops-preview` / CNAME）を
  削除して一本化した（2026-08-01 に CNAME NXDOMAIN 化・tunnel 459059b3… 削除・connector 停止を確認）。
  README / infra Cloudflare README / state.json の記録を一本化済み状態へ更新
  （本番 deploy と DNS/Tunnel 変更は引き続き人間ゲート）。

## [0.1.12] - 2026-07-20

### Fixed (2026-07-20 Verify: fail-closed 化のテスト回帰)

- **🧪 test_sso_service の MagicMock fixture に `is_production = False` を明示** — SSOService の本番 stub 拒否ガードが truthy な MagicMock 属性で誤発火し 3 failed + 34 errors となる回帰を修正（production=True 経路は `test_production_stub_guards.py` が担当）

### Added (2026-07-19 Phase 1 確定: Neon 実環境検証 + Cloudflare preview 実デプロイ)

- **🗄️ Neon 実プロジェクト作成と migration 検証** (グローバル CLAUDE.md §27.2 包括承認範囲):
  `Construction-LegalOps-DX` (aws-ap-southeast-1 / PG16) を作成し、`development` branch で
  alembic 001→005 適用 + roundtrip (downgrade base → re-upgrade) + SQLAlchemy asyncpg
  `?ssl=require` 接続を検証した (17 tables / pg_trgm / uuid-ossp)。本番用 `main` branch は未適用。
- **🌐 Cloudflare 非本番 preview 実デプロイ**（※ 2026-08-01 に本番 `legalops.mirai-dx-platform.com` へ一本化のため削除済み）: named tunnel `legalops-preview` +
  DNS CNAME `legalops-preview.mirai-dx-platform.com` (ユーザー承認済み・可逆) で
  docker compose (staging 相当・Neon development DB) を公開し、デプロイ後検証 16/16 PASS
  (health / 主要画面 / 401 fail-closed / JWT→JIT provisioning / Neon read・write /
  CSP・nosniff ヘッダ / server tokens 秘匿 / JS bundle secret 露出なし)。
- **📝 監査証跡の実書込確認**: preview 経由の認証リクエストで Neon `users` JIT 行 +
  `audit_logs` (`user.jit_provision`) の永続化を確認した。

### Fixed (2026-07-19 Phase 1 確定: preview デプロイが暴いた本番系欠陥 2 件)

- **🐛 mode 700 ファイルの non-root コンテナ import 不能**: 前セッションが umask 077 で
  作成した 61 ファイル (auth_service.py / observability/ 等) が root 所有 mode 700 のまま
  Docker COPY され、uid 10001 の backend が `ModuleNotFoundError` で crash-loop する欠陥を
  検出・修正 (ローカル pytest では検出不能な欠陥クラス)。
- **🐛 frontend healthcheck の IPv6 解決不全**: コンテナ内 `localhost` が `::1` に解決される
  一方 Next.js standalone は IPv4 のみ listen するため busybox wget が常に失敗し、
  frontend 恒久 unhealthy → `depends_on: service_healthy` の nginx が起動不能となる構造欠陥を
  `127.0.0.1` 固定で根治。
- **🔧 nginx 443 vhost の証明書必須起動**: Tunnel 構成 (edge TLS) では証明書未配置で
  nginx が起動不能。preview では self-signed placeholder を named volume に生成して解決
  (本番手順は Runbook に記載)。

### Changed (2026-07-19 Loop 91 吸収: contracts subresource API)

- **contracts versions/clauses API の legacy 501 stub 撤去** (並行セッション Loop 91 成果を
  検証の上吸収): `GET /contracts/{id}/versions` は現行 row のバージョンスナップショット、
  `GET /contracts/{id}/clauses` は seq 順の DB-backed clauses を返却し、missing contract は
  404 へ変換。unit + integration 43 passed / ruff / mypy を本セッションで再検証済み。

### Changed (2026-07-19 Loop 88: Notification real mode)

- **通知 real mode を外部送信契約へ対応**:
  `backend/app/services/notification_service.py` に Exchange Graph sendMail、
  Teams webhook、desknet's webhook の real mode を追加し、送信者 / webhook URL 不足時は
  `NotificationError` で fail-closed にした。
- **通知送信契約テストを追加**:
  `backend/tests/unit/test_notification_service.py` に Graph token + sendMail、Teams adaptive card、
  desknet's webhook、設定不足 fail-closed の unit contract を追加し、32 passed / ruff clean /
  mypy success を確認した。
- **環境変数とrelease docs gateを同期**:
  `.env.example` に `NOTIFY_MODE` / `EXCHANGE_SENDER_UPN` / `TEAMS_WEBHOOK_URL` /
  `DESKNETS_WEBHOOK_URL` を追加し、`scripts/verify_release_docs.sh` が通知 real mode の
  README / evidence / final report / source / test 証跡を監視するようにした。

### Changed (2026-07-19 Loop 87: SharePoint Graph real mode)

- **SharePoint real mode を Microsoft Graph 対応に更新**:
  `backend/app/services/sharepoint_service.py` の real path を Entra client-credentials、
  Graph drive upload、Graph item `webUrl` 解決に対応させ、`SHAREPOINT_DRIVE_ID` 不足、
  token / upload / get_url の不正応答を `SharePointError` で fail-closed にした。
- **SharePoint Graph 契約テストを追加**:
  `backend/tests/unit/test_sharepoint_service.py` に real upload / get_url / drive id不足 /
  Graph不正応答の unit contract を追加し、33 passed / ruff clean / mypy success を確認した。
- **release docs gateへ接続**:
  `scripts/verify_release_docs.sh` が SharePoint Graph real mode の README / evidence /
  final report / source / test 証跡を監視するようにした。

### Changed (2026-07-19 Loop 86: Dependency audit evidence preflight)

- **依存関係監査証跡をread-only gate化**:
  `scripts/verify_dependency_audit_evidence.sh` を追加し、npm audit high/critical 0、
  moderate 4 の既知残リスク、CI の strict project-scoped pip-audit、ambient pip 誤検知回避、
  ecdsa ignore の到達不能根拠、PyJWT 移行、pip-audit 72 deps / 0 vulnerabilities を
  検証するようにした。
- **pre-deploy gateへ接続**:
  `scripts/pre_deploy_check.sh` から dependency audit evidence preflight を呼び出し、
  pre-deploy の mandatory checks を Passed 22 / Failed 0 / Warnings 5 へ更新した。
- **release docs gateへ接続**:
  `scripts/verify_release_docs.sh` から dependency audit evidence verifier の存在と
  pre-deploy 接続を監視し、依存関係監査証跡の drift を検出するようにした。

### Changed (2026-07-19 Loop 85: Review evidence preflight)

- **Review証跡の境界をread-only gate化**:
  `scripts/verify_review_evidence.sh` を追加し、CodeRabbit CLI/auth、findings前timeout、
  CodeRabbit findingsが得られていないため Critical/High 0件とは断言しない制限、
  代替静的検証、security review、過去のadversarial/silent-failure review証跡を
  検証するようにした。
- **pre-deploy gateへ接続**:
  `scripts/pre_deploy_check.sh` から review evidence preflight を呼び出し、
  pre-deploy の mandatory checks を Passed 21 / Failed 0 / Warnings 5 へ更新した。
- **release docs gateへ接続**:
  `scripts/verify_release_docs.sh` から review evidence verifier の存在と
  pre-deploy 接続を監視し、レビュー証跡の過剰主張や欠落を検出するようにした。

### Changed (2026-07-19 Loop 84: Goal completion evidence preflight)

- **/goal完了条件の証拠マップをread-only gate化**:
  `scripts/verify_goal_completion_evidence.sh` を追加し、必須機能、lint/type/test/build、
  security、DB migration/rollback、release checklist、WebUI、GitHub Project/Issue/CI、
  本番承認待ち stop-line の各完了条件が `docs/RELEASE_EVIDENCE_MATRIX.md` と
  `docs/FINAL_RELEASE_STOP_REPORT.md` に証拠付きで対応していることを検証するようにした。
- **pre-deploy gateへ接続**:
  `scripts/pre_deploy_check.sh` から goal completion evidence preflight を呼び出し、
  pre-deploy の mandatory checks を Passed 20 / Failed 0 / Warnings 5 へ更新した。
- **release docs gateへ接続**:
  `scripts/verify_release_docs.sh` から goal evidence verifier の存在と
  pre-deploy 接続を監視し、`/goal` 証跡の drift を検出するようにした。

### Changed (2026-07-19 Loop 83: Standalone WebUI runtime contract hardening)

- **Standalone WebUI runtime preflightを拡張**:
  `scripts/verify_standalone_webui_runtime.sh` が status JSON、systemd enabled/active、
  unit の `ExecStart` / `WorkingDirectory` / `Restart=always` / `NoNewPrivileges`、
  `38100-38999` の自動port範囲、Linux host上の選択IP、`ss` によるlisten実体を
  read-onlyで検証するようにした。
- **release docs gateへ接続**:
  `scripts/verify_release_docs.sh` に WebUI status JSON / auto port / selected host /
  listen / systemd ExecStart の検証観点を追加し、WebUI提示要件のdriftを検出するようにした。
- **承認者向け証跡をLoop 83へ同期**:
  README / approval packet / evidence matrix / final stop report / release checklist /
  handover に Standalone WebUI runtime preflight の拡張証跡を追加した。

### Changed (2026-07-19 Loop 82: Production stop-line preflight)

- **Production stop-line証跡をread-only gateへ追加**:
  `scripts/verify_production_stop_line.sh` を追加し、`legalops.mirai-dx-platform.com`
  の CNAME / A 未作成、Git tag 0、GitHub Release 0、GitHub Deployments 0、
  open PR 0、open issues #23/#24/#50、Issue #50 の blocked / human-decision labels、
  GitHub Project #30 の Todo 状態を検証するようにした。
- **release docs gateへ接続**:
  `scripts/verify_release_docs.sh` から production stop-line の検証観点を監視し、
  本番未実行の証跡が drift した場合に release docs preflight を失敗させるようにした。
- **承認者向け証跡をLoop 82へ同期**:
  README / approval packet / evidence matrix / final stop report / release checklist /
  handover に production stop-line preflight の証跡を追加した。

### Changed (2026-07-19 Loop 81: Release checklist pending classification)

- **Release checklistの未チェック項目分類を追加**:
  `scripts/verify_release_checklist_pending_items.sh` を追加し、`docs/RELEASE_CHECKLIST.md`
  の未チェック73件が人間承認 / 本番実行 / リリース後確認に分類されることを
  read-only で検証するようにした。
- **docs gateへ接続**:
  `scripts/verify_release_docs.sh` から checklist分類スクリプトの検証観点を監視し、
  未分類の未チェック項目が混入した場合にrelease docs preflightを失敗させるようにした。
- **承認者向け証跡をLoop 81へ同期**:
  README / approval packet / evidence matrix / final stop report / handover に
  checklist pending classification の証跡を追加した。

### Changed (2026-07-19 Loop 80: Pre-deploy warning classification)

- **Pre-deploy warning分類を承認前ゲートへ追加**:
  `scripts/verify_predeploy_warning_classification.sh` を追加し、pre-deploy log の
  Passed / Failed / Warnings 数、既知warning 5件、本番secret / SSO / AI key / Docker build skip
  の分類、未知warning 0 を read-only で検証するようにした。
- **警告の説明責任をdocs gateへ接続**:
  `scripts/verify_release_docs.sh` から warning分類スクリプトの検証観点を監視し、
  Approval Packet / Final Stop Report / Evidence Matrix にwarning分類の証跡を追加した。
- **古いpre-deploy証跡を修正**:
  `docs/FINAL_RELEASE_STOP_REPORT.md` の pre-deploy 結果を
  Passed 19 / Failed 0 / Warnings 5 へ更新した。

### Changed (2026-07-19 Loop 79: Standalone WebUI runtime preflight)

- **Standalone WebUIの実起動証跡をpre-deployへ追加**:
  `scripts/verify_standalone_webui_runtime.sh` を追加し、systemd user service active、
  `/healthz` ok、`HEAD /` 200、Content-Length と standalone HTML実体サイズの一致、
  security headers、`/standalone-source` のHTML実体パス一致を read-only で検証するようにした。
- **WebUI runtime gateを承認前ゲートへ接続**:
  `scripts/pre_deploy_check.sh` から WebUI runtime preflight を呼び出し、
  `scripts/verify_release_docs.sh` で pre-deployへの接続とruntime検証観点を監視するようにした。
- **承認者向け文書をLoop 79へ同期**:
  README / release checklist / approval packet / evidence matrix / final stop report / handover に
  WebUI runtime preflight の証跡を追加した。

### Changed (2026-07-19 Loop 78: GitHub Actions CI gate preflight)

- **最新CI成功をGitHub Release Gateへ追加**:
  `scripts/verify_github_release_gate.sh` が `gh run list` で main ブランチの最新 `CI`
  workflow run を読み取り、`completed` / `success` / `main` / run URL ありを
  本番承認前ゲートとして検証するようにした。
- **承認者向け証跡をCI状態まで拡張**:
  README / release checklist / approval packet / evidence matrix / final stop report / handover に
  latest main CI success を追加し、GitHub Project / Issue / CI の外部状態を同じpreflightで監視するようにした。

### Changed (2026-07-19 Loop 77: GitHub release gate preflight)

- **GitHub Release Gateをpre-deployへ追加**:
  `scripts/verify_github_release_gate.sh` を追加し、open PR 0、open issues #23/#24/#50、
  Issue #50 の `blocked` / `human-decision` / `infra` labels、Project #30 readme、
  Project item status (#23/#24/#50 Todo) を read-only で検証するようにした。
- **本番承認前ゲートを強化**:
  `scripts/pre_deploy_check.sh` から GitHub release gate preflight を呼び出し、
  `scripts/verify_release_docs.sh` で pre-deploy への接続と検証観点を監視するようにした。
- **承認者向け文書をLoop 77へ同期**:
  README / release checklist / approval packet / evidence matrix / final stop report / handover に
  GitHub release gate の証跡を追加した。

### Changed (2026-07-19 Loop 76: GitHub Project release gate sync)

- **GitHub Project #30 を現行Release Gateへ同期**:
  `Construction-LegalOps-DX 開発管理` Project readme を更新し、open PR 0、
  open issues #23/#24/#50、pre-deploy / release docs / secret scan /
  Cloudflare legalops / WebUI / production stop line を可視化した。
- **Project証跡をrelease docsへ反映**:
  `docs/RELEASE_EVIDENCE_MATRIX.md` と `docs/PRODUCTION_APPROVAL_PACKET.md` に
  Project #30 readme同期済み、#23/#24/#50 がTodoの人間ゲートであることを追加した。

### Changed (2026-07-19 Loop 75: README release-ready truth guard)

- **READMEを承認者向け入口として再同期**:
  冒頭に現在のリリース直前状態表を追加し、本番 deploy 未実行、公開 DNS 未変更、
  `legalops.mirai-dx-platform.com` CNAME/A 未作成、Cloudflare / Vault / CSP 人間承認待ち、
  WebUI URL、承認パケット / 最終停止報告リンクを明示した。
- **READMEのWebUI運用証跡を強化**:
  Standalone WebUI 節に `http://192.168.0.185:38100/`、`/healthz`、`HEAD /`、
  `/standalone-source`、systemd unit、停止コマンドを追加した。
- **README preflight guardを追加**:
  `scripts/verify_release_docs.sh` が README の Loop marker、WebUI URL、Cloudflare legalops hostname、
  CNAME/A 未作成、production approval packet / final stop report links を検証するようにした。

### Changed (2026-07-19 Loop 74: Cloudflare approval safety guard)

- **Cloudflare `legalops` 承認前安全線を release docs preflight で強制**:
  `scripts/verify_release_docs.sh` が Runbook / Approval Packet / Final Stop Report /
  Evidence Matrix の Access-before-DNS、CNAME/A 未作成、Tunnel / Access / secret stop line、
  Cloudflare rollback 手順を検証するようにした。
- **bash 検証ガードのMarkdown記号耐性を修正**:
  backtick を含むパターンを避け、bash が Markdown のコード記法をコマンド置換として
  解釈しない安定した部分一致へ置き換えた。

### Changed (2026-07-19 Loop 73: WebUI approval evidence guard)

- **WebUI 承認前証跡を release docs preflight で強制**:
  `scripts/verify_release_docs.sh` が Final Stop Report、Approval Packet、Evidence Matrix の
  WebUI URL、HEAD 確認、source endpoint、systemd 停止コマンドを検証するようにした。
- **Approval Packet の WebUI 確認欄を拡張**:
  承認者が `http://192.168.0.185:38100/`、`/healthz`、`HEAD /`、systemd active、
  `/standalone-source`、停止方法を同じ資料で確認できるようにした。

### Changed (2026-07-19 Loop 72: Standalone WebUI release-docs guard)

- **Release docs preflight の Standalone WebUI 監視を強化**:
  `scripts/verify_release_docs.sh` が `scripts/pre_deploy_check.sh` 内の
  Standalone WebUI 契約テスト、`serve_standalone_webui.py` 構文チェック、
  `install_standalone_webui_systemd.sh` 構文チェックのラベルとパスを検証するようにした。
- **承認前停止証跡を同期**:
  本番 deploy / 公開 DNS / Cloudflare Tunnel / Access / secret 投入は未実行のまま、
  `legalops.mirai-dx-platform.com` と WebUI systemd の承認前検証証跡を Loop 72 に更新した。

### Changed (2026-07-19 Loop 71: Standalone WebUI pre-deploy gate)

- **Standalone WebUI を pre-deploy gate に統合**:
  `scripts/pre_deploy_check.sh` に `tests/test_standalone_webui.py`、
  `scripts/serve_standalone_webui.py` の py_compile、
  `scripts/install_standalone_webui_systemd.sh` の bash 構文チェックを追加した。
- **Pre-deploy 件数を同期**:
  Standalone WebUI 3 チェック追加により、`SKIP_DOCKER_BUILD=1 ./scripts/pre_deploy_check.sh`
  の必須通過数を Passed 17 / Failed 0 / Warnings 5 に同期した。

### Changed (2026-07-19 Loop 70: Standalone WebUI HEAD verification)

- **Standalone WebUI の HEAD 対応**:
  `scripts/serve_standalone_webui.py` が `HEAD /`、`HEAD /index.html`、
  `HEAD /healthz`、`HEAD /standalone-source` を本文なしで返すようにした。
  監視・運用確認の `curl -I` で 501 にならない。
- **Standalone WebUI テスト強化**:
  `tests/test_standalone_webui.py` に HEAD 応答の `200`、空body、
  `Content-Type`、`Content-Length` 検証を追加した。

### Changed (2026-07-19 Loop 69: Standalone WebUI evidence guard)

- **Standalone WebUI 証跡の自動検証を拡張**:
  `scripts/verify_release_docs.sh` が final stop report と evidence matrix の
  WebUI URL、`/healthz`、`construction-legalops-standalone-webui.service`、
  `docs/Construction-LegalOps-DX (Standalone).html` を検証するようにした。
- **Release-facing docs を Loop 69 に同期**:
  handover / checklist / approval packet / evidence matrix / final stop report の
  current marker を Loop 69 に更新した。

### Changed (2026-07-19 Loop 68: pre-deploy release-docs gate integration guard)

- **Pre-deploy gate 統合の自己検証を追加**:
  `scripts/verify_release_docs.sh` が `scripts/pre_deploy_check.sh` 内の
  `./scripts/verify_release_docs.sh` 呼び出しと `release documentation preflight`
  ラベルを検証し、リリース文書 preflight が pre-deploy から外れた場合に検出できるようにした。
- **Release-facing docs を Loop 68 に同期**:
  handover / checklist / approval packet / evidence matrix / final stop report の
  current marker を Loop 68 に更新した。

### Changed (2026-07-19 Loop 67: stop-line preflight guard)

- **Stop Line の自動検証を拡張**:
  `scripts/verify_release_docs.sh` が final stop report だけでなく
  `docs/RELEASE_EVIDENCE_MATRIX.md` の本番 release/deploy、Cloudflare Tunnel/Access、
  Cloudflare/Neon secret、CSP enforce、Git 操作の停止線も検証するようにした。
- **Approval packet の禁止事項を自動検証**:
  `docs/PRODUCTION_APPROVAL_PACKET.md` が自動本番 deploy、公開 DNS 自動変更、
  secret/token/接続文字列の README/Issue/log 露出を禁止していることを preflight で確認する。

### Changed (2026-07-19 Loop 66: issue comment evidence drift guard)

- **Issue comment 証跡の pending 表記を検出**:
  `scripts/verify_release_docs.sh` が `docs/RELEASE_EVIDENCE_MATRIX.md` の
  `コメント予定` 表記を検出して失敗するようにし、Issue #50 更新後の証跡表が
  「予定」のまま残らないようにした。
- **Release-facing docs を Loop 66 に同期**:
  handover / checklist / approval packet / evidence matrix / final stop report の
  current marker を Loop 66 に更新した。

### Changed (2026-07-19 Loop 65: release checklist evidence drift guard)

- **Release Evidence Matrix の同期表記を補正**:
  `docs/RELEASE_EVIDENCE_MATRIX.md` に残っていた「release checklist は Loop 63 まで同期」
  という古い現在証跡を Loop 65 に更新し、Issue #50 の報告状態も現行ループに合わせた。
- **Release docs preflight の検出範囲を拡張**:
  `scripts/verify_release_docs.sh` が evidence matrix 内の古い checklist-sync 表記を検出し、
  承認判断に使う証跡表が古い状態を正としないようにした。

### Changed (2026-07-19 Loop 64: handover release marker drift guard)

- **HANDOVER の現行 Loop drift を解消**:
  `docs/HANDOVER.md` に残っていた Loop 60 の現在状態表記を Loop 64 に同期し、
  release docs preflight が HANDOVER の current marker と stale Loop 60 表記も検出するようにした。
- **Release evidence の検証値を同期**:
  release evidence matrix / approval packet / final stop report / release checklist の pre-deploy 件数と
  current marker を Loop 64 に更新し、`scripts/pre_deploy_check.sh` の Passed 14 と整合させた。

### Changed (2026-07-19 Loop 63: dynamic release docs loop marker)

- **Release docs preflight の Loop 固定を解消**:
  `scripts/verify_release_docs.sh` が `state.json` の `project.last_loop_completed` を読み取り、
  release checklist / approval packet / evidence matrix / final stop report の current marker と照合するよう変更。
  次ループ以降にスクリプト本体の固定 Loop 番号を書き換える必要をなくした。

### Added (2026-07-19 Loop 62: release docs preflight)

- **Release docs preflight 追加**:
  `scripts/verify_release_docs.sh` を追加し、final stop report / approval packet / evidence matrix /
  release checklist / handover / Standalone HTML の存在、重要見出し、WebUI URL、Stop Line、
  stale Loop 表記を read-only で検証できるようにした。
- **Pre-deploy gate統合**:
  `scripts/pre_deploy_check.sh` に release documentation preflight を組み込み、
  本番承認前の文書証跡が CI 相当の自動ゲートで確認されるようにした。

### Added (2026-07-19 Loop 61: final release stop report)

- **Final Release Stop Report 追加**:
  本番リリース直前で停止するための最終報告書 `docs/FINAL_RELEASE_STOP_REPORT.md` を追加。
  変更内容、レビュー、テスト結果、WebUI確認方法、残課題、リスク、本番デプロイ手順、
  ロールバック手順、Stop Line を一枚に集約。
- **Release docs 同期**:
  README、HANDOVER、PRODUCTION_APPROVAL_PACKET、RELEASE_EVIDENCE_MATRIX、RELEASE_CHECKLIST から
  final stop report へリンクし、release checklist フッターの古い Loop 57 表記を Loop 61 に修正。

### Changed (2026-07-19 Loop 60: release gate cross-document synchronization)

- **Handover / approval / evidence の横断同期**:
  `docs/HANDOVER.md` の古い Loop 56/57 表記を Loop 60 に更新し、
  `docs/RELEASE_EVIDENCE_MATRIX.md` を現行承認判断の正本に追加。
- **Evidence matrix 現行化**:
  `docs/PRODUCTION_APPROVAL_PACKET.md`、`docs/RELEASE_CHECKLIST.md`、`docs/RELEASE_EVIDENCE_MATRIX.md`
  の Loop 表記と #50 進捗証跡を Loop 60 に同期。

### Added (2026-07-19 Loop 59: release evidence matrix)

- **Release Evidence Matrix 追加**:
  `/goal` の完了条件と現在証拠を対応付ける `docs/RELEASE_EVIDENCE_MATRIX.md` を追加。
  必須機能、lint/type/test/build、security、migration rollback、release checklist、WebUI、GitHub 状態、
  本番承認待ち状態を一枚で監査できるようにした。
- **承認文書の参照整理**:
  README、production approval packet、release checklist から evidence matrix へリンクし、
  人間承認ゲートと CTO が実行してはいけない stop line を明確化。

### Changed (2026-07-19 Loop 58: production approval evidence packet)

- **承認パケットの証跡強化**:
  `docs/PRODUCTION_APPROVAL_PACKET.md` に Loop 58 時点の GitHub Issue / CI / pre-deploy /
  secret scan / Cloudflare legalops preflight / DNS 未作成 / WebUI / CodeRabbit 実施状況を集約。
  本番 secret 未投入と Docker build skip の warnings は人間承認ゲートとして明示した。
- **Review 証跡**:
  CodeRabbit CLI 0.6.5 と認証状態は確認済み。`coderabbit review --agent -t uncommitted` は解析開始後、
  findings 出力前に 240 秒でタイムアウトしたため、ローカル静的検証を代替証跡として記録。

### Changed (2026-07-19 Loop 57: Cloudflare legalops runbook final sync)

- **Cloudflare `legalops.mirai-dx-platform.com` 対応を承認待ち状態へ再同期**:
  `docs/CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK.md` の古い Loop 49 記述を Loop 57 の read-only 検証状態に更新し、
  Cloudflare Tunnel DNS / Published applications / Access self-hosted application の公式ドキュメント URL を参照として追記。
- **Release docs 同期**:
  README、release checklist、handover の最終同期表記を Loop 57 に進め、
  Cloudflare 本番適用は DNS / Tunnel / Access / secret / Neon の人間承認後のみであることを維持。

### Changed (2026-07-19 Loop 56: handover release gate synchronization)

- **HANDOVER を現行リリースゲートへ同期**:
  `docs/HANDOVER.md` の古い Loop 33/45/48、906/910 tests、未完扱いの運用・Cloudflare記述を更新し、
  Loop 56 時点の pre-deploy gate、Standalone WebUI、Cloudflare `legalops` read-only preflight、
  fail-closed test gate、人間承認ゲート (#23/#24/#50) に同期。
- **README / RELEASE_CHECKLIST の Loop 表記を統一**:
  README と release checklist の最終整備表記を Loop 56 に進め、承認判断資料の参照関係を明確化。

### Changed (2026-07-19 Loop 55: release checklist and README readiness sync)

- **リリースチェックリストを現行リリースゲートへ同期**:
  `docs/RELEASE_CHECKLIST.md` の古い Loop 5 / v0.1.8 / 906 tests 表記を撤去し、
  Loop 55 時点の pre-deploy gate、Cloudflare `legalops`、Standalone WebUI、
  secret scan、rollback drill、人間承認ゲート (#23/#24/#50) を反映。
- **README のリリース指標を現行化**:
  Phase 1 範囲を Loop 31〜55 に更新し、Backend API カバレッジ見出しを
  `v0.1.12 / Loop 55` に同期。テスト数は pre-deploy の実表示に合わせて `900+` とした。

### Changed (2026-07-19 Loop 54: unit test import fail-closed hardening)

- **自前モジュール import skip の撤去**:
  `review_service` / `file_parser` / `workflow_engine` / `sensitive_detector` /
  `audit_hash_chain` / `risk_scoring` / `ai_review` の unit tests から、実装済み内部モジュールを
  `pytest.importorskip` で隠す経路を撤去。内部モジュールが import できない場合は skip ではなくテスト失敗として扱う。
- **リスク・AI・監査・個人情報検知テストの fail-closed 化**:
  risk scoring 24件、AI review stub、workflow engine、file parser、sensitive detector、audit hash chain、
  review service の対象 unit tests を実実装に直接接続し、168件の対象テストを skip なしで確認。

### Changed (2026-07-19 Loop 53: review flow PATCH contract hardening)

- **レビューE2E相当フローの古い422許容を撤去**:
  `tests/integration/test_reviews_flow.py` の `PATCH /reviews/{id}` 検証を、実仕様の
  `legal_comment` / `final_decision` / `overall_risk` 更新に合わせ、`200` と保存済み `result` JSON を必須確認する形に強化。
- **契約ズレ再発防止**:
  review CRUD 単体フローだけでなく、契約作成 → AIレビュー開始 → 取得 → PATCH → accept の一連フローでも
  人間判断メタデータ永続化を検証する。

### Changed (2026-07-19 Loop 52: review PATCH contract persistence)

- **レビュー更新 API の契約整合**:
  `PATCH /reviews/{id}` が `overall_risk` だけでなく、OpenAPI/route description が示す
  `legal_comment` と `final_decision` も `legal_reviews.result` JSON に保存してレスポンスへ返すよう修正。
- **レビュー・監査テストの古い許容を解消**:
  監査ログ hash chain テストから空配列なら通る古いコメントを除去し、実データ件数を確認。
  review CRUD integration は `PATCH` が 200 で人間判断メタデータを永続化することを検証。
- **API設計書同期**:
  `docs/api_design.md` に `PATCH /reviews/{id}` の保存先・状態遷移境界を明記。
- **レビュー証跡**:
  CodeRabbit light review は uncommitted 差分で実行したが、180秒で結果生成前に timeout。
  ruff / mypy / integration tests / secret scan / pre-deploy gate / WebUI・DNS read-only 確認を代替証跡とした。

### Changed (2026-07-19 Loop 51: knowledge API contract wording alignment)

- **Knowledge API の OpenAPI / docs 表記を実装に同期**:
  `GET /knowledge/search` と `GET /knowledge/similar/{contract_id}` は既に DB-backed 検索として動作しているため、
  router summary / description、knowledge schema docstring、similarity search service docstring から古い stub / Loop 5 予定表記を除去。
- **API設計書・README同期**:
  `docs/api_design.md` の Knowledge 節を実エンドポイント構成（list/search/similar/get/create）へ更新し、
  README footer を Loop 51 時点へ更新。

### Added (2026-07-19 Loop 50: notification API DB-backed completion)

- **通知センター API の DB-backed 化**:
  `notification_service.list_for_user` / `mark_read` / `mark_all_read` を
  `notifications` テーブルへ接続し、本人スコープ、`read_at` 更新、`email -> mail` channel alias、
  status/channel filter、pagination を実装。所有者以外の既読化は `403 Forbidden` で fail-closed。
- **通知テスト拡充**:
  notification service unit tests と `tests/integration/test_notifications_flow.py` を追加し、
  一覧・既読・全既読・他人アクセス拒否・不正filter 400を検証。
- **未実装誤表示の解消**:
  `app/main.py` の API router import 失敗ログから古い `not yet implemented` 表記を除去し、
  実際の import failure として記録するよう修正。

### Added (2026-07-19 Loop 49: Cloudflare legalops DNS readiness)

- **Cloudflare `legalops` サブドメイン確認をAPI対応へ拡張**:
  `scripts/verify_cloudflare_legalops.sh` に Cloudflare API read-only 確認を追加し、
  `mirai-dx-platform.com` zone が active であること、`legalops.mirai-dx-platform.com` の DNS record が
  Cloudflare API 上も 0 件であることを確認できるようにした。preflight は 22/22 PASS。
- **Cloudflare Runbook更新**:
  `docs/CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK.md` と `infra/cloudflare/README.md` に、
  Zone ID、Cloudflare NS、WebUI preview URL、systemd user service、DNS 未作成状態を反映。

### Added (2026-07-19 Loop 48: auth/upload API runtime completion)

- **認証 API の 501 経路解消**:
  `auth_service.exchange_code` / `revoke_session` を実装し、`GET /auth/sso/callback` と `POST /auth/logout` が
  汎用 stub に落ちず、SSOService wrapper + HttpOnly cookie / idempotent logout として動作するよう修正。
- **アップロード API の DB-backed 化**:
  `upload_service` を署名付き upload token + `attachments` メタデータ永続化へ置換。
  `POST /uploads/init` → `POST /uploads/complete` → `GET /uploads/{id}` → `DELETE /uploads/{id}` のフローを実装し、
  受理 MIME / 100MB 上限 / token署名検証 / soft delete を追加。

### Added (2026-07-19 Loop 47: user management API completion)

- **ユーザー管理 API の DB-backed 化**:
  `POST /users`, `PATCH /users/{id}`, `DELETE /users/{id}`, `POST /users/sync` を 501/stub 経路から外し、
  作成・部分更新・論理削除・Microsoft Graph 同期ジョブ受付を実装。削除は `is_active=false` + `deleted_at` の soft delete とし、
  admin 自身の自己削除は `409 Conflict` で拒否、`user.delete` 監査ログを記録。
- **ユーザー管理テスト拡充**:
  user service 単体テストと JIT identity integration に admin soft delete / self-delete fail-closed を追加。

### Added (2026-07-19 Loop 46: AI review start + Cloudflare legalops preflight)

- **AI レビュー開始 API の 501 解消**: `POST /contracts/{id}/reviews` が旧スタブ実装の 501 ではなく、
  `AIReviewService` 経由で構造化レビュー結果を `legal_reviews` に保存するよう修正。実本番 Claude key がない環境では
  決定論的 fallback を使い、API 契約を維持する。
- **Cloudflare `legalops` サブドメイン preflight**:
  `scripts/verify_cloudflare_legalops.sh` を追加し、`legalops.mirai-dx-platform.com` の Tunnel/DNS/Access/compose 設定、
  Cloudflare NS、CNAME 未作成状態、`cloudflared tunnel ingress validate` を read-only で検証。`pre_deploy_check.sh` に必須 gate として組み込み。

### Added (2026-07-19 Loop 45: contract template persistence)

- **契約ひな形 DB 永続化**: `contract_templates` ORM + Alembic `005_contract_templates` を追加し、既存 5 件の建設・法務向けテンプレートを seed。
  `POST /templates` は 501 ではなく `201 Created` を返し、`legal` / `admin` 権限で作成、`code` 重複時は `409 Conflict`。
- **API/DB 整合修正**: 条項ライブラリの `recommendation` を DB 制約と同じ `required/recommended/optional/prohibited` に統一し、backend schema と frontend API schema を更新。

### Changed (2026-07-19 Loop 44: CD approval gate hardening)

- **本番 CD fail-closed 強化**: `.github/workflows/deploy.yml` は `workflow_dispatch` / main / CI green / GitHub `production` environment 承認に加え、
  `production_change_approval=APPROVE_PRODUCTION_CHANGE` が無い限り GHCR publish と Cloudflare/Neon production gate を開始しない。
- **Cloudflare Tunnel dry-run 化**: Tunnel job は YAML と compose overlay の検証、および人間向け DNS route command 表示のみを行い、DNS/Tunnel/Access の実作成は行わない。

### Added (2026-07-18 Loop 33: Phase 1 最終整備 — CF/Neon IaC + 監視基盤完成)

- **Cloudflare/Neon IaC 整備 (Issue #50)**:
  `infra/cloudflare/wrangler.toml` (Pages 設定)、`access-policy.yml` (Access ポリシー定義)、
  `neon-config.md` (Neon 接続設定・マイグレーション手順)、`README.md` 更新。
  CD 経路に CF/Neon デプロイジョブ 3 件追加（当初 skip 設計。Loop 44 で approval phrase + fail-closed へ強化済み）。
- **JIT プロビジョニング残課題 2 件 (Issue #48)**:
  commit-after-response 窓の可観測性向上（`db_commit_failures_total` Counter + ログ警告）、
  JIT プロビジョニングを audit chain に統合（`audit_service.log` で `user.jit_provision` 記録）。
- **運用基盤完成 (Issue #51)**:
  `infra/monitoring/alertmanager.yml` (Alertmanager 設定)、
  `infra/monitoring/grafana-dashboard.json` (Grafana ダッシュボード 8 パネル)、
  DB プールメトリクス（`db_pool_size`/`db_pool_available`/`db_connection_errors_total`）、
  `DatabaseCommitFailures` アラートルール追加、
  docker-compose に Prometheus/Alertmanager/Grafana サービス追加（`--profile monitoring`）。

### Changed (2026-07-18 Loop 32: Phase 1 最終整備 — P2 改善)

- **PyJWT 移行 (Issue #41, commit 4ca68f3)**: `python-jose[cryptography]` → `PyJWT[crypto]>=2.9.0`。
  ecdsa/rsa 純 Python 暗号依存を除去。`security.py` の `JWTError` → `jwt.PyJWTError` への
  例外クラス変更 2 箇所、import を `import jwt` に統一。`session.py` に SQLite NullPool 検出を
  追加し pool_size 引数競合を防止。全回帰 906 passed / 19 JWT tests passed。
- **JIT プロビジョニング残課題 3 件修正 (Issue #48, commit 52d5a88)**:
  `ai_review_service.start_review` に `reviewer_id` を記録、
  `auth.refresh_token` に `oid` claim を伝搬（リフレッシュ後 JIT 不整合防止）、
  `audit_service` の `user_id` 型注釈を `UUID|None` → `int|UUID|None` に修正。
- **運用基盤設定追加 (Issue #51, commit 62e0032)**:
  `infra/monitoring/prometheus.yml` (FastAPI scrape 設定) +
  `infra/monitoring/alert.rules.yml` (6 alert rules) +
  `scripts/backup_db.sh` (pg_dump 圧縮バックアップ + restore スクリプト、30 日世代管理)。

### Added (2026-07-14: k6 負荷テスト基盤 — Issue #35, PR #36)

- **k6 負荷テストスイート** (`infra/k6/load-test.js`): smoke (5VU/30s) / load (最大20VU/約5min,
  SLO ゲート) / soak (10VU/10min) の 3 シナリオ。SLO: `p(95) < 500ms`・エラー率 `< 1%`。
- **CI ワークフロー** (`.github/workflows/load-test.yml`): workflow_dispatch + 週次スケジュール。
  `github.event.inputs.*` は `env:` 経由参照 (command injection 防御)、JWT は env 注入のみ。

### Fixed (2026-07-14 Supervisor session)

- **test_ai_settings の date bomb 解消 (Issue #43, PR #44)**: Claude dormancy gate (2026-07-01)
  通過で決定論的に失敗していた 2 テストを monkeypatch の日付固定で恒久修正。post-gate の
  fail-closed 挙動 (キー無し→failed / 形式不正→failed / 形式OK→unavailable) に新規テストを追加。
- **weekly pip-audit の赤化解消 (Issue #40, PR #42)**: `ecdsa 0.19.2` の PYSEC-2026-1325
  (CVE-2024-23342, Minerva timing attack, upstream won't-fix) を到達不能根拠付きで
  `--ignore-vuln` 化 (本プロジェクトは RS256/RSA のみ・ES*/ECDSA 使用 0 件)。
  恒久対応 (python-jose → PyJWT 移行による ecdsa 依存除去) は Issue #41 で追跡。
  main での security.yml 全 5 ジョブ TRUE GREEN を確認 (run 29296717568)。

### Fixed (2026-07-14: identity マッピング根治 — Issue #45, PR #47)

- **JIT ユーザープロビジョニング**: `get_current_user` が JWT principal を実 `users.id`
  (`CurrentUser.db_id`) へ解決 (oid/email lookup → get-or-create、savepoint 競合吸収)。
  JWT subject 文字列を BIGINT id として使う誤用 (hash 合成 drafter_id / スコープ WHERE 型不一致 /
  本人アクセス恒久 403 / 監査 actor_id 常時 NULL / workflow assignee 恒久拒否) を全数根絶。
- **fail-closed ガード**: 同一 email + 異 oid の解決拒否 (メール再割当てによる別人 merge 防止)、
  `is_active=false` / 論理削除行の解決拒否、token role の真実保存。対抗レビュー 2 系統
  (adversarial + silent-failure-hunter) の Critical 2 / High 2 を反映。残課題は Issue #48。
- **GET /users の MissingGreenlet 500 解消**: department の selectinload + `get_user` 実装。

### Changed (2026-07-14: CI fail-closed 化の完遂)

- **Jest HARD gate 化** (`ci.yml`, PR #37): `|| true` を除去 + `--forceExit`。`jest.config.ts` の
  `testPathIgnorePatterns` に `/e2e/` を追加し Playwright spec の誤収集 (7 スイート失敗) を解消。
- **backend-pg HARD gate 化** (`ci.yml`, PR #38): PG 統合テストの `|| true` を除去。
  SQLAlchemy 2.x の plain-str `server_default` DDL 破壊の `text()` ラップ修正、
  PG テストエンジンの NullPool 化 (asyncpg のループ跨ぎ根絶)、departments マスタシード、
  pure-ASGI ミドルウェア化 (BaseHTTPMiddleware 廃止)、電話マスキング最小桁ガードを含む。
  hard-gate 下で **PG 統合 151 passed / 0 failed** の真の green を実証。

### Added (Loop 20: AI プロバイダ設定 UI + 暗号化キー保管)

- **管理設定に「AI設定」タブを追加**: 管理者が Perplexity / Claude の API キーを
  入力・保存・接続テストできる UI (`frontend/components/settings/ai-settings-panel.tsx`)。
  キーは常にマスク済み (`••••abcd`) のみ表示し、平文は画面にもレスポンスにも一切返さない。
- **API キーの暗号化保管 (fail-closed)**: `settings_service.py` が `cryptography` Fernet で
  保存前に暗号化。鍵の解決順は ① `SETTINGS_ENCRYPTION_KEY` が有効な Fernet 鍵ならそのまま
  → ② 任意パスフレーズなら SHA-256 派生 → ③ 未設定なら `jwt_secret` から決定的に派生。
  どの経路でも **DB には平文を書かない**（復号不能時は保存自体を拒否）。
- **管理 API**: `GET /api/v1/admin/ai-settings`(一覧・マスク済) /
  `PUT /api/v1/admin/ai-settings/{provider}`(保存/クリア) /
  `POST /api/v1/admin/ai-settings/{provider}/test`(接続テスト)。
  すべて `require_role("admin")` で RBAC 保護。`provider` は
  `Literal["perplexity","claude"]` 型で DB CheckConstraint の前段に HTTP 422 を返す（多層防御）。
- **Claude の段階的縮退 (2026-07-01 まで)**: Claude キーは保存可能だが、接続テストは
  ゲート日前まで一切ネットワーク送信せず `status="unavailable"` を返す（エラーにしない）。
  Perplexity は初日から接続テスト可能。
- **DB スキーマ**: `ai_provider_settings` テーブル + Alembic migration `004`。
- **テスト**: `test_settings_service.py`(32) + `test_ai_settings.py`(14)。
  `settings_service.py` カバレッジ 99%。

### Security (Loop 20)

- API キーは平文で DB 保存しない（Fernet 暗号化・fail-closed）。
- 機密契約本文は Perplexity に送らない方針を `config.py` の設計コメントに明文化
  （送信は抽象化した論点・キーワードのみ、引用は公的ソース allowlist に限定）。

### Added (RS256 JWT 鍵ローテーション — Issue #19)

- **`kid` ヘッダ付き RS256 トークン**: 署名鍵の SHA-256 サムプリント先頭 8 バイト（16 hex）を `kid` として埋め込み。`JWT_KEY_ID` で明示指定も可能。
- **複数鍵検証セット (zero-downtime rotation)**: `JWT_PUBLIC_KEYS`（PEM の JSON 配列）に退役鍵を保持することで、旧鍵で署名されたトークンが失効まで検証可能。
- **Fail-closed 設計**: 不正な `JWT_PUBLIC_KEYS` は空集合へフォールバック（信頼鍵を黙って拡張しない）。未知の `kid` を持つトークンは拒否。空文字列 `kid`（`{"kid": ""}`）も「kid なし」として扱い、細工トークンが鍵探索をすり抜けるのを防止。
- **署名側 fail-fast / 検証側 resilient の責務分離**: `create_access_token` は RS256 設定下で kid を導出できない場合に署名を拒否（kid なし RS256 トークンを発行しない）。一方、検証セット構築（`_jwt_active_kid` / 退役鍵スキップ）は壊れた鍵を None+警告で受け流し、退役鍵による検証可用性を維持。
- **`JWT_REQUIRE_KID` 運用スイッチ**: ローテーション移行完了後に kid なし RS256 トークンを fail-closed で拒否（既定 false。全トークンが kid を持つ運用に切り替わってから true へ）。
- **可観測性**: 鍵設定の不正（公開鍵 malformed・`JWT_PUBLIC_KEYS` の JSON parse 失敗・非 list・退役鍵スキップ）は全て `logging.warning` で記録（本番でのサイレント失敗を禁止）。`security.py` / `config.py` の import 軽量性を保つため structlog ではなく stdlib `logging` を採用。
- **後方互換**: `kid` を持たないローテーション前トークンはアクティブ公開鍵にフォールバック（`JWT_REQUIRE_KID=false` 時）。HS256 パスも維持（dev/test）。
- **テスト**: `tests/unit/test_jwt_rs256.py` に 19 ケース（HS256/RS256 roundtrip・wrong key 拒否・rotation・unknown kid 拒否・explicit kid・legacy token・malformed 退役鍵混在・空 kid 拒否・`JWT_REQUIRE_KID` legacy 拒否・署名側 fail-fast）。

### Added (Loop 24-30: 本番同等スタック検証 + CD 経路確立 + 運用文書整備)

> **現状**: v0.1.11 / Loop 30 完了 / 全 PR マージ済み / main CI 7/7 SUCCESS（run 29309456627, 2026-07-14）。
> **本番デプロイ**: 未実行（人間承認待ち状態）。

#### Loop 24 (k6 負荷テスト基盤 — Issue #35, PR #36)
- 3 シナリオ構成: smoke(5VU/30s) / load(0→20VU ramp SLO ゲート) / soak(10VU/10min メモリリーク検出)
- SLO: p(95) < 500ms / エラー率 < 1%
- 認証エンドポイントは `JWT_TOKEN` 環境変数設定時のみ実行、CI は無認証で liveness/readyz 計測
- `/readyz` 呼び出し頻度制限（`__ITER % 5 === 0` ゲート）で DB 過負荷回避
- `infra/k6/load-test.js` + `infra/k6/README.md`

#### Loop 25 (Jest HARD ゲート化 — PR #37)
- `|| true` ソフトフェイル廃止 → HARD CI ゲート化
- `frontend/e2e/` を Jest `testPathIgnorePatterns` に追加（Playwright spec の誤収集解消）
- `@testing-library/dom` を devDependencies に追加

#### Loop 27 (Issue #45 根治 + PR #38 hard-gate)
- **CurrentUser.db_id + JIT プロビジョニング**: `get_current_user` で oid/email lookup → get-or-create、savepoint 競合吸収
- 誤用全数修正: hash 合成廃止 / WHERE ×8 / 認可比較 / 監査 actor ×30
- `user_service.selectinload` + ARRAY patch 自己再帰修正
- users シード撤去（JIT が代替）
- PR #47 / PR #38

#### Loop 28 (運用文書 4 本 + Cloudflare/Neon 移行計画)
- `docs/OPERATIONS.md` — 日常運用手順（サービス構成・起動停止・ログ・スケール）
- `docs/MONITORING.md` — 監視対象・エンドポイント仕様・未整備項目の明示
- `docs/INCIDENT_RESPONSE.md` — 障害対応手順（エスカレーション・復旧ランブック）
- `docs/BACKUP_RESTORE.md` — バックアップ・リストア手順
- `docs/CLOUDFLARE_NEON_MIGRATION_PLAN.md` — 採用判断用候補文書（人間判断待ち、Issue #50）
- PR #52

#### Loop 29 (CD 経路 + マイグレーション CI ゲート)
- `.github/workflows/deploy.yml` (CD: image publish) — GHCR イメージ発行
- `infra/cloudflare/tunnel-config.example.yml` — Cloudflare Tunnel IaC 雛形
- `infra/cloudflare/README.md`
- alembic URL 解決の欠陥修正 + マイグレーション CI ゲート新設
- PR #53 / PR #54

#### Loop 30 (P1 ×3 根治 + 本番同等スタック検証)
- CI 内本番同等スタック検証の確立（PostgreSQL 16 + Redis 7 で実走）
- k6 SLO 達成（p95 < 500ms、エラー率 < 1%）
- マイグレーションゲートで本番スキーマ整合性を保証
- PR #55

### Security (Loop 21-30)
- **weekly security.yml true green**: pip-audit スコープ修正 + python-jose >=3.4.0 bump + Bandit SARIF graceful (PR #30, v0.1.11)
- **HIGH CVE 修正**: form-data CRLF injection + ws DoS を npm audit fix で解消 (PR #33)
- **ecdsa PYSEC-2026-1325 (won't-fix) 到達不能根拠付き ignore**: 依存ツリーには存在するが実コードで未使用 (PR #42, Issue #40)
- **Trivy install 404 回避**: main 版・version 引数省略 + backend/frontend image CVE 解消 (PR #26)

### Compliance Notes
- 本プロダクトは **生成 AI による法的判断の確定を提供しません**。AI 出力は下書きであり、弁護士法第 72 条の遵守、社内法務ガバナンス、顧問弁護士の最終確認を必須運用とします。
- 監査ログ (プロンプト・応答・モデルバージョン) は法定保存期間に従い保持されます。
- 認証・認可・DB スキーマ・並列処理変更は Codex 対抗レビュー必須。

### Known Limitations (Loop 30 時点の本番デプロイ前残課題)
- ⚠️ **P0: 本番環境 Vault secrets 投入**（人間作業: `./scripts/setup_vault_secrets.sh`、Issue #23）
- ⚠️ **P0: CSP Report-Only → enforce 移行**（ops 7 日後: `infra/nginx/security-headers.enforce.conf` 適用、Issue #24）
- ⚠️ **P2: Cloudflare/Neon 移行の採否**（人間判断: Issue #50）
- ⚠️ **P2: 運用基盤ギャップ**（Prometheus/Grafana/Alertmanager/自動バックアップ — Issue #51）
- ⚠️ **P2: python-jose → PyJWT 移行**（ecdsa/rsa 純 Python 暗号依存の除去 — Issue #41）
- ⚠️ **P2: JIT プロビジョニング残課題**（commit 境界 / requester 帰属 / identity linking — Issue #48）

[Unreleased]: https://github.com/Kensan196948G/Construction-LegalOps-DX/compare/v0.1.12...HEAD
[0.1.12]: https://github.com/Kensan196948G/Construction-LegalOps-DX/compare/v0.1.11...v0.1.12

## [0.1.8] - 2026-05-30

### Added (Loop 18 Part 2: Test Coverage 91% Milestone)

- **Unit テスト大幅追加**: 84 → 812 件 (+728件)。全サービス 90%+ カバレッジ達成。
  `dashboard/contract/compliance/risk/knowledge/template/audit/notification/file_parser/ai_review/clause_extractor/sharepoint/sso` 全サービスをカバー。
- **knowledge_service ハイブリッド検索**: `KnowledgeArticle` + `Contract` 両ソースを統合検索。
  記事を優先（score=1.0）、契約書補完（score=0.8）。
- **Alembic migration 003**: `pg_trgm` GIN インデックスを `knowledge_articles.title/body` に追加。
- **GitHub Project #30**: Construction-LegalOps-DX 開発管理プロジェクト作成、Issue #19-21 登録。
- **RSA 鍵生成スクリプト**: `scripts/generate_rsa_keys.sh` 追加（RS256 コードは既実装済み）。

### Fixed (Loop 18 Part 2)

- **review_service.accept() ステータスガード**: `COMPLETED` が pre-condition として許可されていた fail-open バグを修正。正しくは `PENDING` または `RUNNING` のみ許可。
- **review_service.list_reviews()**: `__import__("sqlalchemy")` インラインハック → `from sqlalchemy import func` に修正。
- **mypy 2.1 互換**: `# type: ignore[method-assign, assignment]` — `method-assign` は `assignment` をカバーしなくなった変更への対応。

### Added (Loop 18: Backend DB Persistence + Test Coverage)

- **知識記事 DB**: `KnowledgeArticle` ORM モデル + Alembic migration 002。`create_article()` を実装 (以前は 501)。
- **pg_trgm インデックス**: Alembic migration 003 で `knowledge_articles.title/body` に GIN trigram インデックスを追加。
- **条項ライブラリ DB 永続化**: `template_service.list_clauses/create_clause/update_clause` を `ClauseLibrary` ORM に切替。in-memory シードから完全 DB バックへ移行。
- **RSA 鍵生成スクリプト**: `scripts/generate_rsa_keys.sh` 追加。RS256 は `security.py` で既に実装済み。
- **GitHub Project #30**: Construction-LegalOps-DX 開発管理プロジェクト作成。Issue #19〜#21 登録。
- **E2E Playwright 基盤**: `playwright.config.ts` + `e2e/smoke.spec.ts` / `contracts.spec.ts` / `dashboard.spec.ts`。
- **テストカバレッジ向上**: 84 → 253 件 (+169)
  - `workflow_service.py`: 38% → 100% (ユニット 46 件 + 統合 27 件)
  - `review_service.py`: 38% → 100% (ユニット 43 件)
  - 全体カバレッジ: 68% → 74%
- **pyproject.toml**: `[[tool.mypy.overrides]]` で `tests.*` を ignore_errors 対象に追加 (mypy strict はプロダクション限定)。

### Fixed

- **FastAPI 0.115**: `HTTP 204` エンドポイントで `response_model=None` が必要。`-> None` の return annotation が `NoneType`（truthy）として解釈されていた問題を修正。
- **Trivy CI**: `aquasecurity/trivy-action@0.29.0/0.31.0` が存在しない → Trivy CLI 直接インストールに変更。fail-closed スキャン + JSON アーティファクト保存に変更。
- **SQLAlchemy ARRAY SQLite**: `@compiles(ARRAY, "sqlite")` は DDL のみ対応。`bind_processor` / `result_processor` monkey-patch を追加し Python list の JSON シリアライズを実現。
- **mypy 2.1 互換**: `# type: ignore[method-assign]` が `assignment` エラーをカバーしなくなった。`[method-assign, assignment]` に変更。
- **code review 指摘 (Loop 18)**: N+1 full-table fetch → COUNT subquery + LIMIT/OFFSET / GROUP BY subquery / HTTPException in service layer → NotImplementedError / compliance viewer scope / \_NOW → \_STUB_TS。

## [0.1.0] - 2026-05-16

本リリースは Construction-LegalOps-DX の最小実行可能プロダクト (MVP) を構成する 5 ループ分の成果をまとめたものです。すべての AI 機能は **「AI は法的判断を確定しない。最終判断は法務担当者および顧問弁護士に帰属する」** という原則のもとに設計されています。

### Added (Loop 1: Foundation / プロジェクト基盤構築)

- リポジトリ初期スキャフォールド (backend / frontend / infra / docs ディレクトリ)。
- `README.md` (プロジェクト概要・技術スタック・起動手順・AI 免責) を作成。
- `LICENSE` (Apache License 2.0、Copyright 2026 Construction-LegalOps-DX Contributors) を追加。
- `.gitignore` / `.env.example` / `.editorconfig` を整備。
- `CONTRIBUTING.md` (Conventional Commits、AI レビュー人間確認義務) を追加。
- `CHANGELOG.md` (Keep a Changelog 形式) を追加。
- GitHub Actions ワークフロー `.github/workflows/ci.yml` (backend / frontend / security / docker build) を追加。
- `infra/docker/docker-compose.yml` のサービス枠 (postgres / backend / frontend / nginx) を追加。
- 法務 DX 設計ドキュメント (`docs/requirements.md`, `system_architecture.md`, `api_design.md`, `database_design.md`, `ai_disclaimer_policy.md`, `legal_playbook.md` 等) を整備。

### Added (Loop 2: Backend MVP / FastAPI コア実装)

- FastAPI アプリケーションエントリ (`backend/app/main.py`) と設定モジュール (`app/core/config.py`)。
- SQLAlchemy 2.x モデル (users / contracts / contract_reviews / workflows / audit_logs) と Alembic マイグレーション。
- 認証ルーター (Entra ID OIDC + JWT 発行、RBAC ミドルウェア)。
- 契約書 CRUD ルーターと SharePoint 連携サービススタブ。
- Claude API ラッパー (`app/services/ai/claude_client.py`) と契約書レビュー下書き生成 API。AI 出力には常に「下書き / 人間確認必須」のメタデータを付与。
- desknet's NEO ワークフロー連携サービススタブ。
- 監査ログ書き込みサービス (プロンプト・モデル・応答メタを保存)。
- pytest による単体・結合テスト初期セット。

### Added (Loop 3: Frontend MVP / Next.js 画面実装)

- Next.js 14 App Router 構成と Tailwind / shadcn/ui セットアップ。
- ログイン画面 (Entra ID 認証フロー) とトークン管理 hook。
- ダッシュボード・契約書一覧・契約書詳細・AI レビュー結果表示画面。
- AI 出力表示コンポーネントに **「AI による下書きです。法的判断は法務担当者・顧問弁護士の確認を経てください」** のディスクレーマーを常時表示。
- ワークフロー申請・承認 UI と監査ログ閲覧ビュー。
- TanStack Query によるサーバ状態管理、Jest / React Testing Library テスト。

### Added (Loop 4: Security & Infra / セキュリティ・基盤強化)

- nginx リバースプロキシ設定 (TLS 終端、HSTS、セキュリティヘッダ)。
- Content Security Policy を Report-Only モードで導入 (本番 enforce 移行は次バージョン)。
- PostgreSQL 16 本番想定パラメータと audit_logs テーブルの INSERT/UPDATE/DELETE トリガー。
- Redis 7 によるセッション / レートリミット基盤。
- `/healthz` / `/readyz` ヘルスエンドポイント。
- Trivy / Bandit / npm audit を CI に組み込み、Critical/High はマージブロック。
- secrets 管理ポリシー (HENNGE / Entra / Anthropic / JWT keys を `.env` / Secrets Manager 経由で投入)。

### Added (Loop 5: Integration & Finalization / 統合・最終化)

- E2E 結合シナリオ (login → 契約書アップロード → AI レビュー → ワークフロー承認 → 監査ログ確認) のテストハーネス。
- `docs/RELEASE_CHECKLIST.md` (本番リリース前チェックリスト) を新規追加。
- `docs/HANDOVER.md` (次セッション引き継ぎ書) を新規追加。
- `README.md` に Quick Start / Compliance & Disclaimer / Project Timeline セクションを追加。
- `state.json` にループ完了状態 (`loops_total: 5`, `status: "loops_complete"`) を反映。

### Compliance Notes

- 本プロダクトは **生成 AI による法的判断の確定を提供しません**。AI 出力は下書きであり、弁護士法第 72 条の遵守、社内法務ガバナンス、顧問弁護士の最終確認を必須運用とします。
- 監査ログ (プロンプト・応答・モデルバージョン) は法定保存期間に従い保持されます。
- 認証・認可・DB スキーマ・並列処理変更は Codex 対抗レビュー必須。

### Known Limitations (Loop 5 時点の未解決事項)

- CSP は Report-Only のまま (enforce 移行は本番リリース前に実施)。
- `/readyz` の本番チューニング (依存サービス全件 deep check) は未完。
- JWT 署名鍵は HS256 暫定運用、本番リリース前に RS256 鍵生成・ローテーション機構へ切替予定。
- 結合テストの PostgreSQL profile 切替は SQLite フォールバックが残存。

[Unreleased]: https://github.com/Construction-LegalOps-DX/Construction-LegalOps-DX/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Construction-LegalOps-DX/Construction-LegalOps-DX/releases/tag/v0.1.0
