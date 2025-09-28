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
                        <button @click="$root.resetImagingSessionFilters" class="btn btn-red">Reset Filters</button>
                        <button @click="$root.loadImagingSessions" class="btn btn-blue">Apply Filters</button>
                    </div>
                </div>
                
                <!-- Session Filters -->
                <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4">
                    <div>
                        <label class="block text-xs font-medium text-gray-700 mb-1">Date Range</label>
                        <div class="space-y-1">
                            <input v-model="imagingSessionFilters.date_start" type="date" placeholder="Start date" class="filter-input" @change="$root.loadImagingSessions">
                            <input v-model="imagingSessionFilters.date_end" type="date" placeholder="End date" class="filter-input" @change="$root.loadImagingSessions">
                        </div>
                    </div>
                    
                    <div>
                        <label class="block text-xs font-medium text-gray-700 mb-1">Camera</label>
                        <div class="relative">
                            <button @click.stop="$root.toggleImagingSessionFilter('cameras')" class="filter-button">
                                <span>{{ getImagingSessionFilterText('cameras') }}</span>
                                <span class="text-gray-400">▼</span>
                            </button>
                            <div v-show="activeImagingSessionFilter === 'cameras'" class="filter-dropdown">
                                <div class="p-2">
                                    <label v-for="camera in filterOptions.cameras" :key="camera" class="block">
                                        <input type="checkbox" :value="camera" v-model="imagingSessionFilters.cameras" @change="$root.loadImagingSessions" class="mr-2">
                                        {{ camera }}
                                    </label>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div>
                        <label class="block text-xs font-medium text-gray-700 mb-1">Telescope</label>
                        <div class="relative">
                            <button @click.stop="$root.toggleImagingSessionFilter('telescopes')" class="filter-button">
                                <span>{{ getImagingSessionFilterText('telescopes') }}</span>
                                <span class="text-gray-400">▼</span>
                            </button>
                            <div v-show="activeImagingSessionFilter === 'telescopes'" class="filter-dropdown">
                                <div class="p-2">
                                    <label v-for="telescope in filterOptions.telescopes" :key="telescope" class="block">
                                        <input type="checkbox" :value="telescope" v-model="imagingSessionFilters.telescopes" @change="$root.loadImagingSessions" class="mr-2">
                                        {{ telescope }}
                                    </label>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div v-if="hasActiveImagingSessionFilters" class="flex items-end">
                        <div class="filter-tag-container">
                            <div class="text-xs text-gray-600 mb-1">Active Filters</div>
                            <div @click="$root.clearImagingSessionFilters" class="text-blue-600">Filtered results</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Sessions List -->
            <div class="bg-white rounded-lg shadow">
                <div class="p-6">
                    <div v-if="imagingSessions.length === 0" class="text-center py-8 text-gray-500">
                        <div class="text-6xl mb-4">📅</div>
                        <p class="text-lg">No imaging sessions found</p>
                        <p class="text-sm">Import or scan your FITS files to see sessions</p>
                    </div>
                    <div v-else class="space-y-4">
                        <div v-for="session in imagingSessions" :key="session.session_id" 
                            class="bg-white rounded-lg shadow hover:shadow-md transition-shadow p-4">
                            <div class="flex justify-between items-start">
                                <!-- Session Info (clickable) -->
                                <div @click="$root.viewSessionDetails(session.session_id)" class="flex-1 cursor-pointer">
                                    <h3 class="font-semibold text-lg">{{ session.session_date }}</h3>
                                    <p class="text-gray-600">{{ session.camera }} + {{ session.telescope }}</p>
                                    <p class="text-sm text-gray-500">{{ session.file_count }} files</p>
                                    <p class="text-sm text-gray-500" v-if="session.site_name">{{ session.site_name }}</p>
                                    <p class="text-xs text-gray-500 font-mono">{{ session.session_id }}</p>
                                    <p class="text-xs text-gray-500" v-if="session.observer">{{ session.observer }}</p>
                                    <div v-if="session.notes" class="mt-2 text-sm text-gray-700">
                                        {{ session.notes }}
                                    </div>
                                </div>
                                
                                <!-- Action Buttons -->
                                <div class="flex flex-col space-y-2 ml-4">
                                    <button @click="openImagingSessionEditor(session.session_id, session.session_date, session.telescope, $event)" class="btn btn-green text-sm">
                                        📝 Edit Notes
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Sessions Pagination -->
                <div v-if="imagingSessions.length > 0" class="pagination-container">
                    <div class="flex items-center justify-between">
                        <div class="text-sm text-gray-700">
                            Showing {{ (imagingSessionPagination.page - 1) * imagingSessionPagination.limit + 1 }} to 
                            {{ Math.min(imagingSessionPagination.page * imagingSessionPagination.limit, imagingSessionPagination.total) }} 
                            of {{ imagingSessionPagination.total }} sessions
                        </div>
                        <div class="flex space-x-2">
                            <button @click="$root.prevImagingSessionPage" :disabled="imagingSessionPagination.page <= 1" class="pagination-button">
                                Previous
                            </button>
                            <span class="px-3 py-1 text-sm text-gray-700">
                                Page {{ imagingSessionPagination.page }} of {{ imagingSessionPagination.pages }}
                            </span>
                            <button @click="$root.nextImagingSessionPage" :disabled="imagingSessionPagination.page >= imagingSessionPagination.pages" class="pagination-button">
                                Next
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    methods: {
        ...ImagingSessionsComponent.methods,
        
        openImagingSessionEditor(sessionId, sessionDate, telescope, event) {
            event.stopPropagation(); // Prevent detail modal from opening
            const sessionName = `${sessionDate} - ${telescope || 'Unknown'}`;
            const url = `/imaging-editor?session_id=${sessionId}&session_name=${encodeURIComponent(sessionName)}`;
            window.open(url, '_blank');
        }
    },
    
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