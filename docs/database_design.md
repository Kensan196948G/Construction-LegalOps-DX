# データベース設計 — Construction-LegalOps-DX

最終更新: 2026-05-16
版数: v1.0 (Draft)
所管: アーキテクチャドキュメントチーム
DBMS: PostgreSQL 16

---

## 1. 設計方針

1. **スキーマ命名**: 全テーブル小文字 + スネークケース、複数形。
2. **主キー**: `id BIGSERIAL` を採用。外部連携キーは別途 `external_id` を用意。
3. **論理削除**: 全業務テーブルに `deleted_at TIMESTAMPTZ` を持たせ、`NULL` のものを生存行とみなす。物理削除は監査ログのみ禁止、その他は GDPR 等の削除要請時のみ運用許容。
4. **タイムスタンプ**: `created_at`, `updated_at` を全テーブル必須。タイムゾーンは UTC で保存。
5. **作成者 / 更新者**: `created_by`, `updated_by` を `users.id` への FK で持つ。
6. **改ざん防止**: `audit_logs.hash_chain` に SHA-256 ベースのチェーン値を格納。
7. **行レベルセキュリティ (RLS)**: `contracts`, `legal_reviews`, `comments`, `attachments` に対し PostgreSQL RLS を有効化。
8. **インデックス**: 検索 / 結合に使用するカラム + `deleted_at IS NULL` の部分インデックス。
9. **JSONB**: AI レビュー結果や設定値は JSONB で柔軟に保持し、必須キーは CHECK 制約 + アプリ層 Pydantic で検証。

---

## 2. 共通カラム規約

```sql
-- すべての業務テーブルに展開される共通カラム (テンプレ)
-- id          BIGSERIAL    PRIMARY KEY
-- created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
-- updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
-- created_by  BIGINT       REFERENCES users(id)
-- updated_by  BIGINT       REFERENCES users(id)
-- deleted_at  TIMESTAMPTZ  -- NULL = 生存
-- version     INTEGER      NOT NULL DEFAULT 1  -- 楽観ロック
```

`updated_at` は `BEFORE UPDATE` トリガで自動更新する。

---

## 3. ER 関係 (ASCII)

```
                  +-------------+        +----------------+
                  | departments |<------*| users          |
                  +-------------+        +----------------+
                                              |  *
                                              v
                                       +-------------+
                                       |  contracts  |
                                       +-------------+
                                          |  |   | *
              +---------------------------+  |   +-------------+
              |                              |                 |
              v                              v                 v
       +---------------+            +----------------+   +-------------+
       | legal_reviews |            |    clauses     |   | attachments |
       +---------------+            +----------------+   +-------------+
              |  *                          |
              v                             v
       +---------------+            +----------------+
       |  risk_items   |            | clause_library |
       +---------------+            +----------------+

       +-------------+        +------------------+        +---------------+
       | workflows   |---*--->| workflow_steps   |---*--->|  contracts    |
       +-------------+        +------------------+        +---------------+

       +-------------+   +---------------+   +---------------+
       |  comments   |   | notifications |   |  audit_logs   |
       +-------------+   +---------------+   +---------------+
```

---

## 4. テーブル定義

### 4.1 departments (部署)

```sql
CREATE TABLE departments (
    id              BIGSERIAL PRIMARY KEY,
    code            VARCHAR(32) NOT NULL UNIQUE,
    name            VARCHAR(128) NOT NULL,
    parent_id       BIGINT REFERENCES departments(id),
    sort_order      INTEGER NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX ix_departments_parent ON departments(parent_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_departments_active ON departments(is_active) WHERE deleted_at IS NULL;
```

### 4.2 users (ユーザー)

```sql
CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    entra_oid       UUID NOT NULL UNIQUE,              -- Entra ID 'oid' クレーム
    email           VARCHAR(256) NOT NULL UNIQUE,
    display_name    VARCHAR(128) NOT NULL,
    department_id   BIGINT REFERENCES departments(id),
    role            VARCHAR(32) NOT NULL CHECK (role IN
                       ('viewer','drafter','reviewer','approver','admin','auditor','guest')),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    attributes      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX ix_users_department ON users(department_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_users_role       ON users(role)          WHERE deleted_at IS NULL;
CREATE INDEX ix_users_active     ON users(is_active)     WHERE deleted_at IS NULL;
```

