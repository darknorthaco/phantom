import React, { useEffect, useRef } from 'react';
import {
  View,
  Text,
  ScrollView,
  Dimensions,
  StyleSheet,
  Animated,
  TouchableOpacity,
} from 'react-native';

const { width } = Dimensions.get('window');

const GPUMonitor = ({ gpuData }) => {
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const slideAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    // Pulse animation for active GPUs
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1.05,
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

    // Slide in animation
    Animated.timing(slideAnim, {
      toValue: 1,
      duration: 800,
      useNativeDriver: true,
    }).start();
  }, []);

  const getGPUColor = (gpuType) => {
    switch (gpuType) {
      case 'gtx1080': return '#00FF41'; // Matrix green for LLM Task Master
      case 'firepro': return '#FF4444'; // Red for Memory Specialist (matching your logo!)
      case 'rtx5080': return '#00FFFF'; // Teal for ML Powerhouse (matching your logo eye!)
      case 'rtx5060': return '#FFFF00'; // Yellow for Modern Compute
      default: return '#666666';
    }
  };

  const getGPURole = (gpuType) => {
    switch (gpuType) {
      case 'gtx1080': return 'LLM TASK MASTER';
      case 'firepro': return 'MEMORY SPECIALIST';
      case 'rtx5080': return 'ML POWERHOUSE';
      case 'rtx5060': return 'MODERN COMPUTE';
      default: return 'UNKNOWN';
    }
  };

  const getGPUName = (gpuType) => {
    switch (gpuType) {
      case 'gtx1080': return 'GTX 1080';
      case 'firepro': return 'FIREPRO W9100';
      case 'rtx5080': return 'RTX 5080';
      case 'rtx5060': return 'RTX 5060';
      default: return 'UNKNOWN GPU';
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'online': return '#00FF41';
      case 'offline': return '#FF4444';
      case 'warning': return '#FFFF00';
      default: return '#666666';
    }
  };

  const renderGPUCard = (gpuType, gpu, index) => {
    const color = getGPUColor(gpuType);
    const statusColor = getStatusColor(gpu.status);
    
    return (
      <Animated.View
        key={gpuType}
        style={[
          styles.gpuCard,
          { 
            borderColor: color,
            transform: [
              { 
                translateX: slideAnim.interpolate({
                  inputRange: [0, 1],
                  outputRange: [width, 0],
                })
              },
              { scale: gpu.status === 'online' ? pulseAnim : 1 }
            ]
          }
        ]}
      >
        {/* GPU Header */}
        <View style={styles.gpuHeader}>
          <View style={styles.gpuTitleContainer}>
            <Text style={[styles.gpuName, { color }]}>
              {getGPUName(gpuType)}
            </Text>
            <Text style={[styles.gpuRole, { color: color + '80' }]}>
              {getGPURole(gpuType)}
            </Text>
          </View>
          
          <View style={styles.statusContainer}>
            <View style={[styles.statusDot, { backgroundColor: statusColor }]} />
            <Text style={[styles.statusText, { color: statusColor }]}>
              {gpu.status?.toUpperCase() || 'OFFLINE'}
            </Text>
          </View>
        </View>

        {/* GPU Stats Grid */}
        <View style={styles.statsGrid}>
          <View style={styles.statItem}>
            <Text style={styles.statLabel}>UTILIZATION</Text>
            <Text style={[styles.statValue, { color }]}>
              {gpu.util || 0}%
            </Text>
            <View style={styles.statBar}>
              <View 
                style={[
                  styles.statBarFill, 
                  { 
                    backgroundColor: color,
                    width: `${gpu.util || 0}%`
                  }
                ]} 
              />
            </View>
          </View>

          <View style={styles.statItem}>
            <Text style={styles.statLabel}>TEMPERATURE</Text>
            <Text style={[styles.statValue, { color }]}>
              {gpu.temp || 0}°C
            </Text>
            <View style={styles.statBar}>
              <View 
                style={[
                  styles.statBarFill, 
                  { 
                    backgroundColor: gpu.temp > 80 ? '#FF4444' : color,
                    width: `${Math.min((gpu.temp || 0) / 100 * 100, 100)}%`
                  }
                ]} 
              />
            </View>
          </View>

          <View style={styles.statItem}>
            <Text style={styles.statLabel}>MEMORY</Text>
            <Text style={[styles.statValue, { color }]}>
              {gpu.mem || 0}MB
            </Text>
            <View style={styles.statBar}>
              <View 
                style={[
                  styles.statBarFill, 
                  { 
                    backgroundColor: color,
                    width: `${Math.min((gpu.mem || 0) / 24000 * 100, 100)}%`
                  }
                ]} 
              />
            </View>
          </View>
        </View>

        {/* GPU Activity Indicator */}
        <View style={styles.activityContainer}>
          <Text style={styles.activityLabel}>NEURAL ACTIVITY</Text>
          <View style={styles.activityWave}>
            {[...Array(20)].map((_, i) => (
              <Animated.View
                key={i}
                style={[
                  styles.activityBar,
                  {
                    backgroundColor: color,
                    height: Math.random() * (gpu.util || 0) / 100 * 20 + 2,
                    opacity: 0.3 + (gpu.util || 0) / 100 * 0.7,
                  }
                ]}
              />
            ))}
          </View>
        </View>

        {/* Matrix Enhancement */}
        <View style={[styles.matrixGlow, { borderColor: color + '30' }]} />
      </Animated.View>
    );
  };

  const renderClusterOverview = () => {
    const totalUtil = Object.values(gpuData).reduce((sum, gpu) => sum + (gpu.util || 0), 0) / 4;
    const onlineGPUs = Object.values(gpuData).filter(gpu => gpu.status === 'online').length;
    
    return (
      <View style={styles.overviewCard}>
        <Text style={styles.overviewTitle}>PHANTOM NEURAL CLUSTER</Text>
        
        <View style={styles.overviewStats}>
          <View style={styles.overviewStat}>
            <Text style={styles.overviewLabel}>TOTAL GPUS</Text>
            <Text style={styles.overviewValue}>4</Text>
          </View>
          
          <View style={styles.overviewStat}>
            <Text style={styles.overviewLabel}>ONLINE</Text>
            <Text style={[styles.overviewValue, { color: '#00FF41' }]}>
              {onlineGPUs}
            </Text>
          </View>
          
          <View style={styles.overviewStat}>
            <Text style={styles.overviewLabel}>AVG UTIL</Text>
            <Text style={[styles.overviewValue, { color: '#00FFFF' }]}>
              {Math.round(totalUtil)}%
            </Text>
          </View>
        </View>

        <View style={styles.clusterBar}>
          <View 
            style={[
              styles.clusterBarFill,
              { width: `${totalUtil}%` }
            ]}
          />
        </View>
        
        <Text style={styles.clusterStatus}>
          DISTRIBUTED NEURAL NETWORK: {onlineGPUs === 4 ? 'OPTIMAL' : 'DEGRADED'}
        </Text>
      </View>
    );
  };

  return (
    <ScrollView style={styles.container} showsVerticalScrollIndicator={false}>
      {/* Cluster Overview */}
      {renderClusterOverview()}
      
      {/* Fedora Server Section */}
      <View style={styles.nodeSection}>
        <Text style={styles.nodeTitle}>FEDORA SERVER [192.168.1.103]</Text>
        {renderGPUCard('gtx1080', gpuData.gtx1080 || {}, 0)}
        {renderGPUCard('firepro', gpuData.firepro || {}, 1)}
      </View>

      {/* Windows PC Section */}
      <View style={styles.nodeSection}>
        <Text style={styles.nodeTitle}>WINDOWS WORKSTATION</Text>
        {renderGPUCard('rtx5080', gpuData.rtx5080 || {}, 2)}
        {renderGPUCard('rtx5060', gpuData.rtx5060 || {}, 3)}
      </View>

      {/* Dark North Co. Branding */}
      <View style={styles.brandingSection}>
        <Text style={styles.brandingText}>Powered by Dark North Co.</Text>
        <Text style={styles.brandingSubtext}>Your AI. Your Hardware. Your Rules.</Text>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 15,
  },
  overviewCard: {
    backgroundColor: 'rgba(0, 59, 0, 0.6)',
    borderWidth: 1,
    borderColor: '#00FF41',
    borderRadius: 8,
    padding: 20,
    marginBottom: 20,
  },
  overviewTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#00FF41',
    fontFamily: 'monospace',
    textAlign: 'center',
    letterSpacing: 2,
    marginBottom: 15,
    textShadowColor: '#00FF41',
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 5,
  },
  overviewStats: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginBottom: 15,
  },
  overviewStat: {
    alignItems: 'center',
  },
  overviewLabel: {
    fontSize: 10,
    color: '#666666',
    fontFamily: 'monospace',
    marginBottom: 5,
  },
  overviewValue: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#FFFFFF',
    fontFamily: 'monospace',
  },
  clusterBar: {
    height: 6,
    backgroundColor: 'rgba(0, 255, 65, 0.2)',
    borderRadius: 3,
    overflow: 'hidden',
    marginBottom: 10,
  },
  clusterBarFill: {
    height: '100%',
    backgroundColor: '#00FF41',
    borderRadius: 3,
  },
  clusterStatus: {
    fontSize: 10,
    color: '#00FFFF',
    fontFamily: 'monospace',
    textAlign: 'center',
    letterSpacing: 1,
  },
  nodeSection: {
    marginBottom: 25,
  },
  nodeTitle: {
    fontSize: 14,
    color: '#00FFFF',
    fontFamily: 'monospace',
    fontWeight: 'bold',
    letterSpacing: 2,
    marginBottom: 15,
    textAlign: 'center',
    textShadowColor: '#00FFFF',
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 3,
  },
  gpuCard: {
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    borderWidth: 2,
    borderRadius: 8,
    padding: 15,
    marginBottom: 15,
    position: 'relative',
  },
  matrixGlow: {
    position: 'absolute',
    top: -1,
    left: -1,
    right: -1,
    bottom: -1,
    borderWidth: 1,
    borderRadius: 8,
    opacity: 0.3,
  },
  gpuHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 15,
  },
  gpuTitleContainer: {
    flex: 1,
  },
  gpuName: {
    fontSize: 14,
    fontWeight: 'bold',
    fontFamily: 'monospace',
    letterSpacing: 1,
  },
  gpuRole: {
    fontSize: 10,
    fontFamily: 'monospace',
    letterSpacing: 1,
    marginTop: 2,
  },
  statusContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 8,
  },
  statusText: {
    fontSize: 10,
    fontFamily: 'monospace',
    letterSpacing: 1,
  },
  statsGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 15,
  },
  statItem: {
    flex: 1,
    alignItems: 'center',
    marginHorizontal: 5,
  },
  statLabel: {
    fontSize: 8,
    color: '#666666',
    fontFamily: 'monospace',
    marginBottom: 5,
    textAlign: 'center',
  },
  statValue: {
    fontSize: 12,
    fontWeight: 'bold',
    fontFamily: 'monospace',
    marginBottom: 8,
  },
  statBar: {
    width: '100%',
    height: 4,
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 2,
    overflow: 'hidden',
  },
  statBarFill: {
    height: '100%',
    borderRadius: 2,
  },
  activityContainer: {
    marginTop: 10,
  },
  activityLabel: {
    fontSize: 8,
    color: '#666666',
    fontFamily: 'monospace',
    marginBottom: 8,
    textAlign: 'center',
  },
  activityWave: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
    height: 25,
  },
  activityBar: {
    width: 3,
    borderRadius: 1,
    minHeight: 2,
  },
  brandingSection: {
    alignItems: 'center',
    paddingVertical: 20,
    marginTop: 20,
    borderTopWidth: 1,
    borderTopColor: 'rgba(0, 255, 255, 0.3)',
  },
  brandingText: {
    fontSize: 12,
    color: '#00FFFF',
    fontFamily: 'monospace',
    letterSpacing: 1,
    marginBottom: 5,
  },
  brandingSubtext: {
    fontSize: 10,
    color: '#FF4444',
    fontFamily: 'monospace',
    letterSpacing: 1,
    opacity: 0.8,
  },
});

export default GPUMonitor;