#!/bin/bash

echo "==============================================="
echo "   🔧 Phantom Socket Cleanup & Modernization"
echo "==============================================="

PROJECT_DIR="/opt/phantom_test"
CONTROLLER_FILE="$PROJECT_DIR/phantom_core/controller_api.py"
SOCKET_FILE="$PROJECT_DIR/phantom_core/socket_integration.py"

# 1. Ensure we are in the correct directory
if [[ ! -d "$PROJECT_DIR" ]]; then
    echo "❌ ERROR: $PROJECT_DIR not found. Are you on the right machine?"
    exit 1
fi

echo "📁 Project directory found: $PROJECT_DIR"

# 2. Kill any leftover socket servers on port 8081
echo "🔍 Checking for processes using port 8081..."
PIDS=$(sudo lsof -t -i :8081)

if [[ -n "$PIDS" ]]; then
    echo "🛑 Killing old socket server processes: $PIDS"
    sudo kill -9 $PIDS
else
    echo "✅ No processes using port 8081"
fi

# 3. Remove old Phantom OG socket startup from controller
echo "🔧 Checking controller for old socket startup..."

if grep -q "socket_manager.start" "$CONTROLLER_FILE"; then
    echo "🛠️ Removing old socket server startup from controller_api.py"
    sudo sed -i 's/await socket_manager.start()/pass  # removed old socket server/' "$CONTROLLER_FILE"
else
    echo "✅ Old socket server startup already removed"
fi

# 4. Ensure handle_client has correct signature
echo "🔍 Verifying handle_client signature..."

if grep -q "async def handle_client(self, websocket, path)" "$SOCKET_FILE"; then
    echo "✅ Correct handle_client signature already present"
else
    echo "❌ ERROR: handle_client signature incorrect. Please update manually."
    exit 1
fi

# 5. Restart Phantom system
echo "🚀 Restarting Phantom Integrated System..."
cd "$PROJECT_DIR"
./start_complete_phantom.sh

echo "==============================================="
echo "   🎉 Cleanup Complete — System Restarted"
echo "==============================================="
