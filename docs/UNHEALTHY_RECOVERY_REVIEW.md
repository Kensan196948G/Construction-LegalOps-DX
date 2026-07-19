# 🐳 Unhealthy Recovery Review — Issue #57

> Docker Compose healthcheck の `unhealthy` 検知後に、どこまで自動復旧するかの CTO 判断メモ。
> 本番デプロイや host 権限変更は実行せず、承認待ちの設計として残す。

## 📌 1. 結論

| 項目 | CTO 判断 |
|---|---|
| 採用方式 | ✅ **手動承認型 watchdog** (`scripts/check_unhealthy_services.sh`) |
| 常駐 autoheal daemon | ❌ 今回は不採用 |
| 理由 | Docker socket 書込権限を持つ常駐コンテナは host root 相当の攻撃面を増やすため |
| 本番自動化 | ⏳ systemd timer / external monitor は本番運用体制承認後に検討 |

## 📌 2. 方式比較

| 方式 | 長所 | リスク | 判断 |
|---|---|---|---|
| 手動 runbook | 権限追加なし。判断と証跡を残せる | 検知から復旧まで人手が必要 | ✅ 採用 |
| systemd watchdog / timer | host 側で制御でき、cron より監査しやすい | Docker 操作権限を持つ unit の管理が必要 | ⏳ 本番承認後 |
| Docker socket autoheal | 復旧が速い | `/var/run/docker.sock` は host root 相当。侵害時の blast radius が大きい | ❌ 不採用 |
| 外部監視 + 手動 restart | Cloudflare / Prometheus / Alertmanager と相性がよい | 通知 secret と on-call 運用が必要 | ✅ 推奨 |

## 📌 3. Threat Model

| 脅威 | 影響 | 緩和 |
|---|---|---|
| Docker socket を持つ autoheal コンテナ侵害 | 任意コンテナ起動・volume 読取・host 権限昇格 | 常駐 autoheal 不採用。restart は人間承認後の CLI 実行 |
| 誤検知による restart loop | 可用性低下、調査証跡喪失 | report-only を default。`--restart` は対象 service 明示 |
| P1 障害時の過剰自動復旧 | 根本原因やログが失われる | restart 前に `docker compose ps` と logs tail を保存 |
| 本番 secrets のログ露出 | インシデント拡大 | restart スクリプトは環境変数や logs を出力しない |

## 📌 4. Drill 手順

```bash
# 1. report-only で unhealthy を検出
./scripts/check_unhealthy_services.sh

# 2. 障害証跡を保存
docker compose -f infra/docker/docker-compose.yml ps
docker compose -f infra/docker/docker-compose.yml logs --tail=200 <service>

# 3. Incident Commander / Infra Lead の承認後に単一 service を restart
./scripts/check_unhealthy_services.sh --restart <service>

# 4. 復旧確認
docker compose -f infra/docker/docker-compose.yml ps
curl -s http://localhost:8410/healthz
curl -s http://localhost:8010/api/v1/readyz | jq .
```

## 📌 5. 本番化条件

- [ ] 本番 on-call receiver secret が投入済み
- [ ] `scripts/check_unhealthy_services.sh` を P1/P2 drill で 1 回実演済み
- [ ] systemd timer 化する場合、unit file と実行ユーザーを security review 済み
- [ ] Docker socket を直接 mount する常駐コンテナ方式を採る場合、別途 CTO + Security + Infra Lead の承認がある
