# REST API 設計 — Construction-LegalOps-DX

最終更新: 2026-05-16
版数: v1.0 (Draft)
所管: アーキテクチャドキュメントチーム
ベース URL: `https://legalops.mirai-dx-platform.com/api/v1`

---

## 1. 全体方針

1. **バージョニング**: パスに `/api/v1` を含める。後方非互換変更は `/api/v2` を新設。
2. **認証**: Entra ID OIDC で発行された JWT (RS256) を `Authorization: Bearer <token>` で送信。フロントは HttpOnly Cookie で保持し Backend が抽出する。
3. **権限**: ロール (viewer / drafter / reviewer / approver / admin / auditor / guest) + RLS。
4. **コンテンツ型**: 既定 `application/json; charset=utf-8`。ファイルアップロードは `multipart/form-data`。
5. **日時表現**: ISO 8601 (UTC)。例: `2026-05-16T03:21:00Z`。
6. **ページング**: `?page=1&page_size=20`。レスポンスに `meta.total`、`meta.page`、`meta.page_size`。
7. **フィルタ**: `?status=in_review&department_id=12&q=工事`。
8. **冪等性**: 作成系 POST は `Idempotency-Key` ヘッダ受付。
9. **エラー**: RFC 7807 (Problem Details) 準拠。
10. **OpenAPI**: FastAPI から自動生成、`/openapi.json` および社内向け `/docs`。

---

## 2. 共通仕様

### 2.1 共通ヘッダ

| ヘッダ                        | 用途           |
| ----------------------------- | -------------- |
| `Authorization: Bearer <JWT>` | 認証           |
| `Idempotency-Key: <uuid>`     | 冪等 POST      |
| `X-Request-Id: <uuid>`        | リクエスト相関 |
| `Accept-Language: ja`         | 多言語化       |

### 2.2 共通レスポンス構造

```json
{
  "data": {/* オブジェクト or 配列 */},
  "meta": {
    "request_id": "8b3a...",
    "page": 1,
    "page_size": 20,
    "total": 145
  }
}
```

### 2.3 エラー (RFC 7807)

```json
{
  "type": "https://legalops.mirai-dx-platform.com/errors/validation",
  "title": "Validation Error",
  "status": 422,
  "detail": "title must not be empty",
  "instance": "/api/v1/contracts",
  "errors": [{ "field": "title", "message": "required" }],
  "request_id": "8b3a..."
}
```

### 2.4 HTTP ステータス使い分け

| コード | 用途                                                        |
| ------ | ----------------------------------------------------------- |
| 200    | 取得・更新成功                                              |
| 201    | 新規作成成功                                                |
| 202    | 非同期処理受付 (AI レビューなど)                            |
| 204    | ボディなし成功 (削除等)                                     |
| 400    | リクエスト不正                                              |
| 401    | 未認証                                                      |
| 403    | 権限不足                                                    |
| 404    | 存在しない / アクセス不可 (情報秘匿のため 403 ではなく 404) |
| 409    | 競合 (楽観ロック失敗、状態遷移違反)                         |
| 422    | バリデーション失敗                                          |
| 429    | レート制限                                                  |
| 500    | サーバ内部エラー                                            |

---

## 3. 認証 (`/auth/sso`)

### 3.1 `GET /auth/sso/login`

OIDC 認可エンドポイントへリダイレクト。

- 認可: 不要 (未認証アクセス)
- レスポンス: `302 Found`、`Location: https://login.microsoftonline.com/...`
- クエリ: `redirect_to` (任意、ログイン後に戻す相対 URL)

### 3.2 `GET /auth/sso/callback`

Entra ID 認可コードを受け、ID/Access トークンを取得して HttpOnly Cookie を設定。

- クエリ: `code`, `state`
- レスポンス: `302 Found` → `redirect_to`
- 失敗: `400`

### 3.3 `POST /auth/sso/logout`

