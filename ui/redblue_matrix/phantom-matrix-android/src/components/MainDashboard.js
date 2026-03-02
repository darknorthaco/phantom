import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  Dimensions,
  StyleSheet,
  StatusBar,
  Animated,
  Vibration,
} from 'react-native';
import MatrixLogo from './MatrixLogo';
import MatrixRain from './MatrixRain';
import GPUMonitor from './GPUMonitor';
import AIChat from './AIChat';
import SystemStats from './SystemStats';

const { width, height } = Dimensions.get('window');

const MainDashboard = () => {
  const [activeTab, setActiveTab] = useState('monitor');
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [systemData, setSystemData] = useState({
    gpus: {
      gtx1080: { util: 0, temp: 0, mem: 0, status: 'offline' },
      firepro: { util: 0, temp: 0, mem: 0, status: 'offline' },
      rtx5080: { util: 0, temp: 0, mem: 0, status: 'offline' },
      rtx5060: { util: 0, temp: 0, mem: 0, status: 'offline' },
    },
    tasks: [],
    uptime: 0,
    powerConsumption: 0,
  });

  const slideAnim = useRef(new Animated.Value(0)).current;
  const pulseAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    StatusBar.setBarStyle('light-content');
    StatusBar.setBackgroundColor('#000000');
    
    // Simulate connection and data
    simulateConnection();
    
    // Start pulse animation for logo
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1.1,
          duration: 2000,
          useNativeDriver: true,
        }),
        Animated.timing(pulseAnim, {
          toValue: 1,
          duration: 2000,
          useNativeDriver: true,
        }),
      ])
    ).start();
  }, []);

  const simulateConnection = () => {
    setTimeout(() => {
      setConnectionStatus('connected');
      simulateSystemData();
    }, 2000);
  };

  const simulateSystemData = () => {
    setInterval(() => {
      setSystemData(prev => ({
        ...prev,
        gpus: {
          gtx1080: {
            util: Math.floor(Math.random() * 40) + 30,
            temp: Math.floor(Math.random() * 20) + 65,
            mem: Math.floor(Math.random() * 2000) + 6000,
            status: 'online'
          },
          firepro: {
            util: Math.floor(Math.random() * 60) + 20,
            temp: Math.floor(Math.random() * 25) + 70,
            mem: Math.floor(Math.random() * 4000) + 12000,
            status: 'online'
          },
          rtx5080: {
            util: Math.floor(Math.random() * 80) + 10,
            temp: Math.floor(Math.random() * 30) + 60,
            mem: Math.floor(Math.random() * 8000) + 16000,
            status: 'online'
          },
          rtx5060: {
            util: Math.floor(Math.random() * 70) + 15,
            temp: Math.floor(Math.random() * 25) + 55,
            mem: Math.floor(Math.random() * 4000) + 12000,
            status: 'online'
          },
        },
        uptime: prev.uptime + 1,
        powerConsumption: Math.floor(Math.random() * 200) + 800,
      }));
    }, 3000);
  };

  const switchTab = (tab) => {
    if (tab !== activeTab) {
      Vibration.vibrate(50);
      setActiveTab(tab);
      
      Animated.timing(slideAnim, {
        toValue: tab === 'monitor' ? 0 : tab === 'chat' ? 1 : 2,
        duration: 300,
        useNativeDriver: true,
      }).start();
    }
  };

  const getConnectionColor = () => {
    switch (connectionStatus) {
      case 'connected': return '#00FF41';
      case 'connecting': return '#FFFF00';
      case 'disconnected': return '#FF0040';
      default: return '#666666';
    }
  };

  const renderHeader = () => (
    <View style={styles.header}>
      {/* Dark North Co. Logo */}
      <Animated.View style={[styles.logoContainer, { transform: [{ scale: pulseAnim }] }]}>
        <MatrixLogo size={60} animated={false} />
      </Animated.View>
      
      {/* App Title */}
      <View style={styles.titleContainer}>
        <Text style={styles.appTitle}>PHANTOM REDBLUE</Text>
        <Text style={styles.subtitle}>Distributed Compute Fabric</Text>
      </View>
      
      {/* Connection Status */}
      <View style={styles.connectionContainer}>
        <View style={[styles.connectionDot, { backgroundColor: getConnectionColor() }]} />
        <Text style={[styles.connectionText, { color: getConnectionColor() }]}>
          {connectionStatus.toUpperCase()}
        </Text>
      </View>
    </View>
  );

  const renderTabBar = () => (
    <View style={styles.tabBar}>
      <TouchableOpacity
        style={[styles.tab, activeTab === 'monitor' && styles.activeTab]}
        onPress={() => switchTab('monitor')}
      >
        <Text style={[styles.tabText, activeTab === 'monitor' && styles.activeTabText]}>
          GPU CLUSTER
        </Text>
      </TouchableOpacity>
      
      <TouchableOpacity
        style={[styles.tab, activeTab === 'chat' && styles.activeTab]}
        onPress={() => switchTab('chat')}
      >
        <Text style={[styles.tabText, activeTab === 'chat' && styles.activeTabText]}>
          TASK INTERFACE
        </Text>
      </TouchableOpacity>
      
      <TouchableOpacity
        style={[styles.tab, activeTab === 'stats' && styles.activeTab]}
        onPress={() => switchTab('stats')}
      >
        <Text style={[styles.tabText, activeTab === 'stats' && styles.activeTabText]}>
          SYSTEM STATS
        </Text>
      </TouchableOpacity>
    </View>
  );

  const renderContent = () => {
    switch (activeTab) {
      case 'monitor':
        return <GPUMonitor gpuData={systemData.gpus} />;
      case 'chat':
        return <AIChat isConnected={connectionStatus === 'connected'} onSendMessage={onSendMessage} />;
      case 'stats':
        return <SystemStats systemData={systemData} />;
      default:
        return <GPUMonitor gpuData={systemData.gpus} />;
    }
  };

  return (
    <View style={styles.container}>
      {/* Matrix Rain Background */}
      <MatrixRain 
        style={styles.matrixBackground}
        intensity={0.2}
        speed={1}
        gpuData={systemData.gpus}
      />
      
      {/* Dark overlay */}
      <View style={styles.overlay} />
      
      {/* Main Content */}
      <View style={styles.content}>
        {renderHeader()}
        {renderTabBar()}
        
        <ScrollView 
          style={styles.scrollContainer}
          showsVerticalScrollIndicator={false}
        >
          {renderContent()}
        </ScrollView>
      </View>
      
      {/* Emergency Controls */}
      <View style={styles.emergencyControls}>
        <TouchableOpacity 
          style={styles.emergencyButton}
          onPress={() => {
            Vibration.vibrate([100, 50, 100]);
            // Emergency stop logic
          }}
        >
          <Text style={styles.emergencyText}>EMERGENCY STOP</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000000',
  },
  matrixBackground: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
  },
  overlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
  },
  content: {
    flex: 1,
    paddingTop: StatusBar.currentHeight || 0,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 15,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(0, 255, 65, 0.3)',
  },
  logoContainer: {
    marginRight: 15,
  },
  titleContainer: {
    flex: 1,
  },
  appTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#00FF41',
    fontFamily: 'monospace',
    letterSpacing: 2,
    textShadowColor: '#00FF41',
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 5,
  },
  subtitle: {
    fontSize: 10,
    color: '#00FFFF',
    fontFamily: 'monospace',
    letterSpacing: 1,
    marginTop: 2,
  },
  connectionContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  connectionDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 8,
  },
  connectionText: {
    fontSize: 10,
    fontFamily: 'monospace',
    letterSpacing: 1,
  },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: 'rgba(0, 59, 0, 0.6)',
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(0, 255, 65, 0.3)',
  },
  tab: {
    flex: 1,
    paddingVertical: 15,
    alignItems: 'center',
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  activeTab: {
    borderBottomColor: '#00FF41',
    backgroundColor: 'rgba(0, 255, 65, 0.1)',
  },
  tabText: {
    fontSize: 11,
    color: '#666666',
    fontFamily: 'monospace',
    letterSpacing: 1,
  },
  activeTabText: {
    color: '#00FF41',
    textShadowColor: '#00FF41',
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 3,
  },
  scrollContainer: {
    flex: 1,
  },
  emergencyControls: {
    position: 'absolute',
    bottom: 20,
    right: 20,
  },
  emergencyButton: {
    backgroundColor: 'rgba(255, 0, 64, 0.8)',
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 5,
    borderWidth: 1,
    borderColor: '#FF0040',
  },
  emergencyText: {
    color: '#FFFFFF',
    fontSize: 10,
    fontFamily: 'monospace',
    fontWeight: 'bold',
    letterSpacing: 1,
  },
});

export default MainDashboard;