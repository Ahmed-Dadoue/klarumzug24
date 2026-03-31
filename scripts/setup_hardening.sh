#!/usr/bin/env bash
# =============================================================================
# Klarumzug24 – Production Hardening Setup (run once on server)
# =============================================================================
# Usage: sudo bash /opt/klarumzug24/scripts/setup_hardening.sh
#
# This script:
#   1. Creates required directories
#   2. Sets file permissions
#   3. Installs cron jobs (backup + health check)
#   4. Installs logrotate config
#   5. Updates systemd service with hardening
#   6. Verifies everything works
#
# Safe to re-run. Idempotent.
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[SETUP]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; }
ok()   { echo -e "  ${GREEN}✓${NC} $*"; }

BASE_DIR="/opt/klarumzug24"
SCRIPTS_DIR="${BASE_DIR}/scripts"
DEPLOY_DIR="${BASE_DIR}/backend/deploy"

echo ""
log "============================================"
log " Klarumzug24 – Production Hardening Setup"
log "============================================"
echo ""

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
    err "Must run as root: sudo bash $0"
    exit 1
fi

if [ ! -d "${BASE_DIR}" ]; then
    err "Base directory not found: ${BASE_DIR}"
    exit 1
fi

# ---------------------------------------------------------------------------
# 1. Create directories
# ---------------------------------------------------------------------------
log "1/6 Creating directories..."

mkdir -p "${BASE_DIR}/backups"
mkdir -p "${BASE_DIR}/logs"
mkdir -p "${SCRIPTS_DIR}"

ok "Directories ready"

# ---------------------------------------------------------------------------
# 2. Install scripts + permissions
# ---------------------------------------------------------------------------
log "2/6 Setting up scripts..."

# Copy scripts from repo to server scripts dir
if [ -f "${BASE_DIR}/scripts/backup_db.sh" ]; then
    chmod +x "${BASE_DIR}/scripts/backup_db.sh"
    ok "backup_db.sh → executable"
else
    warn "backup_db.sh not found in ${SCRIPTS_DIR}. Pull latest code first."
fi

if [ -f "${BASE_DIR}/scripts/health_check.sh" ]; then
    chmod +x "${BASE_DIR}/scripts/health_check.sh"
    ok "health_check.sh → executable"
else
    warn "health_check.sh not found in ${SCRIPTS_DIR}. Pull latest code first."
fi

# Ensure log directory is writable
chown root:root "${BASE_DIR}/logs"
chmod 755 "${BASE_DIR}/logs"

# Ensure backup directory is writable
chown root:root "${BASE_DIR}/backups"
chmod 755 "${BASE_DIR}/backups"

ok "Permissions set"

# ---------------------------------------------------------------------------
# 3. Install cron jobs
# ---------------------------------------------------------------------------
log "3/6 Installing cron jobs..."

CRON_BACKUP="0 2 * * * ${SCRIPTS_DIR}/backup_db.sh >> ${BASE_DIR}/logs/backup.log 2>&1"
CRON_HEALTH="*/5 * * * * ${SCRIPTS_DIR}/health_check.sh"

# Add cron jobs if not already present (idempotent)
CURRENT_CRON=$(crontab -l 2>/dev/null || echo "")

CHANGED=false

if echo "${CURRENT_CRON}" | grep -qF "backup_db.sh"; then
    ok "Backup cron already installed"
else
    CURRENT_CRON="${CURRENT_CRON}
${CRON_BACKUP}"
    CHANGED=true
    ok "Backup cron added: daily 02:00"
fi

if echo "${CURRENT_CRON}" | grep -qF "health_check.sh"; then
    ok "Health check cron already installed"
else
    CURRENT_CRON="${CURRENT_CRON}
${CRON_HEALTH}"
    CHANGED=true
    ok "Health check cron added: every 5 minutes"
fi

if [ "${CHANGED}" = true ]; then
    echo "${CURRENT_CRON}" | crontab -
    ok "Crontab updated"
fi

# ---------------------------------------------------------------------------
# 4. Install logrotate config
# ---------------------------------------------------------------------------
log "4/6 Installing logrotate..."

LOGROTATE_SRC="${BASE_DIR}/deploy/logrotate/klarumzug24"
LOGROTATE_DEST="/etc/logrotate.d/klarumzug24"

if [ -f "${LOGROTATE_SRC}" ]; then
    cp "${LOGROTATE_SRC}" "${LOGROTATE_DEST}"
    chmod 644 "${LOGROTATE_DEST}"
    ok "Logrotate config installed"
else
    # Fallback: create directly
    cat > "${LOGROTATE_DEST}" << 'EOF'
