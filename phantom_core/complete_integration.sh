#!/bin/bash

# Phantom Complete Integration Script
# Integrates all components into a unified system

set -e
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔧 Phantom Complete Integration"
echo "=============================="
echo ""

# Function to create integrated configuration
create_integrated_config() {
    echo "📝 Creating integrated configuration..."
    
    cat > "$SCRIPT_DIR/integrated_config.yaml" << EOF
# Phantom Distributed Integrated Configuration
system:
  name: "Phantom Distributed Compute Fabric"
  version: "2.0.0"
  mode: "integrated"

controller:
  host: "127.0.0.1"
  port: 8080
  security_level: "basic"
  
socket_infrastructure:
  enabled: true
  port: 8081
  host: "127.0.0.1"
  
llm_taskmaster:
  enabled: true
  target_gpu: "GTX 1080"
  model_size: "lightweight"
  memory_limit_mb: 2048

security:
  level: "basic"  # disabled, basic, enhanced, enterprise
  api_keys_enabled: false
  jwt_tokens_enabled: false
  rate_limiting_enabled: false
  ip_filtering_enabled: false

workers:
  linux:
    auto_deploy: true
    base_port: 8090
    
  windows:
    controller_host: "192.168.1.103"
    rtx5080_port: 8091
    rtx5060_port: 8092

network:
  topology: "heterogeneous_cluster"
  fedora_server: "192.168.1.103"
  windows_pc: "auto_detect"
  
performance:
  gpu_hierarchy:
    - name: "RTX 5080"
      performance_score: 10.0
      memory_gb: 24
      specialization: ["large_model_inference", "real_time_ai", "training"]
    - name: "RTX 5060" 
      performance_score: 7.0
      memory_gb: 16
      specialization: ["ml_inference", "batch_processing", "medium_training"]
    - name: "GTX 1080"
      performance_score: 5.0
      memory_gb: 8
      specialization: ["stable_inference", "llm_task_master", "compatibility"]
    - name: "FirePro W9100"
      performance_score: 6.0
      memory_gb: 16
      specialization: ["data_processing", "large_datasets", "memory_intensive"]

monitoring:
  health_check_interval: 30
  performance_logging: true
  audit_logging: false
  
storage:
  models_path: "/var/lib/phantom/models"
  datasets_path: "/var/lib/phantom/datasets"
  cache_path: "/var/lib/phantom/cache"
  max_cache_gb: 100
EOF

    echo "✅ Integrated configuration created"
}

# Function to create requirements file
create_requirements() {
    echo "📦 Creating requirements file..."
    
    cat > "$SCRIPT_DIR/requirements.txt" << EOF
# Phantom Distributed Requirements
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.5.0
httpx>=0.25.0
websockets>=12.0
psutil>=5.9.0
asyncio-mqtt>=0.13.0
python-multipart>=0.0.6
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4
python-dotenv>=1.0.0
pyyaml>=6.0.1
numpy>=1.24.0
pandas>=2.0.0
aiofiles>=23.0.0
jinja2>=3.1.0
prometheus-client>=0.19.0

# Optional GPU libraries (install if available)
# torch>=2.1.0
# tensorflow>=2.15.0
# cupy-cuda12x>=12.0.0
EOF

    echo "✅ Requirements file created"
}

# Function to create systemd service files
create_systemd_services() {
    echo "🔧 Creating systemd service files..."
    
    # Main controller service
    cat > "$SCRIPT_DIR/phantom-controller.service" << EOF
[Unit]
Description=Phantom Distributed Controller
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR
Environment=PYTHONPATH=$SCRIPT_DIR
ExecStart=/usr/bin/python3 run_integrated_phantom.py --host 127.0.0.1 --port 8080
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    # Socket infrastructure service
    cat > "$SCRIPT_DIR/phantom-socket.service" << EOF
[Unit]
Description=Phantom Socket Infrastructure
After=network.target
Wants=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR/socket_infrastructure
Environment=PYTHONPATH=$SCRIPT_DIR
ExecStart=/usr/bin/python3 hybrid_socket_server.py --host 127.0.0.1 --port 8081
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    # LLM Task Master service
    cat > "$SCRIPT_DIR/phantom-llm-taskmaster.service" << EOF
[Unit]
Description=Phantom LLM Task Master
After=network.target phantom-socket.service
Wants=network.target
Requires=phantom-socket.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$SCRIPT_DIR/llm_taskmaster
Environment=PYTHONPATH=$SCRIPT_DIR
ExecStart=/usr/bin/python3 lightweight_llm_setup.py --controller-host localhost --socket-port 8081
Restart=always
RestartSec=15
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    echo "✅ Systemd service files created"
    echo "   To install: sudo cp *.service /etc/systemd/system/"
    echo "   To enable: sudo systemctl enable phantom-controller phantom-socket phantom-llm-taskmaster"
}

