#!/bin/bash
# Professional uninstaller with complete verification for Linux

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
INSTALL_DIR="/opt/phantom"
SERVICE_NAME="phantom"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
DESKTOP_FILE="/usr/share/applications/phantom.desktop"

show_banner() {
    echo -e "${RED}"
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║              Phantom Uninstallation Wizard              ║"
    echo "║                    Linux Edition                        ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

confirm_uninstall() {
    echo -e "${YELLOW}⚠️  WARNING: You are about to completely remove Phantom${NC}"
    echo
    echo "This will:"
    echo "• Stop and disable the Phantom service"
    echo "• Terminate all running Phantom processes"
    echo "• Remove all Phantom files and directories"
    echo "• Remove desktop shortcuts and menu entries"
    echo "• Free up network ports (8765, 8082, 8080)"
    echo
    echo -e "${RED}This action cannot be undone!${NC}"
    echo

    while true; do
        read -r -p "Are you sure you want to uninstall Phantom? [y/N]: " choice
        case $choice in
            y|Y) break ;;
            n|N|"") echo "Uninstall cancelled."; exit 0 ;;
            *) echo "Please answer y or n." ;;
        esac
    done
}

check_running_service() {
    echo -e "${BLUE}🔍 Checking for running services...${NC}"

    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        echo "Found active Phantom service"
        return 0
    else
        echo "No active Phantom service found"
        return 1
    fi
}

stop_and_remove_service() {
    echo -e "${BLUE}🛑 Stopping and removing service...${NC}"

    # Stop service if running
    if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        systemctl stop "$SERVICE_NAME"
        echo "✓ Stopped Phantom service"
    fi

    # Disable service
    if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
        systemctl disable "$SERVICE_NAME"
        echo "✓ Disabled Phantom service"
    fi

    # Remove service file
    if [ -f "$SERVICE_FILE" ]; then
        rm -f "$SERVICE_FILE"
        systemctl daemon-reload
        echo "✓ Removed service file"
    fi

    echo -e "${GREEN}✅ Service cleanup complete${NC}"
}

kill_processes() {
    echo -e "${BLUE}🔪 Terminating Phantom processes...${NC}"

    # Use the enhanced process cleanup from rm-phantom assimilation
    if [ -f "$SCRIPT_DIR/installer/modules/process_cleanup.py" ]; then
        cd "$SCRIPT_DIR"
        python3 -c "
import sys
sys.path.insert(0, 'installer/modules')
from process_cleanup import ProcessCleanup
cleanup = ProcessCleanup()
cleanup.cleanup()
"
        echo "✓ Used enhanced process cleanup"
    else
        # Fallback to manual process killing
        echo "Enhanced cleanup not available, using fallback..."

        # Find and kill phantom processes
        pids=$(pgrep -f phantom 2>/dev/null || true)
        if [ -n "$pids" ]; then
            echo "Found phantom PIDs: $pids"
            # Graceful termination
            kill -TERM $pids 2>/dev/null || true
            sleep 5
            # Force kill survivors
            survivors=$(pgrep -f phantom 2>/dev/null || true)
            if [ -n "$survivors" ]; then
                kill -KILL $survivors 2>/dev/null || true
            fi
            echo "✓ Terminated phantom processes"
        else
            echo "No phantom processes found"
        fi
    fi

    echo -e "${GREEN}✅ Process cleanup complete${NC}"
}

