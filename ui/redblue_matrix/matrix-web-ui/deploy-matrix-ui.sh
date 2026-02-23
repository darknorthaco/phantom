#!/bin/bash
# Phantom Matrix UI Deployment Script
# Deploys the Matrix-style interface to web server

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔋 Phantom Matrix UI Deployment${NC}"
echo "=================================="

# Configuration
DEFAULT_WEB_DIR="/var/www/html"
DEFAULT_PORT="3000"
DEFAULT_PHANTOM_HOST="192.168.1.103"
DEFAULT_PHANTOM_PORT="8765"

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${CYAN}ℹ${NC} $1"
}

# Function to check if running as root
check_root() {
    if [ "$EUID" -eq 0 ]; then
        print_warning "Running as root - be careful with file permissions"
        return 0
    else
        return 1
    fi
}

# Function to detect web server
detect_web_server() {
    if command -v nginx &> /dev/null; then
        echo "nginx"
    elif command -v apache2 &> /dev/null || command -v httpd &> /dev/null; then
        echo "apache"
    elif command -v python3 &> /dev/null; then
        echo "python"
    else
        echo "none"
    fi
}

# Function to get web directory
get_web_directory() {
    local web_server=$1
    
    case $web_server in
        "nginx")
            if [ -d "/var/www/html" ]; then
                echo "/var/www/html"
            elif [ -d "/usr/share/nginx/html" ]; then
                echo "/usr/share/nginx/html"
            else
                echo "/var/www/html"
            fi
            ;;
        "apache")
            if [ -d "/var/www/html" ]; then
                echo "/var/www/html"
            elif [ -d "/var/www" ]; then
                echo "/var/www"
            else
                echo "/var/www/html"
            fi
            ;;
        *)
            echo "$DEFAULT_WEB_DIR"
            ;;
    esac
}

# Function to configure Phantom connection
configure_phantom_connection() {
    local phantom_host=${1:-$DEFAULT_PHANTOM_HOST}
    local phantom_port=${2:-$DEFAULT_PHANTOM_PORT}
    
    print_info "Configuring Phantom connection: ws://${phantom_host}:${phantom_port}"
    
    # Update WebSocket URL in phantom-interface.js
    sed -i.bak "s|ws://192.168.1.103:8765|ws://${phantom_host}:${phantom_port}|g" phantom-interface.js
    
    if [ $? -eq 0 ]; then
        print_status "Phantom connection configured"
        rm -f phantom-interface.js.bak
    else
        print_error "Failed to configure Phantom connection"
        if [ -f phantom-interface.js.bak ]; then
            mv phantom-interface.js.bak phantom-interface.js
        fi
        return 1
    fi
}

