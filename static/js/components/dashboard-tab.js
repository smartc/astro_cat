/**
 * Dashboard Tab Component
 * Save as: static/js/components/dashboard-tab.js
 */

const DashboardTab = {
    template: `
        <div class="space-y-6">
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
        </div>
    `,
    
    computed: {
        stats() {
            return this.$root.stats;
        }
    }
};

window.DashboardTab = DashboardTab;