/**
 * Monitoring Panel Component - Collapsible
 */

const MonitoringPanel = {
    template: `
        <div class="bg-white rounded-lg shadow">
            <div class="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 transition-colors" @click="expanded = !expanded">
                <div class="flex items-center space-x-3">
                    <svg class="w-5 h-5 text-gray-400 transition-transform" :class="{'rotate-90': expanded}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                    </svg>
                    <h3 class="text-lg font-semibold text-gray-800">Auto-Monitoring</h3>
                    <span :class="statusClass" class="px-2 py-1 rounded-full text-xs font-semibold">
                        {{ monitoringStatus.is_active ? 'Active' : 'Inactive' }}
                    </span>
                </div>
                <div class="flex items-center space-x-2">
                    <span class="text-sm text-gray-600">{{ formatInterval }}</span>
                    <button 
                        @click.stop="toggleMonitoring" 
                        :disabled="loading"
                        :class="toggleButtonClass"
                        class="px-3 py-1 rounded text-sm font-semibold transition-colors disabled:opacity-50">
                        {{ monitoringStatus.is_active ? 'Stop' : 'Start' }}
                    </button>
                </div>
            </div>

            <div v-show="expanded" class="px-4 pb-4 border-t">
                <div class="pt-4">
                    <p class="text-sm text-gray-600 mb-4">Configure automatic scanning and processing</p>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">
                                Scan Interval (minutes)
                            </label>
                            <input 
                                type="number" 
                                v-model.number="config.interval_minutes"
                                @change="saveConfig"
                                min="5" 
                                max="1440"
                                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500">
                            <p class="text-xs text-gray-500 mt-1">How often to check for new files (5-1440)</p>
                        </div>
                        
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">
                                Ignore Files Newer Than (minutes)
                            </label>
                            <input 
                                type="number" 
                                v-model.number="config.ignore_files_newer_than_minutes"
                                @change="saveConfig"
                                min="1" 
                                max="1440"
                                class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500">
                            <p class="text-xs text-gray-500 mt-1">Skip files modified within this window</p>
                        </div>
                    </div>

                    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t">
                        <div class="text-center">
                            <div class="text-2xl font-bold text-blue-600">{{ formatInterval }}</div>
                            <div class="text-sm text-gray-600">Current Interval</div>
                        </div>
                        <div class="text-center">
                            <div class="text-2xl font-bold text-green-600">{{ lastScanTime }}</div>
                            <div class="text-sm text-gray-600">Last Scan</div>
                        </div>
                        <div class="text-center">
                            <div class="text-2xl font-bold text-purple-600">{{ monitoringStatus.last_scan_file_count || 0 }}</div>
                            <div class="text-sm text-gray-600">Files Tracked</div>
                        </div>
                    </div>

                    <div class="mt-4 p-3 bg-blue-50 rounded-lg">
                        <div class="flex items-start">
                            <svg class="w-5 h-5 text-blue-600 mt-0.5 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                            </svg>
                            <div class="text-sm text-blue-800">
                                <strong>Auto-chain:</strong> New files trigger Scan → Validate → Migrate. Files scoring ≥95 are auto-migrated.
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    data() {
        return {
            expanded: false,
            monitoringStatus: {
                is_active: false,
                enabled: false,
                interval_minutes: 30,
                ignore_files_newer_than_minutes: 30,
                last_scan_time: null,
                last_scan_file_count: 0
            },
            config: {
                enabled: false,
                interval_minutes: 30,
                ignore_files_newer_than_minutes: 30
            },
            loading: false,
            pollInterval: null
        };
    },
    
    computed: {
        statusClass() {
            return this.monitoringStatus.is_active 
                ? 'bg-green-100 text-green-800' 
                : 'bg-gray-100 text-gray-800';
        },
        
        toggleButtonClass() {
            return this.monitoringStatus.is_active
                ? 'bg-red-500 hover:bg-red-600 text-white'
                : 'bg-green-500 hover:bg-green-600 text-white';
        },
        
        formatInterval() {
            const mins = this.monitoringStatus.interval_minutes || 30;
            if (mins >= 60) {
                const hours = Math.floor(mins / 60);
                const remainingMins = mins % 60;
                return remainingMins > 0 ? `${hours}h ${remainingMins}m` : `${hours}h`;
            }
            return `${mins}m`;
        },
        
        lastScanTime() {
            if (!this.monitoringStatus.last_scan_time) {
                return 'Never';
            }
            const timestamp = this.monitoringStatus.last_scan_time * 1000;
            const now = Date.now();
            const diff = now - timestamp;
            const minutes = Math.floor(diff / 60000);
            
            if (minutes < 1) return 'Just now';
            if (minutes < 60) return `${minutes}m ago`;
            const hours = Math.floor(minutes / 60);
            if (hours < 24) return `${hours}h ago`;
            const days = Math.floor(hours / 24);
            return `${days}d ago`;
        }
    },
    
    methods: {
        async loadStatus() {
            try {
                const response = await fetch('/api/monitoring/status');
                this.monitoringStatus = await response.json();
                
                this.config = {
                    enabled: this.monitoringStatus.enabled,
                    interval_minutes: this.monitoringStatus.interval_minutes,
                    ignore_files_newer_than_minutes: this.monitoringStatus.ignore_files_newer_than_minutes
                };
            } catch (error) {
                console.error('Error loading monitoring status:', error);
            }
        },
        
        async toggleMonitoring() {
            this.loading = true;
            try {
                const endpoint = this.monitoringStatus.is_active ? 'stop' : 'start';
                const response = await fetch(`/api/monitoring/${endpoint}`, {
                    method: 'POST'
                });
                
                if (response.ok) {
                    await this.loadStatus();
                } else {
                    const error = await response.json();
                    alert(`Error: ${error.detail}`);
                }
            } catch (error) {
                console.error('Error toggling monitoring:', error);
                alert('Failed to toggle monitoring');
            } finally {
                this.loading = false;
            }
        },
        
        async saveConfig() {
            try {
                const response = await fetch('/api/monitoring/config', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(this.config)
                });
                
                if (response.ok) {
                    await this.loadStatus();
                } else {
                    const error = await response.json();
                    alert(`Error: ${error.detail}`);
                    await this.loadStatus();
                }
            } catch (error) {
                console.error('Error saving config:', error);
                alert('Failed to save configuration');
            }
        },
        
        startPolling() {
            this.pollInterval = setInterval(() => {
                this.loadStatus();
            }, 10000);
        },
        
        stopPolling() {
            if (this.pollInterval) {
                clearInterval(this.pollInterval);
                this.pollInterval = null;
            }
        }
    },
    
    async mounted() {
        await this.loadStatus();
        this.startPolling();
    },
    
    beforeUnmount() {
        this.stopPolling();
    }
};