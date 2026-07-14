# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
