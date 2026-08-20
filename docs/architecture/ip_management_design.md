# 知財管理・競合出願ウォッチ・審査書類AI解析 設計書

- ステータス: 実装済み (MVP)
- 対象環境: MVP (https://legalops-mvp.mirai-dx-platform.com)
- 対象外: 本番 (legalops.mirai-dx-platform.com) — 本番への適用は人間ゲート後

## 1. 目的

特許庁（JPO）の「特許情報取得 API」（https://ip-data.jpo.go.jp）を前提とした、法務部門向けの知財管理機能を MVP 環境に追加する。

| 機能 | 概要 | JPO API |
|---|---|---|
| 知財管理 | 自社・関連の特許/意匠/商標出願の台帳管理。出願番号をキーに審査経過・登録情報・番号相互参照・J-PlatPat 固定アドレスを取得しダッシュボード化 | app_progress, registration_info, case_number_reference, jpp_fixed_address, divisional_app_info, priority_right_app_info, applicant_attorney(_cd) |
| 競合出願ウォッチ | 競合企業（申請人）の出願をウォッチ対象として登録し、対象出願番号の経過情報を定期ポーリングして変化（新規イベント・ステータス遷移）を検知・記録 | app_progress, applicant_attorney |
| 審査書類の収集・AI解析 | 拒絶理由通知書・意見書・補正書・発送書類（ZIP/XML）を収集し、テキスト化の上 AI で要約・論点・対応方針・期限を解析 | app_doc_cont_refusal_reason, app_doc_cont_opinion_amendment, app_doc_cont_refusal_reason_decision, cite_doc_info |

## 2. JPO API の前提

- 利用には特許庁への利用登録（ID・パスワード発行）が必要。
- 認証: `POST https://ip-data.jpo.go.jp/auth/token` に `grant_type=password&username=...&password=...` を送り、`access_token`（有効 1 時間）と `refresh_token`（有効 8 時間）を取得。アクセストークン失効後は `grant_type=refresh_token` で再取得。
- API アクセス: `GET https://ip-data.jpo.go.jp/api/{domain}/v1/{api}/{案件番号}` に `Authorization: Bearer <access_token>` を付与。
  - 国内: `https://ip-data.jpo.go.jp/api`、OPD: `https://ip-data.jpo.go.jp/opdapi`
- レスポンス形式: `{"result": {"statusCode": "100", "errorMessage": "", "remainAccessCount": "399", "data": {...}}}`
  - `statusCode=100` が成功。書類系は ZIP (application/zip) が返る。
- アクセス制限（重要）:
  - 国内 API: 1 分間に **10 回以下**、API ごとに日次上限（経過情報 400、番号参照 50 など）。
  - 本実装ではクライアント側に **1 分 10 回のレートリミッタ** と **日次上限カウンタ（remainAccessCount 記録）** を組み込む。
- MVP では API キー未設定時（デモモード）でも全機能が動作するよう、決定的なデモデータを返すフォールバックを実装する（既存の AI_REVIEW_STUB と同じ思想）。

## 3. DB 設計（マイグレーション 009_ip_management）

### 3.1 `ip_assets` — 知財台帳（出願単位）

| カラム | 型 | 説明 |
|---|---|---|
| id | BIGSERIAL PK | |
| application_number | VARCHAR(16) UNIQUE NOT NULL | 出願番号（例: 2020008423） |
| ip_type | VARCHAR(16) NOT NULL | patent / design / trademark |
| invention_title | VARCHAR(512) | 発明等の名称 |
| filing_date | DATE | 出願日 |
| applicants | JSONB | 申請人一覧（コード・名称・種別） |
| publication_number | VARCHAR(32) | 公開番号 |
| registration_number | VARCHAR(32) | 登録番号 |
| status | VARCHAR(32) | 経過情報から導出したステータス |
| progress_data | JSONB | 直近の経過情報レスポンス全体 |
| registration_data | JSONB | 直近の登録情報レスポンス |
| jplatpat_url | VARCHAR(512) | J-PlatPat 固定アドレス |
| last_synced_at | TIMESTAMPTZ | 最終同期日時 |
| watch_target_id | BIGINT FK ip_watch_targets.id NULL | ウォッチ対象（競合）に紐づく場合 |
| notes | TEXT | 社内メモ |
| created_at / updated_at / deleted_at / created_by / updated_by | | 共通ミックスイン |

### 3.2 `ip_watch_targets` — 競合ウォッチ対象（申請人）

| カラム | 型 | 説明 |
|---|---|---|
| id | BIGSERIAL PK | |
| name | VARCHAR(256) UNIQUE NOT NULL | 競合企業名 |
| applicant_code | VARCHAR(16) | 申請人コード |
| ip_types | JSONB | 対象区分（patent/design/trademark） |
| status | VARCHAR(16) | active / paused |
| notes | TEXT | |
| created_at / updated_at / deleted_at / created_by / updated_by | | |

### 3.3 `ip_watch_events` — ウォッチ検知イベント

| カラム | 型 | 説明 |
|---|---|---|
| id | BIGSERIAL PK | |
| watch_target_id | BIGINT FK NOT NULL | ウォッチ対象 |
| ip_asset_id | BIGINT FK NULL | 関連出願（あれば） |
| application_number | VARCHAR(16) | 対象出願番号 |
| event_type | VARCHAR(32) | new_application / status_change / new_progress / registration / publication |
| event_code | VARCHAR(32) | JPO 経過イベントコード（あれば） |
| description | TEXT | 日本語要約 |
| event_data | JSONB | 元レスポンス断片 |
| is_read | BOOLEAN | 既読フラグ |
| created_at | TIMESTAMPTZ | 検知日時 |

### 3.4 `ip_documents` — 審査書類（収集・AI 解析結果）

| カラム | 型 | 説明 |
|---|---|---|
| id | BIGSERIAL PK | |
| ip_asset_id | BIGINT FK NOT NULL | 対象出願 |
| doc_type | VARCHAR(32) | refusal_reason / opinion_amendment / decision / citation |
| doc_name | VARCHAR(256) | 書類名 |
| fetched_at | TIMESTAMPTZ | 収集日時 |
| content_text | TEXT | ZIP/XML から抽出したテキスト（解析入力） |
| ai_summary | TEXT | AI 要約 |
| ai_findings | JSONB | AI 論点・対応方針・期限の構造化結果 |
| ai_model | VARCHAR(64) | 使用モデル（demo 含む） |
| analyzed_at | TIMESTAMPTZ | AI 解析日時 |
| error | TEXT | 収集/解析エラー |
| created_at / updated_at | | |

## 4. API 設計（/api/v1 配下）

### 4.1 `/ip-assets` — 知財台帳

- `GET /ip-assets` — 一覧（q / ip_type / status / page / size）
- `POST /ip-assets` — 出願番号・区分を登録し、JPO API から初期情報を取得（デモ時はデモデータ）
- `GET /ip-assets/{id}` — 詳細（progress_data 含む）
- `PATCH /ip-assets/{id}` — notes 等の更新
- `DELETE /ip-assets/{id}` — 論理削除
- `POST /ip-assets/{id}/sync` — JPO API から再取得して更新（レートリミット順守）
- `POST /ip-assets/{id}/sync-watch-events` — 経過情報の差分からウォッチイベントを生成

### 4.2 `/ip-watch-targets` / `/ip-watch-events` — 競合ウォッチ

- `GET /ip-watch-targets` / `POST` / `PATCH /{id}` / `DELETE /{id}`
- `POST /ip-watch-targets/{id}/sync` — 対象に紐づく全出願を順次ポーリングし差分イベント生成（1 分 10 回制限内で分割実行）
- `GET /ip-watch-events` — イベント一覧（unread フィルタ、watch_target_id フィルタ）
- `PATCH /ip-watch-events/{id}/read` — 既読化

### 4.3 `/ip-documents` — 審査書類

- `GET /ip-assets/{asset_id}/documents` — 書類一覧
- `POST /ip-assets/{asset_id}/documents/fetch` — 指定種別の書類を JPO API から収集（ZIP → XML → テキスト化）
- `POST /ip-documents/{id}/analyze` — AI 解析（要約・論点・対応方針・期限）。デモ時は決定論的スタブ結果
- `GET /ip-documents/{id}` — 解析結果取得

### 4.4 `/ip-dashboard` — サマリ

- `GET /ip-dashboard` — 台帳件数・ステータス内訳・未読イベント数・直近イベント・書類解析件数

## 5. フロントエンド

| ルート | 画面 |
|---|---|
| `/ip-assets` | 知財台帳一覧（検索・種別フィルタ・登録ボタン・同期ボタン） |
| `/ip-assets/[id]` | 出願詳細（基本情報・経過情報・登録情報・J-PlatPat リンク・書類一覧） |
| `/ip-watch` | 競合ウォッチ（対象 CRUD・対象別出願・イベントフィード・同期ボタン） |
| `/ip-documents` | 審査書類一覧・AI 解析結果（要約・論点・対応方針・期限） |

サイドバーに「知財管理」グループ（知財台帳 / 競合ウォッチ / 審査書類）を追加。既存画面と同じくオフライン時はモックデータにフォールバック。

## 6. AI 解析（書類）

- 入力: `content_text`（拒絶理由通知書等の抽出テキスト）
- 出力: 要約 / 論点一覧（severity・該当条文） / 対応方針 / 期限
- 本番プロバイダ未設定時は `AIReviewService` と同じ方針で、決定論的なデモ解析結果を返す（`AI_REVIEW_STUB=1` 相当）。
- 免責: 既存 `AiDisclaimerBanner` を表示し、AI 結果は参考情報である旨を明示。

## 7. レートリミットと運用

- JPO API は 1 分 10 回 / 日次上限。`JpoApiClient` に固定ウィンドウのレートリミッタ（1 分 10 回）を持たせ、超過時は待機して順次実行。
- 日次上限到達（statusCode != 100 かつ remainAccessCount=0）時はエラーとして記録し、`last_synced_at` は更新しない。
- MVP デモモードではレートリミット・認証ともスキップ（決定的デモデータ）。

## 8. 設定（環境変数）

| 変数 | 既定 | 説明 |
|---|---|---|
| JPO_API_MODE | demo | demo / live。live は ID/PW 必須 |
| JPO_API_ID | 空 | 特許庁発行 ID |
| JPO_API_PASSWORD | 空 | 特許庁発行パスワード |
| JPO_API_BASE_URL | https://ip-data.jpo.go.jp | API ベース |
