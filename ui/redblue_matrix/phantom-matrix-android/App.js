import React, { useState, useEffect } from 'react';
import {
  View,
  StyleSheet,
  StatusBar,
  Dimensions,
  BackHandler,
  Alert,
} from 'react-native';

// Import our Matrix components
import SplashScreen from './src/components/SplashScreen';
import MainDashboard from './src/components/MainDashboard';
import MatrixRain from './src/components/MatrixRain';

const { width, height } = Dimensions.get('window');

const App = () => {
  const [isLoading, setIsLoading] = useState(true);
  const [isConnected, setIsConnected] = useState(false);
  const [currentTab, setCurrentTab] = useState('gpu');
  // GPU data — keys are generic slots, populated from backend during
  // WebSocket handshake after installation network scan discovers workers.
  const [gpuData, setGpuData] = useState({
    gpu_0: { status: 'online', util: 75, temp: 68, mem: 8192, name: '(scanning...)' },
    gpu_1: { status: 'online', util: 45, temp: 72, mem: 16384, name: '(scanning...)' },
    gpu_2: { status: 'online', util: 89, temp: 65, mem: 16384, name: '(scanning...)' },
    gpu_3: { status: 'online', util: 62, temp: 58, mem: 8192, name: '(scanning...)' },
  });
  const [systemData, setSystemData] = useState({
    network: {
      latency: '< 1ms',
      bandwidth: '1Gb/s',
      packets: '99.9%',
    },
    performance: {
      tflops: '47.2',
      tasksPerSec: '1,247',
      efficiency: '94.7%',
    },
  });

  useEffect(() => {
    // Simulate app initialization
    const initializeApp = async () => {
      try {
        // Simulate loading time for Matrix effect
        await new Promise(resolve => setTimeout(resolve, 4000));
        
        // Simulate connection to Phantom backend
        await connectToPhantom();
        
        setIsLoading(false);
      } catch (error) {
        console.error('App initialization failed:', error);
        setIsLoading(false);
      }
    };

    initializeApp();

    // Start real-time GPU data updates; capture interval ID for cleanup
    const updateInterval = startDataUpdates();

    // Handle Android back button
    const backAction = () => {
      Alert.alert(
        'Exit Phantom Matrix',
        'Are you sure you want to disconnect from the compute fabric?',
        [
          {
            text: 'Cancel',
            onPress: () => null,
            style: 'cancel',
          },
          {
            text: 'EXIT',
            onPress: () => BackHandler.exitApp(),
            style: 'destructive',
          },
        ]
      );
      return true;
    };

    const backHandler = BackHandler.addEventListener('hardwareBackPress', backAction);

    return () => {
      backHandler.remove();
      clearInterval(updateInterval);
    };
  }, []);

  const connectToPhantom = async () => {
    try {
      // In real implementation, this would connect to the controller
      // and receive discovered worker/GPU data from the installation scan
      console.log('Connecting to Phantom Compute Fabric...');
      
      // Simulate connection delay
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      setIsConnected(true);
      
      console.log('Connected to Phantom Compute Fabric successfully!');
    } catch (error) {
      console.error('Failed to connect to Phantom:', error);
      setIsConnected(false);
    }
  };

  const startDataUpdates = () => {
    // Simulate real-time GPU data updates; returns interval ID for cleanup
    return setInterval(() => {
      setGpuData(prevData => ({
        gpu_0: {
          ...prevData.gpu_0,
          util: Math.max(0, Math.min(100, prevData.gpu_0.util + (Math.random() - 0.5) * 10)),
          temp: Math.max(40, Math.min(85, prevData.gpu_0.temp + (Math.random() - 0.5) * 5)),
        },
        gpu_1: {
          ...prevData.gpu_1,
          util: Math.max(0, Math.min(100, prevData.gpu_1.util + (Math.random() - 0.5) * 8)),
          temp: Math.max(45, Math.min(90, prevData.gpu_1.temp + (Math.random() - 0.5) * 4)),
        },
        gpu_2: {
          ...prevData.gpu_2,
          util: Math.max(0, Math.min(100, prevData.gpu_2.util + (Math.random() - 0.5) * 12)),
          temp: Math.max(35, Math.min(80, prevData.gpu_2.temp + (Math.random() - 0.5) * 6)),
        },
        gpu_3: {
          ...prevData.gpu_3,
          util: Math.max(0, Math.min(100, prevData.gpu_3.util + (Math.random() - 0.5) * 15)),
          temp: Math.max(30, Math.min(75, prevData.gpu_3.temp + (Math.random() - 0.5) * 7)),
        },
      }));
    }, 2000);
  };

  const handleSendMessage = (message, model) => {
    // Handle AI chat messages
    console.log(`Sending message to ${model}:`, message);
    
    // In real implementation, this would send via WebSocket to Phantom backend
    // For now, we'll just log it
    
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          response: `Message processed by ${model.toUpperCase()} compute node`,
          timestamp: new Date(),
        });
      }, 1500);
    });
  };

  const handleTabChange = (tab) => {
    setCurrentTab(tab);
  };

  if (isLoading) {
    return (
      <View style={styles.container}>
        <StatusBar 
          barStyle="light-content" 
          backgroundColor="#000000" 
          translucent={true}
        />
        <SplashScreen />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <StatusBar 
        barStyle="light-content" 
        backgroundColor="#000000" 
        translucent={true}
      />
      
      {/* Matrix Rain Background */}
      <MatrixRain gpuData={gpuData} />
      
      {/* Main Dashboard */}
      <MainDashboard
        isConnected={isConnected}
        currentTab={currentTab}
        onTabChange={handleTabChange}
        gpuData={gpuData}
        systemData={systemData}
        onSendMessage={handleSendMessage}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000000',
  },
});

export default App;