# 🔋 Phantom RedBlue - Android App

**Your LLM. Your Hardware. Your Rules.**

A RedBlue-themed Android application for monitoring and controlling the Phantom Distributed Compute Fabric. Built by Dark North Co. for true compute independence.

![Matrix Style](https://img.shields.io/badge/Style-Matrix-00FF41)
![Platform](https://img.shields.io/badge/Platform-Android-green)
![React Native](https://img.shields.io/badge/React%20Native-0.72.6-blue)
![License](https://img.shields.io/badge/License-Dark%20North%20Co.-red)

## 🎯 Features

### 🖥️ **Matrix Digital Rain**
- Real-time animated background using authentic Japanese katakana
- GPU utilization-driven color changes
- Mobile-optimized performance (50 drop limit)

### 🔋 **GPU Cluster Monitoring**
Hardware is auto-discovered during installation when Phantom scans the network for workers.
GPU cards are rendered as generic slots (GPU-0, GPU-1, GPU-2, GPU-3) and populated
with real names/roles from the controller /workers API at runtime.
- **GPU-0** - Slot 0 (Matrix Green)
- **GPU-1** - Slot 1 (Dark North Red)
- **GPU-2** - Slot 2 (Dark North Teal)
- **GPU-3** - Slot 3 (Yellow)

### 🤖 **LLM Chat Interface**
- Terminal-style chat with your homebrew LLM
- Model switching between all 4 GPUs
- WebSocket integration with Phantom backend
- No corporate surveillance - your data stays on YOUR hardware

### 📊 **System Statistics**
- Network topology visualization
- Real-time performance metrics
- System health monitoring
- Emergency control protocols

### 🎨 **Dark North Co. Branding**
- Integrated rubber duck logo with RedBlue effects
- Red outline with teal eye design
- Authentic Dark North aesthetic
- Professional yet playful branding

## 🚀 Quick Start

### Prerequisites
- **Node.js** 16+ 
- **React Native CLI**
- **Android Studio** with SDK
- **Java Development Kit** 11+

### Installation

1. **Clone and Setup**
```bash
git clone <your-repo>
cd phantom-matrix-android
npm install
```

2. **Build for Android**
```bash
chmod +x build-android.sh
./build-android.sh
```

3. **Choose Build Type**
- Debug APK (for testing)
- Release APK (for distribution) 
- Android App Bundle (for Play Store)
- Install on connected device

## 📱 App Structure

```
phantom-matrix-android/
├── src/components/
│   ├── SplashScreen.js      # Matrix-themed startup
│   ├── MainDashboard.js     # Primary interface
│   ├── MatrixRain.js        # Digital rain animation
│   ├── MatrixLogo.js        # Dark North Co. logo
│   ├── GPUMonitor.js        # GPU cluster monitoring
│   ├── AIChat.js            # AI chat interface
│   └── SystemStats.js       # System statistics
├── android/                 # Android native configuration
├── package.json            # React Native dependencies
├── App.js                  # Main application entry
└── build-android.sh        # Build automation script
```

## 🔌 Phantom Backend Integration

The app connects to your Phantom Distributed Compute Fabric via WebSocket:

```javascript
// Default connection — hardware auto-discovered during network scan
ws://<controller-ip>:8081

// GPU topology populated at runtime by controller /workers API
// Example (generic slots until scan completes):
Server Node:
├── GPU-0 (auto-detected)
└── GPU-1 (auto-detected)

Workstation Node:
├── GPU-2 (auto-detected)
└── GPU-3 (auto-detected)
```

## 🎨 Design Philosophy

### Matrix Aesthetic
- **Authentic Matrix digital rain** with Japanese katakana
- **CRT monitor effects** with scan lines and glow
- **Terminal-style interfaces** with monospace fonts
- **RedBlue color scheme** (Matrix green, red, teal, yellow)

### Dark North Co. Branding
- **Rubber duck logo** integrated with Matrix effects
- **Red outline with teal eye** matching original design
- **Professional yet playful** brand identity
- **"Your LLM. Your Hardware. Your Rules."** messaging

## 🔒 Security Features

- **Local network only** - no external data transmission
- **Cleartext traffic** allowed for local Phantom connection
- **Emergency stop protocols** with human override
- **No corporate surveillance** - your data never leaves your network

## 📱 Mobile Optimizations

### Touch Interface
- **Swipe gestures** for GPU switching
- **Tap and hold** for detailed stats
- **Pull to refresh** for real-time updates
- **Haptic feedback** for interactions

### Performance
- **GPU-optimized animations** with 60fps target
- **Memory efficient** Matrix rain (50 drop limit)
- **Background sync** when app is minimized
- **Offline mode** with local AI fallback

## 🏪 Play Store Preparation

### App Information
- **Name**: Phantom RedBlue
- **Package**: com.darknorthco.phantommatrix
- **Category**: Tools / Productivity
- **Target Audience**: Tech enthusiasts, LLM hobbyists, distributed compute users

### Key Features for Store Listing
1. **"Matrix Mode"** - Full-screen digital rain with LLM voice
2. **"Cluster Commander"** - Remote control your GPU farm
3. **"LLM Anywhere"** - Chat with your homebrew LLM on the go
4. **"No Corporate BS"** - Your data stays on YOUR hardware
5. **"Hacker Aesthetic"** - Authentic RedBlue/Dark North interface

## 🛠️ Development

### Adding New Features
1. Create component in `src/components/`
2. Import in `MainDashboard.js`
3. Add to tab navigation
4. Update WebSocket integration

### Customizing Branding
1. Replace logo SVG in `MatrixLogo.js`
2. Update colors in component styles
3. Modify splash screen in `android/res/drawable/`
4. Update app name in `strings.xml`

## 🔧 Build Configuration

### Debug Build
```bash
./build-android.sh
# Choose option 1
```

### Release Build
```bash
./build-android.sh
# Choose option 2
# APK: android/app/build/outputs/apk/release/
```

### Play Store Bundle
```bash
./build-android.sh
# Choose option 3
# AAB: android/app/build/outputs/bundle/release/
```

## 🌐 Network Configuration

The app is configured to connect to your local Phantom network:

- **Primary Server**: 192.168.1.103:8081
- **Fallback**: localhost:8081
- **Security**: Local network cleartext allowed
- **Protocols**: WebSocket, HTTP for local resources

## 🎯 Roadmap

### Phase 1: Core Features ✅
- [x] Matrix UI with digital rain
- [x] GPU monitoring dashboard
- [x] AI chat interface
- [x] Dark North Co. branding
- [x] Android build configuration

### Phase 2: Enhanced Features
- [ ] Voice input for AI chat
- [ ] Push notifications for system alerts
- [ ] Offline LLM model integration
- [ ] Advanced performance analytics
- [ ] Custom Matrix rain patterns

### Phase 3: Advanced Features
- [ ] VPN integration for remote access
- [ ] Multi-cluster support
- [ ] LLM model repository
- [ ] Advanced security protocols
- [ ] Tablet optimization

## 🤝 Contributing

This is a Dark North Co. project for the Phantom Distributed Compute Fabric. 

### Development Guidelines
- Follow RedBlue aesthetic principles
- Maintain Dark North Co. branding consistency
- Optimize for mobile performance
- Ensure local-first architecture

## 📄 License

**Dark North Co. Proprietary License**

Your LLM. Your Hardware. Your Rules.

---

## 🔋 **Ready to Enter the Fabric?**

```bash
chmod +x build-android.sh
./build-android.sh
```

**Welcome to the future of distributed compute — where YOU control the fabric.**

---

*Built with ❤️ by Dark North Co. — Empowering compute independence since 2024*