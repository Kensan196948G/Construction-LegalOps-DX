# 📊 Release Evidence Matrix — Construction-LegalOps-DX

> **最終更新: 2026-07-19 / Loop 93**
> 本書は `/goal` の完了条件を、現在の証拠・検証コマンド・未解決ゲートへ対応付ける CTO 監査表です。  
> 本番 deploy / 公開 DNS 変更 / secret 投入 / PR merge / release tag は、本書の対象外ではなく **人間承認後の実行項目** として扱います。
> 最終報告は [`docs/FINAL_RELEASE_STOP_REPORT.md`](./FINAL_RELEASE_STOP_REPORT.md) を正とする。

---

## ✅ 1. 現在の総合判定

| 項目 | 判定 | 根拠 |
|---|---|---|
| コード完成度 | ✅ Release candidate | Backend / Frontend / DB-backed API / auth / audit / monitoring / docs は実装・検証済み |
| 本番直前状態 | ✅ 承認待ち | #23 / #24 / #50 の人間ゲートのみ open |
| 本番 deploy | 🚫 未実行 | 安全制約により CTO/Supervisor は deploy ready 判定まで |
| 公開 DNS | 🚫 未変更 | `legalops.mirai-dx-platform.com` CNAME / A は未作成。`legalops` 新規サブドメイン要件は Runbook / IaC に反映済み |
| Secrets | 🚫 未投入 | Vault / Key Vault 本番 secret 投入は #23 人間作業 |
| リリースタグ | 🚫 未作成 | 明示承認なしの tag 作成は禁止 |

---

## 🧾 2. `/goal` 完了条件と現在証拠

| `/goal` 要求 | 現在証拠 | 判定 |
|---|---|---|
| 必須機能が実装済み | `README.md` の Phase 1 指標、`docs/HANDOVER.md` §1、DB-backed API 群、SharePoint Graph real mode、Notification real mode、frontend E2E 51 passed | ✅ |
| Lint / 型チェック / テスト / ビルドが成功 | `SKIP_DOCKER_BUILD=1 ./scripts/pre_deploy_check.sh` → Passed 24 / Failed 0 / Warnings 5。goal evidence / review evidence / dependency audit evidence / backup-restore evidence gate を含む | ✅ Mandatory checks 通過 |
| 重大または高危険度の脆弱性なし | Bandit / npm audit high/critical 0 / dependency audit evidence / secret scan が pre-deploy gate で成功。npm moderate 4 は既知残リスク。`scripts/scan_secrets.sh` は high-confidence secret なし | ✅ |
| DB migration と rollback 手順を検証 | `scripts/verify_migrations_roundtrip.sh` が pre-deploy gate 内で成功。`scripts/verify_backup_restore_docs.sh` → Passed 36 / Failed 0。PITR は本番 backup / WAL / Neon 承認後 | ✅ / ⏳ |
| リリース前チェックリストが完成 | `docs/RELEASE_CHECKLIST.md` は Loop 93 まで同期。未チェック73件は `scripts/verify_release_checklist_pending_items.sh` で人間承認 / 本番実行 / リリース後確認項目として分類済み | ✅ / ⏳ |
| WebUI を提示できる | `http://192.168.0.185:38100/`、`/healthz` → `ok`、systemd user service enabled/active、`192.168.0.185:38100` listen、`scripts/verify_standalone_webui_runtime.sh` → Passed 27 / Failed 0 | ✅ |
| GitHub Projects / Issue / CI / 進捗が最新 | GitHub Project #30 readme を Loop 93 に同期済み。`scripts/verify_github_release_gate.sh` → Passed 24 / Failed 0。`scripts/verify_production_stop_line.sh` → Passed 13 / Failed 0。open issues は #23 / #24 / #50 の P0 人間ゲートのみ、open PR 0、#50 は blocked label、最新 main CI は completed/success | ✅ |
| 本番 deploy だけを残した承認待ち | deploy そのものに加え、secret / CSP enforce / Cloudflare DNS-Tunnel-Access / Neon は人間承認ゲート。`scripts/verify_production_stop_line.sh` → Passed 13 / Failed 0 | ✅ / ⏳ |

---

## 🔍 3. 直近検証コマンド

