#!/bin/bash
# Phantom Distributed Compute Fabric - System Monitor
# Real-time monitoring and health checking

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
REFRESH_INTERVAL=5
LOG_FILE="logs/monitor.log"
ALERT_THRESHOLD_CPU=80
ALERT_THRESHOLD_MEMORY=85
ALERT_THRESHOLD_GPU=90

# Create logs directory
mkdir -p logs

echo -e "${BLUE}📊 Phantom System Monitor${NC}"
echo "================================"
echo "Press Ctrl+C to exit"
echo ""

# Function to log with timestamp
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOG_FILE"
}

# Function to get system metrics
get_system_metrics() {
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1 | cut -d',' -f1)
    local memory_info=$(free | grep Mem)
    local memory_total=$(echo $memory_info | awk '{print $2}')
    local memory_used=$(echo $memory_info | awk '{print $3}')
    local memory_percent=$(echo "scale=1; $memory_used * 100 / $memory_total" | bc 2>/dev/null || echo "0")
    
    echo "$cpu_usage,$memory_percent"
}

# Function to get GPU metrics
get_gpu_metrics() {
    if command -v nvidia-smi &> /dev/null; then
        nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits 2>/dev/null || echo "N/A,N/A,N/A,N/A"
    else
        echo "N/A,N/A,N/A,N/A"
    fi
}