### 4.3 contracts (契約)

```sql
CREATE TABLE contracts (
    id                  BIGSERIAL PRIMARY KEY,
    contract_no         VARCHAR(64) NOT NULL UNIQUE,         -- 例: C-2026-000123
    title               VARCHAR(256) NOT NULL,
    counterparty        VARCHAR(256) NOT NULL,
    contract_type       VARCHAR(64) NOT NULL,                -- 請負/委託/JV/賃借/秘密保持 等
    amount              NUMERIC(18, 2),
    currency            CHAR(3) NOT NULL DEFAULT 'JPY',
    start_date          DATE,
    end_date            DATE,
    department_id       BIGINT NOT NULL REFERENCES departments(id),
    drafter_id          BIGINT NOT NULL REFERENCES users(id),
    confidentiality     VARCHAR(16) NOT NULL DEFAULT 'normal'
                          CHECK (confidentiality IN ('public','normal','confidential','restricted')),
    status              VARCHAR(32) NOT NULL DEFAULT 'draft'
                          CHECK (status IN ('draft','in_review','approved','signed','archived','rejected')),
    version             INTEGER NOT NULL DEFAULT 1,
    sharepoint_item_id  VARCHAR(256),
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by          BIGINT REFERENCES users(id),
    updated_by          BIGINT REFERENCES users(id),
    deleted_at          TIMESTAMPTZ
);

CREATE INDEX ix_contracts_status        ON contracts(status)        WHERE deleted_at IS NULL;
CREATE INDEX ix_contracts_department    ON contracts(department_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_contracts_drafter       ON contracts(drafter_id)    WHERE deleted_at IS NULL;
CREATE INDEX ix_contracts_dates         ON contracts(start_date, end_date) WHERE deleted_at IS NULL;
CREATE INDEX ix_contracts_title_trgm    ON contracts USING gin (title gin_trgm_ops);
CREATE INDEX ix_contracts_counter_trgm  ON contracts USING gin (counterparty gin_trgm_ops);
```

### 4.4 legal_reviews (法務レビュー)

```sql
CREATE TABLE legal_reviews (
    id                  BIGSERIAL PRIMARY KEY,
    contract_id         BIGINT NOT NULL REFERENCES contracts(id),
    review_type         VARCHAR(32) NOT NULL CHECK (review_type IN ('ai','human','hybrid')),
    status              VARCHAR(32) NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending','running','completed','failed','rejected','accepted')),
    ai_model            VARCHAR(64),                       -- claude-opus-4-7 等
    ai_input_tokens     INTEGER,
    ai_output_tokens    INTEGER,
    summary             TEXT,
    overall_risk        VARCHAR(16) CHECK (overall_risk IN ('low','medium','high','critical')),
    result              JSONB NOT NULL DEFAULT '{}'::jsonb, -- 条項毎の指摘構造を格納
    started_at          TIMESTAMPTZ,
    finished_at         TIMESTAMPTZ,
    reviewer_id         BIGINT REFERENCES users(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by          BIGINT REFERENCES users(id),
    updated_by          BIGINT REFERENCES users(id),
    deleted_at          TIMESTAMPTZ
);

CREATE INDEX ix_reviews_contract    ON legal_reviews(contract_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_reviews_status      ON legal_reviews(status)      WHERE deleted_at IS NULL;
CREATE INDEX ix_reviews_overall     ON legal_reviews(overall_risk) WHERE deleted_at IS NULL;
```

### 4.5 clauses (契約内の条項)

```sql
CREATE TABLE clauses (
    id                  BIGSERIAL PRIMARY KEY,
    contract_id         BIGINT NOT NULL REFERENCES contracts(id),
    seq                 INTEGER NOT NULL,                  -- 条項順序
    title               VARCHAR(256),
    body                TEXT NOT NULL,
    library_clause_id   BIGINT REFERENCES clause_library(id),
    risk_level          VARCHAR(16) CHECK (risk_level IN ('low','medium','high','critical')),
    ai_findings         JSONB NOT NULL DEFAULT '{}'::jsonb, -- AI 指摘・修正案
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ,
    UNIQUE (contract_id, seq)
);

CREATE INDEX ix_clauses_contract  ON clauses(contract_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_clauses_risk      ON clauses(risk_level)  WHERE deleted_at IS NULL;
CREATE INDEX ix_clauses_body_trgm ON clauses USING gin (body gin_trgm_ops);
```

