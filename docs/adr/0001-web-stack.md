# ADR 0001 — FastAPI + Next.js + PostgreSQL を採用する

- 状態: Accepted
- 決定日: 2026-05-16

## コンテキスト

従業員約 600 名の建設会社で、法務・契約・コンプライアンス業務を支援する基盤を新規構築する。
IT・DX 部門は 7 名と少人数のため、保守しやすく型安全性の高いスタックが求められる。
既存環境は Windows Server / Azure / Microsoft 365 が中心で、添付実体は SharePoint Online を前提とする。

## 決定

- API 基盤: FastAPI（Python 3.12、Pydantic v2、OpenAPI 自動生成）
- Web: Next.js 15（App Router、React Server Components） + shadcn/ui
- DB: PostgreSQL 16（正本） + SQLAlchemy 2.0 + Alembic
- 非同期ジョブ: Celery + Redis
- 監査・監視: Prometheus / Grafana / Loki / Alertmanager

## 結果

- 型検査（mypy strict / TypeScript strict）と静的解析（ruff / ESLint）を CI ハードゲート化できる。
- 既存の Microsoft スタック（Entra ID / SharePoint / Exchange）とは REST + OAuth で連携する。
- 採用時の前提として、SQLite はテスト専用とし、本番相当検証は PostgreSQL 16 で行う。