- 認可: 任意
- レスポンス: `204 No Content`
- 動作: セッション Cookie 破棄 + Entra ID end_session に誘導

### 3.4 `GET /auth/me`

- 認可: 全認証ユーザー
- レスポンス例:

```json
{
  "data": {
    "id": 42,
    "entra_oid": "f5d4...",
    "email": "yamada@example.co.jp",
    "display_name": "山田 太郎",
    "role": "reviewer",
    "department": { "id": 12, "name": "法務部" }
  }
}
```

---

## 4. ユーザー (`/users`)

### 4.1 `GET /users`

- 認可: `admin` / `auditor`
- クエリ: `q`, `role`, `department_id`, `is_active`, `page`, `page_size`
- レスポンス: 200 + ユーザー配列

### 4.2 `GET /users/{id}`

- 認可: `admin` / `auditor` / 本人
- レスポンス: 200 + ユーザー

### 4.3 `POST /users/{id}/identity-link`

oid 無しトークンで JIT 作成されたユーザーを、後日取得した Microsoft Entra ID の実 `oid` に **admin が明示的に紐付ける**。
通常ログイン時の自動マージは禁止し、同一メール・異なる実 `oid` は引き続き `401` で fail-closed する。

- 認可: `admin`
- 監査: `user.identity_link`
- 成功: 200 + 更新後ユーザー
- 失敗: `404` (対象ユーザーなし) / `409` (現在 oid 不一致、同一 oid、または別ユーザーへ既に紐付け済み)

リクエスト例:

```json
{
  "expected_current_entra_oid": "2b0c1c8a-1111-4444-8888-0f7a7d1c0001",
  "new_entra_oid": "5f9f2b12-2222-4444-9999-0f7a7d1c0002",
  "reason": "Operator verified the user's Entra oid during identity migration."
}
```

安全条件:

- `expected_current_entra_oid` が現在の `users.entra_oid` と一致しない場合は拒否。
- `new_entra_oid` が別ユーザーに存在する場合は拒否。
- `attributes.identity_link_history[]` に `from/to/linked_by/linked_at/reason` を保持。

### 4.4 `PATCH /users/{id}`

- 認可: `admin`
- 動作: `display_name`, `role`, `department_id`, `is_active`, `attributes` を部分更新する
- リクエスト:

```json
{ "role": "approver", "department_id": 14, "is_active": true }
```

- レスポンス: 200 + 更新後ユーザー
- 409: `users` テーブルには現時点で `version` 列がないため、`version` を指定した更新は fail-closed で拒否

### 4.5 `DELETE /users/{id}`

- 認可: `admin`
- 動作: ユーザーを `is_active=false` にし、`deleted_at` を設定する論理削除
- 監査: `user.delete`
- 成功: 204
- 失敗: `404` (対象ユーザーなし) / `409` (admin 自身の自己削除)

### 4.6 `POST /users/sync`

- 認可: `admin`
- 動作: Microsoft Graph からユーザー / グループを同期するジョブを受付。Secrets / worker 承認前は外部通信せず `queued` を返し、`user.sync` として監査ログへ記録する。監査 payload は `job_id`、`status`、`external_write=false` を保持する。
- レスポンス: 202 (`job_id`, `status`, `triggered_by`, `queued_at`, `note`)

---

## 5. 契約 (`/contracts`)

### 5.1 `GET /contracts`

- 認可: `viewer` 以上 (RLS 適用)
- クエリ: `q`, `status`, `contract_type`, `department_id`, `from`, `to`, `confidentiality`, `page`, `page_size`, `sort`
- レスポンス例:

```json
{
  "data": [
    {
      "id": 1001,
      "contract_no": "C-2026-000123",
      "title": "○○工事 元請契約",
      "counterparty": "株式会社□□建設",
      "contract_type": "請負",
      "amount": 120000000,
      "currency": "JPY",
      "status": "in_review",
      "department": { "id": 7, "name": "土木事業本部" },
      "drafter": { "id": 88, "display_name": "佐藤 一郎" },
      "start_date": "2026-06-01",
      "end_date": "2027-03-31",
      "updated_at": "2026-05-15T08:21:00Z"
    }
  ],
  "meta": { "page": 1, "page_size": 20, "total": 145 }
}
```

### 5.2 `POST /contracts`

- 認可: `drafter` 以上
- ヘッダ: `Idempotency-Key`
- リクエスト:

```json
{
  "title": "○○工事 元請契約",
  "counterparty": "株式会社□□建設",
  "contract_type": "請負",
  "amount": 120000000,
  "currency": "JPY",
  "start_date": "2026-06-01",
  "end_date": "2027-03-31",
  "department_id": 7,
  "confidentiality": "normal",
  "metadata": { "site": "東京都港区..." }
}
```

- レスポンス: `201 Created` + 作成済 Contract

### 5.3 `GET /contracts/{id}`

- 認可: `viewer` 以上 (RLS)
- レスポンス: 200 + Contract 詳細 (clauses は別エンドポイント)

### 5.4 `PATCH /contracts/{id}`

- 認可: `drafter` (本人) / `admin`
- リクエスト: 差分項目のみ。`version` 必須 (楽観ロック)
- レスポンス: 200 / 409 (version 不一致)

### 5.5 `DELETE /contracts/{id}`

- 認可: `admin`
- 動作: 論理削除 (`deleted_at = now()`)
- レスポンス: 204

### 5.6 `POST /contracts/{id}/submit`

- 認可: `drafter` (本人) / `admin`
- 動作: status を `draft → in_review` に遷移する
- レスポンス: 200 + 更新後 Contract
- 409: 状態遷移違反
- 備考: 承認ワークフローの開始は `POST /contracts/{id}/workflows` で行う

### 5.7 `GET /contracts/{id}/clauses`

- 認可: `viewer` 以上
- レスポンス: clauses 配列 (seq 昇順)

### 5.8 `GET /contracts/{id}/versions`

- 認可: `viewer` 以上
- レスポンス: 現行スキーマでは `contract_versions` 履歴テーブルを持たないため、現在行の version snapshot を返す
- 備考: 完全な履歴テーブル化は非破壊 migration として別途承認後に実施

### 5.9 `GET /contracts/{id}/audit-trail`

- 認可: `auditor` / `admin`
- レスポンス: audit_logs を contract_id で絞った時系列

---

## 6. レビュー (`/reviews`)

### 6.1 `POST /contracts/{id}/reviews`

AI レビューを起動し、`legal_reviews` に構造化レビュー結果を保存する。実本番 Claude key が未投入の環境では、
API 契約を維持するため決定論的 fallback を使い、501 ではなく `running` 状態のレビューを返す。

- 認可: `reviewer` / `drafter` / `admin`
- ヘッダ: `Idempotency-Key`
- リクエスト:

```json
{
  "review_type": "ai",
  "ai_model": "claude-opus-4-7",
  "scope": "full",
  "options": { "use_clause_library": true }
}
```

- レスポンス: `202 Accepted`

```json
{
  "data": {
    "id": 7011,
    "contract_id": 1001,
    "status": "running",
    "started_at": "2026-05-16T03:21:00Z"
  }
}
```

### 6.2 `GET /reviews/{id}`

- 認可: `viewer` 以上 (契約に対する RLS 経由)
- レスポンス:

```json
{
  "data": {
    "id": 7011,
    "contract_id": 1001,
    "status": "completed",
    "overall_risk": "high",
    "summary": "解除条項に過大な裁量、損害賠償上限の欠如あり",
    "ai_model": "claude-opus-4-7",
    "started_at": "2026-05-16T03:21:00Z",
    "finished_at": "2026-05-16T03:22:34Z",
    "findings": [
      {
        "clause_seq": 12,
        "title": "第12条 解除",
        "risk_level": "high",
        "comment": "一方的解除権が広範",
        "suggestion": "...",
        "citations": ["民法541", "下請法第4条"]
      }
    ],
    "disclaimer": "本結果は AI 生成の参考情報であり、最終判断は人間が行ってください。"
  }
}
```

