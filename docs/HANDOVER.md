# HANDOVER — Construction-LegalOps-DX

次セッション (Loop 19 以降、または本番リリース準備チーム) への引き継ぎ書です。

- 作成日: **2026-05-16** (Loop 5 完了時) / **最終更新: 2026-05-30** (Loop 18)
- 対象プロジェクト: Construction-LegalOps-DX
- リリース期限: **2026-11-16** (登録日 2026-05-16 から 6 ヶ月、絶対厳守)
- 現在ステータス: **v0.1.8** — 全 12 API 実装済み / テスト 253 件 / カバレッジ 74%

---

## 1. これまでに完了した範囲 (Loop 1〜5 サマリ)

### Loop 1: Foundation (プロジェクト基盤構築)

- リポジトリ初期スキャフォールド (backend / frontend / infra / docs / .github)。
- ドキュメント整備: `README.md`, `LICENSE` (MIT), `CONTRIBUTING.md`, `CHANGELOG.md`。
- `.env.example`, `.gitignore`, `.editorconfig` で開発環境の共通化。
- GitHub Actions CI (`.github/workflows/ci.yml`) で lint / test / security / docker build を定義。
- 法務 DX 設計ドキュメント (`docs/requirements.md`, `system_architecture.md`, `api_design.md`, `database_design.md`, `ai_disclaimer_policy.md`, `legal_playbook.md`, `audit_log_policy.md`, `security_policy.md`, `construction_law_checklist.md`, `contract_review_policy.md`, `approval_workflow_policy.md`, `risk_scoring_policy.md`, `frontend_design.md`) を整備。

### Loop 2: Backend MVP (FastAPI コア実装)

- FastAPI アプリケーション本体と設定モジュール。
- SQLAlchemy 2.x モデル: `users`, `contracts`, `contract_reviews`, `workflows`, `audit_logs`。
- Alembic マイグレーション基盤。
- Entra ID OIDC 認証 + JWT (HS256 暫定) + RBAC ミドルウェア。
- 契約書 CRUD ルーター、SharePoint / desknet's NEO 連携サービススタブ。
- Claude API ラッパーと「AI 下書き」ディスクレーマー付き契約書レビュー API。
- 監査ログ書き込みサービス。
- pytest 単体・結合テストの初期セット。

### Loop 3: Frontend MVP (Next.js 画面実装)

- Next.js 14 App Router + Tailwind + shadcn/ui セットアップ。
- ログイン (Entra ID 連携) / ダッシュボード / 契約書一覧・詳細 / AI レビュー結果 / ワークフロー / 監査ログ画面。
- AI 出力には常時「AI 下書き / 人間確認必須」ディスクレーマー表示。
- TanStack Query によるサーバ状態管理。
- Jest / React Testing Library テスト。

### Loop 4: Security & Infra (セキュリティ・基盤強化)

- nginx リバースプロキシ (TLS 終端、HSTS、セキュリティヘッダ)。
- CSP **Report-Only** モードで導入 (enforce 移行は未完)。
- PostgreSQL 16 本番想定パラメータ、`audit_logs` トリガー (INSERT/UPDATE/DELETE)。
- Redis 7 (セッション / レートリミット)。
- `/healthz` / `/readyz` ヘルスエンドポイント (`/readyz` 本番チューニングは未完)。
- Trivy / Bandit / npm audit を CI 統合。

### Loop 5: Integration & Finalization

- E2E 結合シナリオ (login → upload → review → workflow → audit) のテストハーネス。
- `docs/RELEASE_CHECKLIST.md` 新規追加 (本番リリース前チェックリスト)。
- `docs/HANDOVER.md` 新規追加 (本ドキュメント)。
- `README.md` に Quick Start / Compliance & Disclaimer / Project Timeline セクション追加。
- `CHANGELOG.md` を `## [0.1.0] - 2026-05-16` で確定。
- `state.json` に `loops_total: 5`, `status: "loops_complete"` を反映。

---

## 2. 未解決の技術負債 (本番リリース前に解消すべき項目)

優先度: **P0** = リリースブロッカー / **P1** = リリース前推奨 / **P2** = リリース後対応可

### P0 (絶対解消)

1. **JWT 署名鍵を HS256 → RS256 に切替** ✅ **コード実装済み (Loop 18)**
   - コード: `backend/app/core/security.py` は RS256 に完全対応済み。
     `JWT_PRIVATE_KEY` + `JWT_PUBLIC_KEY` 環境変数を設定するだけで RS256 に切替わる。
   - 鍵生成: `./scripts/generate_rsa_keys.sh` を実行して RSA-2048 鍵ペアを生成。
   - **残作業**: 本番環境への鍵投入 (Vault) のみ → P0-3 の Vault 投入と統合して対応。
   - 影響範囲: backend 認証層のみ。frontend のトークン検証不要。

2. **CSP Report-Only → enforce 移行**
   - 現状: nginx で `Content-Security-Policy-Report-Only` ヘッダを送出中。
   - 対応: 7 日間のレポート収集 → 違反解消 → `Content-Security-Policy` ヘッダ名に変更 → canary 10/50/100% 段階展開。
   - 詳細手順: `docs/RELEASE_CHECKLIST.md` §6 を参照。

