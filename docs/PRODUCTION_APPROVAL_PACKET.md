# 🚀 Production Approval Packet — Construction-LegalOps-DX

> 本番リリース / 本番デプロイを実行する**直前**に、人間が承認すべき項目を 1 枚に集約した判断資料。
> この文書は承認ゲートであり、DNS 変更・secret 投入・本番 deploy は自動実行しない。
> `/goal` 完了条件ごとの証拠は [`docs/RELEASE_EVIDENCE_MATRIX.md`](./RELEASE_EVIDENCE_MATRIX.md) を正とする。
> 本番直前停止時の最終報告は [`docs/FINAL_RELEASE_STOP_REPORT.md`](./FINAL_RELEASE_STOP_REPORT.md) を正とする。

## 📌 1. 現在の CTO 判定

| 項目             | 判定                 | 根拠                                                                                                                |
| ---------------- | -------------------- | ------------------------------------------------------------------------------------------------------------------- |
| コード完成度     | ✅ Release candidate | Backend / Frontend / DB-backed API / auth / audit / monitoring / docs は検証済み                                    |
| 本番 deploy      | ⏳ 承認待ち          | #23 / #24 / #50 が人間ゲート                                                                                        |
| DNS 変更         | ⏳ 承認待ち          | `legalops.mirai-dx-platform.com` CNAME は未作成                                                                     |
| Secrets          | ⏳ 承認待ち          | Vault / Key Vault への本番 secret 投入は未実施                                                                      |
| 破壊的 migration | 🚫 予定なし          | Alembic rollback は手順化済み。実行は承認後                                                                         |
| CD workflow      | 🔒 承認待ち          | `.github/workflows/deploy.yml` は手動起動 + production environment + `APPROVE_PRODUCTION_CHANGE` 入力で fail-closed |

## 📊 2. 現在の検証スナップショット (2026-07-20 / Loop 107)

