# Phantom AI Matrix Interface

A cyberpunk-inspired Matrix-style web interface for the Phantom Distributed Compute Fabric. This UI provides real-time monitoring and control of your distributed GPU cluster with an authentic retro-futuristic aesthetic.

## 🎮 Features

### 🔋 **Matrix Digital Rain**
- Real-time animated background using actual GPU utilization data
- Color-coded rain based on active GPU (Green=GTX1080, Red=FirePro, Cyan=RTX5080, Yellow=RTX5060)
- Dynamic intensity based on cluster workload

### 🖥️ **Cyberpunk Dashboard**
- **Cluster Status Panel**: Real-time GPU monitoring with temperature, utilization, and memory usage
- **Neural Interface**: AI chat with model switching and terminal-style interaction
- **System Monitor**: Performance graphs, task queue, network status, and security level

### 🎨 **Authentic Matrix Styling**
- CRT screen effects with scan lines and phosphor glow
- Matrix green color scheme with accent colors
- Glitch effects and typing animations
- Retro terminal fonts and ASCII aesthetics

### 🔌 **Real-time Integration**
- WebSocket connection to Phantom backend
- Live GPU utilization data
- Task status updates
- System health monitoring

## 🚀 Quick Start

### 1. **Deploy the Interface**
```bash
# Copy to your web server directory
cp -r matrix-ui/ /var/www/html/phantom-matrix/

# Or serve locally
cd matrix-ui/
python3 -m http.server 8080
```

### 2. **Access the Interface**
Open your browser and navigate to:
- **Local**: `http://localhost:8080`
- **Network**: `http://192.168.1.103:8080`

### 3. **Connect to Phantom**
The interface automatically connects to your Phantom socket server at:
- **WebSocket**: `ws://192.168.1.103:8765`

## 📁 File Structure

```
matrix-ui/
├── index.html              # Main HTML structure
├── styles.css              # Matrix-style CSS with CRT effects
├── matrix-rain.js          # Digital rain animation engine
├── phantom-interface.js    # Main JavaScript controller
├── sounds/                 # Audio files directory
│   ├── typing.mp3          # Keyboard typing sounds
│   ├── notification.mp3    # System notification sounds
│   └── README.md           # Audio setup guide
└── README.md               # This file
```

## 🎯 **Interface Sections**

### **Left Panel - Neural Cluster Status**
- **Fedora Server Node**: GTX 1080 (LLM Task Master) + FirePro W9100 (Memory Specialist)
- **Windows Workstation**: RTX 5080 (ML Powerhouse) + RTX 5060 (Modern Compute)
- Real-time GPU metrics with color-coded status indicators

### **Center Panel - Neural Interface**
- AI chat interface with Matrix terminal styling
- Model selection dropdown (Llama-2, Mistral, CodeLlama, Custom)
- Streaming text responses with typing effects
- Command history and system messages

### **Right Panel - System Monitor**
- Real-time performance graphs
- Active task queue with GPU assignments
- Network node status (Fedora Server + Windows PC)
- Security level indicator

### **Bottom Panel - Control Center**
- Emergency stop, cluster restart, load balancing controls
- System uptime, completed tasks, power consumption
- Status indicators and system metrics

## 🔧 **Configuration**

### **WebSocket Connection**
Edit `phantom-interface.js` to change the connection endpoint:
```javascript
this.socket = new WebSocket('ws://YOUR_PHANTOM_SERVER:8765');
```

### **GPU Configuration**
Update GPU names and roles in `index.html`:
```html
<div class="gpu-name">YOUR_GPU_NAME</div>
<div class="gpu-role">YOUR_GPU_ROLE</div>
```

### **Color Themes**
Modify CSS variables in `styles.css`:
```css
:root {
    --matrix-green: #00FF41;
    --matrix-cyan: #00FFFF;
    --matrix-red: #FF0040;
    /* Add your custom colors */
}
```

## 🎵 **Audio Setup**

1. **Download Matrix-style audio files**:
   - `typing.mp3` - Mechanical keyboard sounds
   - `notification.mp3` - System alert sounds

2. **Place in sounds directory**:
   ```bash
   matrix-ui/sounds/typing.mp3
   matrix-ui/sounds/notification.mp3
   ```

3. **Audio sources**:
   - Freesound.org (free with attribution)
   - Matrix movie sound effects
   - Cyberpunk game audio assets

## 🌐 **Integration with Phantom**

### **WebSocket Messages**
The interface sends/receives these message types:

```javascript
// Outgoing messages
{
    type: 'ai_query',
    message: 'User input',
    model: 'llama2-7b',
    timestamp: Date.now()
}

// Incoming messages
{
    type: 'gpu_status',
    gpus: {
        gtx1080: { utilization: 45, temperature: 72, memory_used: 6800 },
        // ... other GPUs
    }
}
```

### **Demo Mode**
If WebSocket connection fails, the interface automatically enters demo mode with:
- Simulated GPU data
- Mock AI responses
- Fake task generation
- All visual effects still functional

## 🎨 **Customization**

### **Adding New GPU Types**
1. **Update HTML structure** in `index.html`
2. **Add CSS styling** in `styles.css`
3. **Update JavaScript** in `phantom-interface.js`
4. **Configure Matrix rain colors** in `matrix-rain.js`

### **Custom Matrix Effects**
- **Burst effects**: `matrixRain.addBurst(x, y, color)`
- **Pulse effects**: `matrixRain.pulse(color)`
- **Custom characters**: Modify `chars` array in `matrix-rain.js`

### **Responsive Design**
The interface automatically adapts to different screen sizes:
- **Desktop**: Full 3-column layout
- **Tablet**: 2-column layout with stacked monitor panel
- **Mobile**: Single column with collapsible sections

## 🔒 **Security Considerations**

- **Local Network Only**: Interface designed for internal network use
- **No Authentication**: Assumes trusted network environment
- **WebSocket Security**: Uses unencrypted WebSocket (upgrade to WSS for production)
- **CORS Policy**: May need CORS configuration for cross-origin requests

## 🐛 **Troubleshooting**

### **Connection Issues**
```bash
# Check if Phantom socket server is running
netstat -ln | grep 8765

# Test WebSocket connection
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Key: test" -H "Sec-WebSocket-Version: 13" \
  http://192.168.1.103:8765
```

### **Audio Not Working**
- Check browser audio permissions
- Verify audio files exist in `sounds/` directory
- Test with browser developer console for audio errors

### **Performance Issues**
- Reduce Matrix rain density in `matrix-rain.js`
- Disable CRT effects in `styles.css`
- Lower refresh rates in `phantom-interface.js`

## 🎯 **Browser Compatibility**

- **Chrome/Chromium**: Full support
- **Firefox**: Full support
- **Safari**: Partial support (some CSS effects may vary)
- **Edge**: Full support
- **Mobile browsers**: Responsive design with touch support

## 📈 **Performance Tips**

1. **Optimize Matrix Rain**: Reduce character density for lower-end devices
2. **Disable Effects**: Comment out CRT overlay for better performance
3. **Reduce Updates**: Increase refresh intervals for slower connections
4. **Cache Assets**: Use web server caching for faster loading

---

## 🔋 **Welcome to the Matrix, Neo.**

Your Phantom AI cluster awaits. The red pill or the blue pill - the choice is yours, but the Matrix-style interface is ready either way! 🕶️💊

**"There is no spoon... only distributed GPU compute."** 🥄🚫