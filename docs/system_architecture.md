# システムアーキテクチャ — Construction-LegalOps-DX

最終更新: 2026-05-16
版数: v1.0 (Draft)
所管: アーキテクチャドキュメントチーム

---

## 1. 目的とスコープ

本書は Construction-LegalOps-DX (以下、本システム) のシステムアーキテクチャを定義する。MVP リリースに必要なレイヤー構成、技術スタック、主要データフロー、外部連携の境界、AI レビュー処理シーケンス、運用観点までを対象とする。

---

## 2. アーキテクチャ原則

1. **モジュラーモノリスから始める**: FastAPI 上にドメイン分割した単一バイナリで MVP を構築し、必要時にサービス分離する。
2. **Server Components ファースト**: Next.js 15 の RSC を主、Client Components は最小限。
3. **API はバージョニング必須**: `/api/v1/...` を起点、破壊的変更時のみ `v2` 採番。
4. **Idempotent な書き込み**: 重要 API には `Idempotency-Key` を導入。
5. **AI は補助、判断は人間**: AI 出力は記録するが、ステータス遷移には人間承認を必須とする。
6. **すべての書き込みは監査ログに記録**: hash chain による改ざん検知。
7. **ゼロトラスト指向**: 内部ネットワーク信頼に依存しない。SSO + RBAC + RLS。

---

## 3. 全体レイヤー図 (ASCII)

```
+----------------------------------------------------------------------+
|                       利用者 (社内 / 顧問弁護士)                       |
|     ブラウザ (Edge / Chrome)   |   モバイルブラウザ (参照のみ)           |
+--------------------------------+-------------------------------------+
                 |                                |
                 v                                v
+----------------------------------------------------------------------+
|                HENNGE One (IP 制限 / セキュアゲートウェイ)              |
+----------------------------------------------------------------------+
                                |
                                v
+----------------------------------------------------------------------+
|                Edge / リバースプロキシ (Nginx + TLS1.3)                |
+----------------------------------------------------------------------+
        |                                       |
        v                                       v
+---------------------+              +-------------------------------+
|  Frontend           |  RSC fetch   |  Backend (FastAPI)            |
|  Next.js 15         | <----------> |  Python 3.12                  |
|  TypeScript / RSC   |  REST / OIDC |  SQLAlchemy 2.x / Pydantic v2 |
|  Tailwind + shadcn  |              |  Alembic (DB migration)       |
+----------+----------+              +---+-----------+----------+----+
           |                              |           |          |
           |                              v           v          v
           |                       +--------+   +--------+   +--------+
           |                       | Redis  |   | Worker |   | Audit  |
           |                       | Cache  |   | (RQ /  |   | Chain  |
           |                       | Queue  |   | Celery)|   | Verify |
           |                       +--------+   +--------+   +--------+
           |                              |           |
           +-------------+                v           v
                         |        +----------------------------+
                         |        | PostgreSQL 16              |
                         |        |  - contracts / reviews     |
                         |        |  - audit_logs (hash_chain) |
                         |        |  - workflow_*              |
                         |        +----------------------------+
                         |
        +----------------+----------------+----------------+
        v                v                v                v
+---------------+ +---------------+ +---------------+ +---------------+
| Entra ID OIDC | | SharePoint    | | Exchange      | | Claude API    |
| (SSO / Graph) | | Online (file) | | Online (mail) | | Anthropic     |
+---------------+ +---------------+ +---------------+ +---------------+
                         |
                         v
                +-------------------+
                | DeskNet's Neo API |
                +-------------------+
```

---

## 4. 技術スタック

### 4.1 フロントエンド

| 領域 | 技術 | 補足 |
|------|------|------|
| フレームワーク | Next.js 15 (App Router) | RSC を主 |
| 言語 | TypeScript 5.x | strict mode |
| UI | Tailwind CSS + shadcn/ui | 自社デザイントークン |
| 状態管理 | React Server Components + React Context + URL state | client store は最小限 (TanStack Query) |
| フォーム | react-hook-form + zod | バリデーション統一 |
| 国際化 | next-intl | MVP は ja のみ |
| アクセシビリティ | WCAG 2.1 AA | Lighthouse a11y 90+ |

### 4.2 バックエンド

| 領域 | 技術 | 補足 |
|------|------|------|
| フレームワーク | FastAPI 0.115+ | ASGI |
| 言語 | Python 3.12 | uvloop |
| ORM | SQLAlchemy 2.x (async) | 型安全 |
| マイグレーション | Alembic | 自動生成 + 手動レビュー |
| バリデーション | Pydantic v2 | DTO 兼用 |
| 認証 | OIDC (Authlib) + JWT (RS256) | Entra ID 発行 |
| バックグラウンドジョブ | RQ または Celery + Redis | AI レビュー実行 |
| HTTP クライアント | httpx (async) | 外部 API 用 |

