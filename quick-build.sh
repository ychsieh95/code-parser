#!/usr/bin/env bash

# Exit on errors, undefined variables, and failed pipelines
set -euo pipefail
trap 'fail "Script aborted at line $LINENO"' ERR

# Define color codes
BLUE='\033[0;34m'
GREEN='\033[0;32m'
ORANGE='\033[0;33m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color (Reset)

# Log function: log <level_color> <level_text> <message>
log() {
    local color="$1"
    local level="$2"
    local message="$3"
    echo -e "[${color}${level}${NC}] ${message}"
}

# Wrapper functions for cleaner syntax
info() { log "${BLUE}"   " INFO " "$1"; }
ok  () { log "${GREEN}"  "  OK  " "$1"; }
warn() { log "${ORANGE}" " WARN " "$1"; }
fail() { log "${RED}"    " FAIL " "$1"; }
note() { log "${YELLOW}" " NOTE " "$1"; }

INSTALL_DIR="${HOME}/.local/bin/code-parser"
VENV_DIR="${INSTALL_DIR}/.venv"
SERVICE_NAME="discord-bot-code-parser.service"
SERVICE_SRC="${INSTALL_DIR}/deploy/${SERVICE_NAME}"
SERVICE_DST="${HOME}/.config/systemd/user/${SERVICE_NAME}"

command -v python3   >/dev/null 2>&1 || { fail "python3 is required but not installed";  exit 1; }
command -v systemctl >/dev/null 2>&1 || { fail "systemctl is required but not installed"; exit 1; }

# quick-build.sh lives in the project root, so SCRIPT_DIR IS the project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"
info "Project root directory: $PROJECT_ROOT"

# Create the target directory and copy all files
info "Copying files to ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"

if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete \
      --exclude ".git/" \
      --exclude ".venv/" \
      --exclude "__pycache__/" \
      "${PROJECT_ROOT}/" "${INSTALL_DIR}/"
else
    warn "rsync not found, using cp fallback (stale files may remain)"
    cp -a "${PROJECT_ROOT}/." "${INSTALL_DIR}/"
fi

ok "Files copied to ${INSTALL_DIR}"

# Install dependencies and set up the virtual environment
info "Setting up the virtual environment and installing dependencies..."
if [[ ! -d "${VENV_DIR}" ]]; then
    if command -v apt >/dev/null 2>&1; then
        sudo apt install -y -qq python3-venv
    else
        note "Skipping python3-venv package install: apt not available"
    fi
    python3 -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install -r "${INSTALL_DIR}/requirements.txt"
ok "Virtual environment set up and dependencies installed"

# Set up the systemd service
info "Setting up the systemd service..."
mkdir -p "${HOME}/.config/systemd/user"
install -m 644 "${SERVICE_SRC}" "${SERVICE_DST}"
systemctl --user daemon-reload
systemctl --user enable --now "${SERVICE_NAME}"
ok "Systemd service set up and started"