### 4.6 clause_library (条項ライブラリ)

```sql
CREATE TABLE clause_library (
    id              BIGSERIAL PRIMARY KEY,
    code            VARCHAR(64) NOT NULL UNIQUE,           -- 例: NDA-CONF-01
    category        VARCHAR(64) NOT NULL,                  -- 秘密保持/反社/解除 等
    title           VARCHAR(256) NOT NULL,
    body            TEXT NOT NULL,
    recommendation  VARCHAR(16) NOT NULL DEFAULT 'recommended'
                     CHECK (recommendation IN ('required','recommended','optional','prohibited')),
    tags            TEXT[] NOT NULL DEFAULT '{}',
    version         INTEGER NOT NULL DEFAULT 1,
    effective_from  DATE,
    effective_to    DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by      BIGINT REFERENCES users(id),
    updated_by      BIGINT REFERENCES users(id),
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX ix_library_category ON clause_library(category)  WHERE deleted_at IS NULL;
CREATE INDEX ix_library_recom    ON clause_library(recommendation) WHERE deleted_at IS NULL;
CREATE INDEX ix_library_tags     ON clause_library USING gin (tags);
```

### 4.7 risk_items (リスク項目)

```sql
CREATE TABLE risk_items (
    id              BIGSERIAL PRIMARY KEY,
    contract_id     BIGINT NOT NULL REFERENCES contracts(id),
    clause_id       BIGINT REFERENCES clauses(id),
    legal_review_id BIGINT REFERENCES legal_reviews(id),
    category        VARCHAR(64) NOT NULL,                  -- 法令違反/賠償/解除 等
    severity        VARCHAR(16) NOT NULL
                     CHECK (severity IN ('low','medium','high','critical')),
    probability     VARCHAR(16) NOT NULL DEFAULT 'medium'
                     CHECK (probability IN ('low','medium','high')),
    impact          VARCHAR(16) NOT NULL DEFAULT 'medium'
                     CHECK (impact IN ('low','medium','high')),
    description     TEXT NOT NULL,
    mitigation      TEXT,
    status          VARCHAR(32) NOT NULL DEFAULT 'open'
                     CHECK (status IN ('open','in_progress','accepted','transferred','mitigated','avoided','closed')),
    owner_id        BIGINT REFERENCES users(id),
    due_date        DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX ix_risk_contract ON risk_items(contract_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_risk_severity ON risk_items(severity)    WHERE deleted_at IS NULL;
CREATE INDEX ix_risk_status   ON risk_items(status)      WHERE deleted_at IS NULL;
```

### 4.8 workflows (ワークフロー定義)

```sql
CREATE TABLE workflows (
    id              BIGSERIAL PRIMARY KEY,
    code            VARCHAR(64) NOT NULL UNIQUE,
    name            VARCHAR(128) NOT NULL,
    description     TEXT,
    contract_type   VARCHAR(64),                            -- 任意: 契約類型ごとの既定
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    definition      JSONB NOT NULL DEFAULT '{}'::jsonb,     -- 多段ステップの定義
    version         INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);
```

### 4.9 workflow_steps (ワークフロー実行ステップ)

```sql
CREATE TABLE workflow_steps (
    id              BIGSERIAL PRIMARY KEY,
    workflow_id     BIGINT NOT NULL REFERENCES workflows(id),
    contract_id     BIGINT NOT NULL REFERENCES contracts(id),
    seq             INTEGER NOT NULL,
    name            VARCHAR(128) NOT NULL,
    step_type       VARCHAR(32) NOT NULL CHECK (step_type IN
                       ('draft','legal_review','manager_approval','exec_approval','sign','custom')),
    assignee_id     BIGINT REFERENCES users(id),
    assignee_role   VARCHAR(32),
    status          VARCHAR(32) NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending','in_progress','approved','rejected','skipped','sent_back')),
    due_at          TIMESTAMPTZ,
    decided_at      TIMESTAMPTZ,
    decision_note   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ,
    UNIQUE (contract_id, seq)
);

CREATE INDEX ix_wfsteps_contract ON workflow_steps(contract_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_wfsteps_assignee ON workflow_steps(assignee_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_wfsteps_status   ON workflow_steps(status)      WHERE deleted_at IS NULL;
```

