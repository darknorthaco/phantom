/**
 * Phantom AI Matrix Interface
 * Main JavaScript controller for the Matrix-style UI
 */

const CONFIG = {
    PHANTOM_BACKEND: 'ws://192.168.1.103:8765',
    RECONNECT_INTERVAL: 3000,
    MAX_RECONNECT_ATTEMPTS: 5,
    MATRIX_RAIN_DROPS: 50,
    ANIMATION_SPEED: 60,
    COMPANY_NAME: 'Dark North Co.',
    SHOW_LOGO: true
};

class PhantomInterface {
    constructor() {
        this.socket = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = CONFIG.MAX_RECONNECT_ATTEMPTS;
        this.reconnectDelay = CONFIG.RECONNECT_INTERVAL;
        
        // UI Elements
        this.elements = {
            systemTime: document.getElementById('system-time'),
            chatMessages: document.getElementById('chat-messages'),
            chatInput: document.getElementById('chat-input'),
            sendBtn: document.getElementById('send-btn'),
            aiModel: document.getElementById('ai-model'),
            executionMode: document.getElementById('execution-mode'),
            hybridApprovalPanel: document.getElementById('hybrid-approval-panel'),
            manualRoutingPanel: document.getElementById('manual-routing-panel'),
            approvalTaskText: document.getElementById('approval-task-text'),
            approveBtn: document.getElementById('approve-btn'),
            rejectBtn: document.getElementById('reject-btn'),
            manualGpuSelect: document.getElementById('manual-gpu-select'),
            taskList: document.getElementById('task-list'),
            uptime: document.getElementById('uptime'),
            tasksCompleted: document.getElementById('tasks-completed'),
            powerConsumption: document.getElementById('power-consumption'),
            securityLevel: document.getElementById('security-level'),
            refreshIndicator: document.getElementById('refresh-indicator'),
            utilizationGraph: document.getElementById('utilization-graph')
        };
        
        // GPU Elements
        this.gpuElements = {
            gtx1080: {
                util: document.getElementById('gtx1080-util'),
                temp: document.getElementById('gtx1080-temp'),
                mem: document.getElementById('gtx1080-mem'),
                activity: document.getElementById('gtx1080-activity')
            },
            firepro: {
                util: document.getElementById('firepro-util'),
                temp: document.getElementById('firepro-temp'),
                mem: document.getElementById('firepro-mem'),
                activity: document.getElementById('firepro-activity')
            },
            rtx5080: {
                util: document.getElementById('rtx5080-util'),
                temp: document.getElementById('rtx5080-temp'),
                mem: document.getElementById('rtx5080-mem'),
                activity: document.getElementById('rtx5080-activity')
            },
            rtx5060: {
                util: document.getElementById('rtx5060-util'),
                temp: document.getElementById('rtx5060-temp'),
                mem: document.getElementById('rtx5060-mem'),
                activity: document.getElementById('rtx5060-activity')
            }
        };
        
        // System state
        this.systemState = {
            startTime: Date.now(),
            tasksCompleted: 0,
            gpuData: {
                gtx1080: { util: 0, temp: 0, mem: 0 },
                firepro: { util: 0, temp: 0, mem: 0 },
                rtx5080: { util: 0, temp: 0, mem: 0 },
                rtx5060: { util: 0, temp: 0, mem: 0 }
            },
            activeTasks: [],
            networkNodes: [
                { name: 'FEDORA-SERVER', status: 'online', latency: 1 },
                { name: 'WINDOWS-PC', status: 'online', latency: 2 }
            ]
        };
        
        // Performance graph
        this.performanceData = [];
        this.maxDataPoints = 50;
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.startSystemClock();
        this.startPerformanceMonitoring();
        this.connectToPhantom();
        this.initializeTypingEffect();
        this.simulateInitialData();
    }
    