# Function to deploy to web server
deploy_to_web_server() {
    local web_dir=$1
    local target_dir="$web_dir/phantom-matrix"
    
    print_info "Deploying to: $target_dir"
    
    # Create target directory
    if check_root; then
        mkdir -p "$target_dir"
    else
        sudo mkdir -p "$target_dir"
    fi
    
    # Copy files
    if check_root; then
        cp -r ./* "$target_dir/"
        chown -R www-data:www-data "$target_dir" 2>/dev/null || \
        chown -R nginx:nginx "$target_dir" 2>/dev/null || \
        chown -R apache:apache "$target_dir" 2>/dev/null || \
        print_warning "Could not set web server ownership"
    else
        sudo cp -r ./* "$target_dir/"
        sudo chown -R www-data:www-data "$target_dir" 2>/dev/null || \
        sudo chown -R nginx:nginx "$target_dir" 2>/dev/null || \
        sudo chown -R apache:apache "$target_dir" 2>/dev/null || \
        print_warning "Could not set web server ownership"
    fi
    
    print_status "Files deployed to $target_dir"
}

# Function to start Python web server
start_python_server() {
    local port=${1:-$DEFAULT_PORT}
    
    print_info "Starting Python web server on port $port"
    
    # Check if port is available
    if netstat -ln 2>/dev/null | grep -q ":$port "; then
        print_error "Port $port is already in use"
        return 1
    fi
    
    # Start server in background
    python3 -m http.server $port > /dev/null 2>&1 &
    local server_pid=$!
    
    # Wait a moment and check if server started
    sleep 2
    if kill -0 $server_pid 2>/dev/null; then
        print_status "Python web server started (PID: $server_pid)"
        echo $server_pid > .matrix-ui-server.pid
        print_info "Access the interface at: http://localhost:$port"
        print_info "Stop server with: kill $server_pid"
        return 0
    else
        print_error "Failed to start Python web server"
        return 1
    fi
}

# Function to test deployment
test_deployment() {
    local url=$1
    
    print_info "Testing deployment at: $url"
    
    if command -v curl &> /dev/null; then
        if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "200"; then
            print_status "Deployment test successful"
            return 0
        else
            print_error "Deployment test failed - check web server configuration"
            return 1
        fi
    else
        print_warning "curl not available - cannot test deployment automatically"
        print_info "Manually test by opening: $url"
        return 0
    fi
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --web-dir DIR          Web server directory (default: auto-detect)"
    echo "  --port PORT            Port for Python server (default: $DEFAULT_PORT)"
    echo "  --phantom-host HOST    Phantom server host (default: $DEFAULT_PHANTOM_HOST)"
    echo "  --phantom-port PORT    Phantom server port (default: $DEFAULT_PHANTOM_PORT)"
    echo "  --python-server        Use Python HTTP server instead of web server"
    echo "  --test-only           Only test existing deployment"
    echo "  --help                Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Auto-deploy to detected web server"
    echo "  $0 --python-server                   # Use Python HTTP server"
    echo "  $0 --web-dir /custom/web/dir         # Deploy to custom directory"
    echo "  $0 --phantom-host 192.168.1.100     # Connect to different Phantom server"
}

# Main deployment function
main() {
    local web_dir=""
    local port="$DEFAULT_PORT"
    local phantom_host="$DEFAULT_PHANTOM_HOST"
    local phantom_port="$DEFAULT_PHANTOM_PORT"
    local use_python_server=false
    local test_only=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --web-dir)
                web_dir="$2"
                shift 2
                ;;
            --port)
                port="$2"
                shift 2
                ;;
            --phantom-host)
                phantom_host="$2"
                shift 2
                ;;
            --phantom-port)
                phantom_port="$2"
                shift 2
                ;;
            --python-server)
                use_python_server=true
                shift
                ;;
            --test-only)
                test_only=true
                shift
                ;;
            --help)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Test only mode
    if [ "$test_only" = true ]; then
        if [ "$use_python_server" = true ]; then
            test_deployment "http://localhost:$port"
        else
            test_deployment "http://localhost/phantom-matrix"
        fi
        exit $?
    fi
    
    # Check if we're in the matrix-ui directory
    if [ ! -f "index.html" ] || [ ! -f "phantom-interface.js" ]; then
        print_error "Must run from matrix-ui directory"
        exit 1
    fi
    
    # Configure Phantom connection
    configure_phantom_connection "$phantom_host" "$phantom_port"
    
    if [ "$use_python_server" = true ]; then
        # Use Python HTTP server
        start_python_server "$port"
        if [ $? -eq 0 ]; then
            test_deployment "http://localhost:$port"
        fi
    else
        # Deploy to web server
        local web_server=$(detect_web_server)
        print_info "Detected web server: $web_server"
        
        if [ -z "$web_dir" ]; then
            web_dir=$(get_web_directory "$web_server")
        fi
        
        if [ "$web_server" = "none" ]; then
            print_warning "No web server detected, falling back to Python server"
            start_python_server "$port"
            if [ $? -eq 0 ]; then
                test_deployment "http://localhost:$port"
            fi
        else
            deploy_to_web_server "$web_dir"
            if [ $? -eq 0 ]; then
                test_deployment "http://localhost/phantom-matrix"
            fi
        fi
    fi
    
    echo ""
    echo -e "${PURPLE}🔋 Matrix Interface Deployment Complete${NC}"
    echo "========================================"
    
    if [ "$use_python_server" = true ]; then
        echo -e "${CYAN}Access URL:${NC} http://localhost:$port"
        echo -e "${CYAN}Stop Server:${NC} kill \$(cat .matrix-ui-server.pid)"
    else
        echo -e "${CYAN}Access URL:${NC} http://localhost/phantom-matrix"
        echo -e "${CYAN}Web Directory:${NC} $web_dir/phantom-matrix"
    fi
    
    echo -e "${CYAN}Phantom Server:${NC} ws://$phantom_host:$phantom_port"
    echo ""
    echo -e "${GREEN}Welcome to the Matrix, Neo. 🕶️${NC}"
}

# Run main function with all arguments
main "$@"