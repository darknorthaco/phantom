import React, { useEffect, useRef } from 'react';
import { View, Animated, Dimensions } from 'react-native';
import Svg, { Path, Circle, Text as SvgText, Defs, LinearGradient, Stop } from 'react-native-svg';

const { width, height } = Dimensions.get('window');

const MatrixLogo = ({ style, animated = true, size = 120 }) => {
  const glowAnim = useRef(new Animated.Value(0)).current;
  const floatAnim = useRef(new Animated.Value(0)).current;
  const bubbleAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (animated) {
      // Glow animation
      Animated.loop(
        Animated.sequence([
          Animated.timing(glowAnim, {
            toValue: 1,
            duration: 2000,
            useNativeDriver: false,
          }),
          Animated.timing(glowAnim, {
            toValue: 0,
            duration: 2000,
            useNativeDriver: false,
          }),
        ])
      ).start();

      // Float animation
      Animated.loop(
        Animated.sequence([
          Animated.timing(floatAnim, {
            toValue: 1,
            duration: 3000,
            useNativeDriver: true,
          }),
          Animated.timing(floatAnim, {
            toValue: 0,
            duration: 3000,
            useNativeDriver: true,
          }),
        ])
      ).start();

      // Bubble animation
      Animated.loop(
        Animated.timing(bubbleAnim, {
          toValue: 1,
          duration: 4000,
          useNativeDriver: true,
        })
      ).start();
    }
  }, [animated]);

  const glowOpacity = glowAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [0.3, 1],
  });

  const floatTranslate = floatAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [0, -8],
  });

  const bubbleScale = bubbleAnim.interpolate({
    inputRange: [0, 0.5, 1],
    outputRange: [0.8, 1.2, 0.8],
  });

  return (
    <Animated.View 
      style={[
        {
          alignItems: 'center',
          justifyContent: 'center',
        },
        style,
        {
          transform: [{ translateY: floatTranslate }],
        }
      ]}
    >
      <Svg width={size} height={size * 1.2} viewBox="0 0 120 144">
        <Defs>
          {/* Matrix Green Glow */}
          <LinearGradient id="matrixGlow" x1="0%" y1="0%" x2="100%" y2="100%">
            <Stop offset="0%" stopColor="#00FF41" stopOpacity="0.8" />
            <Stop offset="50%" stopColor="#39FF14" stopOpacity="0.6" />
            <Stop offset="100%" stopColor="#00FF41" stopOpacity="0.4" />
          </LinearGradient>
          
          {/* Dark North Teal */}
          <LinearGradient id="darkNorthTeal" x1="0%" y1="0%" x2="100%" y2="100%">
            <Stop offset="0%" stopColor="#00FFFF" stopOpacity="1" />
            <Stop offset="50%" stopColor="#40E0D0" stopOpacity="0.9" />
            <Stop offset="100%" stopColor="#00CED1" stopOpacity="0.8" />
          </LinearGradient>
          
          {/* Dark North Red */}
          <LinearGradient id="darkNorthRed" x1="0%" y1="0%" x2="100%" y2="100%">
            <Stop offset="0%" stopColor="#FF0040" stopOpacity="1" />
            <Stop offset="50%" stopColor="#FF1744" stopOpacity="0.9" />
            <Stop offset="100%" stopColor="#DC143C" stopOpacity="0.8" />
          </LinearGradient>
        </Defs>

        {/* Animated Bubbles */}
        <Animated.View style={{ transform: [{ scale: bubbleScale }] }}>
          <Circle cx="20" cy="15" r="3" fill="url(#darkNorthTeal)" opacity="0.7" />
          <Circle cx="35" cy="8" r="2" fill="url(#matrixGlow)" opacity="0.5" />
          <Circle cx="50" cy="12" r="4" fill="url(#darkNorthRed)" opacity="0.6" />
          <Circle cx="70" cy="6" r="2.5" fill="url(#darkNorthTeal)" opacity="0.8" />
          <Circle cx="85" cy="18" r="3.5" fill="url(#matrixGlow)" opacity="0.4" />
          <Circle cx="95" cy="10" r="2" fill="url(#darkNorthRed)" opacity="0.7" />
          <Circle cx="105" cy="20" r="3" fill="url(#darkNorthTeal)" opacity="0.5" />
        </Animated.View>

        {/* Rubber Duck - Exact Dark North Co. Design with Matrix Enhancement */}
        <Animated.View style={{ opacity: glowOpacity }}>
          {/* Duck Body - Red outline (matching your original logo) */}
          <Path
            d="M25 45 C20 40, 20 35, 25 30 C30 25, 40 25, 50 30 C55 32, 60 35, 65 40 C70 45, 75 50, 80 55 C82 60, 80 65, 75 68 L30 68 C25 68, 20 63, 20 58 C20 53, 22 48, 25 45 Z"
            stroke="#FF0040"
            strokeWidth="2"
            fill="rgba(0, 0, 0, 0.8)"
            opacity="0.9"
          />
          
          {/* Duck Head - Red outline with black fill */}
          <Path
            d="M40 30 C35 25, 30 25, 25 30 C20 35, 20 40, 25 45 C30 48, 40 48, 45 45 C50 40, 50 35, 45 30 C45 25, 40 25, 40 30 Z"
            stroke="#FF0040"
            strokeWidth="2"
            fill="rgba(0, 0, 0, 0.8)"
            opacity="0.9"
          />
          
          {/* Duck Bill - Red outline */}
          <Path
            d="M20 35 C15 35, 12 37, 14 40 C16 42, 20 42, 23 40 C25 38, 23 35, 20 35 Z"
            stroke="#FF0040"
            strokeWidth="2"
            fill="rgba(0, 0, 0, 0.6)"
          />
          
          {/* Duck Eye - Teal dot (matching your logo) */}
          <Circle 
            cx="32" 
            cy="35" 
            r="2.5" 
            fill="#00FFFF"
            stroke="url(#matrixGlow)"
            strokeWidth="0.5"
          />
          
          {/* Matrix Enhancement Glow around duck */}
          <Path
            d="M25 45 C20 40, 20 35, 25 30 C30 25, 40 25, 50 30 C55 32, 60 35, 65 40 C70 45, 75 50, 80 55 C82 60, 80 65, 75 68 L30 68 C25 68, 20 63, 20 58 C20 53, 22 48, 25 45 Z"
            stroke="url(#matrixGlow)"
            strokeWidth="0.5"
            fill="none"
            opacity="0.4"
          />
        </Animated.View>

        {/* Water Waves - Matrix Style */}
        <Path
          d="M15 80 Q30 75, 45 80 T75 80 T105 80"
          stroke="url(#matrixGlow)"
          strokeWidth="2"
          fill="none"
          opacity="0.7"
        />
        <Path
          d="M10 85 Q25 82, 40 85 T70 85 T100 85"
          stroke="url(#darkNorthTeal)"
          strokeWidth="1.5"
          fill="none"
          opacity="0.6"
        />
        <Path
          d="M20 90 Q35 87, 50 90 T80 90 T110 90"
          stroke="url(#darkNorthRed)"
          strokeWidth="1"
          fill="none"
          opacity="0.5"
        />

        {/* Company Name - Matrix Style */}
        <SvgText
          x="60"
          y="110"
          fontSize="12"
          fontFamily="monospace"
          textAnchor="middle"
          fill="url(#darkNorthTeal)"
          opacity="0.9"
        >
          Dark North Co.
        </SvgText>
        
        {/* Matrix Enhancement Text */}
        <SvgText
          x="60"
          y="125"
          fontSize="8"
          fontFamily="monospace"
          textAnchor="middle"
          fill="url(#matrixGlow)"
          opacity="0.7"
        >
          PHANTOM MATRIX AI
        </SvgText>
        
        {/* Digital Enhancement Lines */}
        <Path
          d="M10 100 L110 100"
          stroke="url(#matrixGlow)"
          strokeWidth="0.5"
          opacity="0.3"
          strokeDasharray="2,2"
        />
        <Path
          d="M10 130 L110 130"
          stroke="url(#darkNorthTeal)"
          strokeWidth="0.5"
          opacity="0.3"
          strokeDasharray="1,3"
        />
      </Svg>
    </Animated.View>
  );
};

export default MatrixLogo;