### 4.10 comments (コメント)

```sql
CREATE TABLE comments (
    id              BIGSERIAL PRIMARY KEY,
    contract_id     BIGINT NOT NULL REFERENCES contracts(id),
    clause_id       BIGINT REFERENCES clauses(id),
    parent_id       BIGINT REFERENCES comments(id),
    author_id       BIGINT NOT NULL REFERENCES users(id),
    body            TEXT NOT NULL,
    visibility      VARCHAR(16) NOT NULL DEFAULT 'internal'
                     CHECK (visibility IN ('internal','reviewer_only','public')),
    resolved        BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX ix_comments_contract ON comments(contract_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_comments_clause   ON comments(clause_id)   WHERE deleted_at IS NULL;
CREATE INDEX ix_comments_author   ON comments(author_id)   WHERE deleted_at IS NULL;
```

### 4.11 attachments (添付ファイル)

```sql
CREATE TABLE attachments (
    id                  BIGSERIAL PRIMARY KEY,
    contract_id         BIGINT NOT NULL REFERENCES contracts(id),
    filename            VARCHAR(256) NOT NULL,
    mime_type           VARCHAR(128) NOT NULL,
    size_bytes          BIGINT NOT NULL CHECK (size_bytes >= 0),
    sharepoint_item_id  VARCHAR(256) NOT NULL,
    storage             VARCHAR(32) NOT NULL DEFAULT 'sharepoint'
                          CHECK (storage IN ('sharepoint','directcloud','local')),
    checksum_sha256     CHAR(64) NOT NULL,
    version             INTEGER NOT NULL DEFAULT 1,
    is_primary          BOOLEAN NOT NULL DEFAULT FALSE,
    uploaded_by         BIGINT NOT NULL REFERENCES users(id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ
);

CREATE INDEX ix_attachments_contract ON attachments(contract_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_attachments_primary  ON attachments(contract_id) WHERE is_primary AND deleted_at IS NULL;
```

### 4.12 notifications (通知)

```sql
CREATE TABLE notifications (
    id              BIGSERIAL PRIMARY KEY,
    recipient_id    BIGINT NOT NULL REFERENCES users(id),
    contract_id     BIGINT REFERENCES contracts(id),
    channel         VARCHAR(16) NOT NULL CHECK (channel IN ('mail','teams','in_app','desknets')),
    category        VARCHAR(32) NOT NULL,                  -- approval_request/due/ai_done 等
    subject         VARCHAR(256) NOT NULL,
    body            TEXT,
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    status          VARCHAR(16) NOT NULL DEFAULT 'queued'
                     CHECK (status IN ('queued','sent','failed','read')),
    scheduled_at    TIMESTAMPTZ,
    sent_at         TIMESTAMPTZ,
    read_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX ix_notif_recipient ON notifications(recipient_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_notif_status    ON notifications(status)       WHERE deleted_at IS NULL;
CREATE INDEX ix_notif_scheduled ON notifications(scheduled_at) WHERE status = 'queued';
```

### 4.13 audit_logs (監査ログ / 改ざん防止 hash chain)

```sql
CREATE TABLE audit_logs (
    id                  BIGSERIAL PRIMARY KEY,
    occurred_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_id            BIGINT REFERENCES users(id),       -- システム動作は NULL
    actor_role          VARCHAR(32),
    action              VARCHAR(64) NOT NULL,              -- contract.create 等
    target_type         VARCHAR(64) NOT NULL,              -- contracts 等
    target_id           BIGINT,
    request_id          UUID,
    ip_address          INET,
    user_agent          TEXT,
    payload             JSONB NOT NULL DEFAULT '{}'::jsonb, -- 変更前/変更後の正規化 JSON
    previous_hash       CHAR(64),                          -- 前行のハッシュ
    hash_chain          CHAR(64) NOT NULL,                 -- SHA256(previous_hash || canonical(payload))
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 監査ログは論理削除しない / 更新もしない
CREATE UNIQUE INDEX ux_audit_logs_id ON audit_logs(id);
CREATE INDEX ix_audit_logs_target  ON audit_logs(target_type, target_id);
CREATE INDEX ix_audit_logs_actor   ON audit_logs(actor_id);
CREATE INDEX ix_audit_logs_action  ON audit_logs(action);
CREATE INDEX ix_audit_logs_time    ON audit_logs(occurred_at);

-- 改ざん防止のため UPDATE / DELETE を禁止するトリガを設定する
CREATE OR REPLACE FUNCTION forbid_change_audit_logs() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_logs_no_update
BEFORE UPDATE OR DELETE ON audit_logs
FOR EACH ROW EXECUTE FUNCTION forbid_change_audit_logs();
```

