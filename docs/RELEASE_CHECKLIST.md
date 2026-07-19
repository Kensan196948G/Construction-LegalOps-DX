# RELEASE CHECKLIST — Construction-LegalOps-DX

本ドキュメントは **2026-11-16 本番リリース** に向けた最終確認チェックリストです。

**最終更新: 2026-07-19 (v0.1.12 / Loop 93)** — `legalops.mirai-dx-platform.com` Cloudflare 適用手順、SharePoint Graph real mode、Notification real mode、公式根拠、pre-deploy gate、Standalone WebUI runtime preflight、release docs preflight、goal evidence preflight、review evidence preflight、dependency audit evidence preflight、backup/restore evidence preflight、GitHub release gate、latest main CI success、warning classification、checklist pending classification、production stop-line、final stop report を反映

> 📎 承認者向けの集約資料: [`docs/PRODUCTION_APPROVAL_PACKET.md`](./PRODUCTION_APPROVAL_PACKET.md)。
> Loop 93 時点の CI / pre-deploy / Cloudflare / SharePoint Graph real mode / Notification real mode / WebUI runtime / goal evidence / review evidence / dependency audit evidence / backup/restore evidence / GitHub release gate / warning classification / checklist pending classification / production stop-line / review 実施状況は同パケット §2 を正とする。
> `/goal` 完了条件ごとの証拠は [`docs/RELEASE_EVIDENCE_MATRIX.md`](./RELEASE_EVIDENCE_MATRIX.md) を正とする。

## 📊 Release Readiness ダッシュボード (2026-07-19)