### 6.3 `PATCH /reviews/{id}`

- 認可: `reviewer` / `admin`
- 用途: 法務担当者の人間判断メモ、最終判断メタデータ、リスク再評価を保存
- リクエスト:

```json
{
  "final_decision": "accept",
  "legal_comment": "人間確認済み。解除条項は別紙修正で許容。",
  "overall_risk": "low"
}
```

- 動作: `overall_risk` / `reviewer_id` は `legal_reviews` の列に反映し、`final_decision` / `legal_comment` はレビュー結果の `result` JSON に保持する。`accept` / `reject` の状態遷移は専用エンドポイントで実行する。
- レスポンス: 200 + 更新後 Review

### 6.4 `POST /reviews/{id}/accept`

- 認可: `reviewer`
- 動作: AI 結果を受領、契約 status を更新
- レスポンス: 200

### 6.5 `POST /reviews/{id}/reject`

- 認可: `reviewer`
- リクエスト: `{ "reason": "再レビュー要求" }`
- レスポンス: 200

### 6.6 `GET /reviews?contract_id=...`

- 認可: `viewer` 以上
- 用途: 同一契約の過去レビューを時系列で取得

---

## 7. ワークフロー (`/workflows`)

### 7.1 `GET /workflows`

- 認可: `viewer` 以上
- 用途: ワークフロー定義の一覧

### 7.2 `POST /workflows`

- 認可: `admin`
- リクエスト:

```json
{
  "code": "STANDARD_CONTRACT_V1",
  "name": "標準契約フロー",
  "contract_type": "請負",
  "definition": {
    "steps": [
      { "seq": 1, "name": "起案", "step_type": "draft" },
      {
        "seq": 2,
        "name": "法務レビュー",
        "step_type": "legal_review",
        "assignee_role": "reviewer"
      },
      {
        "seq": 3,
        "name": "部長承認",
        "step_type": "manager_approval",
        "assignee_role": "approver"
      },
      {
        "seq": 4,
        "name": "経営承認",
        "step_type": "exec_approval",
        "assignee_role": "approver"
      }
    ]
  }
}
```

- レスポンス: 201

### 7.3 `GET /contracts/{id}/workflow-steps`

- 認可: `viewer` 以上
- レスポンス: 当該契約のステップ一覧

### 7.4 `POST /workflow-steps/{step_id}/approve`

- 認可: ステップ assignee / 同等ロール / `admin`
- リクエスト:

```json
{ "comment": "問題なし" }
```

- レスポンス: 200
- 409: ステップが pending/in_progress でない場合

### 7.5 `POST /workflow-steps/{step_id}/reject`

- 認可: 同上
- リクエスト: `{ "comment": "..." }`
- レスポンス: 200

### 7.6 `POST /workflow-steps/{step_id}/send-back`

- 差戻し。前ステップに戻す
- リクエスト: `{ "to_seq": 1, "comment": "..." }`

### 7.7 `POST /workflow-steps/{step_id}/delegate`

- 委任。assignee を切替
- リクエスト: `{ "to_user_id": 99, "comment": "..." }`

---

## 8. リスク (`/risks`)

### 8.1 `GET /risks`

- 認可: `viewer` 以上
- クエリ: `severity`, `status`, `contract_id`, `owner_id`, `page`, `page_size`

### 8.2 `PATCH /risks/{id}`

- 認可: `reviewer` / `admin`
- リクエスト: `{ "status": "mitigated", "mitigation": "条文修正済" }`

### 8.3 `GET /risks/heatmap`

- 認可: `viewer` 以上
- レスポンス例:

