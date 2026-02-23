#!/bin/bash

# Phantom Complete System Startup Script
# Starts the entire integrated Phantom distributed system

set -e
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROLLER_HOST="${CONTROLLER_HOST:-127.0.0.1}"
CONTROLLER_PORT="${CONTROLLER_PORT:-8080}"
SOCKET_PORT="${SOCKET_PORT:-8081}"
SECURITY_LEVEL="${SECURITY_LEVEL:-basic}"
ENABLE_LLM_TASKMASTER="${ENABLE_LLM_TASKMASTER:-true}"

echo "🚀 Phantom Complete System Startup"
echo "=================================="
echo "Controller: $CONTROLLER_HOST:$CONTROLLER_PORT"
echo "Socket Infrastructure: $CONTROLLER_HOST:$SOCKET_PORT"
echo "Security Level: $SECURITY_LEVEL"
echo "LLM Task Master: $ENABLE_LLM_TASKMASTER"
echo ""

# Function to check if port is available
check_port() {
    local port=$1
    if netstat -tuln 2>/dev/null | grep -q ":$port "; then
        echo "⚠️ Port $port is already in use"
        return 1
    fi
    return 0
}

# Function to wait for service to be ready
wait_for_service() {
    local host=$1
    local port=$2
    local service_name=$3
    local max_attempts=30
    local attempt=1
    
    echo "⏳ Waiting for $service_name to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "http://$host:$port/health" >/dev/null 2>&1 || \
           curl -s "http://$host:$port/" >/dev/null 2>&1; then
            echo "✅ $service_name is ready"
            return 0
        fi
        
        echo "   Attempt $attempt/$max_attempts..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    echo "❌ $service_name failed to start within timeout"
    return 1
}

# Function to start integrated system
start_integrated_system() {
    echo "🎯 Starting integrated Phantom system..."
    
    # Check port availability
    if ! check_port "$CONTROLLER_PORT"; then
        echo "❌ Controller port $CONTROLLER_PORT is not available"
        exit 1
    fi
    
    if ! check_port "$SOCKET_PORT"; then
        echo "❌ Socket port $SOCKET_PORT is not available"
        exit 1
    fi
    
    # Set Python path
    export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}"
    
    # Start integrated system
    cd "$SCRIPT_DIR"
    
    local llm_flag=""
    if [ "$ENABLE_LLM_TASKMASTER" = "true" ]; then
        llm_flag="--enable-llm-taskmaster"
    fi
    
    echo "🚀 Launching integrated system..."
    python3 run_integrated_phantom.py \
        --host "$CONTROLLER_HOST" \
        --port "$CONTROLLER_PORT" \
        --socket-port "$SOCKET_PORT" \
        --security "$SECURITY_LEVEL" \
        $llm_flag \
        --log-level INFO &
    
    INTEGRATED_PID="$!"
    echo "$INTEGRATED_PID" > phantom_integrated.pid
    
    # Wait for controller to be ready
    if wait_for_service "$CONTROLLER_HOST" "$CONTROLLER_PORT" "Controller"; then
        echo "✅ Integrated system started successfully (PID: $INTEGRATED_PID)"
    else
        echo "❌ Integrated system failed to start"
        kill "$INTEGRATED_PID" 2>/dev/null || true
        rm -f phantom_integrated.pid
        exit 1
    fi
}

# Function to start Linux workers
start_linux_workers() {
    echo "👷 Starting Linux workers..."
    
    if [ -d "$SCRIPT_DIR/linux-worker" ] && [ -f "$SCRIPT_DIR/linux-worker/start_all_workers.sh" ]; then
        cd "$SCRIPT_DIR/linux-worker"
        
        # Set controller host for workers
        export CONTROLLER_HOST="$CONTROLLER_HOST"
        export CONTROLLER_PORT="$CONTROLLER_PORT"
        
        ./start_all_workers.sh
        
        echo "✅ Linux workers startup initiated"
    else
        echo "⚠️ Linux workers not found, skipping..."
    fi
}

# Function to display status
show_status() {
    echo ""
    echo "📊 System Status"
    echo "==============="
    
    # Check integrated system
    if [ -f "phantom_integrated.pid" ]; then
        local pid=$(cat phantom_integrated.pid)
        if kill -0 "$pid" 2>/dev/null; then
            echo "🟢 Integrated System: RUNNING (PID: $pid)"
        else
            echo "🔴 Integrated System: STOPPED"
        fi
    else
        echo "⚪ Integrated System: NOT STARTED"
    fi
    
    # Check controller endpoint
    if curl -s "http://$CONTROLLER_HOST:$CONTROLLER_PORT/health" >/dev/null 2>&1; then
        echo "🟢 Controller API: ACCESSIBLE"
    else
        echo "🔴 Controller API: NOT ACCESSIBLE"
    fi
    
    # Check socket infrastructure
    if curl -s "http://$CONTROLLER_HOST:$CONTROLLER_PORT/socket/status" >/dev/null 2>&1; then
        echo "🟢 Socket Infrastructure: RUNNING"
    else
        echo "🔴 Socket Infrastructure: NOT RUNNING"
    fi
    
    # Check Linux workers
    if [ -d "$SCRIPT_DIR/linux-worker" ] && [ -f "$SCRIPT_DIR/linux-worker/monitor_workers.sh" ]; then
        echo ""
        echo "👷 Linux Workers:"
        cd "$SCRIPT_DIR/linux-worker"
        ./monitor_workers.sh | grep -E "(RUNNING|STOPPED|NOT STARTED)" | head -5
    fi
    
    echo ""
    echo "🌐 Access Points:"
    echo "  Controller API: http://$CONTROLLER_HOST:$CONTROLLER_PORT"
    echo "  Health Check:   http://$CONTROLLER_HOST:$CONTROLLER_PORT/health"
    echo "  Worker Status:  http://$CONTROLLER_HOST:$CONTROLLER_PORT/workers"
    echo "  System Stats:   http://$CONTROLLER_HOST:$CONTROLLER_PORT/stats"
    
    if [ "$SECURITY_LEVEL" != "disabled" ]; then
        echo "  Security:       $SECURITY_LEVEL level enabled"
    fi
}

