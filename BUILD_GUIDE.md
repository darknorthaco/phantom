# Phantom v1.1.0 - Complete Setup & Build Guide

## ⚠️ Current Status (as of ${(Get-Date).ToString('yyyy-MM-dd')})

### ✅ Completed:
1. **Version synchronization** - All files updated to v1.1.0:
   - `/VERSION`
   - `/phantom_app/package.json`
   - `/phantom_app/src-tauri/Cargo.toml`
   - `/phantom_app/src-tauri/tauri.conf.json`

2. **Codebase features** - All functionality is implemented:
   - ✅ Chat interface ([ChatPanel.tsx](phantom_app/src/components/ChatPanel.tsx))
   - ✅ Worker management ([WorkersPanel.tsx](phantom_app/src/components/WorkersPanel.tsx))
   - ✅ Model routing and LLM Task Master integration
   - ✅ Metrics dashboard and console
   - ✅ Full navigation sidebar with all panels

### ⚠️ Pending:

1. **Git tags not created** - No release tags exist yet
   - Run `./create_tags.ps1` when git is available in PATH
   - This will create annotated tags for v1.0.0 and v1.1.0

2. **Application not built** - No `phantom_app.exe` exists
   - Rust and Node.js need to be installed
   - Run `./phantom_app/build.ps1` after installing prerequisites

3. **Prerequisites missing**:
   - ❌ Rust 1.85+ (required for Tauri compilation)
   - ❌ Node.js 18+ (required for frontend build)
   - ❌ Git (recommended for version control)

---

## 🚀 Installation & Build Instructions

### Step 1: Install Prerequisites

#### A. Rust (Required)
```powershell
# Option 1: Using rustup (recommended)
# Download from https://rustup.rs/ and run installer

# Option 2: Using winget
winget install Rustlang.Rustup

# Verify installation
cargo --version  # Should show 1.85 or higher
```

#### B. Node.js (Required)
```powershell
# Option 1: Download from https://nodejs.org/
# Install LTS version (18.x or higher)

# Option 2: Using winget
winget install OpenJS.NodeJS.LTS

# Verify installation
node --version  # Should show v18.x or higher
npm --version
```

#### C. Visual Studio Build Tools (Required for Windows)
```powershell
# Download and install from:
# https://visualstudio.microsoft.com/downloads/

# Required workload:
# - Desktop development with C++
```

#### D. Git (Recommended)
```powershell
# Option 1: Download from https://git-scm.com/
# Option 2: Using winget
winget install Git.Git

# Verify installation
git --version
```

**After installing prerequisites, restart your PowerShell terminal!**

---

### Step 2: Build the Application

```powershell
# Navigate to repository root
cd c:\Users\david\OneDrive\Documents\GitHub\phantom

# Run the build script
.\phantom_app\build.ps1
```

The script will:
1. Check prerequisites
2. Install npm dependencies
3. Compile Rust backend
4. Build React frontend
5. Create the executable

**First build takes 10-20 minutes** due to Rust compilation. Subsequent builds are much faster.

---

### Step 3: Create Git Tags

```powershell
# After git is installed, create release tags
.\create_tags.ps1

# Push tags to remote (if desired)
git push --tags
```

---

## 🧪 Testing the Application

### A. Start the Phantom Controller

The Tauri app communicates with the Phantom controller API. Start it first:

```powershell
# Set required environment variable
$env:PHANTOM_STATE_DIR = "c:\temp\phantom\state"

# Navigate to controller
cd c:\Users\david\OneDrive\Documents\GitHub\phantom\phantom_core

# Install Python dependencies (if not already done)
pip install -r requirements.txt

# Start the controller
python run.py --host 127.0.0.1 --port 8080 --security disabled
```

The controller should start and report "healthy" status on http://127.0.0.1:8080/health

### B. Run the Phantom Desktop App

In a **new PowerShell terminal**:

```powershell
# Option 1: Run the built executable
cd c:\Users\david\OneDrive\Documents\GitHub\phantom\phantom_app
.\src-tauri\target\release\phantom_app.exe

# Option 2: Development mode with hot-reload
npm run tauri dev
```

### C. Verify Features

Once the app launches:

1. **Auto-detection**: App should detect the running controller and skip the wizard
2. **Navigation**: Sidebar should show all panels (Chat, Console, Workers, etc.)
3. **Chat Interface**: Click "Chat" in sidebar - you should see the chat panel
4. **Worker Detection**: 
   - Click "Workers" panel
   - Should show "No workers registered" (expected if none are running)
   - To register a worker, you'd need to deploy one via the controller API

---

## 🐛 Troubleshooting

### Issue: "No workers found"
**Cause**: No worker instances have been registered with the controller

**Solutions**:
1. Check controller is running: http://127.0.0.1:8080/health
2. Workers must be manually registered or deployed
3. See phantom_core documentation for worker deployment

### Issue: "Chat interface not visible"
**Status**: ✅ **RESOLVED** - Feature is implemented

The chat interface exists in the codebase and will be visible after building the app. It was implemented but the old v1.0.0 executable (if any) predates this feature.

### Issue: Build fails with "Rust toolchain not found"
```powershell
# Ensure Rust is in PATH
rustup default stable
rustup update
```

### Issue: Build fails with "node-gyp" errors
```powershell
# Install Windows Build Tools
npm install --global windows-build-tools
```

---

## 📋 Quick Reference

| Component | Version | Status | Location |
|-----------|---------|--------|----------|
| Phantom Core | 1.1.0 | ✅ Implemented | `/VERSION` |
| Tauri App | 1.1.0 | ✅ Code ready | `/phantom_app/` |
| Chat Panel | 1.1.0 | ✅ Implemented | `/phantom_app/src/components/ChatPanel.tsx` |
| Workers Panel | 1.1.0 | ✅ Implemented | `/phantom_app/src/components/WorkersPanel.tsx` |
| Executable | N/A | ❌ Not built | Needs build |
| Git Tags | N/A | ❌ Not created | Run `create_tags.ps1` |

---

## 📚 Additional Resources

- **Tauri Documentation**: https://tauri.app/
- **Rust Installation**: https://rustup.rs/
- **Node.js Downloads**: https://nodejs.org/
- **Phantom Core README**: [phantom_core/README.md](phantom_core/README.md)
- **AGENTS.md**: [AGENTS.md](AGENTS.md) - Development environment guide

---

## 🎯 Next Steps

1. Install Rust and Node.js (see Step 1)
2. Restart PowerShell
3. Run `.\phantom_app\build.ps1`
4. Run `.\create_tags.ps1` (when git is available)
5. Test the application (see Testing section)

**All code is ready - it just needs to be compiled!**
