/**
 * Starfield Background Component
 * A reusable animated starfield background for headers and other elements
 */

const StarfieldBackground = {
    template: `
        <div class="starfield-container">
            <!-- Gradient background layer -->
            <div class="starfield-gradient" 
                 :style="{ background: gradientStyle }">
            </div>
            
            <!-- SVG Starfield layer -->
            <svg class="starfield-svg" 
                 xmlns="http://www.w3.org/2000/svg" 
                 preserveAspectRatio="none">
                <circle v-for="(star, index) in stars"
                        :key="index"
                        :cx="star.cx + '%'"
                        :cy="star.cy + '%'"
                        :r="star.r"
                        :fill="star.color"
                        :opacity="star.opacity"
                        :style="getStarStyle(index)" />
            </svg>
        </div>
    `,
    
    props: {
        numStars: {
            type: Number,
            default: 55
        },
        minSize: {
            type: Number,
            default: 0.4
        },
        maxSize: {
            type: Number,
            default: 1.0
        },
        gradient: {
            type: String,
            default: 'linear-gradient(135deg, #070F12 0%, #0C0F1A 100%)'
        }
    },
    
    data() {
        return {
            stars: []
        }
    },
    
    computed: {
        gradientStyle() {
            return this.gradient;
        }
    },
    
    methods: {
        getStarStyle(index) {
            // Calculate animation delay based on index
            const delays = ['0s', '1s', '2s', '3s'];
            const delay = delays[index % 4];
            return {
                animation: `starTwinkle 4s infinite ease-in-out ${delay}`
            };
        },
        
        generateStars() {
            // Color palette with weights (more white stars, fewer colored)
            const palette = [
                { color: 'white', weight: 55 },
                { color: '#C8DCFF', weight: 25 },  // cool blue
                { color: '#FFB57A', weight: 15 },  // warm orange
                { color: 'white', weight: 5 }
            ];
            
            // Build weighted color array
            const weightedColors = palette.flatMap(c => 
                Array(c.weight).fill(c.color)
            );
            
            // Generate random stars
            this.stars = Array.from({ length: this.numStars }, () => {
                return {
                    cx: Math.random() * 100,
                    cy: Math.random() * 100,
                    r: this.minSize + Math.random() * (this.maxSize - this.minSize),
                    opacity: 0.2 + Math.random() * 0.3,
                    color: weightedColors[Math.floor(Math.random() * weightedColors.length)]
                };
            });
        }
    },
    
    mounted() {
        // Inject styles into document if not already present
        if (!document.getElementById('starfield-styles')) {
            const style = document.createElement('style');
            style.id = 'starfield-styles';
            style.textContent = `
                .starfield-container {
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    overflow: hidden;
                    z-index: 0;
                }
                
                .starfield-gradient {
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                }
                
                .starfield-svg {
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    width: 100%;
                    height: 100%;
                }
                
                @keyframes starTwinkle {
                    0%, 100% { opacity: 0.2; }
                    50% { opacity: 0.6; }
                }
            `;
            document.head.appendChild(style);
        }
        
        this.generateStars();
    }
};

window.StarfieldBackground = StarfieldBackground;
