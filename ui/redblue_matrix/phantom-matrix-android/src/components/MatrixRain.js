import React, { useEffect, useRef } from 'react';
import { View, Dimensions, Animated } from 'react-native';
import Svg, { Text as SvgText, Defs, LinearGradient, Stop } from 'react-native-svg';

const { width, height } = Dimensions.get('window');

const MatrixRain = ({ style, intensity = 0.3, speed = 1, gpuData = {} }) => {
  const animationRef = useRef();
  const dropsRef = useRef([]);
  const frameRef = useRef(0);

  // Matrix characters (including Japanese katakana for authenticity)
  const chars = "アァカサタナハマヤャラワガザダバパイィキシチニヒミリヰギジヂビピウゥクスツヌフムユュルグズブヅプエェケセテネヘメレヱゲゼデベペオォコソトノホモヨョロヲゴゾドボポヴッン0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  const charArray = chars.split('');

  // Mobile-optimized settings
  const fontSize = 12;
  const columns = Math.floor(width / fontSize);
  const maxDrops = Math.min(columns, 50); // Limit for mobile performance

  useEffect(() => {
    initializeDrops();
    startAnimation();
    
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, []);

  const initializeDrops = () => {
    dropsRef.current = [];
    for (let i = 0; i < maxDrops; i++) {
      dropsRef.current[i] = {
        x: (i * fontSize) + Math.random() * fontSize,
        y: Math.random() * height,
        speed: Math.random() * 2 + 1,
        chars: [],
        opacity: Math.random() * 0.8 + 0.2,
        color: getDropColor(),
      };
      
      // Initialize character trail
      for (let j = 0; j < 15; j++) {
        dropsRef.current[i].chars[j] = getRandomChar();
      }
    }
  };

  const getRandomChar = () => {
    return charArray[Math.floor(Math.random() * charArray.length)];
  };

  const getDropColor = () => {
    // Color based on GPU utilization (if available)
    const gpuUtils = Object.values(gpuData);
    if (gpuUtils.length === 0) return '#00FF41'; // Default Matrix green
    
    const maxUtil = Math.max(...gpuUtils.map(gpu => gpu.util || 0));
    
    if (maxUtil > 80) return '#FF0040'; // Red for high utilization
    if (maxUtil > 60) return '#FFFF00'; // Yellow for medium-high
    if (maxUtil > 40) return '#00FFFF'; // Cyan for medium
    return '#00FF41'; // Green for low/normal
  };

  const updateDrops = () => {
    dropsRef.current.forEach(drop => {
      // Update position
      drop.y += drop.speed * speed;
      
      // Reset when off screen
      if (drop.y > height + 100) {
        drop.y = -100;
        drop.x = Math.random() * width;
        drop.speed = Math.random() * 2 + 1;
        drop.color = getDropColor();
        
        // Refresh characters
        for (let j = 0; j < drop.chars.length; j++) {
          drop.chars[j] = getRandomChar();
        }
      }
      
      // Randomly change characters
      if (Math.random() < 0.02) {
        const randomIndex = Math.floor(Math.random() * drop.chars.length);
        drop.chars[randomIndex] = getRandomChar();
      }
    });
  };

  const startAnimation = () => {
    const animate = () => {
      frameRef.current++;
      
      // Update drops every few frames for performance
      if (frameRef.current % 3 === 0) {
        updateDrops();
      }
      
      animationRef.current = requestAnimationFrame(animate);
    };
    
    animate();
  };

  const renderDrops = () => {
    return dropsRef.current.map((drop, index) => (
      <View key={index}>
        {drop.chars.map((char, charIndex) => {
          const charY = drop.y - (charIndex * fontSize);
          const alpha = Math.max(0, (drop.chars.length - charIndex) / drop.chars.length * drop.opacity);
          
          if (charY < -fontSize || charY > height + fontSize) return null;
          
          return (
            <SvgText
              key={`${index}-${charIndex}`}
              x={drop.x}
              y={charY}
              fontSize={fontSize}
              fontFamily="monospace"
              fill={drop.color}
              opacity={alpha * intensity}
              textAnchor="middle"
            >
              {char}
            </SvgText>
          );
        })}
      </View>
    ));
  };

  return (
    <View style={[{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }, style]}>
      <Svg width={width} height={height}>
        <Defs>
          <LinearGradient id="matrixGlow" x1="0%" y1="0%" x2="100%" y2="100%">
            <Stop offset="0%" stopColor="#00FF41" stopOpacity="0.8" />
            <Stop offset="50%" stopColor="#39FF14" stopOpacity="0.6" />
            <Stop offset="100%" stopColor="#00FF41" stopOpacity="0.4" />
          </LinearGradient>
        </Defs>
        {renderDrops()}
      </Svg>
    </View>
  );
};

export default MatrixRain;