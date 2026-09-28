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

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

# ---- Client/server version pinning -----------------------------------------
# 2026-09-28 (Deep Debug Round 1): this host ships several PostgreSQL client
# majors and PATH decides which one runs. /usr/local/bin/pg_dump was 17.10 while
# the server is 16.14, so a plain `pg_dump -Fc` produced a custom-format archive
# (header version 1.16) that the only installed pg_restore (16.14) refuses with
# "ファイルヘッダ内のバージョン(1.16)はサポートされていません" — a backup that
# cannot be restored. Select the client whose major matches the server, in both
# backup and restore paths, and fail closed if no match exists.
PG_SERVER_MAJOR=""
detect_server_major() {
    [ -n "$PG_SERVER_MAJOR" ] && { printf '%s' "$PG_SERVER_MAJOR"; return 0; }
    local v
    # No pipes here on purpose: `set -o pipefail` turns the SIGPIPE from an early
    # `head` exit into a pipeline failure, which previously made every version
    # probe look like "no matching client found".
    v="$(psql -Atc 'show server_version' 2>/dev/null || true)"
    if [[ "$v" =~ ^([0-9]+) ]]; then
        PG_SERVER_MAJOR="${BASH_REMATCH[1]}"
        printf '%s' "$PG_SERVER_MAJOR"
        return 0
    fi
    return 1
}

# Echo the path of <tool> whose major version matches the server exactly.
#
# Why exact and not "newer is fine": a pg_dump from a newer major emits GUCs the
# older server rejects (e.g. pg_dump 17 writes `SET transaction_timeout = 0`,
# which PostgreSQL 16 fails on), so a 17/18 dump cannot be restored into this
# 16 server. Exact major match is the only verifiable choice.
#
# Why the /usr/lib/postgresql/<major>/bin path comes first: on Debian/Ubuntu
# /usr/bin/pg_dump is a symlink to `pg_wrapper`, a Perl dispatcher whose
# --version output depends on PGHOST/PGPORT in the environment — it reported
# 16.14 with no PG* vars set and 18.4 with them set, so probing it is not
# deterministic. The version-suffixed binaries are the real ones.
pick_client() {
    local tool="$1" want="$2" cand out
    for cand in "/usr/lib/postgresql/$want/bin/$tool" \
        "/usr/bin/$tool" "/bin/$tool" "$(command -v "$tool" 2>/dev/null || true)"; do
        [ -n "$cand" ] && [ -x "$cand" ] || continue
        out="$("$cand" --version 2>/dev/null || true)"
        if [[ "$out" =~ \(PostgreSQL\)\ ([0-9]+)\. ]] && [ "${BASH_REMATCH[1]}" = "$want" ]; then
            printf '%s' "$cand"
            return 0
        fi
    done
    return 1
}

# ---- Backup ----
do_backup() {
    local timestamp
    timestamp=$(date -u +%Y%m%dT%H%M%SZ)
    local backup_file="${BACKUP_DIR}/legalops_${timestamp}.sql.gz"

    local server_major pg_dump_bin
    if ! server_major="$(detect_server_major)"; then
        log "ERROR: cannot determine server version; refusing to guess a client major"
        return 1
    fi
    if ! pg_dump_bin="$(pick_client pg_dump "$server_major")"; then
        log "ERROR: no pg_dump with major ${server_major} (server major) found — refusing to write an unrestorable archive"
        return 1
    fi
    # The paired restore tool must be able to read what we produce.
    if ! pick_client pg_restore "$server_major" >/dev/null; then
        log "ERROR: no pg_restore with major ${server_major} found — backup would not be verifiable"
        return 1
    fi

    log "Starting backup to ${backup_file} (server major ${server_major}, client ${pg_dump_bin})"
    "$pg_dump_bin" --no-owner --no-acl --compress=9 \
        --file="${backup_file}"

    log "Backup complete: $(du -h "${backup_file}" | cut -f1)"
    sha256sum "${backup_file}" > "${backup_file}.sha256"
    log "Checksum written: ${backup_file}.sha256"

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

    if [ -f "${RESTORE_FILE}.sha256" ]; then
        log "Verifying checksum: ${RESTORE_FILE}.sha256"
        sha256sum -c "${RESTORE_FILE}.sha256"
    else
        log "WARNING: checksum file not found for ${RESTORE_FILE}"
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
    # Use the same-major client as the server (see the pinning note above).
    local server_major psql_bin
    if server_major="$(detect_server_major)" && psql_bin="$(pick_client psql "$server_major")"; then
        log "Using client ${psql_bin} (server major ${server_major})"
    else
        psql_bin="psql"
        log "WARNING: no same-major psql found; falling back to $(command -v psql)"
    fi
    gunzip -c "$RESTORE_FILE" | "$psql_bin" -d "$PGDB"

    log "Restore complete. Running migrations..."
    (
        cd "${REPO_ROOT}/backend"
        PYTHONPATH="${REPO_ROOT}/backend" alembic -c alembic.ini upgrade head
    )

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