```json
{
  "data": {
    "matrix": [
      { "probability": "high", "impact": "high", "count": 4 },
      { "probability": "high", "impact": "medium", "count": 9 },
      { "probability": "medium", "impact": "high", "count": 6 }
    ]
  }
}
```

---

## 9. コンプライアンス (`/compliance`)

### 9.1 `GET /compliance/checklists`

- 認可: `viewer` 以上
- 用途: 適用可能なチェックリスト

### 9.2 `POST /compliance/checks/{contract_id}/run`

- 認可: `legal` / `admin`
- クエリ: `checklist_codes` (複数指定可・未指定時は全件)。`?checklist_codes=A&checklist_codes=B` の繰り返し形式で bind する (`checklist_codes[]=` 形式は非対応)
- 動作: チェックリスト適用。外部 worker 未承認の現フェーズでは、`GET /compliance/checks/{contract_id}` と同じ ComplianceChecker を即時実行し、job-shaped response を `status=done` で返す。
- レスポンス: 202 (`job_id`, `contract_id`, `accepted_at`, `status`, `disclaimer`)

### 9.3 `GET /compliance/checks/{contract_id}`

- 認可: 特権ロールは全件、それ以外は自身が起案した契約のみ
- クエリ: `checklist_codes` (複数指定可・未指定時は全件)。指定時は findings と `overall_status` を対象ルールへ絞り込む
- 動作: ComplianceChecker を実行し、横断統合した最終ビュー (`ComplianceCheckResult`) を返す

---

## 10. テンプレート / 条項ライブラリ (`/templates`, `/clauses-library`)

### 10.1 `GET /clauses-library`

- 認可: `viewer` 以上
- クエリ: `category`, `recommendation`, `tag`, `q`
- `recommendation`: `required` / `recommended` / `optional` / `prohibited`

### 10.2 `POST /clauses-library`

- 認可: `legal` / `admin`
- リクエスト: 条項のフルテキスト + メタ

### 10.3 `GET /templates`

- 認可: `viewer` 以上
- 用途: 契約類型ごとのテンプレ一覧

### 10.4 `GET /templates/{id}`

- 認可: `viewer` 以上
- 用途: 永続化済み契約ひな形の詳細取得

### 10.5 `POST /templates`

- 認可: `legal` / `admin`
- 動作: 契約ひな形を `contract_templates` に永続化し、`template.create` を監査ログへ記録
- 競合: `code` 重複時は `409 Conflict`
- リクエスト例:

```json
{
  "code": "TMPL-UKEOI-CUSTOM-001",
  "name": "工事請負契約書（社内標準）",
  "contract_type": "請負",
  "description": "社内標準条項を反映した工事請負契約ひな形",
  "body": "契約本文...",
  "is_active": true
}
```

---

## 11. ナレッジ (`/knowledge`)

### 11.1 `GET /knowledge`

- クエリ: `page`, `size`
- レスポンス: `Page<KnowledgeArticleOut>`

### 11.2 `GET /knowledge/search`

- クエリ: `q`, `tag`, `contract_type`, `page`, `size`
- 動作: `knowledge_articles` と契約メタデータをDB-backedで横断検索し、スコア付きで返す
- レスポンス: `Page<KnowledgeSearchResult>`

### 11.3 `GET /knowledge/similar/{contract_id}`

- クエリ: `top_k`
- 動作: 対象契約の本文・メタデータを元に、過去契約とのTF-cosine類似度を算出する
- レスポンス: `SimilarContractOut[]`

### 11.4 `GET /knowledge/{id}`

- 動作: 指定IDのナレッジ記事を返す。存在しない場合は `404`
- レスポンス: `KnowledgeArticleOut`

### 11.5 `POST /knowledge`

- 認可: `legal` / `admin`
- 動作: ナレッジ記事を `knowledge_articles` に永続化し、`knowledge.create` 監査ログを記録
- レスポンス: `201 KnowledgeArticleOut`

