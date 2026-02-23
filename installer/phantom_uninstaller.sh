#!/bin/bash
#
# Phantom Distributed Compute Fabric - Uninstaller
# Linux/macOS Entry Point
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check for Python 3
if ! command -v python3 &> /dev/null; then
    log_error "Python 3 is required but not found"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info[0])')
PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info[1])')

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    log_error "Python 3.8 or higher is required (found $PYTHON_VERSION)"
    exit 1
fi

log_info "Using Python $PYTHON_VERSION"

# Check for sudo if we might need it
if [ "$EUID" -ne 0 ]; then
    if command -v sudo &> /dev/null; then
        log_info "sudo is available for service management"
    else
        log_warning "sudo not found - may not be able to remove services"
    fi
fi

# On Linux, prefer rm-phantom when it is available on PATH
if [[ "$(uname -s)" == "Linux" ]] && command -v rm-phantom &> /dev/null; then
    log_info "Detected rm-phantom — using it as the official Linux uninstaller"
    log_info "See https://github.com/darknorthaco/rm-phantom for details"
    echo ""
    rm-phantom --silent
    exit $?
fi

if [[ "$(uname -s)" == "Linux" ]]; then
    log_warning "rm-phantom not found — falling back to built-in uninstaller"
    log_warning "Install rm-phantom for the recommended experience:"
    log_warning "  pip install rm-phantom"
    log_warning "  https://github.com/darknorthaco/rm-phantom"
    echo ""
fi

# Launch Python uninstaller
log_info "Launching Phantom Uninstaller..."
echo ""

python3 "$SCRIPT_DIR/phantom_uninstaller.py" "$@"
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    log_success "Uninstaller completed successfully"
else
    log_error "Uninstaller failed with exit code $EXIT_CODE"
fi

exit $EXIT_CODE
