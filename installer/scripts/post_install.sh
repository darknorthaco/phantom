#!/bin/bash
# Phantom Post-Installation Script
# Linux/Mac

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$(dirname "$SCRIPT_DIR")"

echo "🔧 Phantom Post-Installation Setup"
echo "==================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to set permissions
set_permissions() {
    echo "Setting file permissions..."
    
    # Make scripts executable
    find "$INSTALL_DIR" -name "*.sh" -type f -exec chmod +x {} \;
    
    # Set directory permissions
    chmod -R 755 "$INSTALL_DIR/config"
    chmod -R 755 "$INSTALL_DIR/logs"
    chmod -R 755 "$INSTALL_DIR/data"
    
    print_success "Permissions set"
}

# Function to create systemd service
create_systemd_service() {
    echo "Creating systemd service..."
    
    # Create PID directory
    PID_DIR="$INSTALL_DIR/run"
    mkdir -p "$PID_DIR"
    
    # Service file location (temporary, will be copied with sudo)
    SERVICE_FILE="$INSTALL_DIR/phantom.service"
    
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Phantom Distributed Compute Controller
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venvs/phantom/bin/python $INSTALL_DIR/run_integrated_phantom.py
ExecStop=/bin/kill \$MAINPID
PIDFile=$PID_DIR/phantom.pid
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    print_success "Systemd service file created at $SERVICE_FILE"
    echo ""
    echo "  To install the service, run these commands:"
    echo "    sudo cp $SERVICE_FILE /etc/systemd/system/phantom.service"
    echo "    sudo systemctl daemon-reload"
    echo "    sudo systemctl enable phantom.service"
    echo "    sudo systemctl start phantom.service"
}

# Function to create convenience scripts
create_convenience_scripts() {
    echo "Creating convenience scripts..."
    
    # Start script
    cat > "$INSTALL_DIR/start_phantom.sh" << 'EOF'
#!/bin/bash
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$INSTALL_DIR/venvs/phantom/bin/activate"
cd "$INSTALL_DIR"
python run_integrated_phantom.py
EOF
    chmod +x "$INSTALL_DIR/start_phantom.sh"
    
    # Stop script (using PID file for safe process termination)
    cat > "$INSTALL_DIR/stop_phantom.sh" << 'EOF'
#!/bin/bash
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$INSTALL_DIR/run/phantom.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Stopping Phantom (PID: $PID)..."
        kill "$PID"
        sleep 2
        # Force kill if still running
        if kill -0 "$PID" 2>/dev/null; then
            echo "Force stopping..."
            kill -9 "$PID"
        fi
        rm -f "$PID_FILE"
        echo "✅ Phantom stopped"
    else
        echo "⚠️  PID file exists but process not running"
        rm -f "$PID_FILE"
    fi
else
    echo "❌ Phantom not running (no PID file)"
fi
EOF
    chmod +x "$INSTALL_DIR/stop_phantom.sh"
    
    # Status script
    cat > "$INSTALL_DIR/status_phantom.sh" << 'EOF'
#!/bin/bash
if pgrep -f "run_integrated_phantom.py" > /dev/null; then
    echo "✅ Phantom is running"
    curl -s http://localhost:8080/health || echo "  ⚠️ Health check failed"
else
    echo "❌ Phantom is not running"
fi
EOF
    chmod +x "$INSTALL_DIR/status_phantom.sh"
    
    print_success "Convenience scripts created"
}

# Main execution
echo "Install directory: $INSTALL_DIR"
echo ""

set_permissions
create_systemd_service
create_convenience_scripts

echo ""
echo "==================================="
print_success "Post-installation complete!"
echo "==================================="
echo ""
echo "📋 Next steps:"
echo "  1. Install systemd service (optional, requires sudo)"
echo "  2. Install Python dependencies:"
echo "     $INSTALL_DIR/venvs/phantom/bin/pip install -r requirements.txt"
echo "  3. Start Phantom:"
echo "     $INSTALL_DIR/start_phantom.sh"
echo ""