---

## 12. 監査ログ (`/audit-logs`)

### 12.1 `GET /audit-logs`

- 認可: `auditor` / `admin`
- クエリ: `target_type`, `target_id`, `action`, `actor_id`, `from`, `to`, `page`, `page_size`
- レスポンス例:

```json
{
  "data": [
    {
      "id": 9001,
      "occurred_at": "2026-05-16T03:21:00Z",
      "actor": { "id": 42, "display_name": "山田 太郎" },
      "action": "contract.update",
      "target_type": "contracts",
      "target_id": 1001,
      "request_id": "8b3a...",
      "payload": {
        "before": { "status": "draft" },
        "after": { "status": "in_review" }
      },
      "previous_hash": "0d3a...",
      "hash_chain": "b34c..."
    }
  ]
}
```

### 12.2 `POST /audit-logs/verify`

- 認可: `auditor` / `admin`
- 動作: hash_chain を全件再計算し整合性を検証
- レスポンス: 200

```json
{ "data": { "verified": true, "total": 123456, "broken_at": null } }
```

### 12.3 `GET /audit-logs/export`

- 認可: `auditor`
- クエリ: 期間など
- レスポンス: 200 + `text/csv`

---

## 13. ファイルアップロード (`/uploads`)

### 13.1 `POST /uploads/init`

- 認可: `drafter` / `reviewer` / `admin`
- 動作: ファイルメタデータを検証し、完了報告に使う署名付き `upload_token` を発行する。APIサーバーはファイル本体を受け取らない。
- リクエスト:

```json
{
  "contract_id": 1001,
  "filename": "draft.docx",
  "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "size_bytes": 234123,
  "is_primary": true
}
```

- レスポンス例:

```json
{
  "upload_id": "opaque-upload-id",
  "upload_url": null,
  "upload_token": "signed-token",
  "storage": "sharepoint",
  "expires_in": 3600
}
```

- 制約:
  - 最大サイズ 100 MB
  - 受理 MIME: `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
  - 受理 NG 時は `415 Unsupported Media Type`
  - 承認済み SharePoint/Graph direct-upload URL がない場合、`upload_url` は `null` とし、`sharepoint-stub://` などの疑似外部 URL は返さない
  - 画像PDFは実OCRバックエンドが承認・設定されるまで解析を fail-closed とし、placeholder OCR テキストを契約レビューやAIレビューへ流さない

### 13.2 `POST /uploads/complete`

- 認可: `drafter` / `reviewer` / `admin`
- 動作: `upload_token` を検証し、SharePoint item ID / checksum を `attachments` に登録する
- 成功: `201 Created` + Attachment metadata
- 失敗: `404` (契約なし) / `403` (他ユーザー token) / `409` (token 不正・期限切れ等)

### 13.3 `GET /uploads/{id}`

- 認可: `admin` / `auditor` / `reviewer` / `approver` / アップロード者
- 動作: attachment metadata を返す

### 13.4 `GET /uploads/{id}/download`

- 認可: アップロード者 / `reviewer` / `approver` / `auditor` / `admin`
- 動作: SharePoint item ID から Microsoft Graph / SharePoint の閲覧 URL を解決し、302 redirect する
- 失敗時:
  - 添付が存在しない場合は `404`
  - 権限がない場合は `403`
  - SharePoint URL を解決できない場合は `502 sharepoint url unavailable`
- 制約:
  - URL 解決失敗時に `sharepoint-stub://` などの疑似 URL へフォールバックしない
  - 本番 secret / Graph 設定未投入時は失敗を明示し、利用者に疑似ダウンロード経路を提示しない
  - 成功時の監査 payload は `external_url_resolved=true` / `external_write=false` を保持し、URL文字列そのものは監査ログへ残さない
  - URL 解決失敗 (`502`) 時も `external_url_resolved=false` で監査ログへ記録する