# Function to stop system
stop_system() {
    echo "🛑 Stopping Phantom system..."
    
    # Stop integrated system
    if [ -f "phantom_integrated.pid" ]; then
        local pid=$(cat phantom_integrated.pid)
        if kill -0 "$pid" 2>/dev/null; then
            echo "🔄 Stopping integrated system (PID: $pid)..."
            kill -TERM "$pid"
            
            # Wait for graceful shutdown
            local attempts=10
            while [ $attempts -gt 0 ] && kill -0 "$pid" 2>/dev/null; do
                sleep 1
                attempts=$((attempts - 1))
            done
            
            # Force kill if still running
            if kill -0 "$pid" 2>/dev/null; then
                echo "🔨 Force stopping integrated system..."
                kill -KILL "$pid"
            fi
            
            echo "✅ Integrated system stopped"
        fi
        rm -f phantom_integrated.pid
    fi
    
    # Stop Linux workers
    if [ -d "$SCRIPT_DIR/linux-worker" ] && [ -f "$SCRIPT_DIR/linux-worker/stop_all_workers.sh" ]; then
        echo "🔄 Stopping Linux workers..."
        cd "$SCRIPT_DIR/linux-worker"
        ./stop_all_workers.sh
    fi
    
    echo "✅ Phantom system stopped"
}

# Function to restart system
restart_system() {
    echo "🔄 Restarting Phantom system..."
    stop_system
    sleep 3
    start_integrated_system
    sleep 5
    start_linux_workers
    show_status
}

# Function to show logs
show_logs() {
    echo "📋 Recent System Logs"
    echo "===================="
    
    # Show integrated system logs if available
    if [ -f "phantom_integrated.pid" ]; then
        echo "🎯 Integrated System Logs (last 20 lines):"
        journalctl -u phantom-integrated --lines=20 --no-pager 2>/dev/null || \
        echo "   (System logs not available via journalctl)"
        echo ""
    fi
    
    # Show Linux worker logs
    if [ -d "$SCRIPT_DIR/linux-worker/instances" ]; then
        echo "👷 Linux Worker Logs (recent):"
        for instance_dir in "$SCRIPT_DIR/linux-worker/instances"/*; do
            if [ -d "$instance_dir" ] && [ -f "$instance_dir/worker.log" ]; then
                worker_id="$(basename "$instance_dir")"
                echo "   $worker_id (last 5 lines):"
                tail -5 "$instance_dir/worker.log" 2>/dev/null | sed 's/^/     /' || echo "     (No logs available)"
            fi
        done
    fi
}

# Function to run health check
health_check() {
    echo "🏥 System Health Check"
    echo "====================="
    
    local issues=0
    
    # Check controller
    if curl -s "http://$CONTROLLER_HOST:$CONTROLLER_PORT/health" >/dev/null 2>&1; then
        echo "✅ Controller: Healthy"
    else
        echo "❌ Controller: Unhealthy"
        issues=$((issues + 1))
    fi
    
    # Check socket infrastructure
    if curl -s "http://$CONTROLLER_HOST:$CONTROLLER_PORT/socket/status" >/dev/null 2>&1; then
        echo "✅ Socket Infrastructure: Healthy"
    else
        echo "❌ Socket Infrastructure: Unhealthy"
        issues=$((issues + 1))
    fi
    
    # Check worker connectivity
    local worker_response=$(curl -s "http://$CONTROLLER_HOST:$CONTROLLER_PORT/workers" 2>/dev/null)
    if [ -n "$worker_response" ]; then
        local worker_count=$(echo "$worker_response" | grep -o '"worker_id"' | wc -l)
        echo "✅ Workers: $worker_count connected"
    else
        echo "❌ Workers: Unable to check status"
        issues=$((issues + 1))
    fi
    
    echo ""
    if [ $issues -eq 0 ]; then
        echo "🎉 System is healthy!"
    else
        echo "⚠️ Found $issues issue(s)"
    fi
}

# Main command handling
case "${1:-start}" in
    start)
        start_integrated_system
        sleep 5
        start_linux_workers
        show_status
        ;;
    stop)
        stop_system
        ;;
    restart)
        restart_system
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    health)
        health_check
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|health}"
        echo ""
        echo "Commands:"
        echo "  start   - Start the complete Phantom system"
        echo "  stop    - Stop the complete Phantom system"
        echo "  restart - Restart the complete Phantom system"
        echo "  status  - Show system status"
        echo "  logs    - Show recent system logs"
        echo "  health  - Run health check"
        echo ""
        echo "Environment Variables:"
        echo "  CONTROLLER_HOST     - Controller host (default: 127.0.0.1)"
        echo "  CONTROLLER_PORT     - Controller port (default: 8080)"
        echo "  SOCKET_PORT         - Socket port (default: 8081)"
        echo "  SECURITY_LEVEL      - Security level (default: basic)"
        echo "  ENABLE_LLM_TASKMASTER - Enable LLM Task Master (default: true)"
        exit 1
        ;;
esac