### 4.14 hash_chain 計算ロジック

```sql
-- 概念
-- canonical_payload = json_canonicalize(payload)
-- raw = COALESCE(previous_hash, '0000...0') || canonical_payload
-- hash_chain = encode(digest(raw, 'sha256'), 'hex')

-- 挿入時の例 (擬似)
WITH last AS (
    SELECT hash_chain FROM audit_logs ORDER BY id DESC LIMIT 1
)
INSERT INTO audit_logs (action, target_type, target_id, payload, previous_hash, hash_chain)
SELECT
    'contract.update',
    'contracts',
    :contract_id,
    :payload::jsonb,
    last.hash_chain,
    encode(digest(coalesce(last.hash_chain, repeat('0', 64)) || :payload_canonical, 'sha256'), 'hex')
FROM last;
```

整合性検証バッチ (擬似):

```sql
WITH ordered AS (
    SELECT id, payload, previous_hash, hash_chain,
           LAG(hash_chain) OVER (ORDER BY id) AS prev
    FROM audit_logs
)
SELECT id
FROM ordered
WHERE previous_hash IS DISTINCT FROM prev
   OR hash_chain <> encode(digest(coalesce(prev, repeat('0',64)) || payload::text, 'sha256'), 'hex');
```

---

## 5. 行レベルセキュリティ (RLS) 例

```sql
ALTER TABLE contracts ENABLE ROW LEVEL SECURITY;

CREATE POLICY contracts_dept_isolation ON contracts
USING (
       confidentiality IN ('public','normal')
    OR department_id = current_setting('app.current_department_id')::bigint
    OR current_setting('app.current_role') IN ('admin','auditor')
);
```

アプリ側 (FastAPI) は接続セッション開始時に `SET LOCAL app.current_department_id = ...; SET LOCAL app.current_role = ...;` を発行する。

---

## 6. インデックス戦略まとめ

| テーブル | 主要インデックス | 種別 |
|---------|----------------|------|
| contracts | status / department_id / drafter_id / (start_date,end_date) | B-Tree (partial) |
| contracts | title / counterparty | GIN (pg_trgm) |
| clauses | contract_id / risk_level / body | B-Tree + GIN |
| legal_reviews | contract_id / status / overall_risk | B-Tree |
| risk_items | contract_id / severity / status | B-Tree |
| audit_logs | (target_type, target_id) / occurred_at | B-Tree |

---

## 7. パーティショニング方針 (将来)

- `audit_logs` は月次のレンジパーティション (`occurred_at`) を将来導入想定。MVP では未採用。
- `notifications` は 12 ヶ月で巨大化が予想されるため運用観察し、必要に応じてアーカイブテーブルへ移送。

---

## 8. マイグレーション運用

- Alembic で前進専用
- ステージング → 本番 へ同じスクリプトを適用
- 破壊的変更時は Expand-Migrate-Contract パターン

---

## 9. データ保持 / 削除ポリシー

| データ | 保持期間 | 削除方法 |
|--------|---------|---------|
| contracts | 締結後 10 年 | 論理削除 + アーカイブ |
| legal_reviews | 契約に従属 | 同上 |
| audit_logs | 10 年以上 | 物理削除禁止 |
| notifications | 1 年 | 物理削除可 |
| attachments メタ | 契約に従属 | SharePoint 側保存ポリシーと同期 |

---

## 10. 変更履歴

| 日付 | 版 | 変更内容 |
|------|----|---------|
| 2026-05-16 | v1.0 | 初版作成 |
