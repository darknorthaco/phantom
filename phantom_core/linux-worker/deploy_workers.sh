#!/bin/bash

# Phantom Linux Worker Deployment Script
# Deploys multiple worker instances based on detected GPUs

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTROLLER_HOST="${CONTROLLER_HOST:-localhost}"
CONTROLLER_PORT="${CONTROLLER_PORT:-8080}"
BASE_WORKER_PORT="${BASE_WORKER_PORT:-8090}"

echo "🚀 Phantom Linux Worker Deployment"
echo "=================================="
echo "Controller: $CONTROLLER_HOST:$CONTROLLER_PORT"
echo "Base Worker Port: $BASE_WORKER_PORT"
echo ""

# Function to detect GPUs
detect_gpus() {
    echo "🔍 Detecting available GPUs..."
    
    # Check for NVIDIA GPUs
    if command -v nvidia-smi &> /dev/null; then
        echo "📊 NVIDIA GPUs detected:"
        nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader,nounits | while IFS=',' read -r index name memory; do
            echo "  GPU $index: $name (${memory}MB)"
        done
    fi
    
    # Check for AMD GPUs
    if command -v rocm-smi &> /dev/null; then
        echo "📊 AMD GPUs detected:"
        rocm-smi --showid --showproductname | grep -E "GPU\[|Card series:" | paste - - | while read -r line; do
            echo "  $line"
        done
    elif command -v lspci &> /dev/null; then
        echo "📊 AMD GPUs detected (via lspci):"
        lspci | grep -i "vga.*amd\|vga.*ati" | while read -r line; do
            echo "  $line"
        done
    fi
    
    echo ""
}

# Function to create worker instance
create_worker_instance() {
    local worker_id="$1"
    local worker_port="$2"
    local gpu_index="$3"
    local gpu_name="$4"
    
    echo "👷 Creating worker instance: $worker_id"
    
    # Create instance directory
    local instance_dir="$SCRIPT_DIR/instances/$worker_id"
    mkdir -p "$instance_dir"
    
    # Create worker configuration
    cat > "$instance_dir/worker_config.json" << EOF
{
    "worker_id": "$worker_id",
    "controller_host": "$CONTROLLER_HOST",
    "controller_port": $CONTROLLER_PORT,
    "worker_port": $worker_port,
    "gpu_index": $gpu_index,
    "gpu_name": "$gpu_name",
    "max_concurrent_tasks": 1,
    "log_level": "INFO"
}
EOF

    # Create worker startup script
    cat > "$instance_dir/start_worker.sh" << 'EOF'
#!/bin/bash

INSTANCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKER_DIR="$(dirname "$INSTANCE_DIR")"
CONFIG_FILE="$INSTANCE_DIR/worker_config.json"

echo "🚀 Starting Phantom Linux Worker"
echo "Instance: $(basename "$INSTANCE_DIR")"
echo "Config: $CONFIG_FILE"
echo ""

# Set Python path
export PYTHONPATH="$WORKER_DIR:$PYTHONPATH"

# Change to worker directory
cd "$WORKER_DIR"

# Start worker with configuration
python3 -m linux_worker.main --config "$CONFIG_FILE" 2>&1 | tee "$INSTANCE_DIR/worker.log"
EOF

    chmod +x "$instance_dir/start_worker.sh"
    
    # Create worker stop script
    cat > "$instance_dir/stop_worker.sh" << 'EOF'
#!/bin/bash

INSTANCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKER_ID="$(basename "$INSTANCE_DIR")"

echo "🛑 Stopping worker: $WORKER_ID"

# Find and kill worker process
pkill -f "worker_config.json.*$WORKER_ID" || echo "No running worker process found"

# Clean up PID file if it exists
if [ -f "$INSTANCE_DIR/worker.pid" ]; then
    rm "$INSTANCE_DIR/worker.pid"
fi

echo "✅ Worker $WORKER_ID stopped"
EOF

    chmod +x "$instance_dir/stop_worker.sh"
    
    echo "✅ Worker instance created: $instance_dir"
}

# Function to deploy NVIDIA workers
deploy_nvidia_workers() {
    if ! command -v nvidia-smi &> /dev/null; then
        echo "ℹ️ NVIDIA drivers not found, skipping NVIDIA workers"
        return
    fi
    
    echo "🎮 Deploying NVIDIA workers..."
    
    local worker_count=0
    nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader,nounits | while IFS=',' read -r index name memory; do
        # Clean up GPU name
        gpu_name=$(echo "$name" | xargs)
        worker_id="nvidia-gpu-$index"
        worker_port=$((BASE_WORKER_PORT + worker_count))
        
        create_worker_instance "$worker_id" "$worker_port" "$index" "$gpu_name"
        
        worker_count=$((worker_count + 1))
    done
}

