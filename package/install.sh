#!/bin/bash
# Professional installation wizard for Linux

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

show_banner() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║              Phantom Installation Wizard                 ║"
    echo "║                    Linux Edition                        ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

check_requirements() {
    echo -e "${BLUE}🔍 Checking system requirements...${NC}"

    # Check OS
    if [ ! -f /etc/os-release ]; then
        echo -e "${RED}❌ Unsupported OS${NC}"
        exit 1
    fi

    # shellcheck source=/dev/null
    . /etc/os-release
    echo "OS: ${PRETTY_NAME:-$(uname -s)}"

    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 required${NC}"
        exit 1
    fi

    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    echo "Python: $PYTHON_VERSION"

    if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)"; then
        echo -e "${GREEN}✅ Python 3.8+ found${NC}"
    else
        echo -e "${RED}❌ Python 3.8+ required${NC}"
        exit 1
    fi

    # Check ports
    check_ports_free

    echo -e "${GREEN}✅ System requirements met${NC}"
}

check_ports_free() {
    local ports=(8765 8082 8080)
    local in_use=()

    for port in "${ports[@]}"; do
        if lsof -i ":$port" &> /dev/null || ss -tln | grep -q ":$port "; then
            in_use+=("$port")
        fi
    done

    if [ ${#in_use[@]} -gt 0 ]; then
        echo -e "${YELLOW}⚠️  Ports in use: ${in_use[*]}${NC}"
        echo "These ports will be freed during installation if needed."
    fi
}

select_installation_type() {
    echo -e "${BLUE}📦 Installation Type:${NC}"
    echo "1. Complete Installation (Recommended)"
    echo "   - Phantom Core"
    echo "   - RedBlue Matrix UI"
    echo "   - All components"
    echo
    echo "2. Core Only"
    echo "   - Phantom Core only"
    echo "   - No UI components"
    echo
    echo "3. Custom Installation"
    echo "   - Choose components manually"

    while true; do
        read -r -p "Select installation type [1-3]: " choice
        case $choice in
            1) INSTALL_TYPE="complete"; break ;;
            2) INSTALL_TYPE="core"; break ;;
            3) INSTALL_TYPE="custom"; break ;;
            *) echo "Invalid choice. Please select 1-3." ;;
        esac
    done
}

custom_component_selection() {
    if [ "$INSTALL_TYPE" != "custom" ]; then
        return
    fi

    echo -e "${BLUE}🛠️  Component Selection:${NC}"

    # Core is always required
    echo "✓ phantom_core (required)"

    # UI Components
    read -r -p "Install RedBlue Matrix UI? [Y/n]: " -n 1 ui_choice
    echo
    case $ui_choice in
        n|N) INSTALL_UI=false ;;
        *) INSTALL_UI=true ;;
    esac

    # Examples
    read -r -p "Install UI examples? [y/N]: " -n 1 examples_choice
    echo
    case $examples_choice in
        y|Y) INSTALL_EXAMPLES=true ;;
        *) INSTALL_EXAMPLES=false ;;
    esac
}

create_installation_directory() {
    echo -e "${BLUE}📁 Creating installation directory...${NC}"

    if [ -d "$INSTALL_DIR" ]; then
        echo "Installation directory exists. Backing up..."
        backup_dir="${INSTALL_DIR}.backup.$(date +%Y%m%d_%H%M%S)"
        mv "$INSTALL_DIR" "$backup_dir"
        echo "Backup created: $backup_dir"
    fi

    mkdir -p "$INSTALL_DIR"
    echo -e "${GREEN}✅ Installation directory created: $INSTALL_DIR${NC}"
}

