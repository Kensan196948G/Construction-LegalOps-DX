# HANDOVER — Construction-LegalOps-DX

次セッション (Loop 34 以降、または本番リリース準備チーム) への引き継ぎ書です。

- 作成日: **2026-05-16** (Loop 5 完了時)
- 最終更新: **2026-07-18** (Loop 33 / Phase 1 最終整備 完了時点で更新)
- 対象プロジェクト: Construction-LegalOps-DX
- リリース期限: **2026-11-16** (登録日 2026-05-16 から 6 ヶ月、絶対厳守)
- 現在ステータス: **v0.1.12** — 全 PR マージ済み / 906 tests passed / 0 failed / Phase 1 完了
- **本番デプロイ**: **未実行・人間承認待ち**（PR マージ・タグ作成・DNS 変更・本番デプロイは CTO/Supervisor 範囲外）

> 📌 Loop 33 完了時点: Phase 1 のコード作業は完了。CF/Neon IaC コード完成、監視基盤（Prometheus/Alertmanager/Grafana）完成、JIT プロビジョニング audit chain 統合・可観測性向上完了。
> 本書は「未解決事項 / 人間判断待ち / 残課題」と「Loop 1-5 までの設計履歴」を保持する。

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

1. **JWT 署名鍵を HS256 → RS256 に切替** ✅ **コード実装 + 鍵ローテ機構 完了 (Loop 18 + Loop 22)**
   - コード: `backend/app/core/security.py` は RS256 に完全対応済み (kid ヘッダ + JWT_PUBLIC_KEYS 退役鍵検証セット)
   - 鍵生成: `./scripts/generate_rsa_keys.sh` を実行して RSA-2048 鍵ペアを生成
   - 鍵ローテ: ゼロダウンタイムで active/retired を切替 (PR #27 マージ済み)
   - **残作業**: 本番環境への鍵投入 (Vault) のみ → P0-3 の Vault 投入と統合して対応
   - 影響範囲: backend 認証層のみ。frontend のトークン検証不要

2. **CSP Report-Only → enforce 移行** ⏳ **人間作業待ち (Issue #24)**
   - 現状: nginx で `Content-Security-Policy-Report-Only` ヘッダを送出中
   - 対応: 7 日間のレポート収集 → 違反解消 → `Content-Security-Policy` ヘッダ名に変更 → canary 10/50/100% 段階展開
   - **enforce 用設定ファイル準備済み**: `infra/nginx/security-headers.enforce.conf` (PR #4 で追加)
   - 詳細手順: `docs/RELEASE_CHECKLIST.md` §6 + Issue #24 を参照

3. **本番 secrets の Vault 投入** ⏳ **人間作業待ち (Issue #23)**
   - HENNGE / Entra / Anthropic / SharePoint / desknet's NEO / Perplexity / Claude の本番キーを Azure Key Vault / HashiCorp Vault に投入
   - `.env` ファイルへの直接記載は禁止
   - **投入スクリプト準備済み**: `./scripts/setup_vault_secrets.sh` (Loop 18 で追加)
   - **鍵生成スクリプト**: `./scripts/generate_rsa_keys.sh` (Loop 18 で追加)
   - 詳細: `docs/RELEASE_CHECKLIST.md` §1 + Issue #23 を参照

### P1 (リリース前推奨)

4. **`/readyz` の本番チューニング** ✅ **完了 (Loop 18)**
   - DB (critical: SELECT 1) + Redis / Claude (degraded) の deep check を実装
   - 200 vs 503 のステータス分離を実装

5. **結合テストの PostgreSQL profile 切替** ✅ **完了 (Loop 22-27)**
   - pytest fixture は本番同等 PostgreSQL 16 を使用 (CI: `services.postgres`)
   - `backend-pg` ジョブ (PR #38) で hard-gate 化
   - 143 PG integration DDL エラーは PR #38 で解消
   - Issue #32 (--maxfail=1 flaky) も PR #34 で解消

6. **alembic マイグレーションのリストアテスト** ⏳ **ステージング 1 回実施推奨**
   - 本番 PITR リストアを 1 回ステージング環境で実施し、所要時間を計測
   - Loop 30 で **migrations CI ゲート** を新設 (PR #54): alembic URL 解決欠陥修正 + CI で `alembic upgrade head` を常時実行

7. **AI 監査ログのパーティショニング** ⏳ **未着手 (P2 推奨)**
   - `audit_logs` テーブルが月次大量レコード化する見込み。月次パーティショニングを検討

8. **k6 負荷テストの SLO 達成** ✅ **完了 (Loop 30)**
   - smoke / load / soak 3 シナリオ実装 (PR #36)
   - SLO: p95 < 500ms / エラー率 < 1% を CI で検証

### P2 (リリース後対応可)

9. **運用基盤ギャップ** ✅ **完了 (Loop 33, Issue #51)**
   - Prometheus / Alertmanager / Grafana dashboard / DB プールメトリクス / backup_db.sh — 完了
   - 未整備: Loki/OTel ログ集約 / TLS 自動更新 (P2 継続、運用開始後に整備)

10. **python-jose → PyJWT 移行** ✅ **完了 (Loop 32, Issue #41)**
    - ecdsa / rsa 純 Python 暗号依存を除去。全回帰 906 passed。

11. **JIT プロビジョニング残課題** ✅ **完了 (Loop 32+33, Issue #48)**
    - 6 件の残課題のうち 5 件完了: reviewer_id 記録 / oid claim 伝搬 / user_id 型注釈修正 / commit 窓可観測性 / audit chain 統合
    - 未了 1 件: identity linking ポリシー（設計判断要・人間判断）

12. **Cloudflare / Neon 移行** ✅ **IaC コード完成 (Loop 33, Issue #50)**
    - `infra/cloudflare/`: wrangler.toml / access-policy.yml / neon-config.md / tunnel-config.example.yml
    - CD 経路: deploy.yml に CF/Neon デプロイジョブ 3 件追加（fail-safe skip 設計）
    - **本番適用は人間による API token 発行・リソース作成後**

---

## 3. 推奨次アクション (Loop 34 以降の優先順)

### Sprint 1 (リリース 2026-08-16 〜 2026-10-16) — ✅ **Loop 32-33 で完了**

1. ✅ P2 #41 python-jose → PyJWT 移行 — 完了
2. ✅ P2 #48 JIT プロビジョニング残課題 — 5/6 完了、1 件 identity linking ポリシーは設計判断要
3. ✅ P2 #51 運用基盤ギャップ #1-3 — Prometheus / アラート / 自動バックアップ 完了

### Sprint 2 (リリース 60 日前: 〜 2026-09-16)

4. **P0 #24 CSP Report-Only でレポート収集開始** — 期間 7〜30 日
5. **P0 #23 本番 Vault 構築と secrets 投入 (人間作業)** — 工数 5 日
6. **alembic PITR リストアテスト** — ステージングで 1 回実演

### Sprint 3 (リリース 30 日前: 〜 2026-10-17)

7. **P0 #24 CSP enforce 移行 (人間作業)** — canary 展開で 7 日かけて 100% 化
8. **TLS 証明書 (Let's Encrypt) 本番導入** — `docs/RELEASE_CHECKLIST.md` §2
9. **Issue #50 Cloudflare/Neon 本番リソース作成** — 人間が API token / Neon プロジェクトを作成後に CTO が適用

### Sprint 4 (リリース 7 日前: 〜 2026-11-09)

10. **`docs/RELEASE_CHECKLIST.md` の全項目チェック** — リリース責任者・法務・インフラの三者確認
11. **法務担当者・顧問弁護士による UI ディスクレーマー最終承認**
12. **ロールバック手順のドリル (ステージングで 1 回実演)**

### リリース当日 (2026-11-16)

13. **人間による本番デプロイ実行** → スモークテスト (`docs/RELEASE_CHECKLIST.md` §7) → GitHub Release `v1.0.0` 公開
    - ⚠️ CTO / Supervisor は deploy ready の判定まで。**実際の deploy コマンド実行は人間**

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
