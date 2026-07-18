# Neon PostgreSQL 接続設定 — Construction-LegalOps-DX
# Status: IaC 雛形（本番適用は人間による Neon プロジェクト作成後）

# ============================================================
# 接続文字列テンプレート
# ============================================================
# Direct connection (asyncpg prepared statement 互換):
#   postgresql+asyncpg://user:password@ep-xxxx.us-east-2.aws.neon.tech/dbname?sslmode=require
#
# Pooled connection (PgBouncer transaction mode):
#   postgresql+asyncpg://user:password@ep-xxxx-pooler.us-east-2.aws.neon.tech/dbname?sslmode=require
#   ※ asyncpg の prepared statement と競合するため statement_cache_size=0 が必要な場合あり
#
# 推奨: direct connection を DB_URL に使用し、pooled は read-replica 用に別途設定

# ============================================================
# 環境変数 (Vault / GitHub Secrets で管理、平文コミット禁止)
# ============================================================
# DB_URL=postgresql+asyncpg://<NEON_USER>:<NEON_PASSWORD>@<NEON_HOST>/<NEON_DB>?sslmode=require
# NEON_PROJECT_ID=ep-xxxx
# NEON_API_KEY=<api_key>  # CI/CD でのブランチ作成・マイグレーション用

# ============================================================
# Alembic マイグレーション (Neon 向け注意事項)
# ============================================================
# 1. Neon は DDL トランザクションをサポートしない操作がある
#    (CREATE INDEX CONCURRENTLY 等)。alembic の transactional_ddl は
#    False に設定することを推奨。
# 2. Neon のブランチ機能を使う場合:
#    - 本番ブランチ: main
#    - ステージングブランチ: staging (本番から分岐)
#    - CI 検証ブランチ: ci-<sha> (使い捨て、検証後削除)
# 3. migration 前に Neon ブランチを作成し、検証後に本番へ promote する
#    フローが安全（Neon の branching は瞬時）

# ============================================================
# CI/CD での Neon ブランチ検証フロー (将来実装)
# ============================================================
# 1. `neonctl branches create --project-id $NEON_PROJECT_ID --name ci-$GITHUB_SHA`
# 2. `alembic upgrade head` (CI ブランチで実行)
# 3. テスト実行
# 4. 成功 → 本番ブランチへ promote or merge
# 5. 失敗 → CI ブランチ削除
# 6. `neonctl branches delete --project-id $NEON_PROJECT_ID --name ci-$GITHUB_SHA`