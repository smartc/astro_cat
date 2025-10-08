/**
 * App Footer Component - Shared across all pages
 */

const AppFooter = {
    template: `
        <footer class="text-center py-3 text-xs border-t bg-gray-50">
            <div class="container mx-auto flex justify-between items-center px-6">
                <!-- Version -->
                <div class="text-gray-500">
                    AstroCat {{ appVersion }}
                </div>
                
                <!-- Monitoring Status -->
                <div v-if="monitoringStatus" class="flex items-center space-x-4">
                    <div class="flex items-center space-x-2">
                        <span :class="monitoringStatus.enabled ? 'status-indicator status-success' : 'status-indicator status-error'"></span>
                        <span class="text-gray-600">
                            Monitoring: {{ monitoringStatus.enabled ? 'Active' : 'Inactive' }}
                        </span>
                    </div>
                    
                    <div v-if="monitoringStatus.enabled && monitoringStatus.last_scan" class="text-gray-500">
                        Last scan: {{ formatTime(monitoringStatus.last_scan) }}
                    </div>
                </div>
                
                <!-- Placeholder when no monitoring status -->
                <div v-else class="text-gray-400">
                    Loading status...
                </div>
            </div>
        </footer>
    `,
    
    data() {
        return {
            appVersion: 'loading...',
            monitoringStatus: null,
            statusInterval: null
        }
    },
    
    methods: {
        async loadVersion() {
            try {
                const response = await axios.get('/api/version');
                this.appVersion = response.data.version;
            } catch (error) {
                console.error('Error loading version:', error);
                this.appVersion = 'unknown';
            }
        },
        
        async checkMonitoringStatus() {
            try {
                const response = await axios.get('/api/monitoring/status');
                this.monitoringStatus = response.data;
            } catch (error) {
                console.error('Error loading monitoring status:', error);
            }
        },
        
        formatTime(isoString) {
            if (!isoString) return 'Never';
            const date = new Date(isoString);
            const now = new Date();
            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000);
            
            if (diffMins < 1) return 'Just now';
            if (diffMins < 60) return `${diffMins}m ago`;
            const diffHours = Math.floor(diffMins / 60);
            if (diffHours < 24) return `${diffHours}h ago`;
            const diffDays = Math.floor(diffHours / 24);
            return `${diffDays}d ago`;
        }
    },
    
    mounted() {
        this.loadVersion();
        this.checkMonitoringStatus();
        
        // Poll monitoring status every 10 seconds
        this.statusInterval = setInterval(() => {
            this.checkMonitoringStatus();
        }, 10000);
    },
    
    beforeUnmount() {
        if (this.statusInterval) {
            clearInterval(this.statusInterval);
        }
    }
};

window.AppFooter = AppFooter;