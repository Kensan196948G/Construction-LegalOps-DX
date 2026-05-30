# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
