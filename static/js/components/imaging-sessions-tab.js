/**
 * Imaging Sessions Tab Component
 */

const ImagingSessionsTab = {
    template: `
        <div class="space-y-6">
            <!-- Session Controls -->
            <div class="bg-white rounded-lg shadow p-4">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-xl font-bold">Imaging Sessions</h2>
                    <div class="flex space-x-4 items-center">
                        <button @click="resetImagingSessionFilters" class="btn btn-red">Reset Filters</button>
                        <button @click="loadImagingSessions" class="btn btn-blue">Refresh</button>
                    </div>
                </div>
                
                <!-- Session Filters -->
                <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
                    <div>
                        <label class="block text-xs font-medium text-gray-700 mb-1">Date Range</label>
                        <div class="space-y-1">
                            <input v-model="imagingSessionFilters.date_start" type="date" placeholder="Start date" class="filter-input">
                            <input v-model="imagingSessionFilters.date_end" type="date" placeholder="End date" class="filter-input">
                        </div>
                    </div>
                    
                    <div>
                        <label class="block text-xs font-medium text-gray-700 mb-1">Camera</label>
                        <div class="relative">
                            <button @click="toggleImagingSessionFilter('cameras')" class="filter-button">
                                <span>{{ getImagingSessionFilterText('cameras') }}</span>
                                <span class="text-gray-400">▼</span>
                            </button>
                            <div v-show="activeImagingSessionFilter === 'cameras'" class="filter-dropdown">
                                <div class="p-2">
                                    <label v-for="option in filterOptions.cameras" :key="option" class="filter-option">
                                        <input type="checkbox" :checked="imagingSessionFilters.cameras.includes(option)" @change="toggleImagingSessionFilterOption('cameras', option)">
                                        <span>{{ option }}</span>
                                    </label>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div>
                        <label class="block text-xs font-medium text-gray-700 mb-1">Telescope</label>
                        <div class="relative">
                            <button @click="toggleImagingSessionFilter('telescopes')" class="filter-button">
                                <span>{{ getImagingSessionFilterText('telescopes') }}</span>
                                <span class="text-gray-400">▼</span>
                            </button>
                            <div v-show="activeImagingSessionFilter === 'telescopes'" class="filter-dropdown">
                                <div class="p-2">
                                    <label v-for="option in filterOptions.telescopes" :key="option" class="filter-option">
                                        <input type="checkbox" :checked="imagingSessionFilters.telescopes.includes(option)" @change="toggleImagingSessionFilterOption('telescopes', option)">
                                        <span>{{ option }}</span>
                                    </label>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="flex items-end">
                        <div class="text-sm text-gray-600">
                            <div>Total: {{ imagingSessionPagination.total }} sessions</div>
                            <div v-if="hasActiveImagingSessionFilters" class="text-blue-600">Filtered results</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Sessions List -->
            <div class="bg-white rounded-lg shadow">
                <div class="p-6">
                    <div class="space-y-4">
                        <div v-for="session in imagingSessions" :key="session.session_id" 
                            @click="$root.viewSessionDetails(session.session_id)"
                            class="bg-white rounded-lg shadow hover:shadow-md transition-shadow p-4 cursor-pointer">
                            <div class="flex justify-between items-start">
                                <div>
                                    <h3 class="font-semibold text-lg">{{ session.session_date }}</h3>
                                    <p class="text-gray-600">{{ session.camera }} + {{ session.telescope }}</p>
                                    <p class="text-sm text-gray-500">{{ session.file_count }} files</p>
                                    <p class="text-sm text-gray-500" v-if="session.site_name">{{ session.site_name }}</p>
                                </div>
                                <div class="text-right">
                                    <p class="text-xs text-gray-500 font-mono">{{ session.session_id }}</p>
                                    <p class="text-xs text-gray-500" v-if="session.observer">{{ session.observer }}</p>
                                </div>
                            </div>
                            <div v-if="session.notes" class="mt-2 text-sm text-gray-700">
                                {{ session.notes }}
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Sessions Pagination -->
                <div class="pagination-container">
                    <div class="flex items-center justify-between">
                        <div class="text-sm text-gray-700">
                            Showing {{ (imagingSessionPagination.page - 1) * imagingSessionPagination.limit + 1 }} to 
                            {{ Math.min(imagingSessionPagination.page * imagingSessionPagination.limit, imagingSessionPagination.total) }} 
                            of {{ imagingSessionPagination.total }} sessions
                        </div>
                        <div class="flex space-x-2">
                            <button @click="prevImagingSessionPage" :disabled="imagingSessionPagination.page <= 1" class="pagination-button">
                                Previous
                            </button>
                            <span class="px-3 py-1 text-sm text-gray-700">
                                Page {{ imagingSessionPagination.page }} of {{ imagingSessionPagination.pages }}
                            </span>
                            <button @click="nextImagingSessionPage" :disabled="imagingSessionPagination.page >= imagingSessionPagination.pages" class="pagination-button">
                                Next
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    methods: ImagingSessionsComponent.methods,
    
    computed: {
        imagingSessions() { return this.$root.imagingSessions; },
        imagingSessionPagination() { return this.$root.imagingSessionPagination; },
        imagingSessionFilters() { return this.$root.imagingSessionFilters; },
        activeImagingSessionFilter: {
            get() { return this.$root.activeImagingSessionFilter; },
            set(val) { this.$root.activeImagingSessionFilter = val; }
        },
        filterOptions() { return this.$root.filterOptions; },
        getImagingSessionFilterText() {
            return (filterType) => {
                const selected = this.imagingSessionFilters[filterType];
                if (!selected || selected.length === 0) {
                    return filterType === 'cameras' ? 'All Cameras' : 'All Telescopes';
                }
                if (selected.length === 1) return selected[0];
                return `${selected.length} selected`;
            };
        },
        hasActiveImagingSessionFilters() {
            return this.imagingSessionFilters.date_start !== '' ||
                   this.imagingSessionFilters.date_end !== '' ||
                   this.imagingSessionFilters.cameras.length > 0 ||
                   this.imagingSessionFilters.telescopes.length > 0;
        }
    }
};

window.ImagingSessionsTab = ImagingSessionsTab;