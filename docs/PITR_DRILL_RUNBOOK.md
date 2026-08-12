# 💾 PITR / バックアップ復旧ドリル手順書（P-6）

> 本番（Neon）の PITR ドリルは **Neon リソース作成後（#50）に人間が実施** する。
> 本手順書はその実行手順と、手前で実施可能なローカル論理バックアップ復旧ドリルを定める。

## 📋 1. 対象と目標

| 項目 | 目標（合意推奨値） | 備考 |
| --- | --- | --- |
| RPO | 15 分以内 | Neon は自動バックアップ + PITR で 10 分単位復旧可 |
| RTO | 60 分以内 | リストア + アプリ再起動 + スモーク |
| ドリル頻度 | 四半期 1 回 | リリース前に初回ドリル必須 |

## 🧪 2. ローカル論理バックアップ復旧ドリル（承認前でも実施可）

```bash
# 使い捨て PostgreSQL を起動
docker run -d --name legalops-pitr-drill \
  -e POSTGRES_USER=legalops -e POSTGRES_PASSWORD=legalops_dev -e POSTGRES_DB=legalops \
  -p 55434:5432 postgres:16-alpine

# データ投入
PGPASSWORD=legalops_dev psql -h 127.0.0.1 -p 55434 -U legalops -d legalops \
  -c "CREATE TABLE drill_check(id int primary key, note text); INSERT INTO drill_check VALUES (1,'ok');"

# バックアップ取得（sha256 付き）
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55434 BACKUP_DIR=/tmp/legalops-backup-drill \
  ./scripts/backup_db.sh

# DB 破壊 → 復旧
docker exec legalops-pitr-drill psql -U legalops -d postgres -c "DROP DATABASE legalops;"
docker exec legalops-pitr-drill createdb -U legalops legalops
POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55434 BACKUP_DIR=/tmp/legalops-backup-drill \
  ./scripts/backup_db.sh --restore /tmp/legalops-backup-drill/legalops_*.sql.gz

# 検証
docker exec legalops-pitr-drill psql -U legalops -d legalops \
  -c "SELECT * FROM drill_check;"
# 期待: 1 | ok
```

## ☁️ 3. Neon PITR ドリル（#50 承認後・人間実施）

1. Neon Console で対象ブランチの「Restore to point in time」を選択
2. 復旧ポイントを 10 分前・1 時間前の 2 パターンで実施
3. 復旧ブランチを別名（`pitr-drill-YYYYMMDD`）で作成し、**本番は切替えない**
4. 復旧 DB に接続し整合性確認:
   - `SELECT count(*) FROM contracts;` が直近バックアップ時点と一致
   - 監査ログの `hash_chain` 検証 API（`POST /audit-logs/verify`）が成功
   - 最新マイグレーション（008 以降）が適用可能
5. 結果を `reports/` に記録し、本 Issue（#50）にドリル証跡を添付

## ✅ 4. 完了条件

- [ ] 論理バックアップ→復旧→データ整合確認が成功（ローカル）
- [ ] Neon PITR 復旧で 10 分単位の復旧ポイントが検証できる（本番承認後）
- [ ] 復旧後のスモーク（ログイン / 契約一覧 / 監査検証）が成功
- [ ] RPO/RTO の合意値と実測値が記録される
