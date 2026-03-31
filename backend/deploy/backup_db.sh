#!/usr/bin/env bash
# =============================================================================
# DEPRECATED – use /opt/klarumzug24/scripts/backup_db.sh instead
# =============================================================================
# This file is kept for reference only.
# The new version supports both SQLite and PostgreSQL.
# Cron:    0 2 * * * /opt/klarumzug24/scripts/backup_db.sh
#
# What it does:
#   1. Creates a timestamped copy of the SQLite database
#   2. Keeps the last N backups (default: 30)
#   3. Sends email alert if backup fails (optional, needs SMTP configured)
#
# Safety:
#   - Uses sqlite3 .backup command (safe even during writes)
#   - Never modifies the original database
#   - Silent on success, loud on failure
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BACKEND_DIR="/opt/klarumzug24/backend"
DB_FILE="${BACKEND_DIR}/klarumzug.db"
BACKUP_BASE="/opt/klarumzug24/backups/db"
KEEP_DAYS=30
TS=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_BASE}/klarumzug_${TS}.db"
LOG_TAG="klarumzug24-backup"

# Optional: load .env for SMTP settings (for alert emails)
if [ -f "${BACKEND_DIR}/.env" ]; then
    set -a
    source "${BACKEND_DIR}/.env"
    set +a
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()  { logger -t "${LOG_TAG}" "$*"; echo "[BACKUP] $*"; }
err()  { logger -t "${LOG_TAG}" -p user.err "$*"; echo "[BACKUP ERROR] $*" >&2; }

send_alert() {
    local SUBJECT="$1"
    local BODY="$2"

    # Only send if SMTP is configured
    if [ -z "${SMTP_HOST:-}" ] || [ -z "${SMTP_USER:-}" ] || [ -z "${SMTP_PASS:-}" ]; then
        err "SMTP not configured – alert not sent: ${SUBJECT}"
        return 0
    fi

    # Use Python to send email (already available on server)
    python3 -c "
import smtplib, ssl
from email.mime.text import MIMEText
import os

msg = MIMEText('${BODY}')
msg['Subject'] = '${SUBJECT}'
msg['From'] = os.environ.get('MAIL_FROM', os.environ['SMTP_USER'])
msg['To'] = os.environ.get('MAIL_TO', os.environ['SMTP_USER'])

ctx = ssl.create_default_context()
with smtplib.SMTP_SSL(os.environ['SMTP_HOST'], int(os.environ.get('SMTP_PORT', 465)), context=ctx) as s:
    s.login(os.environ['SMTP_USER'], os.environ['SMTP_PASS'])
    s.send_message(msg)
" 2>/dev/null || err "Failed to send alert email"
}

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------
if [ ! -f "${DB_FILE}" ]; then
    # Check if DATABASE_URL points to a different path
    if [[ "${DATABASE_URL:-}" == sqlite* ]]; then
        # Extract path from sqlite:///./path or sqlite:////absolute/path
        EXTRACTED_PATH=$(echo "${DATABASE_URL}" | sed 's|sqlite:///||')
        if [ -f "${EXTRACTED_PATH}" ]; then
            DB_FILE="${EXTRACTED_PATH}"
        elif [ -f "${BACKEND_DIR}/${EXTRACTED_PATH}" ]; then
            DB_FILE="${BACKEND_DIR}/${EXTRACTED_PATH}"
        fi
    fi

    if [ ! -f "${DB_FILE}" ]; then
        err "Database not found at ${DB_FILE}"
        send_alert "[Klarumzug24] Backup FAILED" "Database file not found: ${DB_FILE}"
        exit 1
    fi
fi

if ! command -v sqlite3 &>/dev/null; then
    err "sqlite3 not found. Install: apt install -y sqlite3"
    exit 1
fi

# ---------------------------------------------------------------------------
# Create backup
# ---------------------------------------------------------------------------
mkdir -p "${BACKUP_BASE}"

log "Starting backup: ${DB_FILE} → ${BACKUP_FILE}"

# Use sqlite3 .backup for a consistent snapshot (safe during writes)
sqlite3 "${DB_FILE}" ".backup '${BACKUP_FILE}'"

if [ $? -eq 0 ] && [ -f "${BACKUP_FILE}" ]; then
    BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    log "Backup successful: ${BACKUP_FILE} (${BACKUP_SIZE})"
else
    err "Backup FAILED!"
    send_alert "[Klarumzug24] DB Backup FAILED" \
        "Database backup failed at $(date). Server: $(hostname). DB: ${DB_FILE}"
    exit 1
fi

# ---------------------------------------------------------------------------
# Verify backup integrity
# ---------------------------------------------------------------------------
INTEGRITY=$(sqlite3 "${BACKUP_FILE}" "PRAGMA integrity_check;" 2>/dev/null)
if [ "${INTEGRITY}" != "ok" ]; then
    err "Backup integrity check FAILED: ${INTEGRITY}"
    send_alert "[Klarumzug24] Backup CORRUPT" \
        "Database backup integrity check failed. File: ${BACKUP_FILE}. Result: ${INTEGRITY}"
    rm -f "${BACKUP_FILE}"
    exit 1
fi

log "Integrity check passed"

# ---------------------------------------------------------------------------
# Cleanup old backups
# ---------------------------------------------------------------------------
DELETED=0
find "${BACKUP_BASE}" -name "klarumzug_*.db" -type f -mtime "+${KEEP_DAYS}" | while read -r OLD; do
    rm -f "${OLD}"
    DELETED=$((DELETED + 1))
done

REMAINING=$(find "${BACKUP_BASE}" -name "klarumzug_*.db" -type f | wc -l)
log "Cleanup done. Backups kept: ${REMAINING}"

log "=== Backup complete ==="
