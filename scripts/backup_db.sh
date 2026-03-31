#!/usr/bin/env bash
# =============================================================================
# Klarumzug24 – Database Backup (SQLite + PostgreSQL)
# =============================================================================
# Path on server: /opt/klarumzug24/scripts/backup_db.sh
# Cron:           0 2 * * * /opt/klarumzug24/scripts/backup_db.sh
#
# Auto-detects database type from DATABASE_URL in .env:
#   - sqlite:///  → sqlite3 .backup (consistent snapshot, safe during writes)
#   - postgresql  → pg_dump (schema + data)
#
# Keeps last 7 days of backups. Never touches the live database.
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR="/opt/klarumzug24"
BACKEND_DIR="${BASE_DIR}/backend"
BACKUP_DIR="${BASE_DIR}/backups"
LOG_DIR="${BASE_DIR}/logs"
KEEP_DAYS=7
TS=$(date +%Y%m%d_%H%M%S)
LOG_TAG="klarumzug24-backup"

# ---------------------------------------------------------------------------
# Load .env (for DATABASE_URL + SMTP)
# ---------------------------------------------------------------------------
if [ -f "${BACKEND_DIR}/.env" ]; then
    set -a
    source "${BACKEND_DIR}/.env"
    set +a
fi

DATABASE_URL="${DATABASE_URL:-sqlite:///./klarumzug.db}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
mkdir -p "${BACKUP_DIR}" "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/backup.log"

log() {
    local MSG="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "${MSG}" | tee -a "${LOG_FILE}"
    logger -t "${LOG_TAG}" "$*" 2>/dev/null || true
}

err() {
    local MSG="[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*"
    echo "${MSG}" | tee -a "${LOG_FILE}" >&2
    logger -t "${LOG_TAG}" -p user.err "$*" 2>/dev/null || true
}

send_alert() {
    local SUBJECT="$1"
    local BODY="$2"

    if [ -z "${SMTP_HOST:-}" ] || [ -z "${SMTP_USER:-}" ] || [ -z "${SMTP_PASS:-}" ]; then
        return 0
    fi

    python3 << PYEOF 2>/dev/null || err "Alert email failed"
import smtplib, ssl, os
from email.mime.text import MIMEText
msg = MIMEText("""${BODY}""")
msg['Subject'] = "${SUBJECT}"
msg['From'] = os.environ.get('MAIL_FROM', os.environ['SMTP_USER'])
msg['To'] = os.environ.get('MAIL_TO', os.environ['SMTP_USER'])
ctx = ssl.create_default_context()
with smtplib.SMTP_SSL(os.environ['SMTP_HOST'], int(os.environ.get('SMTP_PORT','465')), context=ctx) as s:
    s.login(os.environ['SMTP_USER'], os.environ['SMTP_PASS'])
    s.send_message(msg)
PYEOF
}

# ---------------------------------------------------------------------------
# Detect database type
# ---------------------------------------------------------------------------
log "=== Backup started ==="

if [[ "${DATABASE_URL}" == sqlite* ]]; then
    DB_TYPE="sqlite"
    # Extract file path from sqlite:///./relative or sqlite:////absolute
    DB_PATH=$(echo "${DATABASE_URL}" | sed 's|sqlite:///||')
    # Resolve relative paths against backend dir
    if [[ "${DB_PATH}" != /* ]]; then
        DB_PATH="${BACKEND_DIR}/${DB_PATH}"
    fi
    BACKUP_FILE="${BACKUP_DIR}/klarumzug_${TS}.db"
    log "Detected: SQLite → ${DB_PATH}"

elif [[ "${DATABASE_URL}" == postgres* ]]; then
    DB_TYPE="postgresql"
    BACKUP_FILE="${BACKUP_DIR}/klarumzug_${TS}.sql.gz"
    log "Detected: PostgreSQL"
else
    err "Unknown DATABASE_URL format: ${DATABASE_URL}"
    exit 1
fi

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
if [ "${DB_TYPE}" = "sqlite" ]; then
    if [ ! -f "${DB_PATH}" ]; then
        err "SQLite file not found: ${DB_PATH}"
        send_alert "[Klarumzug24] Backup FAILED" "Database file not found: ${DB_PATH}"
        exit 1
    fi
    if ! command -v sqlite3 &>/dev/null; then
        err "sqlite3 not installed. Run: apt install -y sqlite3"
        exit 1
    fi
fi

if [ "${DB_TYPE}" = "postgresql" ]; then
    if ! command -v pg_dump &>/dev/null; then
        err "pg_dump not installed. Run: apt install -y postgresql-client"
        exit 1
    fi
fi

# ---------------------------------------------------------------------------
# Create backup
# ---------------------------------------------------------------------------
if [ "${DB_TYPE}" = "sqlite" ]; then
    # sqlite3 .backup creates a consistent snapshot even during active writes
    sqlite3 "${DB_PATH}" ".backup '${BACKUP_FILE}'"

    if [ ! -f "${BACKUP_FILE}" ]; then
        err "SQLite backup failed – output file missing"
        send_alert "[Klarumzug24] Backup FAILED" "SQLite backup produced no output. DB: ${DB_PATH}"
        exit 1
    fi

    # Verify integrity
    INTEGRITY=$(sqlite3 "${BACKUP_FILE}" "PRAGMA integrity_check;" 2>/dev/null || echo "FAILED")
    if [ "${INTEGRITY}" != "ok" ]; then
        err "Integrity check FAILED: ${INTEGRITY}"
        send_alert "[Klarumzug24] Backup CORRUPT" "Integrity check failed for ${BACKUP_FILE}"
        rm -f "${BACKUP_FILE}"
        exit 1
    fi

    log "Integrity check: ok"

elif [ "${DB_TYPE}" = "postgresql" ]; then
    # pg_dump using DATABASE_URL, compressed with gzip
    # Extract connection details from DATABASE_URL
    # Format: postgresql+psycopg://user:pass@host:port/dbname
    PG_URL=$(echo "${DATABASE_URL}" | sed 's|+psycopg||; s|+asyncpg||; s|+psycopg2||')

    pg_dump "${PG_URL}" | gzip > "${BACKUP_FILE}"

    if [ ! -s "${BACKUP_FILE}" ]; then
        err "pg_dump failed – output file empty"
        send_alert "[Klarumzug24] Backup FAILED" "pg_dump produced empty output"
        rm -f "${BACKUP_FILE}"
        exit 1
    fi

    log "pg_dump completed"
fi

BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
log "Backup saved: ${BACKUP_FILE} (${BACKUP_SIZE})"

# ---------------------------------------------------------------------------
# Cleanup: keep last KEEP_DAYS days
# ---------------------------------------------------------------------------
BEFORE=$(find "${BACKUP_DIR}" -maxdepth 1 -name "klarumzug_*" -type f | wc -l)

find "${BACKUP_DIR}" -maxdepth 1 -name "klarumzug_*" -type f -mtime "+${KEEP_DAYS}" -delete

AFTER=$(find "${BACKUP_DIR}" -maxdepth 1 -name "klarumzug_*" -type f | wc -l)
REMOVED=$((BEFORE - AFTER))

if [ "${REMOVED}" -gt 0 ]; then
    log "Cleaned ${REMOVED} old backup(s). Remaining: ${AFTER}"
else
    log "No old backups to clean. Total: ${AFTER}"
fi

log "=== Backup complete ==="