# Function to deploy AMD workers
deploy_amd_workers() {
    echo "🔧 Deploying AMD workers..."
    
    local worker_count=10  # Start AMD workers at port offset 10
    
    if command -v rocm-smi &> /dev/null; then
        # Use ROCm for AMD GPU detection
        rocm_output=$(rocm-smi --showid 2>/dev/null || echo "")
        if [ -n "$rocm_output" ]; then
            echo "$rocm_output" | grep "GPU\[" | while read -r line; do
                if [[ $line =~ GPU\[([0-9]+)\] ]]; then
                    index="${BASH_REMATCH[1]}"
                    worker_id="amd-gpu-$index"
                    worker_port=$((BASE_WORKER_PORT + worker_count))
                    
                    # Try to get GPU name
                    gpu_name="AMD GPU $index"
                    if command -v rocm-smi &> /dev/null; then
                        gpu_name=$(rocm-smi --device="$index" --showproductname 2>/dev/null | grep "Card series:" | cut -d: -f2 | xargs || echo "AMD GPU $index")
                    fi
                    
                    create_worker_instance "$worker_id" "$worker_port" "$index" "$gpu_name"
                    
                    worker_count=$((worker_count + 1))
                fi
            done
        fi
    else
        # Fallback to lspci detection
        lspci | grep -i "vga.*amd\|vga.*ati" | while read -r line; do
            # Extract basic info from lspci
            if [[ $line =~ ^([0-9a-f:\.]+) ]]; then
                pci_id="${BASH_REMATCH[1]}"
                gpu_name=$(echo "$line" | sed 's/.*controller: //' | sed 's/ \[.*$//')
                worker_id="amd-pci-$(echo "$pci_id" | tr ':.' '-')"
                worker_port=$((BASE_WORKER_PORT + worker_count))
                
                create_worker_instance "$worker_id" "$worker_port" "0" "$gpu_name"
                
                worker_count=$((worker_count + 1))
            fi
        done
    fi
}

# Function to create storage hub worker
deploy_storage_hub() {
    echo "💾 Deploying storage hub worker..."
    
    local worker_id="storage-hub"
    local worker_port=$((BASE_WORKER_PORT + 20))
    
    create_worker_instance "$worker_id" "$worker_port" "-1" "Storage Hub"
    
    # Add storage-specific configuration
    local instance_dir="$SCRIPT_DIR/instances/$worker_id"
    cat > "$instance_dir/storage_config.json" << EOF
{
    "storage_paths": [
        "/var/lib/phantom/models",
        "/var/lib/phantom/datasets",
        "/var/lib/phantom/cache"
    ],
    "max_storage_gb": 1000,
    "cleanup_policy": "lru",
    "serve_models": true,
    "serve_datasets": true
}
EOF

    echo "✅ Storage hub worker created"
}