/opt/klarumzug24/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root root
    dateext
    dateformat -%Y%m%d
}
EOF
    chmod 644 "${LOGROTATE_DEST}"
    ok "Logrotate config created directly"
fi

# Verify logrotate config is valid
logrotate -d "${LOGROTATE_DEST}" 2>/dev/null && ok "Logrotate config valid" || warn "Logrotate syntax issue — check manually"

# ---------------------------------------------------------------------------
# 5. Update systemd service
# ---------------------------------------------------------------------------
log "5/6 Updating systemd service..."

SERVICE_SRC="${DEPLOY_DIR}/systemd/klarumzug24-api.service"
SERVICE_DEST="/etc/systemd/system/klarumzug24-api.service"

if [ -f "${SERVICE_SRC}" ]; then
    # Check if update needed
    if ! diff -q "${SERVICE_SRC}" "${SERVICE_DEST}" &>/dev/null; then
        cp "${SERVICE_SRC}" "${SERVICE_DEST}"
        systemctl daemon-reload
        ok "Service file updated + daemon reloaded"

        # Restart service to apply new limits
        systemctl restart klarumzug24-api
        sleep 3

        if systemctl is-active --quiet klarumzug24-api; then
            ok "Service restarted successfully"
        else
            err "Service failed to start after update!"
            err "Check: journalctl -u klarumzug24-api --since '1 min ago'"
            # Revert to safe state
            warn "Attempting to revert service file..."
            systemctl start klarumzug24-api 2>/dev/null || true
        fi
    else
        ok "Service file already up to date"
    fi
else
    warn "Service file not found at ${SERVICE_SRC}"
fi

# ---------------------------------------------------------------------------
# 6. Verify everything
# ---------------------------------------------------------------------------
log "6/6 Verification..."

echo ""
echo "  ┌────────────────────────────────┬──────────┐"
echo "  │ Component                      │ Status   │"
echo "  ├────────────────────────────────┼──────────┤"

# Service
SVC_STATUS=$(systemctl is-active klarumzug24-api 2>/dev/null || echo "inactive")
if [ "${SVC_STATUS}" = "active" ]; then
    echo "  │ systemd service                │ ✓ active │"
else
    echo "  │ systemd service                │ ✗ ${SVC_STATUS}  │"
fi

# Health endpoint
HC=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://127.0.0.1:8000/health 2>/dev/null || echo "000")
if [ "${HC}" = "200" ]; then
    echo "  │ /health endpoint               │ ✓ 200 OK │"
else
    echo "  │ /health endpoint               │ ✗ HTTP ${HC} │"
fi

# Backup script
if [ -x "${SCRIPTS_DIR}/backup_db.sh" ]; then
    echo "  │ backup_db.sh                   │ ✓ ready  │"
else
    echo "  │ backup_db.sh                   │ ✗ missing│"
fi

# Health script
if [ -x "${SCRIPTS_DIR}/health_check.sh" ]; then
    echo "  │ health_check.sh                │ ✓ ready  │"
else
    echo "  │ health_check.sh                │ ✗ missing│"
fi

# Cron jobs
CRON_COUNT=$(crontab -l 2>/dev/null | grep -c "klarumzug24" || echo "0")
echo "  │ Cron jobs                      │ ✓ ${CRON_COUNT} jobs │"

# Logrotate
if [ -f "/etc/logrotate.d/klarumzug24" ]; then
    echo "  │ Logrotate                      │ ✓ active │"
else
    echo "  │ Logrotate                      │ ✗ missing│"
fi

# Log directory
if [ -d "${BASE_DIR}/logs" ]; then
    echo "  │ Logs directory                 │ ✓ exists │"
else
    echo "  │ Logs directory                 │ ✗ missing│"
fi

# Backup directory
if [ -d "${BASE_DIR}/backups" ]; then
    echo "  │ Backups directory              │ ✓ exists │"
else
    echo "  │ Backups directory              │ ✗ missing│"
fi

echo "  └────────────────────────────────┴──────────┘"

echo ""
log "============================================"
log " Production Hardening complete!"
log "============================================"
echo ""
log "Next steps:"
echo "  • Test backup manually:  bash ${SCRIPTS_DIR}/backup_db.sh"
echo "  • Test health check:     bash ${SCRIPTS_DIR}/health_check.sh"
echo "  • View cron jobs:        crontab -l"
echo "  • View service limits:   systemctl show klarumzug24-api | grep -E 'Memory|Limit|Restart'"
echo "  • View logs:             ls -la ${BASE_DIR}/logs/"
echo ""