| 項目                             | 現在値                                                                                                                                                                                                                                                                                                                               | 判定                              |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------- |
| GitHub open Issues               | #23 / #24 / #50 の P0 人間ゲートのみ                                                                                                                                                                                                                                                                                                 | ✅ コード系 blocker 0             |
| Open PR                          | 0                                                                                                                                                                                                                                                                                                                                    | ✅ PR #58 merged / 未検証 PR なし |
| GitHub Project #30               | `Construction-LegalOps-DX 開発管理` readme は Loop 106 に同期済み。Loop 107 の upload URL guard はローカル文書/検証へ反映済みで、Project同期は最終検証後に実施。#23/#24/#50 は Todo / human gate                                                                                                                                     | ✅ / ⏳                           |
| 直近 CI                          | `CI` success (2026-07-18)                                                                                                                                                                                                                                                                                                            | ✅ Green                          |
| GitHub release gate              | `./scripts/verify_github_release_gate.sh` → Passed 29 / Failed 0。PR #58 merged / open PR 0 / latest main CI completed/success も検証                                                                                                                                                                                                | ✅                                |
| WebUI runtime                    | `./scripts/verify_standalone_webui_runtime.sh` → Passed 27 / Failed 0。systemd enabled/active / status JSON / 自動port範囲 / listen実体 / health ok / HTML実体一致                                                                                                                                                                   | ✅                                |
| Pre-deploy gate                  | `SKIP_DOCKER_BUILD=1 ./scripts/pre_deploy_check.sh` → Passed 25 / Failed 0 / Warnings 5                                                                                                                                                                                                                                              | ✅ Mandatory checks 通過          |
| Goal completion evidence         | `./scripts/verify_goal_completion_evidence.sh` → Passed 39 / Failed 0。`/goal` 完了条件と証拠表の対応をread-only検証                                                                                                                                                                                                                 | ✅                                |
| Review evidence                  | `./scripts/verify_review_evidence.sh` → Passed 29 / Failed 0。CodeRabbit timeout と代替レビュー境界をread-only検証                                                                                                                                                                                                                   | ✅                                |
| Dependency audit evidence        | `./scripts/verify_dependency_audit_evidence.sh` → Passed 23 / Failed 0。npm audit high/critical 0、moderate 4 は既知残リスク。pip-audit 72 deps / 0 vulnerabilities                                                                                                                                                                  | ✅                                |
| SharePoint Graph real mode       | `backend/tests/unit/test_sharepoint_service.py` → 33 passed。client-credentials / drive upload / webUrl 解決 / fail-closed を検証                                                                                                                                                                                                    | ✅                                |
| Notification real mode           | `backend/tests/unit/test_notification_service.py` → 32 passed。Exchange Graph sendMail / Teams webhook / desknet's webhook / fail-closed を検証                                                                                                                                                                                      | ✅                                |
| Template creation UI             | `CreateTemplateButton` の未実装 alert を撤去し、dialog form + `useCreateTemplate` + `router.refresh()` で `/templates` 作成APIへ接続。typecheck / targeted ESLint / release docs verifier 通過                                                                                                                                       | ✅                                |
| Contract submit                  | `backend/tests/unit/test_contract_service.py` + `backend/tests/integration/test_contracts_crud.py` → 38 passed。draft → in_review 遷移 / 二重提出 409 / legacy 501 stub 回帰防止を検証                                                                                                                                               | ✅                                |
| Contract subresources            | `backend/tests/unit/test_contract_service.py` + `backend/tests/integration/test_contracts_crud.py` → 43 passed。`/versions` current snapshot / `/clauses` DB-backed seq order / legacy 501 stub 回帰防止を検証                                                                                                                       | ✅                                |
| Compliance run                   | `POST /compliance/checks/{contract_id}/run` は ComplianceChecker を即時実行し `status=done` を返す。backend 72 passed / frontend typecheck + targeted lint clean                                                                                                                                                                     | ✅                                |
| User sync queued audit           | `POST /users/sync` は外部 Graph 呼び出しなしで `queued` を返し、`user.sync` 監査 payload に `external_write=false` を記録。backend 25 passed / frontend typecheck + targeted lint clean                                                                                                                                              | ✅                                |
| File parser OCR guard            | 画像PDFは実OCRバックエンド承認・設定まで placeholder OCR を返さず fail-closed。`backend/tests/unit/test_file_parser.py` → 22 passed / ruff clean / mypy success                                                                                                                                                                      | ✅                                |
| Upload URL guard                 | `POST /uploads/init` は承認済みdirect-upload URL未設定時に `upload_url=null`。downloadはSharePoint URL 解決失敗時に `sharepoint-stub://` へフォールバックせず `502 sharepoint url unavailable`。成功時監査 payload は `external_url_resolved=true` / `external_write=false`。upload integration 2 passed / ruff clean / mypy success | ✅                                |
| Monitoring config                | `bash scripts/verify_monitoring_config.sh` → Passed 19 / Failed 0。Prometheus backend DNS discovery / YAML / Grafana / docs 整合を検証                                                                                                                                                                                               | ✅                                |
| Backup / restore evidence        | `bash scripts/verify_backup_restore_docs.sh` → Passed 36 / Failed 0。pg_dump / pg_restore 手順、backup_db.sh checksum、Alembic rollback、PITR未実演停止線をread-only検証                                                                                                                                                             | ✅ / ⏳                           |
| Warning classification           | `./scripts/verify_predeploy_warning_classification.sh` → Passed 13 / Failed 0。既知warning 5件のみ、未知warning 0                                                                                                                                                                                                                    | ✅                                |
| Checklist pending classification | `./scripts/verify_release_checklist_pending_items.sh` → Passed 5 / Failed 0。未チェック73件は承認後/本番時/リリース後項目として分類済み                                                                                                                                                                                              | ✅                                |
| Production stop-line             | `./scripts/verify_production_stop_line.sh` → Passed 13 / Failed 0。Git tag 0 / GitHub Release 0 / GitHub Deployments 0 / DNS未作成                                                                                                                                                                                                   | ✅                                |
| Secret scan                      | `./scripts/scan_secrets.sh` → high-confidence secret なし                                                                                                                                                                                                                                                                            | ✅                                |
| Cloudflare legalops preflight    | `./scripts/verify_cloudflare_legalops.sh` → Passed 37 / Failed 0 / Warnings 0。`legalops.mirai-dx-platform.com` は新規サブドメインとして未作成、承認フレーズ必須 helper `scripts/apply_cloudflare_legalops_after_approval.sh` も検証                                                                                                 | ✅                                |
| DNS                              | `legalops.mirai-dx-platform.com` CNAME / A 未作成                                                                                                                                                                                                                                                                                    | ✅ 承認前状態を維持               |
| WebUI                            | `http://192.168.0.185:38100/healthz` → `ok` / systemd enabled + active / `192.168.0.185:38100` listen                                                                                                                                                                                                                                | ✅                                |
| CodeRabbit review                | CLI 0.6.5 / auth OK。`coderabbit review --agent -t uncommitted` は解析開始後 240s で findings 前タイムアウト                                                                                                                                                                                                                         | ⚠️ ローカル静的検証で代替         |
| Local workspace                  | Loop 94〜107 差分は PR #59 で正本化。本番公開 (DNS / Access / secrets / CSP enforce) は人間ゲート                                                                                                                                                                                                                                    | ✅ 正本化済み                     |
| Local workspace state            | `bash scripts/verify_local_workspace_state.sh` → Passed 8 / Failed 0。時点非依存 fail-closed 検査 (secret 混入 / 実行ビット / git 整合 / verifier 実在) + 現況開示                                                                                                                                                                                  | ✅                                |

Warnings は本番 secret 未投入、SSO / AI key 未投入、Docker build skip に起因する既知5件のみ。いずれも #23 / #50 の人間承認後に解消する前提であり、secret 値はリポジトリ・Issue・ログへ出力しない。未知warningは `scripts/verify_predeploy_warning_classification.sh` で検出時に失敗させる。