# Function to create master deployment script
create_master_scripts() {
    echo "📝 Creating master deployment scripts..."
    
    # Create start all workers script
    cat > "$SCRIPT_DIR/start_all_workers.sh" << 'EOF'
#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Starting all Phantom Linux workers..."
echo ""

# Start all worker instances
for instance_dir in "$SCRIPT_DIR/instances"/*; do
    if [ -d "$instance_dir" ] && [ -f "$instance_dir/start_worker.sh" ]; then
        worker_id="$(basename "$instance_dir")"
        echo "🔄 Starting worker: $worker_id"
        
        # Start worker in background
        cd "$instance_dir"
        nohup ./start_worker.sh > worker.log 2>&1 &
        echo $! > worker.pid
        
        echo "✅ Worker $worker_id started (PID: $(cat worker.pid))"
        sleep 2  # Brief delay between starts
    fi
done

echo ""
echo "🎉 All workers started!"
echo "📊 Use './monitor_workers.sh' to check status"
EOF

    chmod +x "$SCRIPT_DIR/start_all_workers.sh"
    
    # Create stop all workers script
    cat > "$SCRIPT_DIR/stop_all_workers.sh" << 'EOF'
#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🛑 Stopping all Phantom Linux workers..."
echo ""

# Stop all worker instances
for instance_dir in "$SCRIPT_DIR/instances"/*; do
    if [ -d "$instance_dir" ] && [ -f "$instance_dir/stop_worker.sh" ]; then
        worker_id="$(basename "$instance_dir")"
        echo "🔄 Stopping worker: $worker_id"
        
        cd "$instance_dir"
        ./stop_worker.sh
    fi
done

echo ""
echo "✅ All workers stopped!"
EOF

    chmod +x "$SCRIPT_DIR/stop_all_workers.sh"
    
    # Create monitor workers script
    cat > "$SCRIPT_DIR/monitor_workers.sh" << 'EOF'
#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "📊 Phantom Linux Workers Status"
echo "==============================="
echo ""

# Check status of all worker instances
for instance_dir in "$SCRIPT_DIR/instances"/*; do
    if [ -d "$instance_dir" ]; then
        worker_id="$(basename "$instance_dir")"
        
        # Check if PID file exists and process is running
        if [ -f "$instance_dir/worker.pid" ]; then
            pid=$(cat "$instance_dir/worker.pid")
            if kill -0 "$pid" 2>/dev/null; then
                status="🟢 RUNNING (PID: $pid)"
            else
                status="🔴 STOPPED (stale PID)"
            fi
        else
            status="⚪ NOT STARTED"
        fi
        
        # Get worker port from config
        port="N/A"
        if [ -f "$instance_dir/worker_config.json" ]; then
            port=$(grep -o '"worker_port": [0-9]*' "$instance_dir/worker_config.json" | cut -d: -f2 | xargs)
        fi
        
        printf "%-20s %-25s Port: %s\n" "$worker_id" "$status" "$port"
    fi
done

echo ""
echo "💡 Commands:"
echo "  Start all:  ./start_all_workers.sh"
echo "  Stop all:   ./stop_all_workers.sh"
echo "  Monitor:    ./monitor_workers.sh"
EOF

    chmod +x "$SCRIPT_DIR/monitor_workers.sh"
    
    echo "✅ Master scripts created"
}

# Function to create worker main module
create_worker_main() {
    echo "📝 Creating worker main module..."
    
    cat > "$SCRIPT_DIR/linux_worker/main.py" << 'EOF'
#!/usr/bin/env python3
"""
Phantom Linux Worker Main Entry Point
"""

import asyncio
import argparse
import json
import logging
import signal
import sys
from pathlib import Path

from worker import PhantomLinuxWorker, create_worker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config(config_path: str) -> dict:
    """Load worker configuration from JSON file"""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config from {config_path}: {e}")
        raise

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Phantom Linux Worker")
    parser.add_argument("--config", required=True, help="Path to worker configuration file")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    
    args = parser.parse_args()
    
    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))
    
    # Load configuration
    config = load_config(args.config)
    logger.info(f"Loaded configuration: {config['worker_id']}")
    
    # Create worker instance
    worker = create_worker(config)
    
    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating shutdown...")
        asyncio.create_task(worker.shutdown())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize worker
        await worker.initialize()
        
        # Register with controller
        if not await worker.register_with_controller():
            logger.error("Failed to register with controller")
            return 1
        
        # Start background tasks
        await worker.start_background_tasks()
        
        # Start FastAPI server
        import uvicorn
        config = uvicorn.Config(
            worker.app,
            host="0.0.0.0",
            port=worker.worker_port,
            log_level=args.log_level.lower()
        )
        server = uvicorn.Server(config)
        
        logger.info(f"🚀 Starting worker {worker.worker_id} on port {worker.worker_port}")
        await server.serve()
        
    except Exception as e:
        logger.error(f"Worker failed: {e}")
        return 1
    finally:
        await worker.shutdown()
    
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
EOF

    echo "✅ Worker main module created"
}

# Main deployment process
main() {
    echo "🏗️ Starting Phantom Linux Worker deployment..."
    echo ""
    
    # Create instances directory
    mkdir -p "$SCRIPT_DIR/instances"
    
    # Detect available GPUs
    detect_gpus
    
    # Deploy workers for different GPU types
    deploy_nvidia_workers
    deploy_amd_workers
    deploy_storage_hub
    
    # Create master scripts
    create_master_scripts
    
    # Create worker main module
    create_worker_main
    
    echo ""
    echo "🎉 Deployment completed successfully!"
    echo ""
    echo "📋 Next steps:"
    echo "1. Review worker configurations in ./instances/"
    echo "2. Start all workers: ./start_all_workers.sh"
    echo "3. Monitor status: ./monitor_workers.sh"
    echo "4. Check controller connection at $CONTROLLER_HOST:$CONTROLLER_PORT"
    echo ""
    echo "📁 Worker instances created:"
    ls -la "$SCRIPT_DIR/instances/" 2>/dev/null || echo "  (No instances directory yet)"
}

# Run main function
main "$@"