| 検証 | コマンド | 結果 |
|---|---|---|
| Pre-deploy gate | `SKIP_DOCKER_BUILD=1 ./scripts/pre_deploy_check.sh` | ✅ Passed 24 / Failed 0 / Warnings 5 |
| Secret scan | `./scripts/scan_secrets.sh` | ✅ high-confidence secret なし |
| Cloudflare legalops preflight | `./scripts/verify_cloudflare_legalops.sh` | ✅ Passed 22 / Failed 0 / Warnings 0 |
| JSON / diff | `python3 -m json.tool state.json` + `git diff --check` | ✅ |
| Release docs | `./scripts/verify_release_docs.sh` | ✅ Passed 191 / Failed 0 |
| SharePoint Graph real mode | `cd backend && python -m pytest tests/unit/test_sharepoint_service.py -q && python -m ruff check app/services/sharepoint_service.py tests/unit/test_sharepoint_service.py && python -m mypy app/services/sharepoint_service.py` | ✅ 33 passed / ruff clean / mypy success |
| Notification real mode | `cd backend && python -m pytest tests/unit/test_notification_service.py -q && python -m ruff check app/services/notification_service.py tests/unit/test_notification_service.py && python -m mypy app/services/notification_service.py` | ✅ 32 passed / ruff clean / mypy success |
| Contract submit | `cd backend && python -m pytest tests/unit/test_contract_service.py tests/integration/test_contracts_crud.py -q && python -m ruff check app/services/contract_service.py app/api/v1/contracts.py tests/unit/test_contract_service.py tests/integration/test_contracts_crud.py && python -m mypy app/services/contract_service.py app/api/v1/contracts.py` | ✅ 38 passed / ruff clean / mypy success |
| Contract subresources | `cd backend && python -m pytest tests/unit/test_contract_service.py tests/integration/test_contracts_crud.py -q && python -m ruff check app/services/contract_service.py app/api/v1/contracts.py tests/unit/test_contract_service.py tests/integration/test_contracts_crud.py && python -m mypy app/services/contract_service.py app/api/v1/contracts.py` | ✅ 43 passed / versions current snapshot / clauses DB rows / ruff clean / mypy success |
| Monitoring config | `bash scripts/verify_monitoring_config.sh` | ✅ Passed 19 / Failed 0。Prometheus backend DNS discovery、YAML/JSON parse、Grafana dashboard、monitoring docs整合 |
| Backup / restore evidence | `bash scripts/verify_backup_restore_docs.sh` | ✅ Passed 36 / Failed 0。pg_dump / pg_restore 手順、backup_db.sh checksum、Alembic rollback、PITR未実演停止線を検証 |
| Goal completion evidence | `./scripts/verify_goal_completion_evidence.sh` | ✅ Passed 40 / Failed 0。`/goal` 完了条件を証拠表・最終報告・停止線へ対応付け |
| Review evidence | `./scripts/verify_review_evidence.sh` | ✅ Passed 29 / Failed 0。CodeRabbit timeout、代替静的検証、security review、Critical/High limitationを検証 |
| Dependency audit evidence | `./scripts/verify_dependency_audit_evidence.sh` | ✅ Passed 23 / Failed 0。npm audit high/critical 0、moderate 4 は既知残リスク。pip-audit は隔離venv方式で72 deps / 0 vulnerabilities |
| WebUI runtime | `./scripts/verify_standalone_webui_runtime.sh` | ✅ Passed 27 / Failed 0。status JSON、systemd enabled/active、auto port range、listen実体、health ok、HEAD 200、Content-Length一致、source endpoint一致 |
| Warning classification | `./scripts/verify_predeploy_warning_classification.sh` | ✅ Passed 13 / Failed 0。既知warning 5件のみ、未知warning 0 |
| Checklist pending classification | `./scripts/verify_release_checklist_pending_items.sh` | ✅ Passed 5 / Failed 0。未チェック73件は承認後/本番時/リリース後項目として分類済み |
| Production stop-line | `./scripts/verify_production_stop_line.sh` | ✅ Passed 13 / Failed 0。Git tag 0、GitHub Release 0、GitHub Deployments 0、legalops DNS未作成 |
| WebUI health | `curl -fsS http://192.168.0.185:38100/healthz` | ✅ `ok` |
| WebUI HEAD | `curl -fsSI http://192.168.0.185:38100/` | ✅ `200 OK` / `text/html; charset=utf-8` / `Content-Length: 8836022` |
| WebUI systemd | `systemctl --user is-enabled/is-active construction-legalops-standalone-webui.service` | ✅ `enabled` / `active` |
| WebUI status/listen | `reports/webui/standalone-webui.json` + `ss -ltnp` | ✅ `host=192.168.0.185` / `port=38100` / `192.168.0.185:38100` listen |
| WebUI source endpoint | `curl -fsS http://192.168.0.185:38100/standalone-source` | ✅ `docs/Construction-LegalOps-DX (Standalone).html` |
| DNS read-only | `dig +short CNAME legalops.mirai-dx-platform.com` / `dig +short A ...` | ✅ 未作成 |
| GitHub release gate | `./scripts/verify_github_release_gate.sh` | ✅ Passed 24 / Failed 0。open PR 0、open issues #23/#24/#50、latest main CI success、Project #30 #23/#24/#50 Todo、#50 blocked label |
| GitHub state | `gh issue list`, `gh pr list`, `gh run list` | ✅ open issues #23/#24/#50、open PR 0、latest CI success |
| GitHub Project #30 | `gh project list`, `gh project item-list 30`, `gh project edit 30 --readme ...` | ✅ Project readme 同期済み、#23/#24/#50 は Todo、人間ゲートとして可視化 |

