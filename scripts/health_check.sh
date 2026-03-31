#!/usr/bin/env bash
# =============================================================================
# Klarumzug24 – Health Check & Auto-Recovery
# =============================================================================
# Path on server: /opt/klarumzug24/scripts/health_check.sh
# Cron:           */5 * * * * /opt/klarumzug24/scripts/health_check.sh
#
# Checks /health endpoint. If down:
#   1. Logs the failure
#   2. Restarts systemd service
#   3. Waits and re-checks
#   4. Sends email alert if still down after restart
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_DIR="/opt/klarumzug24"
BACKEND_DIR="${BASE_DIR}/backend"
LOG_DIR="${BASE_DIR}/logs"
LOG_FILE="${LOG_DIR}/health.log"
HEALTH_URL="http://127.0.0.1:8000/health"
SERVICE_NAME="klarumzug24-api"
TIMEOUT=10
MAX_RESTART_RETRIES=3
RESTART_WAIT=5
COOLDOWN_FILE="${LOG_DIR}/.health_restart_cooldown"
COOLDOWN_MINUTES=30

mkdir -p "${LOG_DIR}"

# Load .env for SMTP (alert emails)
if [ -f "${BACKEND_DIR}/.env" ]; then
    set -a
    source "${BACKEND_DIR}/.env"
    set +a
fi

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log() {
    local MSG="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "${MSG}" >> "${LOG_FILE}"
}

send_alert() {
    local SUBJECT="$1"
    local BODY="$2"

    if [ -z "${SMTP_HOST:-}" ] || [ -z "${SMTP_USER:-}" ] || [ -z "${SMTP_PASS:-}" ]; then
        return 0
    fi

    python3 << PYEOF 2>/dev/null || true
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
# Health check
# ---------------------------------------------------------------------------
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time "${TIMEOUT}" "${HEALTH_URL}" 2>/dev/null || echo "000")

if [ "${HTTP_CODE}" = "200" ]; then
    # Healthy — nothing to do
    exit 0
fi

# ---------------------------------------------------------------------------
# Service is DOWN — begin recovery
# ---------------------------------------------------------------------------
log "HEALTH CHECK FAILED: HTTP ${HTTP_CODE} from ${HEALTH_URL}"
log "Service status: $(systemctl is-active ${SERVICE_NAME} 2>/dev/null || echo 'unknown')"

# ---------------------------------------------------------------------------
# Cooldown: don't restart if a recent restart already failed
# ---------------------------------------------------------------------------
if [ -f "${COOLDOWN_FILE}" ]; then
    COOLDOWN_AGE=$(( ( $(date +%s) - $(stat -c %Y "${COOLDOWN_FILE}" 2>/dev/null || echo 0) ) / 60 ))
    if [ "${COOLDOWN_AGE}" -lt "${COOLDOWN_MINUTES}" ]; then
        log "SKIP RESTART: cooldown active (last failed restart ${COOLDOWN_AGE}m ago, cooldown=${COOLDOWN_MINUTES}m)"
        exit 1
    fi
    # Cooldown expired — allow retry
    rm -f "${COOLDOWN_FILE}"
    log "Cooldown expired. Allowing restart retry."
fi

# Attempt restart
log "Restarting ${SERVICE_NAME}..."
systemctl restart "${SERVICE_NAME}" 2>>"${LOG_FILE}" || true

# Wait and re-check
RECOVERED=false
for i in $(seq 1 ${MAX_RESTART_RETRIES}); do
    sleep "${RESTART_WAIT}"
    RETRY_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time "${TIMEOUT}" "${HEALTH_URL}" 2>/dev/null || echo "000")
    if [ "${RETRY_CODE}" = "200" ]; then
        RECOVERED=true
        break
    fi
    log "Recovery attempt ${i}/${MAX_RESTART_RETRIES}: HTTP ${RETRY_CODE}"
done

if [ "${RECOVERED}" = true ]; then
    rm -f "${COOLDOWN_FILE}"
    log "RECOVERED: Service back online after restart"
    send_alert "[Klarumzug24] Service recovered" \
        "Health check failed at $(date) but service recovered after automatic restart.
Server: $(hostname)
Previous HTTP code: ${HTTP_CODE}"
else
    touch "${COOLDOWN_FILE}"
    log "CRITICAL: Service NOT recovered after restart! Cooldown activated (${COOLDOWN_MINUTES}m)"
    send_alert "[Klarumzug24] SERVICE DOWN" \
        "CRITICAL: Klarumzug24 backend is DOWN and could not be auto-recovered.
Server: $(hostname)
Time: $(date)
Health URL: ${HEALTH_URL}
Last HTTP code: ${RETRY_CODE:-000}
Service status: $(systemctl is-active ${SERVICE_NAME} 2>/dev/null || echo unknown)

Manual intervention required:
  ssh root@$(hostname) 'journalctl -u ${SERVICE_NAME} --since \"10 min ago\" --no-pager'"
fi
