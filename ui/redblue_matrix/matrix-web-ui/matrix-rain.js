/**
 * Matrix Digital Rain Effect
 * Uses real GPU utilization data to drive the animation
 */

class MatrixRain {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.resizeCanvas();
        
        // Matrix characters (including Japanese katakana)
        this.chars = "アァカサタナハマヤャラワガザダバパイィキシチニヒミリヰギジヂビピウゥクスツヌフムユュルグズブヅプエェケセテネヘメレヱゲゼデベペオォコソトノホモヨョロヲゴゾドボポヴッン0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ";
        this.charArray = this.chars.split('');
        
        // Animation properties
        this.fontSize = 14;
        this.columns = Math.floor(this.canvas.width / this.fontSize);
        this.drops = [];
        this.gpuData = {
            gpu_0: 0,
            gpu_1: 0,
            gpu_2: 0,
            gpu_3: 0
        };
        
        // Initialize drops
        this.initDrops();
        
        // Start animation
        this.animate();
        
        // Handle window resize
        window.addEventListener('resize', () => this.resizeCanvas());
    }
    
    resizeCanvas() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
        this.columns = Math.floor(this.canvas.width / this.fontSize);
        this.initDrops();
    }
    
    initDrops() {
        this.drops = [];
        for (let i = 0; i < this.columns; i++) {
            this.drops[i] = {
                y: Math.random() * this.canvas.height,
                speed: Math.random() * 3 + 1,
                chars: [],
                intensity: Math.random()
            };
            
            // Initialize character trail for each drop
            for (let j = 0; j < 20; j++) {
                this.drops[i].chars[j] = this.getRandomChar();
            }
        }
    }
    
    getRandomChar() {
        return this.charArray[Math.floor(Math.random() * this.charArray.length)];
    }
    
    updateGPUData(gpuData) {
        this.gpuData = { ...this.gpuData, ...gpuData };
    }
    
    getIntensityFromGPU() {
        // Calculate average GPU utilization to drive rain intensity
        const total = this.gpuData.gpu_0 + this.gpuData.gpu_1 + 
                     this.gpuData.gpu_2 + this.gpuData.gpu_3;
        return Math.min(total / 400, 1); // Normalize to 0-1
    }
    
    draw() {
        // Create fade effect
        this.ctx.fillStyle = 'rgba(0, 0, 0, 0.05)';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Set font
        this.ctx.font = `${this.fontSize}px 'Share Tech Mono', monospace`;
        
        const intensity = this.getIntensityFromGPU();
        
        for (let i = 0; i < this.drops.length; i++) {
            const drop = this.drops[i];
            
            // Adjust speed based on GPU utilization
            const speedMultiplier = 0.5 + (intensity * 2);
            drop.y += drop.speed * speedMultiplier;
            
            // Draw character trail
            for (let j = 0; j < drop.chars.length; j++) {
                const char = drop.chars[j];
                const x = i * this.fontSize;
                const y = drop.y - (j * this.fontSize);
                
                if (y > 0 && y < this.canvas.height) {
                    // Calculate alpha based on position in trail
                    const alpha = (drop.chars.length - j) / drop.chars.length;
                    
                    // Color based on GPU that's most active
                    let color = '#00FF41'; // Default matrix green
                    
                    if (this.gpuData.gpu_2 > 50) {
                        color = '#00FFFF'; // Cyan for GPU-2
                    } else if (this.gpuData.gpu_1 > 50) {
                        color = '#FF0040'; // Red for GPU-1
                    } else if (this.gpuData.gpu_3 > 50) {
                        color = '#FFFF00'; // Yellow for GPU-3
                    }
                    
                    // Brightest character at the head
                    if (j === 0) {
                        this.ctx.fillStyle = '#FFFFFF';
                        this.ctx.shadowColor = color;
                        this.ctx.shadowBlur = 10;
                    } else {
                        this.ctx.fillStyle = color;
                        this.ctx.globalAlpha = alpha * 0.8;
                        this.ctx.shadowBlur = 0;
                    }
                    
                    this.ctx.fillText(char, x, y);
                    this.ctx.globalAlpha = 1;
                }
            }
            
            // Reset drop when it goes off screen
            if (drop.y > this.canvas.height + (drop.chars.length * this.fontSize)) {
                drop.y = -drop.chars.length * this.fontSize;
                drop.speed = Math.random() * 3 + 1;
                
                // Refresh characters
                for (let j = 0; j < drop.chars.length; j++) {
                    drop.chars[j] = this.getRandomChar();
                }
            }
            
            // Randomly change characters
            if (Math.random() < 0.01) {
                const randomIndex = Math.floor(Math.random() * drop.chars.length);
                drop.chars[randomIndex] = this.getRandomChar();
            }
        }
        
        // Reset shadow
        this.ctx.shadowColor = 'transparent';
        this.ctx.shadowBlur = 0;
    }
    
    animate() {
        this.draw();
        requestAnimationFrame(() => this.animate());
    }
    
    // Add special effects for system events
    addBurst(x, y, color = '#00FF41') {
        // Create a burst effect at specific coordinates
        for (let i = 0; i < 10; i++) {
            const angle = (Math.PI * 2 * i) / 10;
            const speed = Math.random() * 5 + 2;
            
            // Create temporary particles
            setTimeout(() => {
                this.ctx.fillStyle = color;
                this.ctx.shadowColor = color;
                this.ctx.shadowBlur = 15;
                this.ctx.beginPath();
                this.ctx.arc(
                    x + Math.cos(angle) * speed * 10,
                    y + Math.sin(angle) * speed * 10,
                    3,
                    0,
                    Math.PI * 2
                );
                this.ctx.fill();
            }, i * 50);
        }
    }
    
    // Pulse effect for system alerts
    pulse(color = '#FF0040') {
        const originalIntensity = this.getIntensityFromGPU();
        
        // Temporarily increase intensity
        this.gpuData.gpu_0 = 100;
        this.gpuData.gpu_1 = 100;
        this.gpuData.gpu_2 = 100;
        this.gpuData.gpu_3 = 100;
        
        // Flash effect
        this.ctx.fillStyle = color;
        this.ctx.globalAlpha = 0.3;
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        this.ctx.globalAlpha = 1;
        
        // Reset after pulse
        setTimeout(() => {
            this.gpuData.gpu_0 = originalIntensity * 100;
            this.gpuData.gpu_1 = originalIntensity * 100;
            this.gpuData.gpu_2 = originalIntensity * 100;
            this.gpuData.gpu_3 = originalIntensity * 100;
        }, 500);
    }
}

// Initialize Matrix Rain when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.matrixRain = new MatrixRain('matrix-rain');
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MatrixRain;
}