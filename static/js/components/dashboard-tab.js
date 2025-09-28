/**
 * Dashboard Tab Component - Enhanced with Quarantine and Staging Stats
 * Save as: static/js/components/dashboard-tab.js
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

            <!-- File Location Stats -->
            <div class="bg-white rounded-lg shadow-md p-6">
                <h2 class="text-xl font-bold text-gray-800 mb-4">File Locations</h2>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
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
                    <div class="border-l-4 border-gray-500 pl-4">
                        <h3 class="text-sm font-semibold text-gray-600 mb-1">Missing Files</h3>
                        <p class="text-2xl font-bold text-gray-600">{{ stats.missing_files || 0 }}</p>
                        <p class="text-xs text-gray-500 mt-1">Files not found on disk</p>
                        <button 
                            v-if="stats.missing_files > 0"
                            @click="removeMissingFiles"
                            class="mt-2 text-xs px-3 py-1 bg-red-500 text-white rounded hover:bg-red-600"
                        >
                            Remove from DB
                        </button>
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
                    <div class="text-center p-4 bg-yellow-50 rounded-lg">
                        <p class="text-sm font-semibold text-gray-600 mb-1">FLAT</p>
                        <p class="text-2xl font-bold text-yellow-600">{{ (stats.by_frame_type && stats.by_frame_type.FLAT) || 0 }}</p>
                    </div>
                    <div class="text-center p-4 bg-purple-50 rounded-lg">
                        <p class="text-sm font-semibold text-gray-600 mb-1">BIAS</p>
                        <p class="text-2xl font-bold text-purple-600">{{ (stats.by_frame_type && stats.by_frame_type.BIAS) || 0 }}</p>
                    </div>
                </div>
            </div>

            <!-- Operation Status Alert -->
            <div v-if="operationInProgress" class="bg-yellow-50 border-l-4 border-yellow-400 p-4">
                <div class="flex items-center">
                    <div class="flex-shrink-0">
                        <svg class="h-5 w-5 text-yellow-400 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                    </div>
                    <div class="ml-3">
                        <p class="text-sm text-yellow-700">
                            <strong>{{ operationType }}</strong> operation in progress. Other operations are blocked until complete.
                        </p>
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
                this.operationInProgress = data.operation_in_progress;
                this.operationType = data.operation_type || '';
            } catch (error) {
                console.error('Error checking operation status:', error);
            }
        },
        
        async removeMissingFiles() {
            if (!confirm(`Remove ${this.stats.missing_files} missing file records from database? This cannot be undone.`)) {
                return;
            }
            
            try {
                const response = await fetch('/api/operations/remove-missing?dry_run=false', {
                    method: 'DELETE'
                });
                
                if (response.ok) {
                    const result = await response.json();
                    alert(`Removed ${result.stats.removed} missing file records`);
                    // Refresh stats - use the global function for consistency
                    await window.refreshStats();
                } else {
                    const error = await response.json();
                    alert(`Error: ${error.detail}`);
                }
            } catch (error) {
                console.error('Error removing missing files:', error);
                alert('Failed to remove missing files');
            }
        }
    },
    
    mounted() {
        // Check operation status on mount
        this.checkOperationStatus();
        
        // Check every 5 seconds for operation status
        this.statusInterval = setInterval(() => {
            this.checkOperationStatus();
        }, 5000);

        // Listen for custom events if needed
        window.addEventListener('stats-updated', () => {
            // Stats will auto-update from parent
        });
    },
    
    beforeUnmount() {
        if (this.statusInterval) {
            clearInterval(this.statusInterval);
        }
    }
};

window.DashboardTab = DashboardTab;