# Function to check service status
check_services() {
    local controller_status="DOWN"
    local socket_status="DOWN"
    local worker_count=0
    
    # Check controller
    if curl -s http://localhost:5000/health > /dev/null 2>&1; then
        controller_status="UP"
        
        # Get worker count
        local workers_response=$(curl -s http://localhost:5000/workers 2>/dev/null)
        if [ $? -eq 0 ]; then
            worker_count=$(echo "$workers_response" | jq '.workers | length' 2>/dev/null || echo "0")
        fi
    fi
    
    # Check socket server
    if netstat -ln 2>/dev/null | grep -q ":8765"; then
        socket_status="UP"
    fi
    
    echo "$controller_status,$socket_status,$worker_count"
}

# Function to display status
display_status() {
    clear
    echo -e "${BLUE}📊 Phantom System Monitor - $(date)${NC}"
    echo "=================================================================="
    
    # Get metrics
    local system_metrics=$(get_system_metrics)
    local cpu_usage=$(echo $system_metrics | cut -d',' -f1)
    local memory_usage=$(echo $system_metrics | cut -d',' -f2)
    
    local service_status=$(check_services)
    local controller_status=$(echo $service_status | cut -d',' -f1)
    local socket_status=$(echo $service_status | cut -d',' -f2)
    local worker_count=$(echo $service_status | cut -d',' -f3)
    
    # Display system resources
    echo -e "\n${PURPLE}💻 System Resources${NC}"
    echo "----------------------------------------"
    
    # CPU Usage with color coding
    if (( $(echo "$cpu_usage > $ALERT_THRESHOLD_CPU" | bc -l 2>/dev/null || echo 0) )); then
        echo -e "CPU Usage: ${RED}${cpu_usage}%${NC} ⚠️"
    elif (( $(echo "$cpu_usage > 50" | bc -l 2>/dev/null || echo 0) )); then
        echo -e "CPU Usage: ${YELLOW}${cpu_usage}%${NC}"
    else
        echo -e "CPU Usage: ${GREEN}${cpu_usage}%${NC}"
    fi
    
    # Memory Usage with color coding
    if (( $(echo "$memory_usage > $ALERT_THRESHOLD_MEMORY" | bc -l 2>/dev/null || echo 0) )); then
        echo -e "Memory Usage: ${RED}${memory_usage}%${NC} ⚠️"
    elif (( $(echo "$memory_usage > 70" | bc -l 2>/dev/null || echo 0) )); then
        echo -e "Memory Usage: ${YELLOW}${memory_usage}%${NC}"
    else
        echo -e "Memory Usage: ${GREEN}${memory_usage}%${NC}"
    fi
    
    # GPU Status
    echo -e "\n${PURPLE}🎮 GPU Status${NC}"
    echo "----------------------------------------"
    
    local gpu_metrics=$(get_gpu_metrics)
    if [ "$gpu_metrics" != "N/A,N/A,N/A,N/A" ]; then
        local gpu_count=0
        echo "$gpu_metrics" | while IFS=, read -r utilization memory_used memory_total temperature; do
            gpu_count=$((gpu_count + 1))
            
            # Color code GPU utilization
            if (( $(echo "$utilization > $ALERT_THRESHOLD_GPU" | bc -l 2>/dev/null || echo 0) )); then
                util_color="${RED}"
            elif (( $(echo "$utilization > 70" | bc -l 2>/dev/null || echo 0) )); then
                util_color="${YELLOW}"
            else
                util_color="${GREEN}"
            fi
            
            echo -e "GPU $gpu_count: ${util_color}${utilization}%${NC} | Memory: ${memory_used}MB/${memory_total}MB | Temp: ${temperature}°C"
        done
    else
        echo "No NVIDIA GPUs detected"
    fi
    
    # Service Status
    echo -e "\n${PURPLE}🔧 Service Status${NC}"
    echo "----------------------------------------"
    
    # Controller status
    if [ "$controller_status" = "UP" ]; then
        echo -e "Controller: ${GREEN}●${NC} Running (port 5000)"
    else
        echo -e "Controller: ${RED}●${NC} Down"
    fi
    
    # Socket server status
    if [ "$socket_status" = "UP" ]; then
        echo -e "Socket Server: ${GREEN}●${NC} Running (port 8765)"
    else
        echo -e "Socket Server: ${RED}●${NC} Down"
    fi
    
    # Worker status
    if [ "$worker_count" -gt 0 ]; then
        echo -e "Workers: ${GREEN}●${NC} $worker_count active"
    else
        echo -e "Workers: ${YELLOW}●${NC} No workers connected"
    fi
    
    # Recent activity
    echo -e "\n${PURPLE}📋 Recent Activity${NC}"
    echo "----------------------------------------"
    
    if [ -f "$LOG_FILE" ]; then
        tail -n 5 "$LOG_FILE" | while read -r line; do
            echo "$line"
        done
    else
        echo "No recent activity logged"
    fi
    
    # Network connections
    echo -e "\n${PURPLE}🌐 Network Connections${NC}"
    echo "----------------------------------------"
    
    local phantom_connections=$(netstat -an 2>/dev/null | grep -E ":(5000|6000|6001|6002|8765)" | wc -l)
    echo "Active Phantom connections: $phantom_connections"
    
    # Show listening ports
    netstat -ln 2>/dev/null | grep -E ":(5000|6000|6001|6002|8765)" | while read -r line; do
        local port=$(echo "$line" | awk '{print $4}' | cut -d':' -f2)
        echo "Listening on port: $port"
    done
    
    echo -e "\n${CYAN}Next refresh in ${REFRESH_INTERVAL}s... (Ctrl+C to exit)${NC}"
}

# Function to check for alerts
check_alerts() {
    local system_metrics=$(get_system_metrics)
    local cpu_usage=$(echo $system_metrics | cut -d',' -f1)
    local memory_usage=$(echo $system_metrics | cut -d',' -f2)
    
    # CPU alert
    if (( $(echo "$cpu_usage > $ALERT_THRESHOLD_CPU" | bc -l 2>/dev/null || echo 0) )); then
        log_message "ALERT: High CPU usage: ${cpu_usage}%"
    fi
    
    # Memory alert
    if (( $(echo "$memory_usage > $ALERT_THRESHOLD_MEMORY" | bc -l 2>/dev/null || echo 0) )); then
        log_message "ALERT: High memory usage: ${memory_usage}%"
    fi
    
    # GPU alerts
    if command -v nvidia-smi &> /dev/null; then
        local gpu_metrics=$(get_gpu_metrics)
        if [ "$gpu_metrics" != "N/A,N/A,N/A,N/A" ]; then
            echo "$gpu_metrics" | while IFS=, read -r utilization memory_used memory_total temperature; do
                if (( $(echo "$utilization > $ALERT_THRESHOLD_GPU" | bc -l 2>/dev/null || echo 0) )); then
                    log_message "ALERT: High GPU utilization: ${utilization}%"
                fi
                
                if (( $(echo "$temperature > 85" | bc -l 2>/dev/null || echo 0) )); then
                    log_message "ALERT: High GPU temperature: ${temperature}°C"
                fi
            done
        fi
    fi
    
    # Service alerts
    local service_status=$(check_services)
    local controller_status=$(echo $service_status | cut -d',' -f1)
    local socket_status=$(echo $service_status | cut -d',' -f2)
    
    if [ "$controller_status" = "DOWN" ]; then
        log_message "ALERT: Controller service is down"
    fi
    
    if [ "$socket_status" = "DOWN" ]; then
        log_message "ALERT: Socket server is down"
    fi
}

# Function to handle cleanup on exit
cleanup() {
    echo -e "\n\n${BLUE}Monitor stopped. Logs saved to: $LOG_FILE${NC}"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Check if bc is available for calculations
if ! command -v bc &> /dev/null; then
    echo -e "${YELLOW}⚠${NC} 'bc' calculator not found. Some calculations may not work properly."
    echo "Install with: sudo apt-get install bc (Ubuntu/Debian) or sudo yum install bc (CentOS/RHEL)"
fi

# Main monitoring loop
log_message "System monitor started"

while true; do
    display_status
    check_alerts
    sleep $REFRESH_INTERVAL
done