    setupEventListeners() {
        // Chat input
        this.elements.chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.sendMessage();
            }
        });
        
        this.elements.sendBtn.addEventListener('click', () => {
            this.sendMessage();
        });
        
        // Control buttons
        document.getElementById('emergency-stop').addEventListener('click', () => {
            this.emergencyStop();
        });
        
        document.getElementById('restart-cluster').addEventListener('click', () => {
            this.restartCluster();
        });
        
        document.getElementById('load-balance').addEventListener('click', () => {
            this.loadBalance();
        });
        
        // Model selection
        this.elements.aiModel.addEventListener('change', (e) => {
            this.switchModel(e.target.value);
        });
        
        // Execution mode selection
        this.elements.executionMode.addEventListener('change', (e) => {
            this.switchMode(e.target.value);
        });
        
        // HYBRID approval buttons
        this.elements.approveBtn.addEventListener('click', () => {
            this.handleApproval(true);
        });
        
        this.elements.rejectBtn.addEventListener('click', () => {
            this.handleApproval(false);
        });
    }
    
    connectToPhantom() {
        try {
            // Prevent creating a new socket if one is already open or connecting
            if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
                return;
            }

            // Connect to Phantom socket server
            this.socket = new WebSocket(CONFIG.PHANTOM_BACKEND);
            
            this.socket.onopen = () => {
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.addSystemMessage('PHANTOM NEURAL NETWORK CONNECTION ESTABLISHED');
                this.playNotificationSound();
                
                // Request initial system status
                this.sendSocketMessage({
                    type: 'get_status',
                    timestamp: Date.now()
                });
            };
            
            this.socket.onmessage = (event) => {
                try {
                    this.handleSocketMessage(JSON.parse(event.data));
                } catch (e) {
                    console.error('Failed to parse socket message:', e);
                    this.addSystemMessage('RECEIVED MALFORMED DATA FROM PHANTOM');
                }
            };
            
            this.socket.onclose = () => {
                this.isConnected = false;
                this.addSystemMessage('CONNECTION TO PHANTOM LOST - ATTEMPTING RECONNECT...');
                this.attemptReconnect();
            };
            
            this.socket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.addSystemMessage('NEURAL NETWORK ERROR DETECTED');
            };
            
        } catch (error) {
            console.error('Failed to connect to Phantom:', error);
            this.addSystemMessage('FAILED TO ESTABLISH NEURAL CONNECTION - RUNNING IN DEMO MODE');
            this.startDemoMode();
        }
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            setTimeout(() => {
                this.addSystemMessage(`RECONNECTION ATTEMPT ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
                this.connectToPhantom();
            }, this.reconnectDelay);
        } else {
            this.addSystemMessage('MAX RECONNECTION ATTEMPTS REACHED - ENTERING OFFLINE MODE');
            this.startDemoMode();
        }
    }
    
    sendSocketMessage(message) {
        if (this.isConnected && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(message));
        }
    }
    
    handleSocketMessage(data) {
        switch (data.type) {
            case 'gpu_status':
                this.updateGPUStatus(data.gpus);
                break;
            case 'task_update':
                this.updateTaskStatus(data.tasks);
                break;
            case 'system_status':
                this.updateSystemStatus(data.status);
                break;
            case 'ai_response':
                this.addAIMessage(data.response, data.model);
                break;
            case 'approval_required':
                this.showApprovalRequest(data.task);
                break;
            case 'error':
                this.addSystemMessage(`ERROR: ${data.message}`);
                break;
            default:
                console.log('Unknown message type:', data.type);
        }
    }
    
    sendMessage() {
        const message = this.elements.chatInput.value.trim();
        if (!message) return;
        
        // Add user message to chat
        this.addUserMessage(message);
        
        // Clear input
        this.elements.chatInput.value = '';
        
        // Send to AI model
        const selectedModel = this.elements.aiModel.value;
        const selectedMode = this.elements.executionMode.value;
        
        if (this.isConnected) {
            const payload = {
                type: 'ai_query',
                message: message,
                model: selectedModel,
                mode: selectedMode,
                timestamp: Date.now()
            };
            if (selectedMode === 'MANUAL') {
                payload.target_gpu = this.elements.manualGpuSelect.value;
            }
            this.sendSocketMessage(payload);
        } else {
            // Demo mode response
            this.simulateAIResponse(message, selectedModel, selectedMode);
        }
        
        this.playTypingSound();
    }
    
    addSystemMessage(message) {
        this.addMessage('system', message);
    }
    
    addUserMessage(message) {
        this.addMessage('user', message);
    }
    
    addAIMessage(message, model) {
        this.addMessage('ai', message, model);
    }
    
    addMessage(type, message, extra = '') {
        const timestamp = this.getCurrentTime();
        const messageDiv = document.createElement('div');
        messageDiv.className = `${type}-message`;
        
        const timestampSpan = document.createElement('span');
        timestampSpan.className = 'timestamp';
        timestampSpan.textContent = `[${timestamp}]`;
        
        const messageSpan = document.createElement('span');
        messageSpan.className = 'message';
        
        if (type === 'ai' && extra) {
            const strong = document.createElement('strong');
            strong.textContent = `[${extra}]:`;
            messageSpan.appendChild(strong);
            messageSpan.appendChild(document.createTextNode(` ${message}`));
        } else if (type === 'user') {
            const strong = document.createElement('strong');
            strong.textContent = 'USER:';
            messageSpan.appendChild(strong);
            messageSpan.appendChild(document.createTextNode(` ${message}`));
        } else {
            messageSpan.textContent = message;
        }
        
        messageDiv.appendChild(timestampSpan);
        messageDiv.appendChild(messageSpan);
        
        this.elements.chatMessages.appendChild(messageDiv);
        this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
        
        // Typing effect for AI messages
        if (type === 'ai') {
            this.typeMessage(messageSpan);
        }
    }
    
    typeMessage(element) {
        // Collect existing child nodes (preserve structure such as <strong> labels)
        const nodes = Array.from(element.childNodes);
        // Get the last text node — this holds the actual message content
        const textNode = nodes.filter(n => n.nodeType === Node.TEXT_NODE).pop();
        if (!textNode) return;

        const fullText = textNode.textContent;
        textNode.textContent = '';
        let i = 0;
        
        const typeInterval = setInterval(() => {
            i++;
            textNode.textContent = fullText.substring(0, i);
            
            if (i >= fullText.length) {
                clearInterval(typeInterval);
            }
            
            this.playTypingSound();
        }, 30);
    }
    
    updateGPUStatus(gpuData) {
        Object.keys(gpuData).forEach(gpuId => {
            const gpu = gpuData[gpuId];
            const elements = this.gpuElements[gpuId];
            
            if (elements) {
                elements.util.textContent = `${gpu.utilization}%`;
                elements.temp.textContent = `${gpu.temperature}°C`;
                elements.mem.textContent = `${gpu.memory_used}MB`;
                elements.activity.style.width = `${gpu.utilization}%`;
                
                // Update system state
                this.systemState.gpuData[gpuId] = {
                    util: gpu.utilization,
                    temp: gpu.temperature,
                    mem: gpu.memory_used
                };
            }
        });
        
        // Update Matrix rain with GPU data
        if (window.matrixRain) {
            const rainData = {};
            Object.keys(this.systemState.gpuData).forEach(gpu => {
                rainData[gpu] = this.systemState.gpuData[gpu].util;
            });
            window.matrixRain.updateGPUData(rainData);
        }
        
        // Update performance graph
        this.updatePerformanceGraph();
    }
    
    updateTaskStatus(tasks) {
        this.systemState.activeTasks = tasks;
        this.renderTaskList();
    }
    
    updateSystemStatus(status) {
        if (status.uptime) {
            this.elements.uptime.textContent = this.formatUptime(status.uptime);
        }
        
        if (status.tasks_completed !== undefined) {
            this.systemState.tasksCompleted = status.tasks_completed;
            this.elements.tasksCompleted.textContent = status.tasks_completed;
        }
        
        if (status.power_consumption) {
            this.elements.powerConsumption.textContent = `${status.power_consumption}W`;
        }
        
        if (status.security_level) {
            this.updateSecurityLevel(status.security_level);
        }
    }
    
    renderTaskList() {
        this.elements.taskList.innerHTML = '';
        
        this.systemState.activeTasks.forEach(task => {
            const taskDiv = document.createElement('div');
            taskDiv.className = 'task-item';
            
            taskDiv.innerHTML = `
                <span class="task-id">[${task.id}]</span>
                <span class="task-type">${task.type}</span>
                <span class="task-gpu">${task.gpu}</span>
                <span class="task-status ${task.status}">${task.status.toUpperCase()}</span>
            `;
            
            this.elements.taskList.appendChild(taskDiv);
        });
    }
    
    updatePerformanceGraph() {
        const canvas = this.elements.utilizationGraph;
        const ctx = canvas.getContext('2d');
        
        // Calculate average utilization
        const avgUtil = Object.values(this.systemState.gpuData)
            .reduce((sum, gpu) => sum + gpu.util, 0) / 4;
        
        // Add to performance data
        this.performanceData.push(avgUtil);
        if (this.performanceData.length > this.maxDataPoints) {
            this.performanceData.shift();
        }
        
        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Draw grid
        ctx.strokeStyle = '#003B00';
        ctx.lineWidth = 1;
        
        // Horizontal lines
        for (let i = 0; i <= 4; i++) {
            const y = (canvas.height / 4) * i;
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(canvas.width, y);
            ctx.stroke();
        }
        
        // Vertical lines
        for (let i = 0; i <= 10; i++) {
            const x = (canvas.width / 10) * i;
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, canvas.height);
            ctx.stroke();
        }
        
        // Draw performance line
        if (this.performanceData.length > 1) {
            ctx.strokeStyle = '#00FF41';
            ctx.lineWidth = 2;
            ctx.beginPath();
            
            this.performanceData.forEach((value, index) => {
                const x = (canvas.width / this.maxDataPoints) * index;
                const y = canvas.height - (canvas.height * (value / 100));
                
                if (index === 0) {
                    ctx.moveTo(x, y);
                } else {
                    ctx.lineTo(x, y);
                }
            });
            
            ctx.stroke();
            
            // Add glow effect
            ctx.shadowColor = '#00FF41';
            ctx.shadowBlur = 10;
            ctx.stroke();
            ctx.shadowBlur = 0;
        }
    }
    
    updateSecurityLevel(level) {
        const indicator = this.elements.securityLevel.querySelector('.level-indicator');
        const text = this.elements.securityLevel.querySelector('.level-text');
        
        indicator.className = `level-indicator ${level.toLowerCase()}`;
        text.textContent = level.toUpperCase();
    }
    
    startSystemClock() {
        setInterval(() => {
            this.elements.systemTime.textContent = this.getCurrentTime();
        }, 1000);
    }
    
    startPerformanceMonitoring() {
        setInterval(() => {
            if (!this.isConnected) {
                this.simulateGPUData();
            }
            this.updateUptime();
        }, 2000);
    }
    
    updateUptime() {
        const uptime = Date.now() - this.systemState.startTime;
        this.elements.uptime.textContent = this.formatUptime(uptime);
    }
    
    formatUptime(milliseconds) {
        const seconds = Math.floor(milliseconds / 1000);
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    
    getCurrentTime() {
        const now = new Date();
        return now.toTimeString().split(' ')[0];
    }
    
    initializeTypingEffect() {
        const typingElements = document.querySelectorAll('.typing-text');
        
        typingElements.forEach(element => {
            const text = element.getAttribute('data-text');
            element.textContent = '';
            
            let i = 0;
            const typeInterval = setInterval(() => {
                element.textContent += text[i];
                i++;
                
                if (i >= text.length) {
                    clearInterval(typeInterval);
                }
            }, 50);
        });
    }
    
    // Demo mode functions
    startDemoMode() {
        this.addSystemMessage('ENTERING DEMONSTRATION MODE');
        this.addSystemMessage('SIMULATING PHANTOM NEURAL NETWORK...');
        
        // Simulate periodic updates
        setInterval(() => {
            this.simulateGPUData();
            this.simulateTaskUpdates();
        }, 3000);
    }
    
    simulateInitialData() {
        // Add some initial tasks
        this.systemState.activeTasks = [
            { id: 'TASK-001', type: 'LLM-INFERENCE', gpu: 'GTX1080', status: 'running' },
            { id: 'TASK-002', type: 'MATRIX-MULT', gpu: 'RTX5080', status: 'running' },
            { id: 'TASK-003', type: 'MEMORY-OPT', gpu: 'FIREPRO', status: 'completed' }
        ];
        
        this.renderTaskList();
        
        // Set initial GPU data
        this.simulateGPUData();
    }
    
    simulateGPUData() {
        const gpuData = {
            gtx1080: {
                utilization: Math.floor(Math.random() * 40) + 30, // 30-70%
                temperature: Math.floor(Math.random() * 20) + 65, // 65-85°C
                memory_used: Math.floor(Math.random() * 2000) + 6000 // 6-8GB
            },
            firepro: {
                utilization: Math.floor(Math.random() * 60) + 20, // 20-80%
                temperature: Math.floor(Math.random() * 25) + 70, // 70-95°C
                memory_used: Math.floor(Math.random() * 4000) + 12000 // 12-16GB
            },
            rtx5080: {
                utilization: Math.floor(Math.random() * 80) + 10, // 10-90%
                temperature: Math.floor(Math.random() * 30) + 60, // 60-90°C
                memory_used: Math.floor(Math.random() * 8000) + 16000 // 16-24GB
            },
            rtx5060: {
                utilization: Math.floor(Math.random() * 70) + 15, // 15-85%
                temperature: Math.floor(Math.random() * 25) + 55, // 55-80°C
                memory_used: Math.floor(Math.random() * 4000) + 12000 // 12-16GB
            }
        };
        
        this.updateGPUStatus(gpuData);
    }
    
    simulateTaskUpdates() {
        // Randomly complete tasks and add new ones
        if (Math.random() < 0.3) {
            const runningTasks = this.systemState.activeTasks.filter(t => t.status === 'running');
            if (runningTasks.length > 0) {
                const taskToComplete = runningTasks[Math.floor(Math.random() * runningTasks.length)];
                taskToComplete.status = 'completed';
                this.systemState.tasksCompleted++;
                this.elements.tasksCompleted.textContent = this.systemState.tasksCompleted;
            }
        }
        
        // Add new task
        if (Math.random() < 0.4 && this.systemState.activeTasks.length < 5) {
            const taskTypes = ['LLM-INFERENCE', 'MATRIX-MULT', 'CONV-NET', 'MEMORY-OPT', 'DATA-PROC'];
            const gpus = ['GTX1080', 'FIREPRO', 'RTX5080', 'RTX5060'];
            
            const newTask = {
                id: `TASK-${String(Date.now()).slice(-3)}`,
                type: taskTypes[Math.floor(Math.random() * taskTypes.length)],
                gpu: gpus[Math.floor(Math.random() * gpus.length)],
                status: 'running'
            };
            
            this.systemState.activeTasks.push(newTask);
        }
        
        this.renderTaskList();
    }
    
    simulateAIResponse(message, model, mode = 'AUTO') {
        const responses = [
            "Neural pathways analyzed. Processing your request through distributed compute fabric.",
            "Quantum entanglement established with knowledge matrix. Retrieving data...",
            "Accessing distributed neural network. Cross-referencing with training data.",
            "Matrix calculations complete. Synthesizing response from collective intelligence.",
            "Phantom AI nodes synchronized. Generating contextual response.",
            "Deep learning algorithms engaged. Processing natural language query.",
            "Distributed inference complete. Compiling results from GPU cluster."
        ];
        
        if (mode === 'HYBRID') {
            setTimeout(() => {
                this.showApprovalRequest(`Demo task: "${message.substring(0, 60)}"`);
            }, 500);
            return;
        }
        
        setTimeout(() => {
            const response = responses[Math.floor(Math.random() * responses.length)];
            const modeTag = mode !== 'AUTO' ? ` [${mode}]` : '';
            this.addAIMessage(response + modeTag, model);
        }, 1000 + Math.random() * 2000);
    }
    
    // Control functions
    emergencyStop() {
        this.addSystemMessage('EMERGENCY STOP INITIATED - HALTING ALL OPERATIONS');
        if (window.matrixRain) {
            window.matrixRain.pulse('#FF0040');
        }
        this.playNotificationSound();
    }
    
    restartCluster() {
        this.addSystemMessage('CLUSTER RESTART SEQUENCE INITIATED');
        this.addSystemMessage('SHUTTING DOWN NEURAL NODES...');
        
        setTimeout(() => {
            this.addSystemMessage('RESTARTING PHANTOM DISTRIBUTED SYSTEM...');
        }, 2000);
        
        setTimeout(() => {
            this.addSystemMessage('CLUSTER RESTART COMPLETE - ALL SYSTEMS ONLINE');
            if (window.matrixRain) {
                window.matrixRain.pulse('#00FF41');
            }
        }, 4000);
    }
    
    loadBalance() {
        this.addSystemMessage('INITIATING LOAD BALANCING ACROSS GPU CLUSTER');
        this.addSystemMessage('REDISTRIBUTING NEURAL WORKLOAD...');
        
        setTimeout(() => {
            this.addSystemMessage('LOAD BALANCING COMPLETE - OPTIMAL DISTRIBUTION ACHIEVED');
        }, 3000);
    }
    
    switchModel(model) {
        this.addSystemMessage(`SWITCHING TO AI MODEL: ${model.toUpperCase()}`);
        
        if (this.isConnected) {
            this.sendSocketMessage({
                type: 'switch_model',
                model: model,
                timestamp: Date.now()
            });
        }
    }
    
    switchMode(mode) {
        this.addSystemMessage(`EXECUTION MODE CHANGED TO: ${mode}`);
        
        // Show/hide mode-specific panels
        this.elements.hybridApprovalPanel.style.display = mode === 'HYBRID' ? 'block' : 'none';
        this.elements.manualRoutingPanel.style.display = mode === 'MANUAL' ? 'block' : 'none';
        
        if (this.isConnected) {
            this.sendSocketMessage({
                type: 'set_mode',
                mode: mode,
                timestamp: Date.now()
            });
        }
    }
    
    handleApproval(approved) {
        const action = approved ? 'APPROVED' : 'REJECTED';
        this.addSystemMessage(`HYBRID MODE: TASK ${action}`);
        this.elements.approvalTaskText.textContent = 'Awaiting task for approval...';
        
        if (this.isConnected) {
            this.sendSocketMessage({
                type: 'approval_response',
                approved: approved,
                mode: 'HYBRID',
                timestamp: Date.now()
            });
        }
    }
    
    showApprovalRequest(task) {
        this.elements.approvalTaskText.textContent = task || 'Pending task requires your approval';
        this.addSystemMessage('HYBRID MODE: TASK REQUIRES APPROVAL');
    }
    
    // Audio functions
    playTypingSound() {
        const audio = document.getElementById('typing-sound');
        if (audio) {
            audio.currentTime = 0;
            audio.play().catch(() => {}); // Ignore audio errors
        }
    }
    
    playNotificationSound() {
        const audio = document.getElementById('notification-sound');
        if (audio) {
            audio.currentTime = 0;
            audio.play().catch(() => {}); // Ignore audio errors
        }
    }
}

// Initialize the interface when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.phantomInterface = new PhantomInterface();
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PhantomInterface;
}