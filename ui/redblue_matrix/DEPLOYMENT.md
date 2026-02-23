# 🚀 RedBlue UI Suite - Deployment Guide

**Your AI. Your Hardware. Your Rules. Your Interface.**

## 📋 Overview

This guide covers deploying both the Matrix Web UI and Android app components of the RedBlue UI Suite. Choose the deployment method that best fits your needs.

## 🌐 Matrix Web UI Deployment

### Quick Start (Recommended)
```bash
# Clone the repository
git clone https://github.com/darknorthaco/redblue
cd redblue/matrix-web-ui

# Deploy with built-in script
chmod +x deploy-matrix-ui.sh
./deploy-matrix-ui.sh --python-server

# Access at http://localhost:3000
```

### Manual Deployment Options

#### Option 1: Python HTTP Server
```bash
cd redblue/matrix-web-ui
python3 -m http.server 3000
# Access at http://localhost:3000
```

#### Option 2: Node.js Server
```bash
cd redblue/matrix-web-ui
npm install -g http-server
http-server -p 3000 -c-1
# Access at http://localhost:3000
```

#### Option 3: Apache/Nginx
```bash
# Copy files to web server directory
sudo cp -r redblue/matrix-web-ui/* /var/www/html/
sudo systemctl restart apache2  # or nginx
# Access at http://your-server-ip
```

### Production Deployment

#### Docker Deployment
```dockerfile
# Create Dockerfile
FROM nginx:alpine
COPY matrix-web-ui/ /usr/share/nginx/html/
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

```bash
# Build and run
docker build -t redblue-web-ui .
docker run -d -p 8080:80 redblue-web-ui
```

#### Kubernetes Deployment
```yaml
# redblue-web-ui.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redblue-web-ui
spec:
  replicas: 3
  selector:
    matchLabels:
      app: redblue-web-ui
  template:
    metadata:
      labels:
        app: redblue-web-ui
    spec:
      containers:
      - name: web-ui
        image: redblue-web-ui:latest
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: redblue-web-ui-service
spec:
  selector:
    app: redblue-web-ui
  ports:
  - port: 80
    targetPort: 80
  type: LoadBalancer
```

## 📱 Android App Deployment

### Development Build
```bash
cd redblue/phantom-matrix-android

# Install dependencies
npm install

# Build debug APK
chmod +x build-android.sh
./build-android.sh
# Choose option 1 for debug build

# Install on connected device
adb install android/app/build/outputs/apk/debug/app-debug.apk
```

### Production Build
```bash
# Build release APK
./build-android.sh
# Choose option 2 for release build

# APK location: android/app/build/outputs/apk/release/app-release.apk
```

### Play Store Deployment
```bash
# Build Android App Bundle
./build-android.sh
# Choose option 3 for AAB bundle

# Upload to Play Console: android/app/build/outputs/bundle/release/app-release.aab
```

### Enterprise Distribution
```bash
# Build signed APK for enterprise
./gradlew assembleRelease

# Distribute via:
# - Internal app store
# - MDM solution
# - Direct download
```

## 🔧 Configuration

### Web UI Configuration
Edit `matrix-web-ui/phantom-interface.js`:
```javascript
// Backend connection settings
const CONFIG = {
    PHANTOM_BACKEND: 'ws://192.168.1.103:8765',
    RECONNECT_INTERVAL: 5000,
    MAX_RECONNECT_ATTEMPTS: 10,
    
    // UI settings
    MATRIX_RAIN_DROPS: 50,
    ANIMATION_SPEED: 60,
    
    // Branding
    COMPANY_NAME: 'Dark North Co.',
    SHOW_LOGO: true
};
```

### Android App Configuration
Edit `phantom-matrix-android/src/config.js`:
```javascript
export const CONFIG = {
    BACKEND_URL: 'ws://192.168.1.103:8765',
    RECONNECT_TIMEOUT: 5000,
    MAX_RETRIES: 10,
    
    // Performance settings
    MATRIX_DROPS_MOBILE: 30,
    ANIMATION_FPS: 60,
    
    // Features
    VOICE_INPUT_ENABLED: true,
    NOTIFICATIONS_ENABLED: true
};
```

## 🔒 Security Configuration

### HTTPS Setup (Web UI)
```nginx
# Nginx configuration
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    
    location / {
        root /var/www/redblue-web-ui;
        index index.html;
    }
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
}
```

### Network Security
```bash
# Firewall configuration
sudo ufw allow 3000/tcp  # Web UI
sudo ufw allow 8765/tcp  # Phantom backend
sudo ufw enable

