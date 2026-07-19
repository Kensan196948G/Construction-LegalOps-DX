# HANDOVER — Construction-LegalOps-DX

次セッション (Loop 93 以降、または本番リリース準備チーム) への引き継ぎ書です。

- 作成日: **2026-05-16** (Loop 5 初版)
- 最終更新: **2026-07-19** (Loop 93: Backup/restore evidence gate + checksum-backed backup script + release gate sync)
- 対象プロジェクト: Construction-LegalOps-DX
- リリース期限: **2026-11-16** (登録日 2026-05-16 から 6 ヶ月、絶対厳守)
- 現在ステータス: **v0.1.12** — pre-deploy gate 900+ tests / frontend E2E 51 passed / Phase 1 完了 / 本番承認待ち
- **本番デプロイ**: **未実行・人間承認待ち**（PR マージ・タグ作成・DNS 変更・本番デプロイは CTO/Supervisor 範囲外）

> 📌 Loop 93 時点: Phase 1 のコード作業は完了し、AI review / templates / users / auth callback / uploads / notifications / knowledge / reviews は DB-backed または runtime-ready の契約に同期済み。SharePoint Graph real mode は Entra client-credentials、Microsoft Graph drive upload、webUrl 解決、設定不足/不正応答 fail-closed に対応済み。Notification real mode は Exchange Graph sendMail、Teams webhook、desknet's webhook、設定不足 fail-closed に対応済み。`PATCH /reviews/{id}` は人間判断メタデータを `result` JSON に永続化し、review flow でも 422 許容を撤去済み。実装済み内部モジュール unit tests は `pytest.importorskip` を撤去し fail-closed 化済み。CF/Neon IaC、`legalops.mirai-dx-platform.com` の Cloudflare read-only preflight、Cloudflare公式根拠付きRunbook、release evidence matrix、final stop report、release docs preflight、goal completion evidence preflight、review evidence preflight、dependency audit evidence preflight、backup/restore evidence preflight、Standalone WebUI systemd (`http://192.168.0.185:38100/`) は確認済み。`scripts/backup_db.sh` は `.sha256` 記録と復元前チェックサム検証に対応し、`scripts/verify_backup_restore_docs.sh` により pg_dump / pg_restore 手順、backup_db.sh checksum、Alembic rollback、PITR未実演停止線をread-onlyで検証する。`scripts/verify_dependency_audit_evidence.sh` により npm audit high/critical 0、moderate 4 の既知残リスク、CI の strict project-scoped pip-audit、ecdsa ignore の到達不能根拠、PyJWT 移行、今回の pip-audit 72 deps / 0 vulnerabilities をread-onlyで検証する。`scripts/verify_review_evidence.sh` により CodeRabbit CLI/auth、findings前timeout、代替静的検証、security review、Critical/High 0件と断言しない制限をread-onlyで検証する。`scripts/verify_goal_completion_evidence.sh` により `/goal` 完了条件と evidence matrix / final stop report / stop-line の対応をread-onlyで検証する。`scripts/verify_standalone_webui_runtime.sh` により status JSON、systemd enabled/active、`38100-38999` のauto port範囲、Linux host上の選択IP、listen実体、health ok、HEAD 200、Content-Length一致、source endpoint一致をread-onlyで検証する。`scripts/verify_predeploy_warning_classification.sh` により pre-deploy warning は本番secret / SSO / AI key / Docker build skip の既知5件のみで、未知warning 0であることを検証する。`scripts/verify_release_checklist_pending_items.sh` により release checklist の未チェック73件は人間承認 / 本番実行 / リリース後確認に限定されていることを検証する。`scripts/verify_production_stop_line.sh` により legalops DNS未作成、Git tag 0、GitHub Release 0、GitHub Deployments 0、Project #30 Todo状態をread-onlyで検証する。GitHub Project #30 `Construction-LegalOps-DX 開発管理` のreadmeもLoop 93のrelease gateへ同期予定で、#23/#24/#50をTodoの人間ゲートとして可視化する。`scripts/verify_github_release_gate.sh` により open PR 0、open issues #23/#24/#50、latest main CI completed/success、Project #30 Todo状態、#50 blocked label をread-onlyで検証する。release docs preflight は README / release docs / pre-deploy gate の現在状態表を監視する。CD workflow は `workflow_dispatch` + `production` environment + `APPROVE_PRODUCTION_CHANGE` 明示入力で fail-closed。Linux host の Next.js build は `ulimit -v 20000000` により直接実行で WebAssembly OOM になるため、Docker Node 20 build と Playwright Docker E2E を標準検証経路とする。
> 本書は「人間判断待ち / 残課題 / 過去設計履歴」を保持する。現行の承認判断は [`docs/PRODUCTION_APPROVAL_PACKET.md`](./PRODUCTION_APPROVAL_PACKET.md)、[`docs/RELEASE_CHECKLIST.md`](./RELEASE_CHECKLIST.md)、[`docs/RELEASE_EVIDENCE_MATRIX.md`](./RELEASE_EVIDENCE_MATRIX.md)、[`docs/FINAL_RELEASE_STOP_REPORT.md`](./FINAL_RELEASE_STOP_REPORT.md) を正とする。

