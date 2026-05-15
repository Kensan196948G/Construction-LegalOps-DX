# Construction-LegalOps-DX

[![Build](https://img.shields.io/github/actions/workflow/status/Construction-LegalOps-DX/Construction-LegalOps-DX/ci.yml?branch=main&label=build&logo=github)](./.github/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-pending-lightgrey.svg)](./.github/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Node](https://img.shields.io/badge/node-20.x-339933?logo=node.js&logoColor=white)](https://nodejs.org/)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow.svg)](https://www.conventionalcommits.org/)

建設業特化型の法務・契約・コンプライアンスを **DX (デジタルトランスフォーメーション)** するための社内基盤プロジェクトです。
契約書管理・電子帳簿保存法対応・建設業法に関する社内法令ナレッジ運用を、AI 支援と既存業務システム（SharePoint / desknet's NEO / Microsoft Entra ID）連携によって統合的に効率化します。

---

## 目次

1. [プロジェクト概要](#プロジェクト概要)
2. [目的とスコープ](#目的とスコープ)
3. [技術スタック](#技術スタック)
4. [ディレクトリ構造](#ディレクトリ構造)
5. [Quick Start](#quick-start)
6. [起動手順](#起動手順)
7. [開発フロー](#開発フロー)
8. [AI 利用に関する免責](#ai-利用に関する免責)
9. [Compliance & Disclaimer](#compliance--disclaimer)
10. [Project Timeline](#project-timeline)
11. [コントリビューション](#コントリビューション)
12. [ライセンス](#ライセンス)

---

## プロジェクト概要

Construction-LegalOps-DX は、建設業の現場・本社・法務部門にまたがる法務オペレーション
（契約書レビュー、下請法対応、建設業法に基づく書類整備、社内法令照会など）を、
以下の三本柱で支援する社内システムです。

- **契約・法務ドキュメント管理**: SharePoint と連携し、契約書のバージョン管理・期限通知・電子帳簿保存法要件を満たすメタデータ管理を提供。
- **AI 法務アシスト**: Claude API を用いた契約書要約・リスク観点抽出・社内ナレッジ Q&A（必ず人間レビューを経由）。
- **業務連携**: desknet's NEO のワークフロー、Microsoft Entra ID による SSO、社内既存ポータルとのシングルサインオン統合。

## 目的とスコープ

| カテゴリ | スコープ内 | スコープ外 |
|----------|------------|------------|
| 契約管理 | 契約書台帳・有効期限通知・改訂履歴 | 外部 EDI 連携 |
| 法務 Q&A | 社内規程・建設業法に基づく一次回答（AI 下書き） | 弁護士業務（独占業務）の代行 |
| 文書保管 | 電子帳簿保存法・建設業法に基づく保管要件 | 紙原本の物理保管 |
| アクセス制御 | Entra ID による SSO・RBAC | 個別アカウントの新規発行 |

## 技術スタック

### バックエンド
- **言語**: Python 3.12
- **フレームワーク**: FastAPI
- **ORM**: SQLAlchemy 2.x / Alembic
- **AuthN/Z**: Microsoft Entra ID (OIDC) + JWT
- **AI**: Anthropic Claude API
- **テスト**: pytest, pytest-asyncio
- **品質**: ruff, mypy, bandit

### フロントエンド
- **フレームワーク**: Next.js 14 (App Router)
- **言語**: TypeScript 5.x
- **UI**: React 18, Tailwind CSS, shadcn/ui
- **状態管理**: TanStack Query
- **テスト**: Jest, React Testing Library, Playwright (E2E は Loop 3 以降)
- **品質**: ESLint, Prettier, tsc --noEmit

### インフラ
- **DB**: PostgreSQL 16
- **キャッシュ**: Redis 7
- **リバースプロキシ**: nginx
- **コンテナ**: Docker / docker compose
- **CI/CD**: GitHub Actions
- **セキュリティ**: Trivy（イメージ脆弱性）、Bandit（Python 静的解析）

### 外部連携
- Microsoft Entra ID（SSO・RBAC）
- SharePoint Online（契約書ストレージ）
- desknet's NEO（ワークフロー）
- Anthropic Claude API（AI 法務アシスト）

## ディレクトリ構造

```
Construction-LegalOps-DX/
├── backend/                  # FastAPI アプリケーション
│   ├── app/                  # API ルーター・ドメイン・サービス層
│   └── tests/                # pytest 単体・結合テスト
├── frontend/                 # Next.js アプリケーション
│   ├── src/                  # ページ・コンポーネント・hooks
│   └── public/               # 静的アセット
├── infra/                    # インフラ関連
│   ├── docker/               # docker-compose 一式
│   ├── nginx/                # nginx 設定
│   └── scripts/              # 補助スクリプト
├── docs/                     # 仕様書・運用手順・ADR
├── .github/
│   └── workflows/            # GitHub Actions
├── .env.example              # 環境変数サンプル
├── .editorconfig             # エディタ共通設定
├── .gitignore
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE                   # Apache License 2.0
└── README.md
```

## Quick Start

最短手順でローカル開発環境を起動するためのガイドです。詳細は後続の「起動手順」セクションを参照してください。

### 必要環境

- **Docker** 24.x 以上 + docker compose v2 系
- **Python** 3.12（ローカル backend 開発時）
- **Node.js** 20.x（ローカル frontend 開発時）
- **OS**: Linux / macOS / WSL2

### 1. リポジトリ取得と環境変数

```bash
git clone https://github.com/Construction-LegalOps-DX/Construction-LegalOps-DX.git
cd Construction-LegalOps-DX
cp .env.example .env
```

`.env` を開き、以下の値を必ず埋めてください（本番では Secrets Manager / Vault 経由を推奨）。

| キー | 用途 | 取得元 |
|------|------|--------|
| `POSTGRES_PASSWORD` | DB パスワード | 任意の強力な値 |
| `JWT_SECRET_KEY` | JWT 署名鍵 (HS256 暫定) | `openssl rand -hex 32` |
| `ENTRA_TENANT_ID` / `ENTRA_CLIENT_ID` / `ENTRA_CLIENT_SECRET` | Entra ID SSO | Azure Portal |
| `ANTHROPIC_API_KEY` | Claude API | Anthropic Console |
| `SHAREPOINT_TENANT_ID` / `SHAREPOINT_CLIENT_ID` | SharePoint 連携 | Microsoft 365 管理センター |
| `HENNGE_*` | HENNGE Access Control (任意) | HENNGE 管理画面 |

### 2. docker compose で一括起動

```bash
docker compose -f infra/docker/docker-compose.yml up -d
```

- 全コンテナ起動後、`http://localhost` (nginx 経由) でフロントエンドへアクセス。
- API は nginx 経由で `http://localhost/api/` にプロキシされます。
- 初回起動時は `alembic upgrade head` を backend コンテナで実行してください。

```bash
docker compose -f infra/docker/docker-compose.yml exec backend alembic upgrade head
```

### 3. 開発モード（ホットリロード）

backend のみ手元で動かす場合:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

frontend のみ手元で動かす場合:

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

### 4. 動作確認

```bash
curl http://localhost/healthz       # nginx 経由のヘルスチェック
curl http://localhost:8000/healthz  # backend 直接
open http://localhost               # フロントエンド
```

---

## 起動手順

### 前提

- Docker 24.x 以上、docker compose v2 系
- （ローカル開発の場合）Python 3.12, Node.js 20.x
- `.env` ファイル（`.env.example` をコピーして編集）

### 1. 環境変数の準備

```bash
cp .env.example .env
# エディタで .env を開き、各種シークレットを設定
```

### 2. Docker Compose による起動

```bash
docker compose -f infra/docker/docker-compose.yml up -d
```

| サービス | デフォルトポート | 説明 |
|----------|------------------|------|
| frontend | 3000             | Next.js 開発サーバ |
| backend  | 8000             | FastAPI |
| postgres | 5432             | PostgreSQL 16 |
| nginx    | 80               | リバースプロキシ |

### 3. 動作確認

```bash
curl http://localhost:8000/healthz
open http://localhost:3000
```

### 4. 停止

```bash
docker compose -f infra/docker/docker-compose.yml down
```

## 開発フロー

本プロジェクトは **6 ヶ月固定スコープ** で進行し、`Monitor → Build → Verify → Improve` の
ループサイクルで CTO 委任のもと運用されます。

1. **Issue 起票**: GitHub Projects に紐付ける（Goal / Loop / Phase ラベル必須）。
2. **ブランチ作成**: `feature/<topic>` / `fix/<topic>` / `docs/<topic>`（詳細は CONTRIBUTING.md）。
3. **実装**: Conventional Commits 準拠でコミット。
4. **PR 作成**: `main` 向け。テンプレートに沿って Test Plan を必ず記載。
5. **AI レビュー**: `/codex:review` と `/coderabbit:review` を併用。Critical/High はマージ前必須解消。
6. **人間レビュー**: 認証・認可・DB スキーマ・並列処理変更時は対抗レビュー必須。
7. **マージ**: Squash Merge を推奨。CHANGELOG.md に追記。

### ローカル品質チェック

```bash
# backend
cd backend && ruff check . && mypy app && pytest

# frontend
cd frontend && npm run lint && npm run typecheck && npm test
```

## AI 利用に関する免責

本システムは Anthropic Claude API を含む生成 AI を法務業務支援に利用しますが、
**AI による出力は最終判断ではなく、必ず有資格者・担当者による人間レビューを経たうえで業務利用してください**。

- AI 出力は **下書き** であり、法的助言・最終判断を構成しません。
- 弁護士法第 72 条に抵触する用途（個別具体的な法律相談への回答の代行など）には利用しないでください。
- AI に投入する情報は、社内データガバナンス規程および個人情報保護法の遵守を前提とします。
- AI の誤出力（ハルシネーション）が発生し得ることを前提に、根拠条文・出典の人間確認を必須プロセスとして組み込みます。
- 監査ログ（プロンプト・モデル・応答メタデータ）は法定保存期間に従って保管します。

## コントリビューション

開発参加方法・コミット規約・PR テンプレートは [CONTRIBUTING.md](./CONTRIBUTING.md) を参照してください。

主な要点:

- Conventional Commits を採用（`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:` など）。
- PR は最低 1 名の人間レビュアー + AI レビュー両方の承認を経てマージ。
- セキュリティ関連の指摘（Trivy/Bandit）は Critical/High を必ず解消。

## Compliance & Disclaimer

本システムは建設業法・電子帳簿保存法・下請法等の業務遵守を支援するための **社内 DX 基盤** です。生成 AI を含むすべての自動処理は法的助言を構成せず、最終判断は人間に帰属します。

- **AI は法的判断を確定しません。** Claude API を含む AI 出力はあくまで一次下書き・参考情報であり、契約締結・法的助言・社内意思決定の根拠となるものではありません。
- **最終判断は法務担当者および顧問弁護士に帰属します。** AI 出力をそのまま外部送付・契約相手方への回答に用いることは禁止です。
- **弁護士法第 72 条遵守。** 個別具体的な法律相談に対する回答代行（非弁行為）には利用しないでください。
- **監査ログの保管。** プロンプト・モデルバージョン・応答メタは法定保存期間に従い `audit_logs` テーブルおよびトリガーで保全されます。
- **データガバナンス。** AI に投入する情報は社内データガバナンス規程・個人情報保護法・営業秘密保護を前提に取扱います。機微情報のマスキング処理は backend サービス層で実施されます。
- **ハルシネーション前提運用。** 根拠条文・出典の人間確認を必須プロセスとして UI / ワークフローに組み込んでいます。

詳細は [`docs/ai_disclaimer_policy.md`](./docs/ai_disclaimer_policy.md) および [`docs/legal_playbook.md`](./docs/legal_playbook.md) を参照してください。

## Project Timeline

本プロジェクトは **登録日から 6 ヶ月の固定スコープ** で運営されます。リリース期限は絶対厳守です。

| 項目 | 日付 |
|------|------|
| プロジェクト登録日 | **2026-05-16** |
| 本番リリース期限 | **2026-11-16** |
| 期間 | 6 ヶ月 (約 184 日) |

### 6 ヶ月分割計画

| 期間 | フォーカス |
|------|------------|
| Month 1〜2 (2026-05-16 〜 2026-07-15) | 基盤整備・主要機能実装 (Loop 1〜3) |
| Month 3〜4 (2026-07-16 〜 2026-09-15) | 品質向上・テスト整備 (Loop 4) |
| Month 5 (2026-09-16 〜 2026-10-15) | 統合テスト・バグ修正 (Loop 5) |
| Month 6 (2026-10-16 〜 2026-11-16) | リリース準備・本番移行 |

### 残日数による自動縮退ルール

リリース期限 **2026-11-16** までの残日数に応じ、以下のルールで開発スコープを自動縮退します。

- **残 30 日以内**: Improvement フェーズを縮退し、Verify / リリース準備を最優先。
- **残 14 日以内**: 新機能開発禁止。バグ修正・安定化のみ許可。
- **残 7 日以内**: リリース準備のみ (CHANGELOG / README / タグ付け / RELEASE_CHECKLIST 完遂)。

詳細な本番移行手順は [`docs/RELEASE_CHECKLIST.md`](./docs/RELEASE_CHECKLIST.md)、次セッション引き継ぎは [`docs/HANDOVER.md`](./docs/HANDOVER.md) を参照してください。

## ライセンス

本プロジェクトは [Apache License 2.0](./LICENSE) のもとで公開されています。

Copyright (c) 2026 Construction-LegalOps-DX Contributors

---

> 本 README は Loop 5（Integration & Finalization, 2026-05-16 更新）時点のものです。
> 本番リリース (2026-11-16) までに残課題（CSP enforce 化、RS256 移行、`/readyz` 本番チューニング等）を解消する計画です。