# Restrict to local network only
sudo ufw delete allow 3000
sudo ufw allow from 192.168.1.0/24 to any port 3000
```

## 🌐 Network Setup

### Local Network Deployment
```bash
# Find your local IP
ip addr show | grep inet

# Update configuration files with your IP
sed -i 's/192.168.1.103/YOUR_IP_HERE/g' matrix-web-ui/phantom-interface.js
sed -i 's/192.168.1.103/YOUR_IP_HERE/g' phantom-matrix-android/src/config.js
```

### VPN Access (Remote Deployment)
```bash
# WireGuard configuration example
[Interface]
PrivateKey = YOUR_PRIVATE_KEY
Address = 10.0.0.2/24

[Peer]
PublicKey = SERVER_PUBLIC_KEY
Endpoint = your-server.com:51820
AllowedIPs = 192.168.1.0/24
```

## 📊 Monitoring & Logging

### Web UI Monitoring
```javascript
// Add to phantom-interface.js
const monitoring = {
    logConnections: true,
    logErrors: true,
    performanceMetrics: true
};

// Error tracking
window.addEventListener('error', (e) => {
    console.error('UI Error:', e.error);
    // Send to monitoring service if needed
});
```

### Android App Monitoring
```javascript
// Add to App.js
import crashlytics from '@react-native-firebase/crashlytics';

// Error boundary
const errorHandler = (error, errorInfo) => {
    crashlytics().recordError(error);
    console.error('App Error:', error, errorInfo);
};
```

## 🔄 Updates & Maintenance

### Automated Updates (Web UI)
```bash
#!/bin/bash
# update-web-ui.sh

cd /var/www/redblue-web-ui
git pull origin main
sudo systemctl reload nginx
echo "Web UI updated successfully"
```

### Android App Updates
```bash
# Build and distribute new version
./build-android.sh
# Upload to distribution channel
# Notify users of update availability
```

## 🐛 Troubleshooting

### Common Web UI Issues

#### Connection Failed
```bash
# Check backend status
curl -I http://192.168.1.103:8765
# Check firewall
sudo ufw status
# Check browser console for errors
```

#### Matrix Rain Performance
```javascript
// Reduce drops for better performance
const MATRIX_RAIN_DROPS = 25; // Default: 50
const ANIMATION_SPEED = 30;   // Default: 60
```

### Common Android App Issues

#### Build Failures
```bash
# Clean and rebuild
cd android
./gradlew clean
cd ..
npm run android
```

#### Connection Issues
```bash
# Check network connectivity
adb shell ping 192.168.1.103
# Check app logs
adb logcat | grep ReactNativeJS
```

## 📱 Multi-Platform Access

### Desktop Access
- **Web UI**: Any modern browser
- **Electron App**: Wrap web UI in Electron for desktop app

### Mobile Access
- **Android**: Native app from this repository
- **iOS**: Web UI works in Safari (native app coming soon)
- **Tablet**: Responsive design adapts to larger screens

### Remote Access
- **VPN**: Secure remote access to local network
- **SSH Tunnel**: Port forwarding for secure access
- **Cloud Proxy**: Reverse proxy for internet access (advanced)

## 🏢 Enterprise Deployment

### Load Balancing
```nginx
upstream redblue_backend {
    server 192.168.1.103:8080;
    server 192.168.1.104:8080;
    server 192.168.1.105:8080;
}

server {
    location / {
        proxy_pass http://redblue_backend;
    }
}
```

### High Availability
```yaml
# Docker Swarm deployment
version: '3.8'
services:
  redblue-web-ui:
    image: redblue-web-ui:latest
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
    ports:
      - "8080:80"
```

## 📞 Support

### Community Support
- **GitHub Issues**: Bug reports and feature requests
- **Discord**: Real-time community help
- **Documentation**: Comprehensive guides and tutorials

### Commercial Support
- **Email**: support@darknorthco.com
- **Priority Support**: Available with commercial licenses
- **Custom Deployment**: Professional services available

---

## 🚀 Ready to Deploy?

Choose your deployment method and start bringing the Matrix to your AI infrastructure!

**Your AI. Your Hardware. Your Rules. Your Interface.**

*For deployment assistance, contact support@darknorthco.com*