### 13.5 `DELETE /uploads/{id}`

- 認可: `admin` / アップロード者
- 動作: `deleted_at` を設定する論理削除

---

## 14. 通知 (`/notifications`)

### 14.1 `GET /notifications`

- 認可: 本人のみ
- クエリ: `status=unread|read`, `channel=in_app|mail|teams|desknets|email`
- 用途: 自身宛て通知センター。`email` は API 利便性のため `mail` channel に正規化する。
- レスポンス: `Page<NotificationOut>`

### 14.2 `PATCH /notifications/{id}/read`

- 動作: `read_at = now()` を設定
- 所有者以外は `403 Forbidden`
- レスポンス: `NotificationOut`

### 14.3 `POST /notifications/read-all`

- 動作: 自身の未読通知すべてに `read_at = now()` を設定
- レスポンス: `{ "updated": <件数> }`

---

## 15. ヘルスチェック / メタ

### 15.1 `GET /healthz`

- 認可: 不要
- レスポンス: `200 {"status": "ok"}`

### 15.2 `GET /readyz`

- DB / Redis / SharePoint 認可の到達性を確認
- レスポンス: 200 / 503

### 15.3 `GET /version`

- レスポンス: `{ "version": "1.0.0", "commit": "abcdef" }`

---

## 16. 高優先業務機能 API（2026-08-05 追加）

### 16.1 紛争・クレーム・事故・債権管理 (`/disputes`)

| メソッド | パス | 概要 |
|---|---|---|
| GET | `/disputes` | 一覧（q / status / dispute_type / page / size） |
| POST | `/disputes` | 案件登録（drafter/reviewer/approver/admin） |
| GET | `/disputes/exposure` | エクスポージャー集計（by_status / total_claimed / total_reserve / deadlines_within_180d） |
| PATCH | `/disputes/{id}` | 状態・金額・期限の更新 |
| POST | `/disputes/{id}/timeline` | 事実経過タイムライン追加 |
| POST | `/disputes/{id}/evidence` | 証拠登録（preserved フラグで保全） |

### 16.2 変更契約・追加工事・クレーム (`/change-orders`)

| メソッド | パス | 概要 |
|---|---|---|
| GET | `/change-orders` | 一覧（contract_id / status） |
| POST | `/change-orders?contract_id=` | 登録（response_deadline は requested_at + 14 日で自動計算） |
| GET | `/change-orders/impact/{contract_id}` | 原契約＋変更の累積金額・工期影響・失権リスク集計 |
| PATCH | `/change-orders/{id}` | 更新（approved 時に cumulative_after_jpy 再計算） |
| POST | `/change-orders/{id}/evidence` | 証拠（日報・写真・メール・議事録・指示書）紐付け |

### 16.3 協力会社コンプライアンス台帳 (`/partners`)

| メソッド | パス | 概要 |
|---|---|---|
| GET | `/partners` | 一覧（q / partner_type / risk_level） |
| GET | `/partners/summary` | リスク集計（by_risk_level / antisocial_unconfirmed / permit_expiring_within_90d） |
| POST | `/partners` | 登録（risk_level と risk_reasons を自動判定） |
| PATCH | `/partners/{id}` | 更新（許可・社会保険・CCUS・反社チェック） |

### 16.4 支払・出来高・検収コンプライアンス (`/contracts/{id}/payment-compliance`)

- `GET /contracts/{contract_id}/payment-compliance`
- 発注日 2026-01-01 前後で取適法/旧下請法を切替、公共工事は 50 日、それ以外は 60 日基準
- 受領日→支払日の実日数、遅延利息概算（年 14.6%）、手形・電子記録債権・ファクタリング・
  不当減額・保留金の文言判定
- レスポンス: `law_version` / `applicable_threshold_days` / `days_receipt_to_payment` /
  `late_interest_jpy` / `overall_status` / `findings[]`

