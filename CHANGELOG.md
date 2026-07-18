# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added (2026-07-18 Loop 33: Phase 1 最終整備 — CF/Neon IaC + 監視基盤完成)

- **Cloudflare/Neon IaC 整備 (Issue #50)**:
  `infra/cloudflare/wrangler.toml` (Pages 設定)、`access-policy.yml` (Access ポリシー定義)、
  `neon-config.md` (Neon 接続設定・マイグレーション手順)、`README.md` 更新。
  CD 経路に CF/Neon デプロイジョブ 3 件追加（fail-safe skip 設計）。
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

[Unreleased]: https://github.com/Construction-LegalOps-DX/Construction-LegalOps-DX/compare/v0.1.11...HEAD

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
