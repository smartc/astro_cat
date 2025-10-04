/**
 * Dashboard Tab Component
 */

const DashboardTab = {
    template: `
        <div class="space-y-6">
            <!-- Main Stats Grid -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
                <div class="stats-card">
                    <h3 class="text-lg font-semibold text-gray-700 mb-2">Total Files</h3>
                    <p class="text-3xl font-bold text-blue-600">{{ stats.total_files || 0 }}</p>
                </div>
                <div class="stats-card">
                    <h3 class="text-lg font-semibold text-gray-700 mb-2">Registered</h3>
                    <p class="text-3xl font-bold text-green-600">{{ (stats.validation && stats.validation.registered) || 0 }}</p>
                    <p class="text-sm text-gray-500">≥95 points</p>
                </div>
                <div class="stats-card">
                    <h3 class="text-lg font-semibold text-gray-700 mb-2">Ready</h3>
                    <p class="text-3xl font-bold text-green-600">{{ (stats.validation && stats.validation.auto_migrate) || 0 }}</p>
                    <p class="text-sm text-gray-500">≥95 points</p>
                </div>
                <div class="stats-card">
                    <h3 class="text-lg font-semibold text-gray-700 mb-2">Needs Review</h3>
                    <p class="text-3xl font-bold text-yellow-600">{{ (stats.validation && stats.validation.needs_review) || 0 }}</p>
                    <p class="text-sm text-gray-500">80-94 points</p>
                </div>
                <div class="stats-card">
                    <h3 class="text-lg font-semibold text-gray-700 mb-2">Manual Only</h3>
                    <p class="text-3xl font-bold text-red-600">{{ (stats.validation && stats.validation.manual_only) || 0 }}</p>
                    <p class="text-sm text-gray-500">&lt;80 points</p>
                </div>
            </div>

            <!-- Session Statistics - Three Column Layout -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <!-- Imaging Sessions Card - Clickable -->
                <div class="bg-white rounded-lg shadow-md p-6 cursor-pointer hover:shadow-lg transition" @click="goToImagingSessions">
                    <div class="flex justify-between items-center mb-4">
                        <h2 class="text-xl font-bold text-gray-800">Imaging Sessions</h2>
                        <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                        </svg>
                    </div>
                    <div class="space-y-3">
                        <div class="border-l-4 border-blue-500 pl-4 h-20">
                            <h3 class="text-sm font-semibold text-gray-600 mb-1">Total Sessions</h3>
                            <p class="text-2xl font-bold text-blue-600">{{ (stats.imaging_sessions && stats.imaging_sessions.total) || 0 }}</p>
                            <p class="text-xs text-gray-500 mt-1">Observation nights</p>
                        </div>
                        <div class="border-l-4 border-purple-500 pl-4 h-20">
                            <h3 class="text-sm font-semibold text-gray-600 mb-1">Unique Cameras</h3>
                            <p class="text-2xl font-bold text-purple-600">{{ (stats.imaging_sessions && stats.imaging_sessions.unique_cameras) || 0 }}</p>
                            <p class="text-xs text-gray-500 mt-1">Used in sessions</p>
                        </div>
                        <div class="border-l-4 border-indigo-500 pl-4 h-20">
                            <h3 class="text-sm font-semibold text-gray-600 mb-1">Unique Telescopes</h3>
                            <p class="text-2xl font-bold text-indigo-600">{{ (stats.imaging_sessions && stats.imaging_sessions.unique_telescopes) || 0 }}</p>
                            <p class="text-xs text-gray-500 mt-1">Used in sessions</p>
                        </div>
                    </div>
                </div>

                <!-- Processing Sessions Card - Clickable -->
                <div class="bg-white rounded-lg shadow-md p-6 cursor-pointer hover:shadow-lg transition" @click="goToProcessingSessions">
                    <div class="flex justify-between items-center mb-4">
                        <h2 class="text-xl font-bold text-gray-800">Processing Sessions</h2>
                        <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                        </svg>
                    </div>
                    <div class="space-y-3">
                        <div class="border-l-4 border-blue-500 pl-4 h-20">
                            <h3 class="text-sm font-semibold text-gray-600 mb-1">Total Sessions</h3>
                            <p class="text-2xl font-bold text-blue-600">{{ (stats.processing_sessions && stats.processing_sessions.total) || 0 }}</p>
                            <p class="text-xs text-gray-500 mt-1">&nbsp;</p>
                        </div>
                        <div class="border-l-4 border-yellow-500 pl-4 h-20">
                            <h3 class="text-sm font-semibold text-gray-600 mb-1">In Progress</h3>
                            <p class="text-2xl font-bold text-yellow-600">{{ (stats.processing_sessions && stats.processing_sessions.in_progress) || 0 }}</p>
                            <p class="text-xs text-gray-500 mt-1">&nbsp;</p>
                        </div>
                        <div class="border-l-4 border-green-500 pl-4 h-20">
                            <h3 class="text-sm font-semibold text-gray-600 mb-1">Active Sessions</h3>
                            <p class="text-2xl font-bold text-green-600">{{ (stats.processing_sessions && stats.processing_sessions.active) || 0 }}</p>
                            <p class="text-xs text-gray-500 mt-1">Not started or in progress</p>
                        </div>
                    </div>
                </div>

                <!-- File Management Card - Clickable -->
                <div class="bg-white rounded-lg shadow-md p-6 cursor-pointer hover:shadow-lg transition" @click="goToOperations">
                    <div class="flex justify-between items-center mb-4">
                        <h2 class="text-xl font-bold text-gray-800">File Management</h2>
                        <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                        </svg>
                    </div>
                    <div class="space-y-3">
                        <div class="border-l-4 border-orange-500 pl-4 h-20">
                            <h3 class="text-sm font-semibold text-gray-600 mb-1">Quarantine</h3>
                            <p class="text-2xl font-bold text-orange-600">{{ stats.quarantine_files || 0 }}</p>
                            <p class="text-xs text-gray-500 mt-1">Awaiting processing</p>
                        </div>
                        <div class="border-l-4 border-purple-500 pl-4 h-20">
                            <h3 class="text-sm font-semibold text-gray-600 mb-1">Staged</h3>
                            <p class="text-2xl font-bold text-purple-600">{{ stats.staged_files || 0 }}</p>
                            <p class="text-xs text-gray-500 mt-1">In processing sessions</p>
                        </div>
                        <div class="border-l-4 border-red-500 pl-4 h-20">
                            <h3 class="text-sm font-semibold text-gray-600 mb-1">Needs Attention</h3>
                            <p class="text-2xl font-bold text-red-600">{{ cleanupTotal }}</p>
                            <p class="text-xs text-gray-500 mt-1">Duplicates, bad, missing</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Frame Type Distribution -->
            <div class="bg-white rounded-lg shadow-md p-6">
                <h2 class="text-xl font-bold text-gray-800 mb-4">Frame Type Distribution</h2>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div class="text-center p-4 bg-blue-50 rounded-lg">
                        <p class="text-sm font-semibold text-gray-600 mb-1">LIGHT</p>
                        <p class="text-2xl font-bold text-blue-600">{{ (stats.by_frame_type && stats.by_frame_type.LIGHT) || 0 }}</p>
                    </div>
                    <div class="text-center p-4 bg-gray-50 rounded-lg">
                        <p class="text-sm font-semibold text-gray-600 mb-1">DARK</p>
                        <p class="text-2xl font-bold text-gray-600">{{ (stats.by_frame_type && stats.by_frame_type.DARK) || 0 }}</p>
                    </div>
                    <div class="text-center p-4 bg-green-50 rounded-lg">
                        <p class="text-sm font-semibold text-gray-600 mb-1">FLAT</p>
                        <p class="text-2xl font-bold text-green-600">{{ (stats.by_frame_type && stats.by_frame_type.FLAT) || 0 }}</p>
                    </div>
                    <div class="text-center p-4 bg-purple-50 rounded-lg">
                        <p class="text-sm font-semibold text-gray-600 mb-1">BIAS</p>
                        <p class="text-2xl font-bold text-purple-600">{{ (stats.by_frame_type && stats.by_frame_type.BIAS) || 0 }}</p>
                    </div>
                </div>
            </div>

            <!-- Cleanup Information -->
            <div v-if="cleanupTotal > 0" class="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
                <h2 class="text-xl font-bold text-yellow-800 mb-4">⚠️ Items Needing Attention</h2>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div v-if="(stats.cleanup && stats.cleanup.duplicates) > 0" class="text-center">
                        <p class="text-3xl font-bold text-yellow-600">{{ stats.cleanup.duplicates }}</p>
                        <p class="text-sm text-gray-600">Duplicate Files</p>
                    </div>
                    <div v-if="(stats.cleanup && stats.cleanup.bad_files) > 0" class="text-center">
                        <p class="text-3xl font-bold text-red-600">{{ stats.cleanup.bad_files }}</p>
                        <p class="text-sm text-gray-600">Bad Files</p>
                    </div>
                    <div v-if="(stats.cleanup && stats.cleanup.missing_files) > 0" class="text-center">
                        <p class="text-3xl font-bold text-orange-600">{{ stats.cleanup.missing_files }}</p>
                        <p class="text-sm text-gray-600">Missing Files</p>
                    </div>
                </div>
            </div>

            <!-- Footer with Monitoring Status -->
            <div class="flex justify-between items-center text-sm text-gray-500 pt-4 border-t">
                <div class="flex items-center space-x-3">
                    <div class="flex items-center space-x-2">
                        <div class="w-2 h-2 rounded-full" :class="monitoringEnabled ? 'bg-green-500' : 'bg-red-500'"></div>
                        <span>{{ monitoringEnabled ? 'Monitoring Active' : 'Monitoring Inactive' }}</span>
                    </div>
                    <span v-if="monitoringEnabled && lastScan" class="text-gray-400">
                        Last scan: {{ formatLastScan(lastScan) }}
                    </span>
                </div>
                <div>
                    Last updated: {{ lastUpdated }}
                </div>
            </div>
        </div>
    `,
    
    data() {
        return {
            operationInProgress: false,
            operationType: '',
            monitoringEnabled: false,
            lastScan: null,
            monitoringPollInterval: null
        };
    },
    
    computed: {
        stats() {
            return this.$root.stats;
        },
        cleanupTotal() {
            if (!this.stats.cleanup) return 0;
            return (this.stats.cleanup.duplicates || 0) + 
                   (this.stats.cleanup.bad_files || 0) + 
                   (this.stats.cleanup.missing_files || 0);
        },
        lastUpdated() {
            if (!this.stats.last_updated) return 'Never';
            const date = new Date(this.stats.last_updated);
            return date.toLocaleString();
        }
    },
    
    methods: {
        async checkOperationStatus() {
            try {
                const response = await fetch('/api/operations/current');
                const data = await response.json();
                this.operationInProgress = data.current_operation !== null;
                this.operationType = data.current_operation || '';
            } catch (error) {
                console.error('Error checking operation status:', error);
            }
        },
        
        async checkMonitoringStatus() {
            try {
                const response = await fetch('/api/monitoring/status');
                const data = await response.json();
                this.monitoringEnabled = data.enabled || false;
                this.lastScan = data.last_scan || null;
            } catch (error) {
                console.error('Error checking monitoring status:', error);
            }
        },
        
        formatLastScan(timestamp) {
            if (!timestamp) return 'Never';
            const date = new Date(timestamp);
            const now = new Date();
            const diff = now - date;
            const minutes = Math.floor(diff / 60000);
            
            if (minutes < 1) return 'Just now';
            if (minutes < 60) return `${minutes}m ago`;
            const hours = Math.floor(minutes / 60);
            if (hours < 24) return `${hours}h ago`;
            const days = Math.floor(hours / 24);
            return `${days}d ago`;
        },
        
        goToOperations() {
            this.$root.changeTab('operations');
        },
        
        goToImagingSessions() {
            this.$root.changeTab('imaging-sessions');
        },
        
        goToProcessingSessions() {
            this.$root.changeTab('processing-sessions');
        }
    },
    
    mounted() {
        this.checkOperationStatus();
        this.checkMonitoringStatus();
        
        this.statusInterval = setInterval(() => {
            this.checkOperationStatus();
        }, 5000);
        
        this.monitoringPollInterval = setInterval(() => {
            this.checkMonitoringStatus();
        }, 10000);
    },
    
    beforeUnmount() {
        if (this.statusInterval) {
            clearInterval(this.statusInterval);
        }
        if (this.monitoringPollInterval) {
            clearInterval(this.monitoringPollInterval);
        }
    }
};

window.DashboardTab = DashboardTab;