install_components() {
    echo -e "${BLUE}🚀 Installing components...${NC}"

    # Install core
    if [ -d "$SCRIPT_DIR/phantom_core" ]; then
        cp -r "$SCRIPT_DIR/phantom_core"/* "$INSTALL_DIR/"
        echo "✓ Installed phantom_core"
    else
        echo -e "${RED}❌ phantom_core not found in package${NC}"
        exit 1
    fi

    # Install UI based on selection
    if [ "$INSTALL_TYPE" = "complete" ] || [ "$INSTALL_UI" = true ]; then
        if [ -d "$SCRIPT_DIR/ui" ]; then
            cp -r "$SCRIPT_DIR/ui" "$INSTALL_DIR/"
            echo "✓ Installed UI components"
        fi
    fi

    # Install examples
    if [ "$INSTALL_TYPE" = "complete" ] || [ "$INSTALL_EXAMPLES" = true ]; then
        if [ -d "$SCRIPT_DIR/ui/examples" ]; then
            cp -r "$SCRIPT_DIR/ui/examples" "$INSTALL_DIR/ui/"
            echo "✓ Installed UI examples"
        fi
    fi

    # Install docs
    if [ -d "$SCRIPT_DIR/docs" ]; then
        cp -r "$SCRIPT_DIR/docs" "$INSTALL_DIR/"
        echo "✓ Installed documentation"
    fi

    echo -e "${GREEN}✅ Components installed${NC}"
}

setup_python_environment() {
    echo -e "${BLUE}🐍 Setting up Python environment...${NC}"

    cd "$INSTALL_DIR"

    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        echo "✓ Created virtual environment"
    fi

    # Activate and install requirements
    source venv/bin/activate
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        echo "✓ Installed Python dependencies"
    fi

    echo -e "${GREEN}✅ Python environment ready${NC}"
}

create_service() {
    echo -e "${BLUE}⚙️  Setting up system service...${NC}"

    # Create service file
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Phantom Distributed Computing Platform
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/run_integrated_phantom.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd and enable service
    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"

    echo -e "${GREEN}✅ Service created and enabled${NC}"
}

create_desktop_shortcuts() {
    echo -e "${BLUE}🖥️  Creating desktop shortcuts...${NC}"

    # Create desktop file for UI
    local desktop_file="/usr/share/applications/phantom.desktop"
    cat > "$desktop_file" << EOF
[Desktop Entry]
Name=Phantom
Comment=Distributed Computing Platform
Exec=xdg-open http://localhost:8080
Icon=applications-system
Terminal=false
Type=Application
Categories=Development;System;
EOF

    echo -e "${GREEN}✅ Desktop shortcuts created${NC}"
}

start_service() {
    echo -e "${BLUE}▶️  Starting Phantom service...${NC}"

    systemctl start "$SERVICE_NAME"

    # Wait a moment for startup
    sleep 3

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo -e "${GREEN}✅ Phantom service started${NC}"
    else
        echo -e "${YELLOW}⚠️  Service may have failed to start. Check logs: journalctl -u $SERVICE_NAME${NC}"
    fi
}

show_completion_message() {
    echo
    echo -e "${GREEN}🎉 Installation completed successfully!${NC}"
    echo
    echo "Phantom has been installed to: $INSTALL_DIR"
    echo
    echo "Service Status:"
    systemctl status "$SERVICE_NAME" --no-pager -l | head -10
    echo
    echo "Access Points:"
    echo "• Web UI: http://localhost:8080"
    echo "• API: http://localhost:8765"
    echo "• Socket: localhost:8082"
    echo
    echo "Management:"
    echo "• Start: sudo systemctl start $SERVICE_NAME"
    echo "• Stop: sudo systemctl stop $SERVICE_NAME"
    echo "• Restart: sudo systemctl restart $SERVICE_NAME"
    echo "• Logs: journalctl -u $SERVICE_NAME -f"
    echo
    echo "Documentation: $INSTALL_DIR/docs/"
    echo "Uninstall: sudo $SCRIPT_DIR/uninstall.sh"
}

main() {
    # Check if running as root
    if [ "$(id -u)" -ne 0 ]; then
        echo -e "${RED}❌ This script must be run as root. Use: sudo bash $0${NC}"
        exit 1
    fi

    show_banner
    check_requirements
    select_installation_type
    custom_component_selection
    create_installation_directory
    install_components
    setup_python_environment
    create_service
    create_desktop_shortcuts
    start_service
    show_completion_message
}

# Run main function
main "$@"