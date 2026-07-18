#!/usr/bin/env bash
# ============================================================
# Construction-LegalOps-DX — PostgreSQL backup script
#
# Usage:
#   ./scripts/backup_db.sh                    # manual run
#   ./scripts/backup_db.sh --restore <file>   # restore from file
#
# Cron (daily at 03:00 JST):
#   0 3 * * * /path/to/scripts/backup_db.sh >> /var/log/legalops-backup.log 2>&1
#
# Environment variables expected:
#   POSTGRES_USER  (default: legalops)
#   POSTGRES_DB    (default: legalops)
#   POSTGRES_HOST  (default: localhost)
#   POSTGRES_PORT  (default: 5432)
#   BACKUP_DIR     (default: ./backups)
#   BACKUP_RETENTION_DAYS (default: 30)
#   PGPASSWORD     (recommended: set via .pgpass or env)
# ============================================================
set -euo pipefail

# ---- Configuration ----
PGUSER="${POSTGRES_USER:-legalops}"
PGDB="${POSTGRES_DB:-legalops}"
PGHOST="${POSTGRES_HOST:-localhost}"
PGPORT="${POSTGRES_PORT:-5432}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION="${BACKUP_RETENTION_DAYS:-30}"

export PGUSER PGDATABASE="$PGDB" PGHOST PGPORT

# ---- CLI ----
MODE="${1:-backup}"
RESTORE_FILE="${2:-}"

# ---- Ensure backup directory ----
mkdir -p "$BACKUP_DIR"

log() {
    echo "[$(date -Iseconds)] $*"
}

# ---- Backup ----
do_backup() {
    local timestamp
    timestamp=$(date -u +%Y%m%dT%H%M%SZ)
    local backup_file="${BACKUP_DIR}/legalops_${timestamp}.sql.gz"

    log "Starting backup to ${backup_file}"
    pg_dump --no-owner --no-acl --compress=9 \
        --file="${backup_file}"

    log "Backup complete: $(du -h "${backup_file}" | cut -f1)"

    # Retain only recent backups
    local count
    count=$(find "$BACKUP_DIR" -name "legalops_*.sql.gz" -mtime "+${RETENTION}" -delete -print | wc -l)
    if [ "$count" -gt 0 ]; then
        log "Cleaned up ${count} old backup(s) older than ${RETENTION} days"
    fi
}

# ---- Restore ----
do_restore() {
    if [ -z "$RESTORE_FILE" ]; then
        echo "Usage: $0 --restore <backup_file.sql.gz>"
        echo "Available backups:"
        ls -lh "$BACKUP_DIR"/legalops_*.sql.gz 2>/dev/null || echo "  (none)"
        exit 1
    fi

    if [ ! -f "$RESTORE_FILE" ]; then
        log "ERROR: backup file not found: ${RESTORE_FILE}"
        exit 1
    fi

    log "WARNING: This will DROP and recreate the database '${PGDB}'."
    read -rp "Continue? (type 'yes' to confirm): " confirm
    if [ "$confirm" != "yes" ]; then
        log "Restore cancelled."
        exit 0
    fi

    log "Terminating active connections to ${PGDB}..."
    psql -d postgres -c "SELECT pg_terminate_backend(pg_stat_activity.pid)
        FROM pg_stat_activity
        WHERE pg_stat_activity.datname = '${PGDB}'
        AND pid <> pg_backend_pid();" 2>/dev/null || true

    log "Dropping and recreating ${PGDB}..."
    dropdb --if-exists "$PGDB"
    createdb "$PGDB"

    log "Restoring from ${RESTORE_FILE}..."
    gunzip -c "$RESTORE_FILE" | psql -d "$PGDB"

    log "Restore complete. Running migrations..."
    alembic -c backend/alembic.ini upgrade head

    log "Restore finished successfully."
}

# ---- Dispatch ----
case "$MODE" in
    --restore)
        do_restore
        ;;
    backup|*)
        do_backup
        ;;
esac