### 4.3 データ層

| 区分 | 技術 |
|------|------|
| RDB | PostgreSQL 16 |
| キャッシュ / キュー | Redis 7 |
| 全文検索 | PostgreSQL `pg_trgm` + GIN index、将来 OpenSearch を選択肢 |
| ファイル | SharePoint Online (主) / DirectCloud (副) |

### 4.4 インフラ / 運用

| 区分 | 技術 |
|------|------|
| コンテナ | Docker / Docker Compose |
| CI | GitHub Actions |
| イメージレジストリ | GitHub Container Registry |
| 観測性 | Prometheus / Grafana / Loki (想定) |
| トレーシング | OpenTelemetry |
| ログ | 構造化 JSON (stdout) |

---

## 5. コンテナ構成 (Docker Compose)

```
+---------------------------- compose.yml ----------------------------+
| services:                                                           |
|   web        : Next.js 15 (node:20-alpine, port 3000)               |
|   api        : FastAPI (python:3.12-slim, port 8000)                |
|   worker     : FastAPI と同イメージ、ジョブ実行                       |
|   db         : postgres:16-alpine                                   |
|   redis      : redis:7-alpine                                       |
|   nginx      : nginx:alpine (TLS 終端、ルーティング)                  |
+---------------------------------------------------------------------+
```

`web` ↔ `api` 間は内部ネットワーク `internal` のみで通信し、外部からは `nginx` を経由する。

---

## 6. ドメインモデル概要

```
+-------------+         +----------------+         +-------------+
|   User      |---*---->|   Contract     |<--1--*--|   Clause    |
|             |         |                |         |             |
+-------------+         +----------------+         +-------------+
       *                       1                          *
       |                       |                          |
       v                       v                          v
+-------------+         +----------------+         +-------------------+
| Department  |         | LegalReview    |         | ClauseLibrary     |
+-------------+         +----------------+         +-------------------+
                               |
                               v
                        +----------------+
                        |   RiskItem     |
                        +----------------+

           Workflow 1 --< WorkflowStep >-- Contract 1
           Contract 1 --< Comment / Attachment / AuditLog >--
```

詳細は `database_design.md` を参照。

---

## 7. データフロー: 契約 AI レビュー (主要シナリオ)

```
[起案者] --(1) POST /api/v1/contracts (multipart, file metadata)
     |
     v
[API] --(2) ファイルメタを contracts に INSERT
     |     ファイル本体は SharePoint Graph API に PUT
     |
     v
[API] --(3) /api/v1/reviews を内部キックして job_id 発行
     |
     v
[Redis Queue] --(4) review.run ジョブ enqueue
     |
     v
[Worker] --(5) 契約書本文を SharePoint から取得 (Graph API)
     |     -> テキスト抽出 (PDF/DOCX → plain text)
     |     -> 条項分割 (見出しベース + LLM 補助)
     |
     v
[Worker] --(6) Claude API 呼び出し
     |     model: claude-opus-4-7 (主) / claude-sonnet-4-6 (副)
     |     prompt: 条項本文 + チェックリスト + 過去ナレッジ
     |
     v
[Worker] --(7) JSON 結果を legal_reviews / risk_items / clauses に保存
     |     audit_logs に hash_chain で 1 行追加
     |
     v
[API] --(8) WebSocket / SSE で進捗通知 (将来) / Exchange メール通知
     |
     v
[Reviewer] --(9) GET /api/v1/contracts/{id}/reviews で確認
     |        UI: AI 免責バナー常設 / リスクヒートマップ
     |
     v
[Reviewer] --(10) 承認 / 修正案を反映 → 次のワークフローステップへ
```

### 7.1 シーケンス図 (ASCII)

```
User      Frontend       API(FastAPI)     Worker        Claude API     SharePoint     DB
 |  upload   |               |               |              |              |          |
 |---------> |               |               |              |              |          |
 |           | POST contracts|               |              |              |          |
 |           |-------------->|               |              |              |          |
 |           |               | PUT file      |              |              |          |
 |           |               |--------------------------------------------->|         |
 |           |               | INSERT contract                              |          |
 |           |               |--------------------------------------------------------->
 |           |               | enqueue review job                                       |
 |           |               |-------------->|              |              |           |
 |           | 202 Accepted  |               |              |              |           |
 |           |<--------------|               |              |              |           |
 |           |               |               | GET file     |              |           |
 |           |               |               |---------------------------->|           |
 |           |               |               | parse + split clauses        |          |
 |           |               |               | POST messages|              |           |
 |           |               |               |------------->|              |           |
 |           |               |               | result       |              |           |
 |           |               |               |<-------------|              |           |
 |           |               |               | INSERT review + risks + audit chain     |
 |           |               |               |---------------------------------------->|
 |           | GET review    |               |              |              |           |
 |           |-------------->|               |              |              |           |
 |           |               | SELECT        |              |              |           |
 |           |               |<----------------------------------------------------------|
 |           | 200 OK (json) |               |              |              |           |
 |           |<--------------|               |              |              |           |
```

