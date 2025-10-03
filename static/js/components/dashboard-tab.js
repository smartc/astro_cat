/**
 * Dashboard Tab Component - Enhanced with Cleanup Information
 */

const DashboardTab = {
    template: `
        <div class="space-y-6">
            <!-- Main Stats Grid -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <div class="stats-card">
                    <h3 class="text-lg font-semibold text-gray-700 mb-2">Total Files</h3>
                    <p class="text-3xl font-bold text-blue-600">{{ stats.total_files || 0 }}</p>
                </div>
                <div class="stats-card">
                    <h3 class="text-lg font-semibold text-gray-700 mb-2">Auto-Migrate Ready</h3>
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

            <!-- Cleanup Required Section - PROMINENT & CLICKABLE -->
            <div v-if="cleanupTotal > 0" 
                 @click="goToOperations"
                 class="bg-red-50 border-2 border-red-200 rounded-lg shadow-md p-6 cursor-pointer hover:bg-red-100 transition">
                <div class="flex items-center mb-4">
                    <svg class="w-6 h-6 text-red-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                    </svg>
                    <h2 class="text-xl font-bold text-red-800">Cleanup Required</h2>
                    <span class="ml-auto text-sm text-red-600">Click to manage →</span>
                </div>
                <p class="text-sm text-red-700 mb-4">{{ cleanupTotal }} file(s) need attention</p>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div class="bg-white rounded-lg p-4 border-l-4 border-orange-500">
                        <h3 class="text-sm font-semibold text-gray-600 mb-1">Duplicate Files</h3>
                        <p class="text-2xl font-bold text-orange-600">{{ (stats.cleanup && stats.cleanup.duplicates) || 0 }}</p>
                        <p class="text-xs text-gray-500 mt-1">In quarantine/Duplicates</p>
                    </div>
                    <div class="bg-white rounded-lg p-4 border-l-4 border-red-500">
                        <h3 class="text-sm font-semibold text-gray-600 mb-1">Bad Files</h3>
                        <p class="text-2xl font-bold text-red-600">{{ (stats.cleanup && stats.cleanup.bad_files) || 0 }}</p>
                        <p class="text-xs text-gray-500 mt-1">In quarantine/Bad</p>
                    </div>
                    <div class="bg-white rounded-lg p-4 border-l-4 border-gray-500">
                        <h3 class="text-sm font-semibold text-gray-600 mb-1">Missing Files</h3>
                        <p class="text-2xl font-bold text-gray-600">{{ (stats.cleanup && stats.cleanup.missing_files) || 0 }}</p>
                        <p class="text-xs text-gray-500 mt-1">DB records, files not found</p>
                    </div>
                </div>
            </div>

            <!-- File Location Stats -->
            <div class="bg-white rounded-lg shadow-md p-6">
                <h2 class="text-xl font-bold text-gray-800 mb-4">File Locations</h2>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="border-l-4 border-orange-500 pl-4">
                        <h3 class="text-sm font-semibold text-gray-600 mb-1">Quarantine</h3>
                        <p class="text-2xl font-bold text-orange-600">{{ stats.quarantine_files || 0 }}</p>
                        <p class="text-xs text-gray-500 mt-1">Files awaiting review</p>
                    </div>
                    <div class="border-l-4 border-purple-500 pl-4">
                        <h3 class="text-sm font-semibold text-gray-600 mb-1">Staged</h3>
                        <p class="text-2xl font-bold text-purple-600">{{ stats.staged_files || 0 }}</p>
                        <p class="text-xs text-gray-500 mt-1">In processing sessions</p>
                    </div>
                </div>
            </div>

            <!-- Processing Sessions -->
            <div class="bg-white rounded-lg shadow-md p-6">
                <h2 class="text-xl font-bold text-gray-800 mb-4">Processing Sessions</h2>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div class="border-l-4 border-indigo-500 pl-4">
                        <h3 class="text-sm font-semibold text-gray-600 mb-1">Total Sessions</h3>
                        <p class="text-2xl font-bold text-indigo-600">{{ (stats.processing_sessions && stats.processing_sessions.total) || 0 }}</p>
                    </div>
                    <div class="border-l-4 border-green-500 pl-4">
                        <h3 class="text-sm font-semibold text-gray-600 mb-1">Active Sessions</h3>
                        <p class="text-2xl font-bold text-green-600">{{ (stats.processing_sessions && stats.processing_sessions.active) || 0 }}</p>
                        <p class="text-xs text-gray-500 mt-1">Not started or in progress</p>
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

            <!-- Last Updated -->
            <div class="text-right text-sm text-gray-500">
                Last updated: {{ lastUpdated }}
            </div>
        </div>
    `,
    
    data() {
        return {
            operationInProgress: false,
            operationType: ''
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
        
        goToOperations() {
            // Switch to operations tab
            this.$root.activeTab = 'operations';
        }
    },
    
    mounted() {
        this.checkOperationStatus();
        
        this.statusInterval = setInterval(() => {
            this.checkOperationStatus();
        }, 5000);
    },
    
    beforeUnmount() {
        if (this.statusInterval) {
            clearInterval(this.statusInterval);
        }
    }
};

window.DashboardTab = DashboardTab;