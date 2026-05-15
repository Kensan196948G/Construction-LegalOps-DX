# REST API 設計 — Construction-LegalOps-DX

最終更新: 2026-05-16
版数: v1.0 (Draft)
所管: アーキテクチャドキュメントチーム
ベース URL: `https://legalops.example.co.jp/api/v1`

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

| ヘッダ | 用途 |
|--------|------|
| `Authorization: Bearer <JWT>` | 認証 |
| `Idempotency-Key: <uuid>` | 冪等 POST |
| `X-Request-Id: <uuid>` | リクエスト相関 |
| `Accept-Language: ja` | 多言語化 |

### 2.2 共通レスポンス構造

```json
{
  "data": { /* オブジェクト or 配列 */ },
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
  "type": "https://legalops.example.co.jp/errors/validation",
  "title": "Validation Error",
  "status": 422,
  "detail": "title must not be empty",
  "instance": "/api/v1/contracts",
  "errors": [
    { "field": "title", "message": "required" }
  ],
  "request_id": "8b3a..."
}
```

### 2.4 HTTP ステータス使い分け

| コード | 用途 |
|--------|------|
| 200 | 取得・更新成功 |
| 201 | 新規作成成功 |
| 202 | 非同期処理受付 (AI レビューなど) |
| 204 | ボディなし成功 (削除等) |
| 400 | リクエスト不正 |
| 401 | 未認証 |
| 403 | 権限不足 |
| 404 | 存在しない / アクセス不可 (情報秘匿のため 403 ではなく 404) |
| 409 | 競合 (楽観ロック失敗、状態遷移違反) |
| 422 | バリデーション失敗 |
| 429 | レート制限 |
| 500 | サーバ内部エラー |

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

### 4.3 `PATCH /users/{id}`

- 認可: `admin`
- リクエスト:

```json
{ "role": "approver", "department_id": 14, "is_active": true }
```

- レスポンス: 200 + 更新後ユーザー
- 409: 楽観ロック (version 不一致)

### 4.4 `POST /users/sync`

- 認可: `admin`
- 動作: Microsoft Graph からユーザー / グループを同期
- レスポンス: 202 (ジョブ ID 返却)

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
- 動作: status を `draft → in_review` に遷移し、ワークフローを開始
- レスポンス: 200 + 更新後 Contract
- 409: 状態遷移違反

### 5.7 `GET /contracts/{id}/clauses`

- 認可: `viewer` 以上
- レスポンス: clauses 配列 (seq 昇順)

### 5.8 `GET /contracts/{id}/audit-trail`

- 認可: `auditor` / `admin`
- レスポンス: audit_logs を contract_id で絞った時系列

---

## 6. レビュー (`/reviews`)

### 6.1 `POST /contracts/{id}/reviews`

AI レビューを起動する。

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

### 6.3 `POST /reviews/{id}/accept`

- 認可: `reviewer`
- 動作: AI 結果を受領、契約 status を更新
- レスポンス: 200

### 6.4 `POST /reviews/{id}/reject`

- 認可: `reviewer`
- リクエスト: `{ "reason": "再レビュー要求" }`
- レスポンス: 200

### 6.5 `GET /reviews?contract_id=...`

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
      { "seq": 2, "name": "法務レビュー", "step_type": "legal_review", "assignee_role": "reviewer" },
      { "seq": 3, "name": "部長承認", "step_type": "manager_approval", "assignee_role": "approver" },
      { "seq": 4, "name": "経営承認", "step_type": "exec_approval", "assignee_role": "approver" }
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
      { "probability": "high",   "impact": "high",   "count": 4 },
      { "probability": "high",   "impact": "medium", "count": 9 },
      { "probability": "medium", "impact": "high",   "count": 6 }
    ]
  }
}
```

---

## 9. コンプライアンス (`/compliance`)

### 9.1 `GET /compliance/checklists`

- 認可: `viewer` 以上
- 用途: 適用可能なチェックリスト

### 9.2 `POST /contracts/{id}/compliance-runs`

- 認可: `reviewer` / `admin`
- 動作: チェックリスト適用
- レスポンス: 202

---

## 10. テンプレート / 条項ライブラリ (`/templates`, `/clauses-library`)

### 10.1 `GET /clauses-library`

- 認可: `viewer` 以上
- クエリ: `category`, `recommendation`, `tag`, `q`

### 10.2 `POST /clauses-library`

- 認可: `admin`
- リクエスト: 条項のフルテキスト + メタ

### 10.3 `GET /templates`

- 認可: `viewer` 以上
- 用途: 契約類型ごとのテンプレ一覧

---

## 11. ナレッジ (`/knowledge`)

### 11.1 `GET /knowledge`

- クエリ: `q`, `tag`
- レスポンス: ナレッジ記事配列

### 11.2 `POST /knowledge`

- 認可: `reviewer` / `admin`

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
      "payload": { "before": {"status":"draft"}, "after": {"status":"in_review"} },
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

### 13.1 `POST /uploads`

- 認可: `drafter` 以上
- Content-Type: `multipart/form-data`
- パート:
  - `file`: バイナリ
  - `contract_id`: 関連契約 (任意、後付け関連付け可)
  - `is_primary`: bool
- レスポンス例:

```json
{
  "data": {
    "id": 5001,
    "contract_id": 1001,
    "filename": "draft.docx",
    "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "size_bytes": 234123,
    "checksum_sha256": "abc123...",
    "storage": "sharepoint",
    "sharepoint_item_id": "01ABCD..."
  }
}
```

- 制約:
  - 最大サイズ 100 MB
  - 受理 MIME: `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
  - 受理 NG 時は `415 Unsupported Media Type`

### 13.2 `GET /uploads/{id}/download`

- 認可: 契約に対するアクセス権あり
- 動作: SharePoint への署名付き URL を生成し `302` リダイレクト

### 13.3 `DELETE /uploads/{id}`

- 認可: `admin` (または起案者・未署名段階のみ)
- 動作: 論理削除

---

## 14. 通知 (`/notifications`)

### 14.1 `GET /notifications`

- 認可: 本人のみ
- クエリ: `status`, `channel`
- 用途: アプリ内通知センター

### 14.2 `POST /notifications/{id}/read`

- 動作: `read_at = now()` を設定
- レスポンス: 204

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

## 16. レート制限

| ルート | 制限 |
|--------|------|
| `POST /contracts/{id}/reviews` | 1 ユーザー 30 req/h |
| `POST /uploads` | 1 ユーザー 60 req/h |
| 既定 | 1 ユーザー 600 req/min |

超過時 `429 Too Many Requests` + `Retry-After` ヘッダ。

---

## 17. 認可マトリクス (抜粋)

| エンドポイント | viewer | drafter | reviewer | approver | admin | auditor |
|---------------|:------:|:-------:|:--------:|:--------:|:-----:|:-------:|
| GET /contracts | o | o | o | o | o | o |
| POST /contracts | - | o | o | o | o | - |
| POST /contracts/{id}/submit | - | o | - | - | o | - |
| POST /contracts/{id}/reviews | - | o | o | - | o | - |
| POST /workflow-steps/{id}/approve | - | - | - | o | o | - |
| GET /audit-logs | - | - | - | - | o | o |
| POST /audit-logs/verify | - | - | - | - | o | o |

---

## 18. 変更履歴

| 日付 | 版 | 変更内容 |
|------|----|---------|
| 2026-05-16 | v1.0 | 初版作成 |