### 🖥️ WebUI 承認前確認

| 項目            | 値                                                                                                                                    |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| URL             | `http://192.168.0.185:38100/`                                                                                                         |
| Health          | `curl -fsS http://192.168.0.185:38100/healthz` → `ok`                                                                                 |
| HEAD            | `curl -fsSI http://192.168.0.185:38100/` → `200 OK` / `text/html; charset=utf-8`                                                      |
| systemd         | `systemctl --user is-enabled construction-legalops-standalone-webui.service` → `enabled`; `systemctl --user is-active ...` → `active` |
| Status file     | `reports/webui/standalone-webui.json` → `host=192.168.0.185` / `port=38100` / stop command 記録済み                                   |
| Listen          | `ss -ltnp` → `192.168.0.185:38100`                                                                                                    |
| Source endpoint | `http://192.168.0.185:38100/standalone-source`                                                                                        |
| 停止            | `ssh kensan@192.168.0.185 "systemctl --user stop construction-legalops-standalone-webui.service"`                                     |

## 📌 3. 人間承認が必要な P0

| Issue                 | 承認者                         | 承認内容                                                             | 承認後に実施すること                                     |
| --------------------- | ------------------------------ | -------------------------------------------------------------------- | -------------------------------------------------------- |
| #23 Vault secrets     | Security Lead / Infra Lead     | 本番 Vault / Key Vault、Entra ID、Claude API、DB/Redis secret の投入 | `scripts/setup_vault_secrets.sh` と Vault 側 secret 登録 |
| #24 CSP enforce       | App Lead / Security Lead       | 7 日分 Report-Only データの違反解消、enforce 切替                    | nginx CSP enforce 設定へ切替、canary → 100%              |
| #50 Cloudflare / Neon | Infra Lead / Legal Lead / 経営 | Cloudflare Access/Tunnel/DNS、Neon 採否、データ所在・課金            | Access/Tunnel/DNS/Neon 作成、smoke / rollback drill      |

## 📌 4. 承認前 Preflight

```bash
# ソース・型・テスト・セキュリティ・compose / monitoring 設定を確認
./scripts/pre_deploy_check.sh

# Cloudflare Tunnel 設定案の構文確認
cloudflared tunnel --config infra/cloudflare/tunnel-config.example.yml ingress validate

# legalops サブドメインの read-only preflight
./scripts/verify_cloudflare_legalops.sh

# DNS がまだ未公開であることの確認
dig +short CNAME legalops.mirai-dx-platform.com
```

期待値:

- `pre_deploy_check.sh` が mandatory checks を通過する
- GitHub Actions CD を使う場合は `production_change_approval=APPROVE_PRODUCTION_CHANGE` を入力し、GitHub Environment `production` で承認する
- `cloudflared ... ingress validate` が `OK`
- `verify_cloudflare_legalops.sh` が mandatory checks を通過する
- `legalops.mirai-dx-platform.com` の CNAME が未作成、または承認済み変更対象として記録済み

## 📌 5. 承認後の実行順序

1. 🔐 #23: Vault / Key Vault へ本番 secrets を投入
2. 🛡️ #24: CSP Report-Only の違反が 0 または承認済み例外のみであることを確認
3. ☁️ #50: Cloudflare Access self-hosted application を作成
4. 🔌 #50: Cloudflare Tunnel を作成し、origin nginx へ接続
5. 🔑 #50: `CLOUDFLARE_TUNNEL_TOKEN` を Vault / secret manager から注入
6. 🔌 #50: `infra/docker/docker-compose.cloudflare-tunnel.yml` overlay で cloudflared を起動
7. 🌐 #50: `legalops` CNAME を `<TUNNEL_ID>.cfargotunnel.com` へ作成
8. 🗄️ #50: Neon 採用時のみ DB 移行 / 接続検証を実施
9. ✅ `docs/RELEASE_CHECKLIST.md` §7 の smoke test を実施

## 📌 6. Rollback

| 事象              | Rollback                                                                       |
| ----------------- | ------------------------------------------------------------------------------ |
| Cloudflare 起因   | `legalops` CNAME を削除 / 無効化、Tunnel connector 停止、Access app disabled   |
| CSP 起因          | `Content-Security-Policy` を `Content-Security-Policy-Report-Only` に戻す      |
| アプリ起因        | `git revert` → CI → production environment 承認 → 旧 image / 修正 image へ切替 |
| DB migration 起因 | 事前 backup 確認後、承認を得て `alembic downgrade -1` または PITR              |

## 📌 7. 禁止事項

- 本番 deploy を自動実行しない
- 公開 DNS を自動変更しない
- secret / token / 接続文字列を README / Issue / log に出さない
- `git push` / PR merge / release tag は明示承認なしに実行しない
- 本番データ削除・破壊的 migration は単独判断で実行しない
