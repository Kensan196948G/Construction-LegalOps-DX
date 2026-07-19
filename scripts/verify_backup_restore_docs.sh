#!/usr/bin/env bash
# verify_backup_restore_docs.sh — read-only backup/restore/PITR evidence checks.
#
# This script validates that release-facing documents describe the database
# backup, restore, migration rollback, and PITR stop-line honestly. It never
# runs pg_dump, pg_restore, Alembic, production DNS, Cloudflare, Neon, or secret
# operations.

set -euo pipefail

PASS=0
FAIL=0

pass() {
  echo "✅ $1"
  PASS=$((PASS + 1))
}

fail() {
  echo "❌ $1"
  FAIL=$((FAIL + 1))
}

contains() {
  local file="$1"
  local pattern="$2"
  grep -Fq -- "$pattern" "$file"
}

echo "================================================"
echo "💾 Backup / Restore Evidence Preflight"
echo "================================================"

required_files=(
  "docs/BACKUP_RESTORE.md"
  "docs/RELEASE_CHECKLIST.md"
  "docs/RELEASE_EVIDENCE_MATRIX.md"
  "docs/FINAL_RELEASE_STOP_REPORT.md"
  "docs/PRODUCTION_APPROVAL_PACKET.md"
  "infra/cloudflare/neon-config.md"
  "docs/CLOUDFLARE_NEON_MIGRATION_PLAN.md"
  "scripts/backup_db.sh"
  "scripts/verify_migrations_roundtrip.sh"
)

for file in "${required_files[@]}"; do
  [ -s "${file}" ] && pass "Backup/restore source exists: ${file}" || fail "Backup/restore source missing or empty: ${file}"
done

contains "docs/BACKUP_RESTORE.md" "pg_dump" && pass "Backup guide documents pg_dump" || fail "Backup guide missing pg_dump"
contains "docs/BACKUP_RESTORE.md" "pg_restore" && pass "Backup guide documents pg_restore" || fail "Backup guide missing pg_restore"
contains "docs/BACKUP_RESTORE.md" "sha256sum" && pass "Backup guide requires checksum recording" || fail "Backup guide missing checksum step"
contains "docs/BACKUP_RESTORE.md" "RPO / RTO" && pass "Backup guide records RPO/RTO approval dependency" || fail "Backup guide missing RPO/RTO dependency"
contains "docs/BACKUP_RESTORE.md" "WAL アーカイブ / PITR" && pass "Backup guide records WAL/PITR gap" || fail "Backup guide missing WAL/PITR gap"
contains "docs/BACKUP_RESTORE.md" "本番データ PITR 実演は未実施" && pass "Backup guide states production PITR drill is not complete" || fail "Backup guide missing PITR not-complete statement"
contains "docs/BACKUP_RESTORE.md" "本番 backup / WAL / Neon 承認後" && pass "Backup guide keeps PITR behind human approval" || fail "Backup guide missing PITR approval boundary"
contains "docs/BACKUP_RESTORE.md" "リストアはデータを上書きする破壊的操作" && pass "Backup guide flags restore as destructive" || fail "Backup guide missing destructive restore warning"
contains "docs/BACKUP_RESTORE.md" "secret" && pass "Backup guide references secret/Vault boundary" || fail "Backup guide missing secret/Vault boundary"

contains "scripts/backup_db.sh" "--restore" && pass "Backup script supports restore mode" || fail "Backup script missing restore mode"
contains "scripts/backup_db.sh" "pg_dump" && pass "Backup script uses pg_dump" || fail "Backup script missing pg_dump"
contains "scripts/backup_db.sh" "psql -d" && pass "Backup script restores SQL through psql" || fail "Backup script missing psql restore path"
contains "scripts/backup_db.sh" "sha256sum" && pass "Backup script records checksum" || fail "Backup script missing checksum"

contains "scripts/verify_migrations_roundtrip.sh" "upgrade head" && pass "Migration verifier performs upgrade head" || fail "Migration verifier missing upgrade head"
contains "scripts/verify_migrations_roundtrip.sh" "downgrade base" && pass "Migration verifier performs downgrade base" || fail "Migration verifier missing downgrade base"
contains "scripts/verify_migrations_roundtrip.sh" "idempotent upgrade" && pass "Migration verifier documents idempotent upgrade" || fail "Migration verifier missing idempotent upgrade"
contains "scripts/verify_migrations_roundtrip.sh" "Never connects to production unless" && pass "Migration verifier documents production safety boundary" || fail "Migration verifier missing production safety boundary"

contains "docs/RELEASE_EVIDENCE_MATRIX.md" "DB migration と rollback 手順を検証" && pass "Evidence matrix covers DB migration/rollback criterion" || fail "Evidence matrix missing DB migration/rollback criterion"
contains "docs/RELEASE_EVIDENCE_MATRIX.md" "PITR は本番 backup / WAL / Neon 承認後" && pass "Evidence matrix keeps PITR as approval gate" || fail "Evidence matrix missing PITR approval gate"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "PITR drill" && pass "Final report lists PITR drill residual gate" || fail "Final report missing PITR drill gate"
contains "docs/FINAL_RELEASE_STOP_REPORT.md" "alembic downgrade -1" && pass "Final report includes Alembic rollback command" || fail "Final report missing Alembic rollback command"
contains "docs/PRODUCTION_APPROVAL_PACKET.md" "alembic downgrade -1" && pass "Approval packet includes Alembic rollback path" || fail "Approval packet missing Alembic rollback path"
contains "docs/RELEASE_CHECKLIST.md" "PITR (Point-in-Time Recovery)" && pass "Release checklist includes PITR approval item" || fail "Release checklist missing PITR item"
contains "docs/RELEASE_CHECKLIST.md" "自動バックアップ (pg_dump + WAL アーカイブ)" && pass "Release checklist includes backup/WAL approval item" || fail "Release checklist missing backup/WAL item"
contains "infra/cloudflare/neon-config.md" "Neon ブランチ" && pass "Neon config records branch-before-migration rule" || fail "Neon config missing branch-before-migration rule"
contains "docs/CLOUDFLARE_NEON_MIGRATION_PLAN.md" "pg_dump" && contains "docs/CLOUDFLARE_NEON_MIGRATION_PLAN.md" "pg_restore" && pass "Cloudflare/Neon migration plan covers dump/restore transfer" || fail "Cloudflare/Neon migration plan missing dump/restore transfer"

if grep -RInE "(PITR drill|PITR \\(Point-in-Time Recovery\\)|本番データ PITR 実演).*(✅|完了|complete)|✅.*(PITR drill|PITR \\(Point-in-Time Recovery\\)|本番データ PITR 実演)" docs/RELEASE_EVIDENCE_MATRIX.md docs/FINAL_RELEASE_STOP_REPORT.md docs/PRODUCTION_APPROVAL_PACKET.md docs/RELEASE_CHECKLIST.md | grep -v "✅ / ⏳" >/tmp/legalops-pitr-complete-claim.txt; then
  cat /tmp/legalops-pitr-complete-claim.txt
  fail "Release docs must not claim PITR is fully complete"
else
  pass "Release docs do not claim PITR is fully complete"
fi
rm -f /tmp/legalops-pitr-complete-claim.txt

echo ""
echo "================================================"
echo "📊 Summary"
echo "================================================"
echo "✅ Passed: ${PASS}"
echo "❌ Failed: ${FAIL}"

if [ "${FAIL}" -gt 0 ]; then
  echo "🚨 Backup/restore evidence preflight failed"
  exit 1
fi

echo "✅ Backup/restore evidence preflight passed"
exit 0