### 16.5 契約文書パッケージ (`/contracts/{id}/documents`)

| メソッド | パス | 概要 |
|---|---|---|
| GET | `/contracts/{id}/documents` | パッケージ文書一覧（priority 順） |
| POST | `/contracts/{id}/documents` | 文書追加（契約書・約款・特記仕様書・設計図書・見積書等） |
| PATCH | `/contracts/{id}/documents/{document_id}` | 文書更新 |
| GET | `/contracts/{id}/documents/consistency` | 文書間の金額（20% 超乖離）・工期逆転・責任帰属の矛盾検出 |

### 16.6 ガバナンス / セキュリティ統制（P0-6）

- ACL: `GET/POST /contracts/{contract_id}/access-control`、`DELETE /contracts/{contract_id}/access-control/{entry_id}`
- Legal Hold: `GET/POST /legal-holds`、`POST /legal-holds/{id}/release`
- 保持期間: `GET/PUT /security/retention-settings`、`POST /security/retention/run`（purge）
- 監査 WORM: `GET/POST /security/audit-export`、アンカー検証
- Sentinel: `GET /security/sentinel/status`

### 16.7 適用法令・根拠検索（AI 第 1 優先）

- `GET /compliance/applicable-laws?contract_id=` — 適用法令自動判定
- `GET /ai/evidence/search?query=` — 一次情報限定 RAG（許可ホスト検証付き）
- `POST /ai/evidence/verify` — 引用 URL の一次情報検証
- `GET /ai/law-change-impact?effective_date=` — 法令改正影響分析

---

## 17. レート制限

| ルート                         | 制限                   |
| ------------------------------ | ---------------------- |
| `POST /contracts/{id}/reviews` | 1 ユーザー 30 req/h    |
| `POST /uploads/init`           | 1 ユーザー 60 req/h    |
| `POST /uploads/complete`       | 1 ユーザー 60 req/h    |
| 既定                           | 1 ユーザー 600 req/min |

超過時 `429 Too Many Requests` + `Retry-After` ヘッダ。

---

## 18. 認可マトリクス (抜粋)

| エンドポイント                    | viewer | drafter | reviewer | approver | admin | auditor |
| --------------------------------- | :----: | :-----: | :------: | :------: | :---: | :-----: |
| GET /contracts                    |   o    |    o    |    o     |    o     |   o   |    o    |
| POST /contracts                   |   -    |    o    |    o     |    o     |   o   |    -    |
| POST /contracts/{id}/submit       |   -    |    o    |    -     |    -     |   o   |    -    |
| POST /contracts/{id}/reviews      |   -    |    o    |    o     |    -     |   o   |    -    |
| POST /workflow-steps/{id}/approve |   -    |    -    |    -     |    o     |   o   |    -    |
| GET /audit-logs                   |   -    |    -    |    -     |    -     |   o   |    o    |
| POST /audit-logs/verify           |   -    |    -    |    -     |    -     |   o   |    o    |
| GET/POST /disputes                |   o    |    o    |    o     |    o     |   o   |    o    |
| GET/POST /change-orders           |   o    |    o    |    o     |    o     |   o   |    o    |
| GET/POST /partners                |   o    |    o    |    o     |    o     |   o   |    o    |
| GET /contracts/{id}/documents     |   o    |    o    |    o     |    o     |   o   |    o    |
| GET /contracts/{id}/payment-compliance | o |    o    |    o     |    o     |   o   |    o    |
| GET/POST /legal-holds             |   -    |    -    |    -     |    -     |   o   |    o    |

---

## 19. 変更履歴

| 日付       | 版   | 変更内容 |
| ---------- | ---- | -------- |
| 2026-05-16 | v1.0 | 初版作成 |
| 2026-08-05 | v0.2 | 高優先業務機能 API（紛争/変更契約/協力会社/支払/文書パッケージ）と P0-6 ガバナンス API を追加 |