---

## 🧪 4. Review 証跡

| Review | 実施状況 | 判定 |
|---|---|---|
| CodeRabbit CLI | `coderabbit --version` → `0.6.5`、auth OK | ✅ 利用可能 |
| CodeRabbit review | `coderabbit review --agent -t uncommitted` は解析開始後 240s で findings 前 timeout | ⚠️ findings なし |
| 代替レビュー | ruff / mypy / pytest / migration roundtrip / Bandit / npm audit / secret scan / Cloudflare preflight / manual release-security review | ✅ |

> CodeRabbit の findings が得られていないため、Critical / High が「0 件」とは断言しない。現時点の release gate では、ローカル静的検証と CI / pre-deploy gate を代替証跡とする。

---

## 🚧 5. 未解決ゲート

| Issue | 種別 | なぜ CTO が実行しないか | 承認後の実行 |
|---|---|---|---|
| #23 | Vault secrets | secret 投入は人間承認・秘匿値管理対象 | `scripts/setup_vault_secrets.sh` + Vault / Key Vault 登録 |
| #24 | CSP enforce | 7 日分 Report-Only データと canary 承認が必要 | nginx CSP enforce 設定へ切替 |
| #50 | Cloudflare / Neon | DNS / Tunnel / Access / Neon / 課金・データ所在は人間判断 | Access / Tunnel / `legalops` CNAME / cloudflared token / Neon 作成 |
| PITR drill | DB 運用 | 本番 backup / WAL / Neon 承認後の検証 | ステージング相当で復元ドリル |

---

## 🖥️ 6. WebUI 確認方法

| 項目 | 値 |
|---|---|
| URL | `http://192.168.0.185:38100/` |
| Health | `http://192.168.0.185:38100/healthz` |
| systemd unit | `construction-legalops-standalone-webui.service` |
| 起動 | `ssh kensan@192.168.0.185 "cd /home/kensan/Projects/Mirai-DX-Project/Construction-LegalOps-DX && bash scripts/install_standalone_webui_systemd.sh --user install"` |
| 停止 | `ssh kensan@192.168.0.185 "systemctl --user stop construction-legalops-standalone-webui.service"` |
| Source endpoint | `http://192.168.0.185:38100/standalone-source` |
| 配信元 | `docs/Construction-LegalOps-DX (Standalone).html` |

---

## 🛑 7. Stop Line

以下は **人間承認なしに実行しない**。

- 本番 release / deploy
- `legalops.mirai-dx-platform.com` DNS CNAME 作成
- Cloudflare Tunnel / Access application 作成
- Cloudflare / Neon secret / token / connection string 投入
- CSP enforce 切替
- Git push / PR merge / release tag
- 本番データ削除 / 破壊的 migration / 課金変更