# Function to create Docker configuration
create_docker_config() {
    echo "🐳 Creating Docker configuration..."
    
    cat > "$SCRIPT_DIR/Dockerfile" << EOF
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    curl \\
    wget \\
    git \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 phantom && chown -R phantom:phantom /app
USER phantom

# Expose ports
EXPOSE 8080 8081

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:8080/health || exit 1

# Start command
CMD ["python3", "run_integrated_phantom.py", "--host", "0.0.0.0", "--port", "8080"]
EOF

    cat > "$SCRIPT_DIR/docker-compose.yml" << EOF
version: '3.8'

services:
  phantom-controller:
    build: .
    ports:
      - "8080:8080"
      - "8081:8081"
    environment:
      - PHANTOM_INTEGRATED=true
      - PHANTOM_SECURITY=basic
      - PHANTOM_LLM_TASKMASTER=true
    volumes:
      - ./data:/app/data
      - /var/run/docker.sock:/var/run/docker.sock:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  phantom-worker-gpu:
    build: .
    command: ["python3", "linux-worker/linux_worker/main.py", "--config", "/app/worker_config.json"]
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
    volumes:
      - ./linux-worker/instances/nvidia-gpu-0/worker_config.json:/app/worker_config.json:ro
    depends_on:
      - phantom-controller
    restart: unless-stopped
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

volumes:
  phantom-data:
    driver: local

networks:
  default:
    name: phantom-network
EOF

    echo "✅ Docker configuration created"
}

