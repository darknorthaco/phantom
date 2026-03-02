import React, { useEffect, useRef } from 'react';
import {
  View,
  Text,
  Animated,
  Dimensions,
  StyleSheet,
  StatusBar,
} from 'react-native';
import MatrixLogo from './MatrixLogo';
import MatrixRain from './MatrixRain';

const { width, height } = Dimensions.get('window');

const SplashScreen = ({ onComplete }) => {
  const fadeAnim = useRef(new Animated.Value(0)).current;
  const scaleAnim = useRef(new Animated.Value(0.5)).current;
  const textAnim = useRef(new Animated.Value(0)).current;
  const glitchAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    StatusBar.setHidden(true);
    
    // Splash animation sequence
    Animated.sequence([
      // Logo appears with scale
      Animated.parallel([
        Animated.timing(fadeAnim, {
          toValue: 1,
          duration: 1000,
          useNativeDriver: true,
        }),
        Animated.spring(scaleAnim, {
          toValue: 1,
          tension: 50,
          friction: 8,
          useNativeDriver: true,
        }),
      ]),
      
      // Text appears with typing effect
      Animated.timing(textAnim, {
        toValue: 1,
        duration: 1500,
        useNativeDriver: true,
      }),
      
      // Glitch effect
      Animated.timing(glitchAnim, {
        toValue: 1,
        duration: 500,
        useNativeDriver: true,
      }),
    ]).start(() => {
      // Complete splash after 4 seconds total
      setTimeout(() => {
        StatusBar.setHidden(false);
        onComplete();
      }, 1000);
    });
  }, []);

  const glitchTranslate = glitchAnim.interpolate({
    inputRange: [0, 0.2, 0.4, 0.6, 0.8, 1],
    outputRange: [0, -2, 2, -1, 1, 0],
  });

  return (
    <View style={styles.container}>
      {/* Matrix Rain Background */}
      <MatrixRain 
        style={styles.matrixBackground}
        intensity={0.3}
        speed={1.5}
      />
      
      {/* Dark overlay for better logo visibility */}
      <View style={styles.overlay} />
      
      {/* Main Content */}
      <View style={styles.content}>
        {/* Dark North Co. Logo */}
        <Animated.View
          style={[
            styles.logoContainer,
            {
              opacity: fadeAnim,
              transform: [
                { scale: scaleAnim },
                { translateX: glitchTranslate },
              ],
            },
          ]}
        >
          <MatrixLogo size={150} animated={true} />
        </Animated.View>

        {/* App Title */}
        <Animated.View
          style={[
            styles.titleContainer,
            {
              opacity: textAnim,
              transform: [{ translateY: textAnim.interpolate({
                inputRange: [0, 1],
                outputRange: [50, 0],
              })}],
            },
          ]}
        >
          <Text style={styles.appTitle}>PHANTOM REDBLUE</Text>
          <Text style={styles.subtitle}>Distributed Compute Fabric</Text>
          <Text style={styles.tagline}>Your LLM. Your Hardware. Your Rules.</Text>
        </Animated.View>

        {/* Loading Indicator */}
        <Animated.View
          style={[
            styles.loadingContainer,
            { opacity: textAnim },
          ]}
        >
          <View style={styles.loadingBar}>
            <Animated.View
              style={[
                styles.loadingProgress,
                {
                  width: textAnim.interpolate({
                    inputRange: [0, 1],
                    outputRange: ['0%', '100%'],
                  }),
                },
              ]}
            />
          </View>
          <Text style={styles.loadingText}>INITIALIZING COMPUTE FABRIC...</Text>
        </Animated.View>

        {/* Matrix Code Effect */}
        <Animated.View
          style={[
            styles.matrixCode,
            { opacity: glitchAnim },
          ]}
        >
          <Text style={styles.codeText}>01001000 01100101 01101100 01101100 01101111</Text>
          <Text style={styles.codeText}>01001110 01100101 01101111</Text>
        </Animated.View>
      </View>

      {/* Bottom Branding */}
      <Animated.View
        style={[
          styles.bottomBranding,
          { opacity: textAnim },
        ]}
      >
        <Text style={styles.brandText}>Powered by Dark North Co.</Text>
        <Text style={styles.versionText}>v1.0.0 - RedBlue Edition</Text>
      </Animated.View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000000',
    justifyContent: 'center',
    alignItems: 'center',
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
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 40,
  },
  logoContainer: {
    marginBottom: 40,
    alignItems: 'center',
  },
  titleContainer: {
    alignItems: 'center',
    marginBottom: 60,
  },
  appTitle: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#00FF41',
    fontFamily: 'monospace',
    textAlign: 'center',
    letterSpacing: 3,
    textShadowColor: '#00FF41',
    textShadowOffset: { width: 0, height: 0 },
    textShadowRadius: 10,
    marginBottom: 10,
  },
  subtitle: {
    fontSize: 16,
    color: '#00FFFF',
    fontFamily: 'monospace',
    textAlign: 'center',
    letterSpacing: 2,
    marginBottom: 20,
  },
  tagline: {
    fontSize: 12,
    color: '#FF0040',
    fontFamily: 'monospace',
    textAlign: 'center',
    letterSpacing: 1,
    opacity: 0.8,
  },
  loadingContainer: {
    width: width * 0.7,
    alignItems: 'center',
    marginBottom: 40,
  },
  loadingBar: {
    width: '100%',
    height: 4,
    backgroundColor: 'rgba(0, 255, 65, 0.2)',
    borderRadius: 2,
    overflow: 'hidden',
    marginBottom: 15,
  },
  loadingProgress: {
    height: '100%',
    backgroundColor: '#00FF41',
    borderRadius: 2,
    shadowColor: '#00FF41',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 1,
    shadowRadius: 5,
  },
  loadingText: {
    fontSize: 10,
    color: '#00FF41',
    fontFamily: 'monospace',
    letterSpacing: 1,
    opacity: 0.7,
  },
  matrixCode: {
    alignItems: 'center',
    marginTop: 20,
  },
  codeText: {
    fontSize: 8,
    color: '#003B00',
    fontFamily: 'monospace',
    letterSpacing: 1,
    marginVertical: 2,
  },
  bottomBranding: {
    position: 'absolute',
    bottom: 40,
    alignItems: 'center',
  },
  brandText: {
    fontSize: 12,
    color: '#00FFFF',
    fontFamily: 'monospace',
    letterSpacing: 1,
    marginBottom: 5,
  },
  versionText: {
    fontSize: 10,
    color: '#666666',
    fontFamily: 'monospace',
    letterSpacing: 1,
  },
});

export default SplashScreen;