verify_ports_free() {
    echo -e "${BLUE}🔍 Verifying ports are free...${NC}"

    local ports=(8765 8082 8080)
    local still_in_use=()

    for port in "${ports[@]}"; do
        if lsof -i ":$port" &> /dev/null || ss -tln | grep -q ":$port "; then
            still_in_use+=("$port")
        fi
    done

    if [ ${#still_in_use[@]} -gt 0 ]; then
        echo -e "${YELLOW}⚠️  Ports still in use: ${still_in_use[*]}${NC}"
        echo "Some processes may still be using these ports."
        return 1
    else
        echo -e "${GREEN}✅ All phantom ports are free${NC}"
        return 0
    fi
}

remove_files() {
    echo -e "${BLUE}🧹 Removing Phantom files...${NC}"

    if [ -d "$INSTALL_DIR" ]; then
        rm -rf "$INSTALL_DIR"
        echo "✓ Removed installation directory: $INSTALL_DIR"
    else
        echo "Installation directory not found: $INSTALL_DIR"
    fi

    # Remove any remaining phantom directories
    for dir in "/usr/local/phantom" "/home/$(whoami)/phantom" "/home/$(whoami)/.phantom"; do
        if [ -d "$dir" ]; then
            rm -rf "$dir"
            echo "✓ Removed additional directory: $dir"
        fi
    done

    echo -e "${GREEN}✅ File cleanup complete${NC}"
}

remove_desktop_shortcuts() {
    echo -e "${BLUE}🖥️  Removing desktop shortcuts...${NC}"

    if [ -f "$DESKTOP_FILE" ]; then
        rm -f "$DESKTOP_FILE"
        echo "✓ Removed desktop shortcut"
    fi

    # Remove from user directories
    for user_dir in "/home"/*; do
        if [ -d "$user_dir" ]; then
            desktop_dir="$user_dir/Desktop"
            if [ -d "$desktop_dir" ]; then
                find "$desktop_dir" -name "*phantom*" -type f -delete 2>/dev/null || true
            fi
        fi
    done

    echo -e "${GREEN}✅ Desktop cleanup complete${NC}"
}

remove_packages() {
    echo -e "${BLUE}📦 Checking for installed packages...${NC}"

    # Detect package manager
    if command -v dpkg &> /dev/null; then
        # Debian/Ubuntu
        phantom_pkgs=$(dpkg -l | awk '/phantom/ {print $2}' || true)
        if [ -n "$phantom_pkgs" ]; then
            echo "Found phantom packages: $phantom_pkgs"
            apt-get remove --purge -y $phantom_pkgs
            echo "✓ Removed phantom packages"
        fi
    elif command -v rpm &> /dev/null; then
        # RHEL/CentOS/Fedora
        phantom_pkgs=$(rpm -qa | grep phantom || true)
        if [ -n "$phantom_pkgs" ]; then
            echo "Found phantom packages: $phantom_pkgs"
            yum remove -y $phantom_pkgs || dnf remove -y $phantom_pkgs
            echo "✓ Removed phantom packages"
        fi
    fi

    echo -e "${GREEN}✅ Package cleanup complete${NC}"
}

final_verification() {
    echo -e "${BLUE}🔍 Performing final verification...${NC}"

    local issues=0

    # Check for remaining processes
    if pgrep -f phantom &> /dev/null; then
        echo -e "${YELLOW}⚠️  Warning: Some phantom processes still running${NC}"
        issues=$((issues + 1))
    fi

    # Check for remaining files
    if [ -d "$INSTALL_DIR" ]; then
        echo -e "${YELLOW}⚠️  Warning: Installation directory still exists${NC}"
        issues=$((issues + 1))
    fi

    # Check ports
    if ! verify_ports_free; then
        issues=$((issues + 1))
    fi

    if [ $issues -eq 0 ]; then
        echo -e "${GREEN}✅ Final verification passed - clean uninstall${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  Final verification found $issues issue(s)${NC}"
        return 1
    fi
}

show_completion_message() {
    echo
    if final_verification; then
        echo -e "${GREEN}🎉 Uninstallation completed successfully!${NC}"
        echo
        echo "Phantom has been completely removed from your system."
        echo
        echo "What was removed:"
        echo "• All Phantom files and directories"
        echo "• System service and configuration"
        echo "• Desktop shortcuts and menu entries"
        echo "• Running processes and freed ports"
        echo
        echo "Your system is clean and ready for a fresh installation if needed."
    else
        echo -e "${YELLOW}⚠️  Uninstallation completed with warnings${NC}"
        echo
        echo "Phantom has been mostly removed, but some components may remain."
        echo "Check the warnings above and clean up manually if needed."
        echo
        echo "For help with manual cleanup, see the documentation."
    fi
}

main() {
    # Check if running as root
    if [ "$(id -u)" -ne 0 ]; then
        echo -e "${RED}❌ This script must be run as root. Use: sudo bash $0${NC}"
        exit 1
    fi

    show_banner
    confirm_uninstall

    # Perform uninstallation steps
    check_running_service
    stop_and_remove_service
    kill_processes
    verify_ports_free
    remove_files
    remove_desktop_shortcuts
    remove_packages

    show_completion_message
}

# Run main function
main "$@"