# Function to create monitoring scripts
create_monitoring_scripts() {
    echo "📊 Creating monitoring scripts..."
    
    cat > "$SCRIPT_DIR/monitor_system.sh" << 'EOF'
#!/bin/bash

# Phantom System Monitor
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "📊 Phantom System Monitor"
echo "========================"
echo ""

# Function to check service status
check_service() {
    local service_name=$1
    local url=$2
    
    if curl -s "$url" >/dev/null 2>&1; then
        echo "✅ $service_name: HEALTHY"
    else
        echo "❌ $service_name: UNHEALTHY"
    fi
}

# Function to get system metrics
get_metrics() {
    echo "🔍 System Metrics:"
    echo "=================="
    
    # CPU and Memory
    echo "CPU Usage: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)%"
    echo "Memory Usage: $(free | grep Mem | awk '{printf "%.1f%%", $3/$2 * 100.0}')"
    
    # GPU Status
    if command -v nvidia-smi &> /dev/null; then
        echo ""
        echo "NVIDIA GPUs:"
        nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits | \
        while IFS=',' read -r name util mem_used mem_total; do
            echo "  $name: ${util}% GPU, ${mem_used}/${mem_total}MB VRAM"
        done
    fi
    
    if command -v rocm-smi &> /dev/null; then
        echo ""
        echo "AMD GPUs:"
        rocm-smi --showuse --showmemuse 2>/dev/null | grep -E "GPU|use" || echo "  No AMD GPU data available"
    fi
}

# Function to check workers
check_workers() {
    echo ""
    echo "👷 Worker Status:"
    echo "================="
    
    local workers_response=$(curl -s http://localhost:8080/workers 2>/dev/null)
    if [ -n "$workers_response" ]; then
        echo "$workers_response" | jq -r '.workers[] | "  \(.worker_id): \(.status // "unknown")"' 2>/dev/null || \
        echo "  Unable to parse worker data"
    else
        echo "  Unable to connect to controller"
    fi
}

# Function to check recent tasks
check_tasks() {
    echo ""
    echo "📋 Recent Tasks:"
    echo "==============="
    
    local tasks_response=$(curl -s http://localhost:8080/tasks 2>/dev/null)
    if [ -n "$tasks_response" ]; then
        echo "$tasks_response" | jq -r '.tasks[-5:] | .[] | "  \(.task_id[0:8]): \(.task_type) - \(.status)"' 2>/dev/null || \
        echo "  Unable to parse task data"
    else
        echo "  Unable to connect to controller"
    fi
}

# Main monitoring loop
if [ "$1" = "--continuous" ]; then
    while true; do
        clear
        echo "$(date)"
        echo ""
        
        check_service "Controller" "http://localhost:8080/health"
        check_service "Socket Infrastructure" "http://localhost:8080/socket/status"
        
        get_metrics
        check_workers
        check_tasks
        
        echo ""
        echo "Press Ctrl+C to stop monitoring..."
        sleep 10
    done
else
    check_service "Controller" "http://localhost:8080/health"
    check_service "Socket Infrastructure" "http://localhost:8080/socket/status"
    
    get_metrics
    check_workers
    check_tasks
    
    echo ""
    echo "💡 Use '$0 --continuous' for continuous monitoring"
fi
EOF

    chmod +x "$SCRIPT_DIR/monitor_system.sh"
    
    echo "✅ Monitoring scripts created"
}

# Function to create backup and restore scripts
create_backup_scripts() {
    echo "💾 Creating backup and restore scripts..."
    
    cat > "$SCRIPT_DIR/backup_system.sh" << 'EOF'
#!/bin/bash

# Phantom System Backup Script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$HOME/phantom_backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="phantom_backup_$TIMESTAMP"

echo "💾 Phantom System Backup"
echo "========================"
echo "Backup location: $BACKUP_DIR/$BACKUP_NAME"
echo ""

# Create backup directory
mkdir -p "$BACKUP_DIR/$BACKUP_NAME"

# Backup configuration files
echo "📝 Backing up configuration..."
cp "$SCRIPT_DIR/integrated_config.yaml" "$BACKUP_DIR/$BACKUP_NAME/" 2>/dev/null || true
cp "$SCRIPT_DIR"/*.json "$BACKUP_DIR/$BACKUP_NAME/" 2>/dev/null || true

# Backup worker configurations
echo "👷 Backing up worker configurations..."
if [ -d "$SCRIPT_DIR/linux-worker/instances" ]; then
    cp -r "$SCRIPT_DIR/linux-worker/instances" "$BACKUP_DIR/$BACKUP_NAME/linux_worker_instances"
fi

if [ -d "$SCRIPT_DIR/windows-worker" ]; then
    cp "$SCRIPT_DIR/windows-worker"/*.json "$BACKUP_DIR/$BACKUP_NAME/" 2>/dev/null || true
fi

# Backup logs (recent only)
echo "📋 Backing up recent logs..."
mkdir -p "$BACKUP_DIR/$BACKUP_NAME/logs"

if [ -d "$SCRIPT_DIR/linux-worker/instances" ]; then
    for instance_dir in "$SCRIPT_DIR/linux-worker/instances"/*; do
        if [ -f "$instance_dir/worker.log" ]; then
            worker_id=$(basename "$instance_dir")
            tail -1000 "$instance_dir/worker.log" > "$BACKUP_DIR/$BACKUP_NAME/logs/${worker_id}.log" 2>/dev/null || true
        fi
    done
fi

# Create backup manifest
echo "📄 Creating backup manifest..."
cat > "$BACKUP_DIR/$BACKUP_NAME/MANIFEST.txt" << EOL
Phantom Distributed System Backup
Created: $(date)
Hostname: $(hostname)
System: $(uname -a)

Contents:
- Configuration files
- Worker instance configurations
- Recent log files (last 1000 lines)

Restore with: ./restore_system.sh $BACKUP_NAME
EOL

# Create compressed archive
echo "🗜️ Creating compressed archive..."
cd "$BACKUP_DIR"
tar -czf "${BACKUP_NAME}.tar.gz" "$BACKUP_NAME"
rm -rf "$BACKUP_NAME"

echo "✅ Backup completed: $BACKUP_DIR/${BACKUP_NAME}.tar.gz"
echo "📊 Backup size: $(du -h "$BACKUP_DIR/${BACKUP_NAME}.tar.gz" | cut -f1)"
EOF

    cat > "$SCRIPT_DIR/restore_system.sh" << 'EOF'
#!/bin/bash

# Phantom System Restore Script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$HOME/phantom_backups}"

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_name>"
    echo ""
    echo "Available backups:"
    ls -1 "$BACKUP_DIR"/*.tar.gz 2>/dev/null | xargs -n1 basename | sed 's/.tar.gz$//' || echo "  No backups found"
    exit 1
fi

BACKUP_NAME="$1"
BACKUP_FILE="$BACKUP_DIR/${BACKUP_NAME}.tar.gz"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "🔄 Phantom System Restore"
echo "========================="
echo "Restoring from: $BACKUP_FILE"
echo ""

# Stop system before restore
echo "🛑 Stopping system..."
"$SCRIPT_DIR/start_complete_phantom.sh" stop 2>/dev/null || true

# Extract backup
echo "📦 Extracting backup..."
cd "$BACKUP_DIR"
tar -xzf "${BACKUP_NAME}.tar.gz"

# Restore configuration files
echo "📝 Restoring configuration..."
cp "$BACKUP_DIR/$BACKUP_NAME"/*.yaml "$SCRIPT_DIR/" 2>/dev/null || true
cp "$BACKUP_DIR/$BACKUP_NAME"/*.json "$SCRIPT_DIR/" 2>/dev/null || true

# Restore worker configurations
echo "👷 Restoring worker configurations..."
if [ -d "$BACKUP_DIR/$BACKUP_NAME/linux_worker_instances" ]; then
    mkdir -p "$SCRIPT_DIR/linux-worker/instances"
    cp -r "$BACKUP_DIR/$BACKUP_NAME/linux_worker_instances"/* "$SCRIPT_DIR/linux-worker/instances/" 2>/dev/null || true
fi

# Clean up extracted backup
rm -rf "$BACKUP_DIR/$BACKUP_NAME"

echo "✅ Restore completed"
echo "💡 Start system with: ./start_complete_phantom.sh start"
EOF

    chmod +x "$SCRIPT_DIR/backup_system.sh"
    chmod +x "$SCRIPT_DIR/restore_system.sh"
    
    echo "✅ Backup and restore scripts created"
}

# Function to create update script
create_update_script() {
    echo "🔄 Creating update script..."
    
    cat > "$SCRIPT_DIR/update_system.sh" << 'EOF'
#!/bin/bash

# Phantom System Update Script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔄 Phantom System Update"
echo "========================"
echo ""

# Function to backup before update
backup_before_update() {
    echo "💾 Creating backup before update..."
    "$SCRIPT_DIR/backup_system.sh"
}

# Function to update Python dependencies
update_dependencies() {
    echo "📦 Updating Python dependencies..."
    pip3 install --user --upgrade -r "$SCRIPT_DIR/requirements.txt"
}

# Function to update system configuration
update_configuration() {
    echo "⚙️ Updating system configuration..."
    
    # Check for configuration changes
    if [ -f "$SCRIPT_DIR/integrated_config.yaml.new" ]; then
        echo "🔧 New configuration template found"
        echo "   Review and merge: $SCRIPT_DIR/integrated_config.yaml.new"
    fi
}

# Function to restart services
restart_services() {
    echo "🔄 Restarting services..."
    "$SCRIPT_DIR/start_complete_phantom.sh" restart
}

# Function to verify update
verify_update() {
    echo "✅ Verifying update..."
    sleep 5
    "$SCRIPT_DIR/start_complete_phantom.sh" health
}

# Main update process
case "${1:-full}" in
    "dependencies")
        update_dependencies
        ;;
    "config")
        update_configuration
        ;;
    "restart")
        restart_services
        ;;
    "verify")
        verify_update
        ;;
    "full")
        backup_before_update
        update_dependencies
        update_configuration
        restart_services
        verify_update
        echo ""
        echo "🎉 Update completed successfully!"
        ;;
    *)
        echo "Usage: $0 {dependencies|config|restart|verify|full}"
        echo ""
        echo "Options:"
        echo "  dependencies - Update Python dependencies only"
        echo "  config       - Update configuration only"
        echo "  restart      - Restart services only"
        echo "  verify       - Verify system health only"
        echo "  full         - Complete update process (default)"
        exit 1
        ;;
esac
EOF

    chmod +x "$SCRIPT_DIR/update_system.sh"
    
    echo "✅ Update script created"
}

# Function to create development tools
create_dev_tools() {
    echo "🛠️ Creating development tools..."
    
    cat > "$SCRIPT_DIR/dev_tools.sh" << 'EOF'
#!/bin/bash

# Phantom Development Tools
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "${1:-help}" in
    "test-task")
        echo "🧪 Submitting test task..."
        curl -X POST http://localhost:8080/tasks/submit \
          -H "Content-Type: application/json" \
          -d '{
            "task_type": "ml_inference",
            "parameters": {
              "model_path": "test_model",
              "batch_size": 2
            },
            "priority": 1
          }'
        echo ""
        ;;
    
    "stress-test")
        echo "⚡ Running stress test..."
        for i in {1..10}; do
            curl -X POST http://localhost:8080/tasks/submit \
              -H "Content-Type: application/json" \
              -d "{
                \"task_type\": \"ml_inference\",
                \"parameters\": {
                  \"model_path\": \"stress_test_$i\",
                  \"batch_size\": $((RANDOM % 8 + 1))
                },
                \"priority\": $((RANDOM % 3 + 1))
              }" &
        done
        wait
        echo "✅ Stress test completed"
        ;;
    
    "benchmark")
        echo "📊 Running benchmark..."
        start_time=$(date +%s)
        
        for i in {1..50}; do
            curl -s -X POST http://localhost:8080/tasks/submit \
              -H "Content-Type: application/json" \
              -d "{
                \"task_type\": \"benchmark\",
                \"parameters\": {
                  \"iteration\": $i
                }
              }" > /dev/null
        done
        
        end_time=$(date +%s)
        duration=$((end_time - start_time))
        echo "✅ Submitted 50 tasks in ${duration}s ($(echo "scale=2; 50/$duration" | bc) tasks/sec)"
        ;;
    
    "debug-worker")
        worker_id="${2:-nvidia-gpu-0}"
        echo "🐛 Debug information for worker: $worker_id"
        curl -s "http://localhost:8080/workers/$worker_id" | jq '.' || echo "Worker not found"
        ;;
    
    "reset-system")
        echo "🔄 Resetting system state..."
        "$SCRIPT_DIR/start_complete_phantom.sh" stop
        
        # Clean up task state
        echo "🧹 Cleaning up state..."
        rm -f "$SCRIPT_DIR"/*.pid
        
        # Restart fresh
        "$SCRIPT_DIR/start_complete_phantom.sh" start
        echo "✅ System reset completed"
        ;;
    
    "logs-tail")
        echo "📋 Tailing all logs..."
        tail -f "$SCRIPT_DIR"/linux-worker/instances/*/worker.log 2>/dev/null &
        TAIL_PID=$!
        
        echo "Press Ctrl+C to stop..."
        trap "kill $TAIL_PID 2>/dev/null" EXIT
        wait
        ;;
    
    "help"|*)
        echo "🛠️ Phantom Development Tools"
        echo "============================"
        echo ""
        echo "Usage: $0 <command> [options]"
        echo ""
        echo "Commands:"
        echo "  test-task              - Submit a single test task"
        echo "  stress-test            - Submit multiple concurrent tasks"
        echo "  benchmark              - Run performance benchmark"
        echo "  debug-worker [id]      - Show debug info for worker"
        echo "  reset-system           - Reset system to clean state"
        echo "  logs-tail              - Tail all worker logs"
        echo "  help                   - Show this help"
        ;;
esac
EOF

    chmod +x "$SCRIPT_DIR/dev_tools.sh"
    
    echo "✅ Development tools created"
}

# Main integration process
main() {
    echo "🚀 Starting complete integration..."
    echo ""
    
    # Create all integration components
    create_integrated_config
    create_requirements
    create_systemd_services
    create_docker_config
    create_monitoring_scripts
    create_backup_scripts
    create_update_script
    create_dev_tools
    
    # Make all scripts executable
    chmod +x "$SCRIPT_DIR"/*.sh
    
    echo ""
    echo "🎉 Complete integration finished!"
    echo ""
    echo "📋 Integration Summary:"
    echo "======================"
    echo "✅ Integrated configuration (integrated_config.yaml)"
    echo "✅ Python requirements (requirements.txt)"
    echo "✅ Systemd service files (*.service)"
    echo "✅ Docker configuration (Dockerfile, docker-compose.yml)"
    echo "✅ Monitoring scripts (monitor_system.sh)"
    echo "✅ Backup/restore scripts (backup_system.sh, restore_system.sh)"
    echo "✅ Update script (update_system.sh)"
    echo "✅ Development tools (dev_tools.sh)"
    echo ""
    echo "🚀 Next Steps:"
    echo "1. Install dependencies: pip3 install --user -r requirements.txt"
    echo "2. Start the system: ./start_complete_phantom.sh"
    echo "3. Monitor status: ./monitor_system.sh"
    echo "4. Run tests: ./dev_tools.sh test-task"
    echo ""
    echo "📖 Documentation:"
    echo "- Topology Setup: TOPOLOGY_SETUP.md"
    echo "- Deployment Guide: DEPLOYMENT_GUIDE.md"
    echo "- Complete README: README_COMPLETE.md"
}

# Run main integration
main "$@"