import React, { useState, useRef, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  Animated,
  Dimensions,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';

const { width, height } = Dimensions.get('window');

const AIChat = ({ isConnected, onSendMessage }) => {
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState([
    {
      id: 1,
      type: 'system',
      text: 'PHANTOM COMPUTE FABRIC INITIALIZED',
      timestamp: new Date(),
    },
    {
      id: 2,
      type: 'system',
      text: 'Dark North Co. Compute Cluster Online',
      timestamp: new Date(),
    },
    {
      id: 3,
      type: 'ai',
      text: 'Welcome to your personal AI matrix. I am running on YOUR hardware, following YOUR rules. How can I assist you today?',
      timestamp: new Date(),
    }
  ]);
  const [selectedModel, setSelectedModel] = useState('gtx1080');
  
  const scrollViewRef = useRef();
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const glowAnim = useRef(new Animated.Value(0)).current;
  const typewriterAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    // Pulse animation for send button
    Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1.1,
          duration: 1500,
          useNativeDriver: true,
        }),
        Animated.timing(pulseAnim, {
          toValue: 1,
          duration: 1500,
          useNativeDriver: true,
        }),
      ])
    ).start();

    // Glow animation for connection status
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
  }, []);

  const getModelColor = (model) => {
    switch (model) {
      case 'gtx1080': return '#00FF41'; // Matrix green for LLM Task Master
      case 'firepro': return '#FF4444'; // Red for Memory Specialist (matching your logo!)
      case 'rtx5080': return '#00FFFF'; // Teal for ML Powerhouse (matching your logo eye!)
      case 'rtx5060': return '#FFFF00'; // Yellow for Modern Compute
      default: return '#666666';
    }
  };

  const getModelName = (model) => {
    switch (model) {
      case 'gtx1080': return 'GTX 1080 - LLM MASTER';
      case 'firepro': return 'FIREPRO - MEMORY BANK';
      case 'rtx5080': return 'RTX 5080 - ML POWERHOUSE';
      case 'rtx5060': return 'RTX 5060 - MODERN CORE';
      default: return 'UNKNOWN MODEL';
    }
  };

  const handleSendMessage = () => {
    if (!message.trim() || !isConnected) return;

    const newMessage = {
      id: Date.now(),
      type: 'user',
      text: message,
      timestamp: new Date(),
      model: selectedModel,
    };

    setMessages(prev => [...prev, newMessage]);
    setMessage('');

    // Simulate AI response
    setTimeout(() => {
      const aiResponse = {
        id: Date.now() + 1,
        type: 'ai',
        text: `Processing on ${getModelName(selectedModel)}... This is your LLM running on YOUR hardware. No corporate surveillance, no data mining, just pure distributed computation under your control.`,
        timestamp: new Date(),
        model: selectedModel,
      };
      setMessages(prev => [...prev, aiResponse]);
    }, 1500);

    // Auto-scroll to bottom
    setTimeout(() => {
      scrollViewRef.current?.scrollToEnd({ animated: true });
    }, 100);
  };

  const renderMessage = (msg) => {
    const isUser = msg.type === 'user';
    const isSystem = msg.type === 'system';
    const modelColor = getModelColor(msg.model || selectedModel);

    return (
      <View key={msg.id} style={[
        styles.messageContainer,
        isUser ? styles.userMessage : styles.aiMessage,
        isSystem && styles.systemMessage
      ]}>
        {/* Message Header */}
        <View style={styles.messageHeader}>
          <Text style={[
            styles.messageAuthor,
            { color: isUser ? '#00FFFF' : isSystem ? '#FFFF00' : modelColor }
          ]}>
            {isUser ? 'USER@DARK_NORTH' : isSystem ? 'SYSTEM' : `AI@${msg.model?.toUpperCase() || 'PHANTOM'}`}
          </Text>
          <Text style={styles.messageTime}>
            {msg.timestamp.toLocaleTimeString()}
          </Text>
        </View>

        {/* Message Content */}
        <View style={[
          styles.messageContent,
          { borderLeftColor: isUser ? '#00FFFF' : isSystem ? '#FFFF00' : modelColor }
        ]}>
          <Text style={[
            styles.messageText,
            { color: isUser ? '#FFFFFF' : isSystem ? '#FFFF00' : '#00FF41' }
          ]}>
            {msg.text}
          </Text>
        </View>

        {/* Matrix Glow Effect */}
        <View style={[
          styles.messageGlow,
          { borderColor: (isUser ? '#00FFFF' : isSystem ? '#FFFF00' : modelColor) + '30' }
        ]} />
      </View>
    );
  };

  const renderModelSelector = () => {
    const models = ['gtx1080', 'firepro', 'rtx5080', 'rtx5060'];
    
    return (
      <View style={styles.modelSelector}>
        <Text style={styles.modelSelectorTitle}>COMPUTE NODE SELECTION</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          {models.map((model) => (
            <TouchableOpacity
              key={model}
              style={[
                styles.modelButton,
                selectedModel === model && styles.modelButtonActive,
                { borderColor: getModelColor(model) }
              ]}
              onPress={() => setSelectedModel(model)}
            >
              <Text style={[
                styles.modelButtonText,
                { color: selectedModel === model ? getModelColor(model) : '#666666' }
              ]}>
                {model.toUpperCase()}
              </Text>
              <View style={[
                styles.modelIndicator,
                { backgroundColor: getModelColor(model) }
              ]} />
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>
    );
  };

  return (
    <KeyboardAvoidingView 
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      {/* Connection Status */}
      <Animated.View style={[
        styles.connectionStatus,
        {
          backgroundColor: glowAnim.interpolate({
            inputRange: [0, 1],
            outputRange: [
              isConnected ? 'rgba(0, 255, 65, 0.1)' : 'rgba(255, 68, 68, 0.1)',
              isConnected ? 'rgba(0, 255, 65, 0.3)' : 'rgba(255, 68, 68, 0.3)'
            ]
          })
        }
      ]}>
        <View style={[
          styles.connectionDot,
          { backgroundColor: isConnected ? '#00FF41' : '#FF4444' }
        ]} />
        <Text style={[
          styles.connectionText,
          { color: isConnected ? '#00FF41' : '#FF4444' }
        ]}>
          {isConnected ? 'PHANTOM COMPUTE LINK ACTIVE' : 'COMPUTE LINK DISCONNECTED'}
        </Text>
      </Animated.View>

      {/* Model Selector */}
      {renderModelSelector()}

      {/* Chat Messages */}
      <ScrollView
        ref={scrollViewRef}
        style={styles.messagesContainer}
        showsVerticalScrollIndicator={false}
        onContentSizeChange={() => scrollViewRef.current?.scrollToEnd({ animated: true })}
      >
        {messages.map(renderMessage)}
      </ScrollView>

      {/* Input Area */}
      <View style={styles.inputContainer}>
        <View style={[
          styles.inputWrapper,
          { borderColor: getModelColor(selectedModel) }
        ]}>
          <TextInput
            style={[styles.textInput, { color: getModelColor(selectedModel) }]}
            value={message}
            onChangeText={setMessage}
            placeholder="Enter command..."
            placeholderTextColor="#666666"
            multiline
            maxLength={500}
            editable={isConnected}
          />
          
          <Animated.View style={{ transform: [{ scale: pulseAnim }] }}>
            <TouchableOpacity
              style={[
                styles.sendButton,
                { 
                  backgroundColor: isConnected ? getModelColor(selectedModel) + '20' : '#333333',
                  borderColor: isConnected ? getModelColor(selectedModel) : '#666666'
                }
              ]}
              onPress={handleSendMessage}
              disabled={!isConnected || !message.trim()}
            >
              <Text style={[
                styles.sendButtonText,
                { color: isConnected ? getModelColor(selectedModel) : '#666666' }
              ]}>
                TRANSMIT
              </Text>
            </TouchableOpacity>
          </Animated.View>
        </View>

        {/* Dark North Co. Branding */}
        <View style={styles.brandingContainer}>
          <Text style={styles.brandingText}>
            Powered by Dark North Co. Compute Architecture
          </Text>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000000',
  },
  connectionStatus: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(0, 255, 255, 0.3)',
  },
  connectionDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 10,
  },
  connectionText: {
    fontSize: 12,
    fontFamily: 'monospace',
    letterSpacing: 1,
    fontWeight: 'bold',
  },
  modelSelector: {
    padding: 15,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(0, 255, 255, 0.2)',
  },
  modelSelectorTitle: {
    fontSize: 10,
    color: '#666666',
    fontFamily: 'monospace',
    letterSpacing: 1,
    marginBottom: 10,
    textAlign: 'center',
  },
  modelButton: {
    borderWidth: 1,
    borderRadius: 6,
    paddingHorizontal: 15,
    paddingVertical: 8,
    marginRight: 10,
    alignItems: 'center',
    minWidth: 80,
    position: 'relative',
  },
  modelButtonActive: {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
  },
  modelButtonText: {
    fontSize: 10,
    fontFamily: 'monospace',
    letterSpacing: 1,
    fontWeight: 'bold',
  },
  modelIndicator: {
    width: 4,
    height: 4,
    borderRadius: 2,
    marginTop: 4,
  },
  messagesContainer: {
    flex: 1,
    padding: 15,
  },
  messageContainer: {
    marginBottom: 20,
    position: 'relative',
  },
  userMessage: {
    alignSelf: 'flex-end',
    maxWidth: '85%',
  },
  aiMessage: {
    alignSelf: 'flex-start',
    maxWidth: '85%',
  },
  systemMessage: {
    alignSelf: 'center',
    maxWidth: '90%',
  },
  messageHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  messageAuthor: {
    fontSize: 10,
    fontFamily: 'monospace',
    letterSpacing: 1,
    fontWeight: 'bold',
  },
  messageTime: {
    fontSize: 8,
    color: '#666666',
    fontFamily: 'monospace',
  },
  messageContent: {
    backgroundColor: 'rgba(0, 0, 0, 0.6)',
    borderLeftWidth: 3,
    borderRadius: 6,
    padding: 12,
  },
  messageText: {
    fontSize: 12,
    fontFamily: 'monospace',
    lineHeight: 18,
    letterSpacing: 0.5,
  },
  messageGlow: {
    position: 'absolute',
    top: 20,
    left: -1,
    right: -1,
    bottom: -1,
    borderWidth: 1,
    borderRadius: 6,
    opacity: 0.3,
  },
  inputContainer: {
    padding: 15,
    borderTopWidth: 1,
    borderTopColor: 'rgba(0, 255, 255, 0.3)',
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    borderWidth: 1,
    borderRadius: 8,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
    paddingHorizontal: 15,
    paddingVertical: 10,
  },
  textInput: {
    flex: 1,
    fontSize: 12,
    fontFamily: 'monospace',
    letterSpacing: 0.5,
    maxHeight: 100,
    marginRight: 10,
  },
  sendButton: {
    borderWidth: 1,
    borderRadius: 6,
    paddingHorizontal: 20,
    paddingVertical: 10,
    alignItems: 'center',
  },
  sendButtonText: {
    fontSize: 10,
    fontFamily: 'monospace',
    letterSpacing: 1,
    fontWeight: 'bold',
  },
  brandingContainer: {
    alignItems: 'center',
    marginTop: 10,
  },
  brandingText: {
    fontSize: 8,
    color: '#FF4444',
    fontFamily: 'monospace',
    letterSpacing: 1,
    opacity: 0.7,
  },
});

export default AIChat;