---

## 8. 外部連携の詳細

### 8.1 Entra ID (SSO / OIDC)

- 認可コードフロー + PKCE
- ID トークン (JWT, RS256) の `oid` をユーザー識別子に採用
- `groups` クレームから部署 / ロールを引き当て (Entra ID の Security Groups)
- アクセストークンで Microsoft Graph を呼び出し、SharePoint / Exchange へ伝搬

### 8.2 SharePoint Online

- 契約書ファイルは `/sites/{contractsSite}/drives/{driveId}/items` に保存
- 命名規則: `contracts/{yyyy}/{contract_id}/{version}.{ext}`
- バージョニング機能を有効化し、版数を DB と同期

### 8.3 Exchange Online

- 通知メールは `sendMail` Graph API で配信
- 共有メールボックス `legalops@example.co.jp` の `from` を使用

### 8.4 DeskNet's Neo

- 期日 / 締結予定日をスケジュールに登録 (REST API)
- 通知トリガは Backend Worker からポーリングではなく即時 POST

### 8.5 Claude API

- エンドポイント: `https://api.anthropic.com/v1/messages`
- モデル: `claude-opus-4-7` (主)、`claude-sonnet-4-6` (副、低コスト用途)
- プロンプトキャッシュを利用してチェックリスト・条項ライブラリを再利用
- レート制限を遵守するため Worker 側でセマフォ管理
- 機密分類「機密」の契約は API 呼び出し前にマスキング処理を強制

---

## 9. セキュリティアーキテクチャ

### 9.1 認証 / 認可

```
Browser
  |
  | (1) GET /  (未認証)
  v
HENNGE One -- IP 制限 -- Nginx
  |
  | (2) /auth/login へリダイレクト
  v
Backend (FastAPI)
  |
  | (3) Entra ID 認可エンドポイントへリダイレクト
  v
Entra ID  -- 認可コード返却 -->  Backend
  |
  | (4) コード + PKCE で ID/Access Token 取得
  v
Backend  --  JWT (RS256, kid 検証) --> Browser (HttpOnly Cookie)
```

- Cookie 属性: `HttpOnly; Secure; SameSite=Lax`
- アクセストークンは Backend のみで保持 (フロントには露出しない)
- API 認可は FastAPI Depends + ロール検証 + RLS (PostgreSQL Policy)

### 9.2 監査ログ改ざん防止 (hash chain)

```
audit_logs[N].hash = SHA256(
    audit_logs[N-1].hash || audit_logs[N].payload_canonical_json
)
```

- 起動時、定期バッチ、CI で全件再計算し検証
- 検知時はアラート + 書き込み停止モードへ移行

---

## 10. 観測性 / 運用

- **Logs**: 構造化 JSON、`request_id` / `user_id` / `contract_id` を全 span に伝搬
- **Metrics**: API 応答時間 (p50/p95/p99)、AI レビュー所要時間、ワーカーキュー長
- **Traces**: OpenTelemetry → OTLP → Grafana Tempo (将来)
- **Alerts**: p95 > 2s が 5 分継続でアラート、AI レビュー失敗率 > 5% でアラート

---

## 11. 環境構成

| 環境 | 用途 | 備考 |
|------|------|------|
| local | 開発者ローカル | Docker Compose |
| dev | 共通開発 | データ匿名化 |
| staging | 受入 / UAT | 本番相当データ (匿名化) |
| prod | 本番 | HENNGE One + Entra ID 本番 |

---

## 12. 移行 / 互換性方針

- DB マイグレーションは Alembic で前進専用 (downgrade は緊急時のみ)
- API 互換性は `v1` を 6 ヶ月以上維持
- 旧データインポートは `scripts/import_legacy/` 配下のバッチで実施

---

## 13. リスクと対応

| リスク | 影響 | 対応 |
|--------|------|------|
| Claude API レート制限 | レビュー遅延 | キュー + リトライ + Sonnet フォールバック |
| SharePoint Graph 認可期限切れ | ファイル取得失敗 | リフレッシュトークン + 監視 |
| DB スキーマの大幅変更 | リリース遅延 | Expand-Migrate-Contract パターン |
| AI 出力の品質不安定 | 法務手戻り増 | 免責 + 人間レビュー必須 + プロンプト評価 |
| 機密情報の AI 流出 | 重大 | 機密案件は API 呼出前にマスキング、契約毎の同意制御 |

---

## 14. 変更履歴

| 日付 | 版 | 変更内容 |
|------|----|---------|
| 2026-05-16 | v1.0 | 初版作成 |