| カテゴリ     | 状態            | 詳細                                                    |
| ------------ | --------------- | ------------------------------------------------------- |
| 🧪 テスト    | ✅              | pre-deploy gate: 900+ tests / ruff clean / mypy 0 errors |
| 🔐 RS256 JWT | ✅ コード完成   | `scripts/generate_rsa_keys.sh` 準備済み。Vault 投入待ち |
| 🏥 /readyz   | ✅ Deep check   | DB(critical) + Redis/Claude(degraded) 実装済み          |
| 📋 全 API    | ✅              | 12 エンドポイント全 DB バック化完了                     |
| 🐳 Docker    | ✅              | docker-compose.yml + prod overlay + monitoring profile  |
| ⚡ E2E       | ✅ 51 passed    | Playwright Docker 公式イメージで 7 ファイル（CI HARD gate）|
| 🔑 Vault     | ⏳              | 本番 secrets 投入が残課題 (#23)                         |
| 🛡️ CSP       | ⏳ Report-Only  | enforce 移行は 7日間データ収集後 (#24)                  |
| ☁️ CF/Neon   | ✅ IaC 完成     | `legalops.mirai-dx-platform.com` Runbook / DNS案 / Access / Tunnel / Neon config。本番リソース作成待ち|
| 📊 監視基盤  | ✅ IaC 完成     | Prometheus/Alertmanager/Grafana/Loki/Promtail + unhealthy watchdog |
| 🖥️ WebUI     | ✅ 検証用起動済 | `http://192.168.0.185:38100/` (`construction-legalops-standalone-webui.service`) |

---

- リリース対象バージョン: `v0.1.12` → 最終リリース `v1.0.0` 予定
- リリース期限: **2026-11-16** (登録日 2026-05-16 から 6 ヶ月後、絶対厳守)
- 本番環境: 社内オンプレ / プライベートクラウド + Cloudflare Tunnel / Access 境界 (候補 FQDN: `legalops.mirai-dx-platform.com`)
- リリース責任者: CTO 代行 (Claude Agent によるループ運用) + 法務リード + インフラリード

---

## 0. 事前確認 (リリース 14 日前まで)

- [ ] GitHub Projects の Production Release マイルストーン (期限 2026-11-16) の未解決 Issue がゼロ。
- [ ] `CHANGELOG.md` の `## [0.1.0] - 2026-05-16` セクションが最新コミットを反映している。
- [ ] `state.json` の `project.status` が `release_ready` / `code_complete_deployment_ready` / `production_ready_pending_human_actions` のいずれかである。
- [ ] CodeRabbit / Codex review の Critical/High 指摘がすべて解消済み。
- [ ] `docs/HANDOVER.md` の未解決事項リストが空、または許容済みリスクとして文書化済み。
- [ ] `docs/PRODUCTION_APPROVAL_PACKET.md` を Security / Infra / Legal / Release の各責任者が確認済み。
- [ ] 開発・検証用 Standalone WebUI が起動し、`/healthz` が `ok` を返す。

---

## 1. シークレット投入

本番環境 Secrets Manager (Azure Key Vault または HashiCorp Vault) に以下を投入し、`.env` で直接保持しないこと。

- [ ] `JWT_PRIVATE_KEY` / `JWT_PUBLIC_KEY` (RS256, 4096bit 推奨)
  - 生成手順: `openssl genrsa -out jwt_private.pem 4096 && openssl rsa -in jwt_private.pem -pubout -out jwt_public.pem`
  - `JWT_ALGORITHM=RS256` に切替、HS256 用 `JWT_SECRET` は破棄。
- [ ] `ENTRA_TENANT_ID` / `ENTRA_CLIENT_ID` / `ENTRA_CLIENT_SECRET` (Microsoft Entra ID、本番テナント)
- [ ] `CLAUDE_API_KEY` (本番用、利用枠と料金アラート設定済み)
- [ ] `SHAREPOINT_SITE_URL` / `SHAREPOINT_DRIVE_ID` / `SHAREPOINT_LIBRARY_NAME`
- [ ] `DESKNET_API_TOKEN` / `DESKNET_API_URL`
- [ ] `HENNGE_TENANT_ID` / `HENNGE_API_KEY` (社内 IDaaS 連携)
- [ ] `POSTGRES_PASSWORD` (本番用、最低 24 文字、Vault 管理)
- [ ] `REDIS_PASSWORD`
- [ ] `HASH_CHAIN_SECRET` (監査ログ hash chain 用。本番では `JWT_SECRET` からの既定導出に依存しない)
- [ ] シークレットローテーション計画 (90 日毎) と責任者を文書化。

---

## 2. TLS 証明書

- [ ] Cloudflare Tunnel 採用時: Cloudflare edge TLS + Tunnel 経由 origin HTTP の運用承認完了。
- [ ] 非 Tunnel / 直接公開時のみ: Let's Encrypt (certbot) または社内 CA 発行証明書の取得完了。
- [ ] 非 Tunnel / 直接公開時のみ: nginx に証明書を配置 (`/etc/letsencrypt/live/<domain>/fullchain.pem` / `privkey.pem`)。
- [ ] 非 Tunnel / 直接公開時のみ: `infra/nginx/nginx.conf` の `ssl_certificate` / `ssl_certificate_key` パスを本番値に切替。
- [ ] HSTS (`max-age=31536000; includeSubDomains; preload`) を有効化。
- [ ] TLS 1.2 / 1.3 のみ許可、1.0 / 1.1 / SSLv3 を無効化。
- [ ] 非 Tunnel / 直接公開時のみ: `--profile tls-renewal` の `certbot-renew` を本番値 (`CERTBOT_DOMAINS` / `CERTBOT_EMAIL`) で起動し、初回発行と更新ドリルを確認。
- [ ] SSL Labs A+ 判定を確認。

---

## 3. PostgreSQL 16 本番チューニング

- [ ] `postgresql.conf` を本番ワークロードに合わせて設定:
  - `shared_buffers = 25% of RAM`
  - `effective_cache_size = 75% of RAM`
  - `work_mem = 16MB` (同時接続数に応じ調整)
  - `maintenance_work_mem = 512MB`
  - `wal_level = replica`
  - `max_wal_size = 4GB`
  - `checkpoint_completion_target = 0.9`
  - `random_page_cost = 1.1` (SSD 前提)
- [ ] `pg_hba.conf` で本番接続元 IP のみ許可、`md5` ではなく `scram-sha-256` を使用。
- [ ] 自動バックアップ (pg_dump + WAL アーカイブ) を日次で取得、保管先は別リージョン。
- [ ] Alembic rollback drill (`scripts/verify_migrations_roundtrip.sh`) が CI / 一時 PostgreSQL で成功。
- [ ] PITR (Point-in-Time Recovery) の本番データ復元ドリルを、本番 backup / WAL / Neon 承認後に 1 回実施。
- [ ] `audit_logs` テーブルのパーティショニング (月次) を検討。

---

## 4. データベースマイグレーション

- [ ] 本番 DB へ接続できる踏み台 / Bastion 設定確認。
- [ ] バックアップ取得後にマイグレーション実行:
  ```bash
  docker compose -f infra/docker/docker-compose.yml exec backend alembic upgrade head
  ```
- [ ] マイグレーション後の `alembic current` で最新リビジョン確認。
- [ ] ロールバック手順 (`alembic downgrade -1`) の前提となる roundtrip drill を `scripts/verify_migrations_roundtrip.sh` で検証。

---

## 5. 監査ログトリガー確認

- [ ] `audit_logs` テーブルへの INSERT/UPDATE/DELETE トリガーが有効:
  ```sql
  SELECT tgname, tgrelid::regclass FROM pg_trigger WHERE tgname LIKE 'audit_%';
  ```
- [ ] AI 呼び出し (`POST /api/v1/ai/contract-review`) で `audit_logs` に prompt / model / response_meta が記録されることをスモークテストで確認。
- [ ] 法定保存期間 (建設業法 5 年 / 電子帳簿保存法 7 年) に応じた保管設定が文書化済み。
- [ ] 監査ログの改ざん防止 (PostgreSQL `REVOKE UPDATE, DELETE ON audit_logs FROM app_user`) を確認。

---

## 6. CSP Report-Only から enforce への移行

現状は `Content-Security-Policy-Report-Only` ヘッダで運用中。本番移行手順:

1. [ ] リリース 7 日前まで Report-Only でレポート収集 (`/csp-report` エンドポイント)。
2. [ ] レポートで検出された全違反を解消、または例外をホワイトリスト化。
3. [ ] `infra/nginx/nginx.conf` のヘッダ名を `Content-Security-Policy-Report-Only` → `Content-Security-Policy` に切替。
4. [ ] 段階的ロールアウト (canary 10% → 50% → 100%) でフロントエンド回帰テスト実施。
5. [ ] 違反発生時のロールバック手順 (ヘッダ名を Report-Only に戻す) を準備。

---

## 7. スモークテストシナリオ (本番投入直後に実施)

すべてのシナリオが PASS することを確認。失敗時は §10 ロールバック手順へ。

1. [ ] **Login**: Entra ID SSO 経由でログインし、JWT が払い出される (`POST /api/v1/auth/login`)。
2. [ ] **Upload**: 契約書 PDF をアップロード (`POST /api/v1/contracts`)、SharePoint への保管とメタデータ DB 登録を確認。
3. [ ] **Review**: AI 契約書レビュー要求 (`POST /api/v1/ai/contract-review`)、Claude API から下書きが返却され、UI に「AI 下書き / 人間確認必須」ディスクレーマーが表示される。
4. [ ] **Workflow**: desknet's NEO ワークフロー申請 (`POST /api/v1/workflows`)、承認ステップ遷移を確認。
5. [ ] **Audit**: 監査ログ閲覧 (`GET /api/v1/audit-logs`) で上記すべての操作が記録されている。
6. [ ] **Healthz / Readyz**: `curl https://legalops.mirai-dx-platform.com/healthz` および `/readyz` が 200 を返す。
7. [ ] **負荷確認**: k6 / Locust で 50 req/s を 5 分間流し、p95 < 500ms を確認。

---

## 7.1 Cloudflare `legalops` サブドメイン適用前確認

- [ ] `docs/CLOUDFLARE_LEGALOPS_SUBDOMAIN_RUNBOOK.md` をレビュー済み。
- [ ] `mirai-dx-platform.com` の NS が Cloudflare (`nia.ns.cloudflare.com`, `kareem.ns.cloudflare.com`) であることを確認。
- [ ] `legalops.mirai-dx-platform.com` に既存 DNS レコードがない、または置換対象として承認済み。
- [ ] Cloudflare Access self-hosted application `LegalOps-DX` を作成済み。
- [ ] Access policy は `LegalOps-Users` / `LegalOps-Admins` + MFA に限定済み。
- [ ] Tunnel ID を取得し、CNAME `legalops -> <TUNNEL_ID>.cfargotunnel.com` の作成承認済み。
- [ ] `CLOUDFLARE_TUNNEL_TOKEN` を Vault / secret manager から注入し、`infra/docker/docker-compose.cloudflare-tunnel.yml` overlay で cloudflared を起動する手順を承認済み。
- [ ] `./scripts/verify_cloudflare_legalops.sh` が成功し、`legalops` CNAME の未作成/承認済み状態、Tunnel ingress、Access policy、compose overlay を read-only で確認済み。
- [ ] `scripts/pre_deploy_check.sh` の Cloudflare Tunnel compose overlay config が成功。
- [ ] `cloudflared tunnel ingress validate infra/cloudflare/tunnel-config.example.yml` が成功。
- [ ] DNS 作成後のロールバック手順（CNAME 削除 / Tunnel 停止 / Access 無効化）を担当者が確認済み。

## 7.2 開発・検証用 Standalone WebUI 確認

本番 deploy ではなく、リリース承認前の人間確認用プレビューとして以下を確認する。

- [ ] systemd user service `construction-legalops-standalone-webui.service` が `active`。
- [ ] URL: `http://192.168.0.185:38100/`
- [ ] Health: `curl -fsS http://192.168.0.185:38100/healthz` が `ok`。
- [ ] HEAD: `curl -fsSI http://192.168.0.185:38100/` が 200 と HTML metadata を返す。
- [ ] 待受: `192.168.0.185:38100`。ポート競合時は `scripts/install_standalone_webui_systemd.sh` が `38100-38999` から空き番号を選ぶ。
- [ ] 起動: `ssh kensan@192.168.0.185 "cd /home/kensan/Projects/Mirai-DX-Project/Construction-LegalOps-DX && bash scripts/install_standalone_webui_systemd.sh --user install"`
- [ ] 停止: `ssh kensan@192.168.0.185 "systemctl --user stop construction-legalops-standalone-webui.service"`
- [ ] 配信元: `docs/Construction-LegalOps-DX (Standalone).html` が変換なしで適用されている。

---

## 8. セキュリティ最終確認

- [ ] Trivy スキャン: 本番イメージに Critical/High 脆弱性がゼロ。
- [ ] Bandit / npm audit: Critical/High 解消済み。
- [ ] `scripts/scan_secrets.sh` が成功し、実 secret / 個人 token / 接続文字列がリポジトリに露出していない。
- [ ] OWASP ZAP / nuclei によるブラックボックスエンドポイントスキャン実施。
- [ ] 本番 `.env` がリポジトリにコミットされていないことを `git log -p` で確認。
- [ ] secrets を環境変数経由でのみ参照、ログに secrets が出力されないことを確認。

---

## 9. 法務・コンプライアンス最終確認

- [ ] 法務担当者・顧問弁護士による UI ディスクレーマー文言レビュー完了。
- [ ] `docs/ai_disclaimer_policy.md` に基づき、AI 出力に **「AI は法的判断を確定しない。最終判断は法務担当者・顧問弁護士に帰属する」** 旨が常時表示されることを確認。
- [ ] 弁護士法第 72 条遵守 (非弁行為防止) の運用ルールが社内周知済み。
- [ ] 個人情報保護法に基づくプライバシーポリシー / 利用規約が公開済み。
- [ ] 監査ログ保管期間が法定要件 (建設業法 5 年 / 電子帳簿保存法 7 年) を満たす。

---

## 10. ロールバック手順

本番リリース失敗時は **30 分以内に判断・実施** すること。

1. [ ] 障害検知 → リリース責任者・インフラリードに即時通知 (Teams / メール / 電話)。
2. [ ] nginx の upstream を旧バージョンに切替、または `docker compose` で旧イメージタグへ pin:
   ```bash
   docker compose -f infra/docker/docker-compose.yml pull backend:v0.0.x
   docker compose -f infra/docker/docker-compose.yml up -d backend
   ```
3. [ ] DB マイグレーションが原因の場合は alembic でダウングレード:
   ```bash
   docker compose -f infra/docker/docker-compose.yml exec backend alembic downgrade -1
   ```
4. [ ] バックアップから PITR で復元が必要な場合は §3 の手順で実施。
5. [ ] CSP 違反でフロント破壊の場合は §6 のロールバック (ヘッダ名を Report-Only に戻す)。
6. [ ] Cloudflare 起因の場合は `legalops` CNAME を削除または無効化し、Tunnel connector を停止。
7. [ ] 事後対応: 障害レポートを `docs/incidents/<YYYY-MM-DD>.md` に記録、再発防止策を Issue 起票。

---

## 11. リリース完了後 (Day 1〜7)

- [ ] 24 時間以内: error rate / latency / DB 接続数を 30 分毎にモニタリング。
- [ ] 72 時間以内: 監査ログから AI 出力に対する人間レビュー実施率を確認 (目標 100%)。
- [ ] 7 日以内: ユーザフィードバック収集、`docs/HANDOVER.md` を更新。
- [ ] GitHub Release ノートを公開、`v0.1.0` タグを付与。

---

> 本チェックリストは Loop 93 (2026-07-19) 時点の実装・検証状態に同期済みです。
> 本番リリース日 (2026-11-16) までに各項目の責任者・期限を再確認し、本番 deploy / DNS / secrets は人間承認後に実行すること。
