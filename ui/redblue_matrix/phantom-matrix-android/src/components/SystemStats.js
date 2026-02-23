import React, { useEffect, useRef } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  Animated,
  Dimensions,
  TouchableOpacity,
} from 'react-native';

const { width } = Dimensions.get('window');

const SystemStats = ({ systemData }) => {
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const rotateAnim = useRef(new Animated.Value(0)).current;
  const glowAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    // Pulse animation for critical stats
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

    // Rotation animation for network indicator
    Animated.loop(
      Animated.timing(rotateAnim, {
        toValue: 1,
        duration: 10000,
        useNativeDriver: true,
      })
    ).start();

    // Glow animation for status indicators
    Animated.loop(
      Animated.sequence([
        Animated.timing(glowAnim, {
          toValue: 1,
          duration: 1500,
          useNativeDriver: false,
        }),
        Animated.timing(glowAnim, {
          toValue: 0,
          duration: 1500,
          useNativeDriver: false,
        }),
      ])
    ).start();
  }, []);

  const getStatusColor = (status) => {
    switch (status) {
      case 'optimal': return '#00FF41';
      case 'warning': return '#FFFF00';
      case 'critical': return '#FF4444';
      case 'offline': return '#666666';
      default: return '#00FFFF';
    }
  };

  const renderNetworkTopology = () => {
    return (
      <View style={styles.topologyCard}>
        <Text style={styles.cardTitle}>PHANTOM NETWORK TOPOLOGY</Text>
        
        {/* Network Diagram */}
        <View style={styles.networkDiagram}>
          {/* Fedora Server Node */}
          <View style={styles.serverNode}>
            <Animated.View style={[
              styles.nodeCore,
              { 
                backgroundColor: '#00FF41',
                transform: [{ scale: pulseAnim }]
              }
            ]}>
              <Text style={styles.nodeLabel}>FEDORA</Text>
              <Text style={styles.nodeSubLabel}>192.168.1.103</Text>
            </Animated.View>
            
            {/* Server GPUs */}
            <View style={styles.gpuCluster}>
              <View style={[styles.gpuNode, { borderColor: '#00FF41' }]}>
                <Text style={styles.gpuLabel}>GTX1080</Text>
              </View>
              <View style={[styles.gpuNode, { borderColor: '#FF4444' }]}>
                <Text style={styles.gpuLabel}>FIREPRO</Text>
              </View>
            </View>
          </View>

          {/* Network Connection */}
          <Animated.View style={[
            styles.networkConnection,
            {
              backgroundColor: glowAnim.interpolate({
                inputRange: [0, 1],
                outputRange: ['rgba(0, 255, 255, 0.3)', 'rgba(0, 255, 255, 0.8)']
              })
            }
          ]} />

          {/* Windows PC Node */}
          <View style={styles.clientNode}>
            <Animated.View style={[
              styles.nodeCore,
              { 
                backgroundColor: '#00FFFF',
                transform: [{ scale: pulseAnim }]
              }
            ]}>
              <Text style={styles.nodeLabel}>WINDOWS</Text>
              <Text style={styles.nodeSubLabel}>WORKSTATION</Text>
            </Animated.View>
            
            {/* Client GPUs */}
            <View style={styles.gpuCluster}>
              <View style={[styles.gpuNode, { borderColor: '#00FFFF' }]}>
                <Text style={styles.gpuLabel}>RTX5080</Text>
              </View>
              <View style={[styles.gpuNode, { borderColor: '#FFFF00' }]}>
                <Text style={styles.gpuLabel}>RTX5060</Text>
              </View>
            </View>
          </View>
        </View>

        {/* Network Stats */}
        <View style={styles.networkStats}>
          <View style={styles.networkStat}>
            <Text style={styles.statLabel}>LATENCY</Text>
            <Text style={[styles.statValue, { color: '#00FF41' }]}>
              {systemData?.network?.latency || '< 1ms'}
            </Text>
          </View>
          <View style={styles.networkStat}>
            <Text style={styles.statLabel}>BANDWIDTH</Text>
            <Text style={[styles.statValue, { color: '#00FFFF' }]}>
              {systemData?.network?.bandwidth || '1Gb/s'}
            </Text>
          </View>
          <View style={styles.networkStat}>
            <Text style={styles.statLabel}>PACKETS</Text>
            <Text style={[styles.statValue, { color: '#FFFF00' }]}>
              {systemData?.network?.packets || '99.9%'}
            </Text>
          </View>
        </View>
      </View>
    );
  };

  const renderSystemHealth = () => {
    const healthMetrics = [
      { 
        name: 'NEURAL CORES', 
        value: '4/4 ONLINE', 
        status: 'optimal',
        description: 'All GPU workers responding'
      },
      { 
        name: 'MEMORY BANKS', 
        value: '96GB TOTAL', 
        status: 'optimal',
        description: '64GB DDR5 + 32GB DDR3'
      },
      { 
        name: 'STORAGE MATRIX', 
        value: 'DISTRIBUTED', 
        status: 'optimal',
        description: 'Model libraries synchronized'
      },
      { 
        name: 'THERMAL STATUS', 
        value: 'NOMINAL', 
        status: 'optimal',
        description: 'All components within limits'
      },
      { 
        name: 'POWER GRID', 
        value: 'STABLE', 
        status: 'optimal',
        description: 'Dual PSU configuration'
      },
      { 
        name: 'SECURITY LAYER', 
        value: 'ACTIVE', 
        status: 'optimal',
        description: 'Dark North Co. protocols'
      }
    ];

    return (
      <View style={styles.healthCard}>
        <Text style={styles.cardTitle}>SYSTEM HEALTH MATRIX</Text>
        
        {healthMetrics.map((metric, index) => (
          <View key={index} style={styles.healthMetric}>
            <View style={styles.metricHeader}>
              <Text style={styles.metricName}>{metric.name}</Text>
              <Animated.View style={[
                styles.statusIndicator,
                { 
                  backgroundColor: glowAnim.interpolate({
                    inputRange: [0, 1],
                    outputRange: [
                      getStatusColor(metric.status) + '60',
                      getStatusColor(metric.status) + 'FF'
                    ]
                  })
                }
              ]} />
            </View>
            
            <Text style={[styles.metricValue, { color: getStatusColor(metric.status) }]}>
              {metric.value}
            </Text>
            
            <Text style={styles.metricDescription}>
              {metric.description}
            </Text>
            
            <View style={[styles.metricBar, { backgroundColor: getStatusColor(metric.status) + '20' }]}>
              <View style={[
                styles.metricBarFill,
                { 
                  backgroundColor: getStatusColor(metric.status),
                  width: metric.status === 'optimal' ? '100%' : '75%'
                }
              ]} />
            </View>
          </View>
        ))}
      </View>
    );
  };

  const renderPerformanceMetrics = () => {
    return (
      <View style={styles.performanceCard}>
        <Text style={styles.cardTitle}>NEURAL PERFORMANCE MATRIX</Text>
        
        {/* Real-time Performance Graph */}
        <View style={styles.performanceGraph}>
          <Text style={styles.graphTitle}>DISTRIBUTED COMPUTE UTILIZATION</Text>
          
          <View style={styles.graphContainer}>
            {/* Y-axis labels */}
            <View style={styles.yAxis}>
              {['100%', '75%', '50%', '25%', '0%'].map((label, index) => (
                <Text key={index} style={styles.axisLabel}>{label}</Text>
              ))}
            </View>
            
            {/* Performance bars */}
            <View style={styles.graphBars}>
              {[...Array(20)].map((_, index) => {
                const height = Math.random() * 80 + 10;
                const color = height > 70 ? '#FF4444' : height > 40 ? '#FFFF00' : '#00FF41';
                
                return (
                  <Animated.View
                    key={index}
                    style={[
                      styles.performanceBar,
                      {
                        height: `${height}%`,
                        backgroundColor: color,
                        opacity: glowAnim.interpolate({
                          inputRange: [0, 1],
                          outputRange: [0.6, 1]
                        })
                      }
                    ]}
                  />
                );
              })}
            </View>
          </View>
          
          {/* X-axis */}
          <View style={styles.xAxis}>
            <Text style={styles.axisLabel}>-60s</Text>
            <Text style={styles.axisLabel}>-30s</Text>
            <Text style={styles.axisLabel}>NOW</Text>
          </View>
        </View>

        {/* Performance Stats */}
        <View style={styles.performanceStats}>
          <View style={styles.perfStat}>
            <Text style={styles.perfStatLabel}>TOTAL TFLOPS</Text>
            <Text style={[styles.perfStatValue, { color: '#00FF41' }]}>
              {systemData?.performance?.tflops || '47.2'}
            </Text>
          </View>
          
          <View style={styles.perfStat}>
            <Text style={styles.perfStatLabel}>TASKS/SEC</Text>
            <Text style={[styles.perfStatValue, { color: '#00FFFF' }]}>
              {systemData?.performance?.tasksPerSec || '1,247'}
            </Text>
          </View>
          
          <View style={styles.perfStat}>
            <Text style={styles.perfStatLabel}>EFFICIENCY</Text>
            <Text style={[styles.perfStatValue, { color: '#FFFF00' }]}>
              {systemData?.performance?.efficiency || '94.7%'}
            </Text>
          </View>
        </View>
      </View>
    );
  };

  const renderEmergencyControls = () => {
    return (
      <View style={styles.emergencyCard}>
        <Text style={styles.cardTitle}>EMERGENCY PROTOCOLS</Text>
        
        <View style={styles.emergencyButtons}>
          <TouchableOpacity style={[styles.emergencyButton, { borderColor: '#FF4444' }]}>
            <Text style={[styles.emergencyButtonText, { color: '#FF4444' }]}>
              EMERGENCY STOP
            </Text>
            <Text style={styles.emergencyButtonDesc}>
              Halt all neural processes
            </Text>
          </TouchableOpacity>
          
          <TouchableOpacity style={[styles.emergencyButton, { borderColor: '#FFFF00' }]}>
            <Text style={[styles.emergencyButtonText, { color: '#FFFF00' }]}>
              SAFE MODE
            </Text>
            <Text style={styles.emergencyButtonDesc}>
              Reduce to minimal load
            </Text>
          </TouchableOpacity>
          
          <TouchableOpacity style={[styles.emergencyButton, { borderColor: '#00FFFF' }]}>
            <Text style={[styles.emergencyButtonText, { color: '#00FFFF' }]}>
              REBOOT CLUSTER
            </Text>
            <Text style={styles.emergencyButtonDesc}>
              Full system restart
            </Text>
          </TouchableOpacity>
        </View>
        
        {/* Dark North Co. Emergency Protocol */}
        <View style={styles.protocolInfo}>
          <Text style={styles.protocolTitle}>DARK NORTH CO. SAFETY PROTOCOL</Text>
          <Text style={styles.protocolText}>
            Your hardware, your control. Emergency stops bypass all AI decision-making 
            and return full control to human operators. No corporate override possible.
          </Text>
        </View>
      </View>
    );
  };

  return (
    <ScrollView style={styles.container} showsVerticalScrollIndicator={false}>
      {/* Network Topology */}
      {renderNetworkTopology()}
      
      {/* System Health */}
      {renderSystemHealth()}
      
      {/* Performance Metrics */}
      {renderPerformanceMetrics()}
      
      {/* Emergency Controls */}
      {renderEmergencyControls()}
      
      {/* Dark North Co. Footer */}
      <View style={styles.footerBranding}>
        <Text style={styles.footerTitle}>DARK NORTH CO. PHANTOM MATRIX</Text>
        <Text style={styles.footerSubtitle}>Distributed Neural Architecture</Text>
        <Text style={styles.footerTagline}>Your AI. Your Hardware. Your Rules.</Text>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 15,
  },
  topologyCard: {
    backgroundColor: 'rgba(0, 59, 0, 0.4)',
    borderWidth: 1,
    borderColor: '#00FF41',
    borderRadius: 8,
    padding: 20,
    marginBottom: 20,
  },
  healthCard: {
    backgroundColor: 'rgba(0, 59, 59, 0.4)',
    borderWidth: 1,
    borderColor: '#00FFFF',
    borderRadius: 8,
    padding: 20,
    marginBottom: 20,
  },
  performanceCard: {
    backgroundColor: 'rgba(59, 59, 0, 0.4)',
    borderWidth: 1,
    borderColor: '#FFFF00',
    borderRadius: 8,
    padding: 20,
    marginBottom: 20,
  },
  emergencyCard: {
    backgroundColor: 'rgba(59, 0, 0, 0.4)',
    borderWidth: 1,
    borderColor: '#FF4444',
    borderRadius: 8,
    padding: 20,
    marginBottom: 20,
  },
  cardTitle: {
    fontSize: 14,
    fontWeight: 'bold',
    fontFamily: 'monospace',
    letterSpacing: 2,
    textAlign: 'center',
    marginBottom: 20,
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 5,
  },
  networkDiagram: {
    alignItems: 'center',
    marginBottom: 20,
  },
  serverNode: {
    alignItems: 'center',
    marginBottom: 20,
  },
  clientNode: {
    alignItems: 'center',
  },
  nodeCore: {
    width: 80,
    height: 80,
    borderRadius: 40,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 10,
  },
  nodeLabel: {
    fontSize: 10,
    fontWeight: 'bold',
    color: '#000000',
    fontFamily: 'monospace',
  },
  nodeSubLabel: {
    fontSize: 8,
    color: '#000000',
    fontFamily: 'monospace',
  },
  gpuCluster: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    width: 120,
  },
  gpuNode: {
    borderWidth: 1,
    borderRadius: 4,
    padding: 8,
    backgroundColor: 'rgba(0, 0, 0, 0.6)',
  },
  gpuLabel: {
    fontSize: 8,
    color: '#FFFFFF',
    fontFamily: 'monospace',
    textAlign: 'center',
  },
  networkConnection: {
    width: 4,
    height: 30,
    marginVertical: 10,
  },
  networkStats: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  networkStat: {
    alignItems: 'center',
  },
  statLabel: {
    fontSize: 8,
    color: '#666666',
    fontFamily: 'monospace',
    marginBottom: 5,
  },
  statValue: {
    fontSize: 12,
    fontWeight: 'bold',
    fontFamily: 'monospace',
  },
  healthMetric: {
    marginBottom: 15,
  },
  metricHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 5,
  },
  metricName: {
    fontSize: 10,
    color: '#FFFFFF',
    fontFamily: 'monospace',
    letterSpacing: 1,
  },
  statusIndicator: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  metricValue: {
    fontSize: 12,
    fontWeight: 'bold',
    fontFamily: 'monospace',
    marginBottom: 3,
  },
  metricDescription: {
    fontSize: 8,
    color: '#666666',
    fontFamily: 'monospace',
    marginBottom: 8,
  },
  metricBar: {
    height: 4,
    borderRadius: 2,
    overflow: 'hidden',
  },
  metricBarFill: {
    height: '100%',
    borderRadius: 2,
  },
  performanceGraph: {
    marginBottom: 20,
  },
  graphTitle: {
    fontSize: 10,
    color: '#FFFF00',
    fontFamily: 'monospace',
    textAlign: 'center',
    marginBottom: 15,
    letterSpacing: 1,
  },
  graphContainer: {
    flexDirection: 'row',
    height: 100,
    marginBottom: 10,
  },
  yAxis: {
    justifyContent: 'space-between',
    marginRight: 10,
    height: 100,
  },
  xAxis: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
  },
  axisLabel: {
    fontSize: 8,
    color: '#666666',
    fontFamily: 'monospace',
  },
  graphBars: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    height: 100,
  },
  performanceBar: {
    width: 3,
    borderRadius: 1,
    minHeight: 2,
  },
  performanceStats: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  perfStat: {
    alignItems: 'center',
  },
  perfStatLabel: {
    fontSize: 8,
    color: '#666666',
    fontFamily: 'monospace',
    marginBottom: 5,
  },
  perfStatValue: {
    fontSize: 14,
    fontWeight: 'bold',
    fontFamily: 'monospace',
  },
  emergencyButtons: {
    marginBottom: 20,
  },
  emergencyButton: {
    borderWidth: 2,
    borderRadius: 8,
    padding: 15,
    marginBottom: 10,
    backgroundColor: 'rgba(0, 0, 0, 0.6)',
  },
  emergencyButtonText: {
    fontSize: 12,
    fontWeight: 'bold',
    fontFamily: 'monospace',
    letterSpacing: 1,
    textAlign: 'center',
    marginBottom: 5,
  },
  emergencyButtonDesc: {
    fontSize: 8,
    color: '#666666',
    fontFamily: 'monospace',
    textAlign: 'center',
  },
  protocolInfo: {
    backgroundColor: 'rgba(0, 0, 0, 0.6)',
    borderRadius: 6,
    padding: 15,
  },
  protocolTitle: {
    fontSize: 10,
    color: '#FF4444',
    fontFamily: 'monospace',
    letterSpacing: 1,
    marginBottom: 8,
    textAlign: 'center',
  },
  protocolText: {
    fontSize: 8,
    color: '#CCCCCC',
    fontFamily: 'monospace',
    lineHeight: 12,
    textAlign: 'center',
  },
  footerBranding: {
    alignItems: 'center',
    paddingVertical: 30,
    marginTop: 20,
    borderTopWidth: 1,
    borderTopColor: 'rgba(0, 255, 255, 0.3)',
  },
  footerTitle: {
    fontSize: 14,
    color: '#00FFFF',
    fontFamily: 'monospace',
    letterSpacing: 2,
    fontWeight: 'bold',
    marginBottom: 5,
  },
  footerSubtitle: {
    fontSize: 10,
    color: '#FF4444',
    fontFamily: 'monospace',
    letterSpacing: 1,
    marginBottom: 5,
  },
  footerTagline: {
    fontSize: 8,
    color: '#00FF41',
    fontFamily: 'monospace',
    letterSpacing: 1,
    opacity: 0.8,
  },
});

export default SystemStats;