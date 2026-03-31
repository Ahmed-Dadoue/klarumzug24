#!/usr/bin/env bash
# =============================================================================
# Klarumzug24 – Production Deployment Script
# =============================================================================
# Usage:   ./deploy.sh
# Purpose: Pull latest code from GitHub, update dependencies if needed,
#          restart backend service, verify health.
#
# Paths (must match systemd service and nginx config):
#   Backend:   /opt/klarumzug24/backend
#   Frontend:  /var/www/html
#   Venv:      /opt/klarumzug24/backend/.venv
#   .env:      /opt/klarumzug24/backend/.env  (never overwritten)
#
# Safety:
#   - Creates timestamped backup before updating
#   - Rolls back automatically if health check fails
#   - Never touches .env or database
#   - Idempotent: safe to run multiple times
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REPO_DIR="/opt/klarumzug24"
BACKEND_DIR="${REPO_DIR}/backend"
FRONTEND_SRC="${REPO_DIR}/docs"
FRONTEND_DEST="/var/www/html"
VENV_DIR="${BACKEND_DIR}/.venv"
SERVICE_NAME="klarumzug24-api"
HEALTH_URL="http://127.0.0.1:8000/health"
BRANCH="main"
MAX_HEALTH_RETRIES=10
HEALTH_RETRY_DELAY=3

# Timestamp for backups
TS=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/opt/klarumzug24/backups/${TS}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[DEPLOY]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; }

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
log "=== Klarumzug24 Deployment – ${TS} ==="

if [ "$(id -u)" -ne 0 ]; then
    err "This script must be run as root (for systemctl). Use: sudo ./deploy.sh"
    exit 1
fi

if [ ! -d "${REPO_DIR}/.git" ]; then
    err "Git repository not found at ${REPO_DIR}."
    err "First-time setup required. Run:"
    err "  git clone git@github.com:YOUR_USER/klarumzug24.git ${REPO_DIR}"
    err "  cd ${BACKEND_DIR} && python3.11 -m venv .venv"
    err "  .venv/bin/pip install -r requirements.txt"
    err "  cp .env.example .env && nano .env"
    exit 1
fi

if [ ! -f "${BACKEND_DIR}/.env" ]; then
    err ".env file missing at ${BACKEND_DIR}/.env"
    err "Create it from template: cp ${BACKEND_DIR}/.env.example ${BACKEND_DIR}/.env"
    err "Then edit with real production values: nano ${BACKEND_DIR}/.env"
    exit 1
fi

if [ ! -d "${VENV_DIR}" ]; then
    err "Python venv not found at ${VENV_DIR}"
    err "Create it: python3.11 -m venv ${VENV_DIR}"
    err "Then: ${VENV_DIR}/bin/pip install -r ${BACKEND_DIR}/requirements.txt"
    exit 1
fi

if ! command -v rsync &>/dev/null; then
    err "rsync not found. Install: apt install -y rsync"
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 1: Backup current state
# ---------------------------------------------------------------------------
log "Step 1/7: Creating backup at ${BACKUP_DIR}"
mkdir -p "${BACKUP_DIR}"

# Save current git commit hash for rollback
PREV_COMMIT=$(cd "${REPO_DIR}" && git rev-parse HEAD)
echo "${PREV_COMMIT}" > "${BACKUP_DIR}/previous_commit.txt"

# Backup critical backend files
cp -r "${BACKEND_DIR}/app" "${BACKUP_DIR}/app"
cp "${BACKEND_DIR}/main.py" "${BACKUP_DIR}/main.py"
cp "${BACKEND_DIR}/requirements.txt" "${BACKUP_DIR}/requirements.txt"

log "  Backup of commit ${PREV_COMMIT:0:8} saved"

# ---------------------------------------------------------------------------
# Step 2: Pull latest code
# ---------------------------------------------------------------------------
log "Step 2/7: Pulling latest code from origin/${BRANCH}"
cd "${REPO_DIR}"

# Stash any local changes (shouldn't be any, but safety)
git stash --quiet 2>/dev/null || true

git fetch origin "${BRANCH}"
git checkout "${BRANCH}"
git reset --hard "origin/${BRANCH}"

NEW_COMMIT=$(git rev-parse HEAD)
log "  Updated: ${PREV_COMMIT:0:8} → ${NEW_COMMIT:0:8}"

if [ "${PREV_COMMIT}" = "${NEW_COMMIT}" ]; then
    log "  No changes detected. Deployment skipped."
    exit 0
fi

# Show what changed
log "  Changes:"
git log --oneline "${PREV_COMMIT}..${NEW_COMMIT}" | head -10

# ---------------------------------------------------------------------------
# Step 3: Update Python dependencies (only if requirements.txt changed)
# ---------------------------------------------------------------------------
log "Step 3/7: Checking Python dependencies"