3. **本番 secrets の Vault 投入**
   - HENNGE / Entra / Anthropic / SharePoint / desknet's NEO の本番キーを Azure Key Vault / HashiCorp Vault に投入。
   - `.env` ファイルへの直接記載は禁止。詳細: `docs/RELEASE_CHECKLIST.md` §1。

### P1 (リリース前推奨)

4. **`/readyz` の本番チューニング**
   - 現状: 最小限の DB ping のみ。
   - 対応: PostgreSQL / Redis / SharePoint / desknet's NEO / Claude API の deep check を実装。タイムアウトと degraded 状態の表現 (200 vs 503) を整理。

5. **結合テストの PostgreSQL profile 切替**
   - 現状: SQLite フォールバックが残存しており、本番と挙動が異なる。
   - 対応: pytest fixture を testcontainers-python で PostgreSQL 16 に統一。CI の `services:` で postgres を起動済みなので、conftest の判定ロジックのみ修正。

6. **alembic マイグレーションのリストアテスト**
   - 本番 PITR リストアを 1 回ステージング環境で実施し、所要時間を計測。

7. **AI 監査ログのパーティショニング**
   - `audit_logs` テーブルが月次大量レコード化する見込み。月次パーティショニングを検討。

### P2 (リリース後対応可)

8. **E2E テストの Playwright 化**
   - Loop 3 で導入予定だった Playwright E2E を Loop 5 では結合テストハーネスで代替。本番リリース後に拡充。

9. **AI レビュー結果の根拠条文ハイライト**
   - 現状はテキスト下書きのみ。条文番号へのリンクや該当箇所ハイライトは v0.2.0 で対応。

10. **多言語化 (i18n)**
    - 現状は日本語のみ。建設業の海外プロジェクト対応は v0.3.0 以降。

---

## 3. 推奨次アクション (Loop 6 以降の優先順)

### Sprint 1 (リリース 90 日前まで: 〜2026-08-16)

1. **RS256 鍵生成と切替 (P0-1)** — 担当: backend リード、工数 2 日。
2. **`/readyz` deep check 実装 (P1-4)** — 担当: backend + インフラ、工数 3 日。
3. **結合テストの PG 統一 (P1-5)** — 担当: QA、工数 2 日。

### Sprint 2 (リリース 60 日前まで: 〜2026-09-16)

4. **CSP Report-Only でレポート収集開始 (P0-2 準備)** — 期間 30 日、違反パターン洗い出し。
5. **本番 Vault 構築と secrets 投入 (P0-3)** — 担当: インフラリード、工数 5 日。
6. **alembic PITR リストアテスト (P1-6)** — 担当: DBA、工数 2 日。

### Sprint 3 (リリース 30 日前まで: 〜2026-10-16)

7. **CSP enforce 移行 (P0-2 本実施)** — canary 展開で 7 日かけて 100% 化。
8. **TLS 証明書 (Let's Encrypt) 本番導入** — `docs/RELEASE_CHECKLIST.md` §2。
9. **負荷テスト (k6 / Locust)** — 目標 50 req/s, p95 < 500ms。

### Sprint 4 (リリース 7 日前まで: 〜2026-11-09)

10. **`docs/RELEASE_CHECKLIST.md` の全項目チェック** — リリース責任者・法務・インフラの三者確認。
11. **法務担当者・顧問弁護士による UI ディスクレーマー最終承認**。
12. **ロールバック手順のドリル (ステージングで 1 回実演)**。

### リリース当日 (2026-11-16)

13. 本番デプロイ → スモークテスト (`docs/RELEASE_CHECKLIST.md` §7) → GitHub Release `v0.1.0` 公開。

---

## 4. 運用上の注意事項

- **法的判断の確定禁止**: AI 出力に「法的判断を断定する文言」を追加してはならない。UI / ドキュメント / プロンプト変更時は法務確認必須。
- **同一エラー 2 回目以降**: Codex rescue (`/codex:rescue --background investigate`) に委任。
- **認証・認可・DB スキーマ・並列処理変更**: Codex 対抗レビュー (`/codex:adversarial-review`) 必須。
- **残日数自動縮退**:
  - 残 30 日 (2026-10-17 以降): Improvement 縮退、Verify / リリース準備優先。
  - 残 14 日 (2026-11-02 以降): 新機能開発禁止、バグ修正・安定化のみ。
  - 残 7 日 (2026-11-09 以降): リリース準備のみ。

---

## 5. 参考ドキュメント

- [`README.md`](../README.md) — Quick Start / Compliance / Project Timeline
- [`CHANGELOG.md`](../CHANGELOG.md) — v0.1.0 リリースノート
- [`docs/RELEASE_CHECKLIST.md`](./RELEASE_CHECKLIST.md) — 本番リリース前チェックリスト
- [`docs/ai_disclaimer_policy.md`](./ai_disclaimer_policy.md) — AI 免責ポリシー
- [`docs/legal_playbook.md`](./legal_playbook.md) — 法務オペレーションプレイブック
- [`docs/security_policy.md`](./security_policy.md) — セキュリティポリシー
- [`docs/audit_log_policy.md`](./audit_log_policy.md) — 監査ログ運用

---

> 本引き継ぎ書は Loop 5 完了時 (2026-05-16) の状態を記録したものです。
> 次セッションは本ドキュメントを起点に `state.json` を確認し、`docs/RELEASE_CHECKLIST.md` の優先順で作業を進めてください。