---

## 1. これまでに完了した範囲 (Loop 1〜82 サマリ)

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

6. **alembic マイグレーション rollback drill** ✅ **一時 PostgreSQL 検証を自動化 (Loop 42)**
   - `scripts/verify_migrations_roundtrip.sh`: `upgrade head -> downgrade base -> upgrade head -> idempotent upgrade`
   - CI migrations job は PostgreSQL 16 service に対して roundtrip verifier を実行
   - 本番データ PITR リストアは backup / WAL / Neon 承認後に 1 回ステージング相当で実施

7. **AI 監査ログのパーティショニング** ⏳ **未着手 (P2 推奨)**
   - `audit_logs` テーブルが月次大量レコード化する見込み。月次パーティショニングを検討

8. **k6 負荷テストの SLO 達成** ✅ **完了 (Loop 30)**
   - smoke / load / soak 3 シナリオ実装 (PR #36)
   - SLO: p95 < 500ms / エラー率 < 1% を CI で検証

### P2 (リリース後対応可)

9. **運用基盤ギャップ** ⚠️ **リリース前必須分は完了、P2 残あり (Loop 33-35, Issue #51)**
   - Prometheus / Alertmanager / Grafana dashboard / DB プールメトリクス / backup_db.sh — 完了
   - Loki / Promtail ログ集約 IaC (`--profile logging`) — 完了
   - certbot renewal helper IaC (`--profile tls-renewal`) — 完了。実発行はDNS/公開方式の人間承認後。
   - 追加メトリクス拡張 (DB pool / Celery queue / business status counts) — 完了
   - On-call 役割表 / incident label catalog / GitHub labels — 完了。実名連絡先と通知先 secret は本番承認時に投入。
   - unhealthy 復旧方式レビュー — 完了。手動承認型 watchdog を採用し、常駐 autoheal は security 理由で不採用。

10. **python-jose → PyJWT 移行** ✅ **完了 (Loop 32, Issue #41)**
    - ecdsa / rsa 純 Python 暗号依存を除去。pre-deploy gate は 900+ tests で継続確認。

11. **JIT プロビジョニング残課題** ✅ **完了 (Loop 32-34, Issue #48)**
    - 6 件の残課題を解消: reviewer_id 記録 / oid claim 伝搬 / user_id 型注釈修正 / commit 窓可観測性 / audit chain 統合 / identity linking ポリシー
    - identity linking は `POST /users/{id}/identity-link` として admin 明示操作のみ許可。通常ログイン時の自動マージは禁止を継続。

12. **Cloudflare / Neon 移行** ✅ **IaC コード完成 + legalops サブドメイン手順化 (Issue #50)**
    - `infra/cloudflare/`: wrangler.toml / access-policy.yml / neon-config.md / tunnel-config.example.yml / dns-records.legalops.example.json
    - `infra/docker/docker-compose.cloudflare-tunnel.yml`: cloudflared connector overlay（承認後に `CLOUDFLARE_TUNNEL_TOKEN` を Vault / secret manager から注入）
    - `docs/CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK.md`: `legalops.mirai-dx-platform.com` の DNS / Tunnel / Access / rollback 手順
    - `scripts/verify_cloudflare_legalops.sh`: DNS を変更せず、Tunnel/DNS/Access/compose/NS/CNAME 未作成状態を検証する read-only preflight
    - CD 経路: deploy.yml に CF/Neon デプロイジョブ 3 件追加（`workflow_dispatch` + `production` environment + `APPROVE_PRODUCTION_CHANGE` + secrets 未設定時 fail-closed）
    - **本番適用は人間による Cloudflare API token 発行・Access/Tunnel/DNS 作成承認後**

---

## 3. 推奨次アクション (Loop 93 以降の優先順)

### Sprint 1 (リリース 2026-08-16 〜 2026-10-16) — ✅ **Loop 32-33 で完了**

1. ✅ P2 #41 python-jose → PyJWT 移行 — 完了
2. ✅ P2 #48 JIT プロビジョニング残課題 — 6/6 完了
3. ✅ P2 #51 運用基盤ギャップ #1-6, #8 — Prometheus / アラート / 自動バックアップ / TLS renewal IaC / Loki-Promtail IaC / 追加メトリクス / on-call labels 完了。#7 は #57 へ分割
4. ✅ P2 #57 unhealthy コンテナ自動復旧方式レビュー — 手動承認型 watchdog / drill 手順で完了

### Sprint 2 (リリース 60 日前: 〜 2026-09-16)

4. **P0 #24 CSP Report-Only でレポート収集開始** — 期間 7〜30 日
5. **P0 #23 本番 Vault 構築と secrets 投入 (人間作業)** — 工数 5 日
6. **本番データ PITR リストアドリル** — backup / WAL / Neon 承認後にステージング相当で 1 回実演

### Sprint 3 (リリース 30 日前: 〜 2026-10-17)

7. **P0 #24 CSP enforce 移行 (人間作業)** — canary 展開で 7 日かけて 100% 化
8. **TLS 方針の最終承認** — Cloudflare Tunnel 採用時は edge TLS + origin HTTP、直接公開 / origin TLS 採用時のみ Let's Encrypt を `docs/RELEASE_CHECKLIST.md` §2 に従い導入
9. **Issue #50 Cloudflare/Neon 本番リソース作成** — 人間が API token / Access application / Tunnel / DNS CNAME / cloudflared token / Neon プロジェクトを承認・作成後に CTO が検証

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
- [`docs/CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK.md`](./CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK.md) — `legalops.mirai-dx-platform.com` Cloudflare 適用手順
- [`docs/RELEASE_EVIDENCE_MATRIX.md`](./RELEASE_EVIDENCE_MATRIX.md) — `/goal` 完了条件と検証証拠の対応表
- [`docs/FINAL_RELEASE_STOP_REPORT.md`](./FINAL_RELEASE_STOP_REPORT.md) — 本番直前停止時の最終報告

---

> 本引き継ぎ書の初版は Loop 5 完了時 (2026-05-16) に作成されました。
> Loop 93 (2026-07-19) 時点で現行リリースゲートへ同期済みです。次セッションは `state.json`、`docs/PRODUCTION_APPROVAL_PACKET.md`、`docs/RELEASE_CHECKLIST.md`、`docs/RELEASE_EVIDENCE_MATRIX.md`、`docs/FINAL_RELEASE_STOP_REPORT.md`、`scripts/verify_backup_restore_docs.sh`、`scripts/verify_dependency_audit_evidence.sh`、`scripts/verify_review_evidence.sh`、`scripts/verify_goal_completion_evidence.sh`、`scripts/verify_github_release_gate.sh`、`scripts/verify_standalone_webui_runtime.sh`、`scripts/verify_predeploy_warning_classification.sh`、`scripts/verify_release_checklist_pending_items.sh`、`scripts/verify_production_stop_line.sh` を確認し、#23 / #24 / #50 / PITR の人間承認ゲートを越えない範囲で Verify / Release 準備を継続してください。