if git diff --name-only "${PREV_COMMIT}" "${NEW_COMMIT}" | grep -q "backend/requirements.txt"; then
    log "  requirements.txt changed – updating dependencies..."
    "${VENV_DIR}/bin/pip" install --quiet --upgrade pip
    "${VENV_DIR}/bin/pip" install --quiet -r "${BACKEND_DIR}/requirements.txt"
    log "  Dependencies updated"
else
    log "  requirements.txt unchanged – skipping pip install"
fi

# ---------------------------------------------------------------------------
# Step 4: Update frontend (only if docs/ changed)
# ---------------------------------------------------------------------------
log "Step 4/7: Checking frontend files"

if git diff --name-only "${PREV_COMMIT}" "${NEW_COMMIT}" | grep -q "^docs/"; then
    log "  Frontend files changed – syncing to ${FRONTEND_DEST}"
    rsync -a --delete \
        --exclude='Dockerfile' \
        --exclude='nginx.conf' \
        "${FRONTEND_SRC}/" "${FRONTEND_DEST}/"
    log "  Frontend updated"
else
    log "  Frontend unchanged – skipping"
fi

# ---------------------------------------------------------------------------
# Step 5: Restart backend service
# ---------------------------------------------------------------------------
log "Step 5/7: Restarting ${SERVICE_NAME}"

systemctl stop "${SERVICE_NAME}"
sleep 2
systemctl start "${SERVICE_NAME}"

log "  Service restarted"

# ---------------------------------------------------------------------------
# Step 6: Health check
# ---------------------------------------------------------------------------
log "Step 6/7: Running health check"

HEALTHY=false
for i in $(seq 1 ${MAX_HEALTH_RETRIES}); do
    sleep "${HEALTH_RETRY_DELAY}"
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${HEALTH_URL}" 2>/dev/null || echo "000")
    if [ "${HTTP_CODE}" = "200" ]; then
        HEALTHY=true
        break
    fi
    warn "  Health check attempt ${i}/${MAX_HEALTH_RETRIES}: HTTP ${HTTP_CODE}"
done

if [ "${HEALTHY}" = true ]; then
    log "  Health check passed ✓"
else
    err "  Health check FAILED after ${MAX_HEALTH_RETRIES} attempts!"
    err "  Starting automatic rollback..."

    # ---------------------------------------------------------------------------
    # ROLLBACK
    # ---------------------------------------------------------------------------
    cd "${REPO_DIR}"
    git reset --hard "${PREV_COMMIT}"

    # Restore dependencies if they were changed
    if [ -f "${BACKUP_DIR}/requirements.txt" ]; then
        "${VENV_DIR}/bin/pip" install --quiet -r "${BACKUP_DIR}/requirements.txt"
    fi

    systemctl stop "${SERVICE_NAME}"
    sleep 2
    systemctl start "${SERVICE_NAME}"

    # Verify rollback
    sleep 5
    RB_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${HEALTH_URL}" 2>/dev/null || echo "000")
    if [ "${RB_CODE}" = "200" ]; then
        warn "  Rollback successful. Service is healthy at ${PREV_COMMIT:0:8}"
    else
        err "  Rollback ALSO FAILED. Manual intervention required!"
        err "  Backup at: ${BACKUP_DIR}"
        err "  Check: journalctl -u ${SERVICE_NAME} --since '5 min ago'"
    fi
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 7: Nginx reload (only if nginx configs changed)
# ---------------------------------------------------------------------------
log "Step 7/7: Checking nginx configuration"

if git diff --name-only "${PREV_COMMIT}" "${NEW_COMMIT}" | grep -q "deploy/nginx"; then
    log "  Nginx configs changed – testing and reloading..."
    if nginx -t 2>&1; then
        systemctl reload nginx
        log "  Nginx reloaded"
    else
        warn "  Nginx config test failed! Skipping reload. Check manually."
    fi
elif git diff --name-only "${PREV_COMMIT}" "${NEW_COMMIT}" | grep -q "^docs/"; then
    log "  Frontend changed – reloading nginx to clear caches..."
    systemctl reload nginx
    log "  Nginx reloaded"
else
    log "  Nginx configs unchanged – skipping"
fi

# ---------------------------------------------------------------------------
# Cleanup old backups (keep last 10)
# ---------------------------------------------------------------------------
BACKUP_BASE="/opt/klarumzug24/backups"
if [ -d "${BACKUP_BASE}" ]; then
    BACKUP_COUNT=$(ls -1d "${BACKUP_BASE}"/*/ 2>/dev/null | wc -l)
    if [ "${BACKUP_COUNT}" -gt 10 ]; then
        ls -1d "${BACKUP_BASE}"/*/ | head -n -10 | xargs rm -rf
        log "  Cleaned old backups (kept last 10)"
    fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
log "============================================"
log " Deployment successful!"
log " Commit:  ${NEW_COMMIT:0:8}"
log " Service: $(systemctl is-active ${SERVICE_NAME})"
log " Health:  ${HEALTH_URL} → 200 OK"
log "============================================"
