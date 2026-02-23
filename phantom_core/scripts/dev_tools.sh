#!/bin/bash
# Phantom Distributed Compute Fabric - Development Tools
# Comprehensive development and debugging utilities

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}🛠️  Phantom Development Tools${NC}"
echo "=================================="

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

# Function to show system status
show_system_status() {
    echo -e "\n${BLUE}📊 System Status${NC}"
    echo "----------------------------------------"
    
    # Check controller
    if curl -s http://localhost:5000/health > /dev/null 2>&1; then
        print_status "Controller running on port 5000"
        
        # Get worker count
        local workers=$(curl -s http://localhost:5000/workers | jq '.workers | length' 2>/dev/null || echo "unknown")
        print_info "Active workers: $workers"
    else
        print_warning "Controller not running"
    fi
    
    # Check socket server
    if netstat -ln 2>/dev/null | grep -q ":8765"; then
        print_status "Socket server running on port 8765"
    else
        print_warning "Socket server not running"
    fi
    
    # Check system resources
    echo -e "\n${PURPLE}💻 System Resources${NC}"
    echo "CPU Usage: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)%"
    echo "Memory Usage: $(free | grep Mem | awk '{printf("%.1f%%", $3/$2 * 100.0)}')"
    
    # Check GPU status
    if command -v nvidia-smi &> /dev/null; then
        echo -e "\n${PURPLE}🎮 GPU Status${NC}"
        nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits | \
        while IFS=, read -r name memory_used memory_total utilization; do
            echo "GPU: $name | Memory: ${memory_used}MB/${memory_total}MB | Utilization: ${utilization}%"
        done
    fi
}

# Function to run benchmarks
run_benchmarks() {
    echo -e "\n${BLUE}⚡ Performance Benchmarks${NC}"
    echo "----------------------------------------"
    
    if [ ! -f "scripts/benchmark.py" ]; then
        print_warning "Creating benchmark script..."
        cat > scripts/benchmark.py << 'EOF'
#!/usr/bin/env python3
import time
import requests
import json
import statistics

def benchmark_controller():
    """Benchmark controller response times"""
    print("🔍 Benchmarking Controller...")
    
    times = []
    for i in range(10):
        start = time.time()
        try:
            response = requests.get("http://localhost:5000/health", timeout=5)
            if response.status_code == 200:
                times.append((time.time() - start) * 1000)
        except:
            print(f"Request {i+1} failed")
    
    if times:
        print(f"Average response time: {statistics.mean(times):.2f}ms")
        print(f"Min: {min(times):.2f}ms, Max: {max(times):.2f}ms")
    else:
        print("All requests failed")

def benchmark_task_submission():
    """Benchmark task submission"""
    print("\n📤 Benchmarking Task Submission...")
    
    test_task = {
        "id": f"benchmark_task_{int(time.time())}",
        "type": "compute",
        "data": {"operation": "test", "size": 100}
    }
    
    times = []
    for i in range(5):
        start = time.time()
        try:
            response = requests.post(
                "http://localhost:5000/submit_task",
                json=test_task,
                timeout=10
            )
            if response.status_code == 200:
                times.append((time.time() - start) * 1000)
        except:
            print(f"Task submission {i+1} failed")
    
    if times:
        print(f"Average submission time: {statistics.mean(times):.2f}ms")
    else:
        print("All submissions failed")

if __name__ == "__main__":
    benchmark_controller()
    benchmark_task_submission()
EOF
    fi
    
    python3 scripts/benchmark.py
}

# Function to monitor logs
monitor_logs() {
    echo -e "\n${BLUE}📋 Log Monitor${NC}"
    echo "----------------------------------------"
    
    local log_files=("phantom_controller.log" "phantom_worker.log" "phantom_socket.log")
    
    for log_file in "${log_files[@]}"; do
        if [ -f "logs/$log_file" ]; then
            echo -e "\n${CYAN}📄 $log_file (last 10 lines)${NC}"
            tail -n 10 "logs/$log_file"
        fi
    done
    
    print_info "Use 'tail -f logs/*.log' to monitor logs in real-time"
}

# Function to debug worker connections
debug_workers() {
    echo -e "\n${BLUE}🔧 Worker Debug Information${NC}"
    echo "----------------------------------------"
    
    if curl -s http://localhost:5000/health > /dev/null 2>&1; then
        echo "Fetching worker information..."
        
        local workers_json=$(curl -s http://localhost:5000/workers)
        echo "$workers_json" | jq '.' 2>/dev/null || echo "$workers_json"
        
        # Test worker connectivity
        echo -e "\n${CYAN}🔗 Testing Worker Connectivity${NC}"
        echo "$workers_json" | jq -r '.workers[]?.endpoint' 2>/dev/null | while read -r endpoint; do
            if [ ! -z "$endpoint" ]; then
                if curl -s "$endpoint/health" > /dev/null 2>&1; then
                    print_status "Worker at $endpoint is responsive"
                else
                    print_warning "Worker at $endpoint is not responding"
                fi
            fi
        done
    else
        print_error "Controller not running - cannot debug workers"
    fi
}

# Function to check network connectivity
check_network() {
    echo -e "\n${BLUE}🌐 Network Connectivity Check${NC}"
    echo "----------------------------------------"
    
    # Check local ports
    local ports=("5000" "6000" "6001" "6002" "8765")
    
    for port in "${ports[@]}"; do
        if netstat -ln 2>/dev/null | grep -q ":$port"; then
            print_status "Port $port is in use"
        else
            print_info "Port $port is available"
        fi
    done
    
    # Check cross-machine connectivity (if configured)
    local remote_ips=("192.168.1.103" "192.168.1.100")  # Example IPs
    
    echo -e "\n${CYAN}🔗 Cross-machine Connectivity${NC}"
    for ip in "${remote_ips[@]}"; do
        if ping -c 1 -W 2 "$ip" > /dev/null 2>&1; then
            print_status "Can reach $ip"
        else
            print_warning "Cannot reach $ip"
        fi
    done
}

# Function to validate configuration
validate_config() {
    echo -e "\n${BLUE}⚙️  Configuration Validation${NC}"
    echo "----------------------------------------"
    
    # Check required files
    local required_files=(
        "run.py"
        "phantom_core/controller_api.py"
        "linux-worker/linux_worker/worker.py"
        "socket_infrastructure/hybrid_socket_server.py"
    )
    
    for file in "${required_files[@]}"; do
        if [ -f "$file" ]; then
            print_status "$file exists"
        else
            print_error "$file missing"
        fi
    done
    
    # Check Python dependencies
    echo -e "\n${CYAN}🐍 Python Dependencies${NC}"
    local python_deps=("flask" "requests" "websockets" "psutil" "pyyaml")
    
    for dep in "${python_deps[@]}"; do
        if python3 -c "import $dep" 2>/dev/null; then
            print_status "$dep available"
        else
            print_warning "$dep not installed"
        fi
    done
    
    # Validate JSON configs
    echo -e "\n${CYAN}📄 Configuration Files${NC}"
    find . -name "*.json" -type f | while read -r json_file; do
        if python3 -c "import json; json.load(open('$json_file'))" 2>/dev/null; then
            print_status "$json_file is valid JSON"
        else
            print_error "$json_file has invalid JSON"
        fi
    done
}

# Function to clean up development artifacts
cleanup_dev() {
    echo -e "\n${BLUE}🧹 Development Cleanup${NC}"
    echo "----------------------------------------"
    
    # Remove Python cache
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    print_status "Removed Python cache files"
    
    # Clean log files
    if [ -d "logs" ]; then
        find logs -name "*.log" -size +10M -delete 2>/dev/null || true
        print_status "Cleaned large log files"
    fi
    
    # Clean test artifacts
    if [ -d "test_results" ]; then
        rm -rf test_results
        print_status "Removed test results"
    fi
    
    # Clean temporary files
    find . -name "*.tmp" -delete 2>/dev/null || true
    find . -name "*.pid" -delete 2>/dev/null || true
    print_status "Removed temporary files"
}

# Function to show help
show_help() {
    echo -e "\n${BLUE}📖 Available Commands${NC}"
    echo "----------------------------------------"
    echo "status      - Show system status and resource usage"
    echo "benchmark   - Run performance benchmarks"
    echo "logs        - Monitor system logs"
    echo "workers     - Debug worker connections"
    echo "network     - Check network connectivity"
    echo "config      - Validate configuration files"
    echo "cleanup     - Clean up development artifacts"
    echo "help        - Show this help message"
    echo ""
    echo "Usage: $0 <command>"
}

# Main execution
main() {
    case "${1:-help}" in
        "status")
            show_system_status
            ;;
        "benchmark")
            run_benchmarks
            ;;
        "logs")
            monitor_logs
            ;;
        "workers")
            debug_workers
            ;;
        "network")
            check_network
            ;;
        "config")
            validate_config
            ;;
        "cleanup")
            cleanup_dev
            ;;
        "help"|*)
            show_help
            ;;
    esac
}

# Create required directories
mkdir -p logs scripts

# Run main function
main "$@"