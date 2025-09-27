// Imaging Session Detail Modal Component
// Full modal with inline template

window.ImagingSessionDetailModal = {
    template: `
        <div v-if="showDetailModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div class="bg-white rounded-lg w-full max-w-6xl max-h-[90vh] overflow-hidden flex flex-col">
                <!-- Modal Header -->
                <div class="bg-blue-600 text-white p-4 flex justify-between items-center">
                    <h2 class="text-xl font-bold">Imaging Session Details</h2>
                    <button @click="closeSessionDetails" class="text-white hover:text-gray-200">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                        </svg>
                    </button>
                </div>

                <!-- Modal Body -->
                <div class="flex-1 overflow-y-auto p-6" style="max-height: calc(90vh - 140px);">
                    <!-- Loading State -->
                    <div v-if="loadingDetails" class="flex justify-center items-center py-12">
                        <div class="spinner"></div>
                        <span class="ml-3 text-gray-600">Loading session details...</span>
                    </div>

                    <!-- Error State -->
                    <div v-else-if="detailsError" class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
                        <strong>Error:</strong> {{ detailsError }}
                    </div>

                    <!-- Session Details Content -->
                    <div v-else-if="sessionDetails" class="space-y-6">
                        <!-- Session-Level Summary -->
                        <div class="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-6 border border-blue-200">
                            <h3 class="text-xl font-bold text-blue-900 mb-4">Session Summary</h3>
                            
                            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
                                <div>
                                    <p class="text-xs text-gray-600 uppercase tracking-wide">Date</p>
                                    <p class="text-lg font-semibold text-gray-900">{{ sessionDetails.session.session_date }}</p>
                                </div>
                                <div>
                                    <p class="text-xs text-gray-600 uppercase tracking-wide">Telescope</p>
                                    <p class="text-lg font-semibold text-gray-900">{{ sessionDetails.session.telescope || 'N/A' }}</p>
                                </div>
                                <div>
                                    <p class="text-xs text-gray-600 uppercase tracking-wide">Camera</p>
                                    <p class="text-lg font-semibold text-gray-900">{{ sessionDetails.session.camera || 'N/A' }}</p>
                                </div>
                                <div v-if="sessionDetails.session.observer">
                                    <p class="text-xs text-gray-600 uppercase tracking-wide">Observer</p>
                                    <p class="text-lg font-semibold text-gray-900">{{ sessionDetails.session.observer }}</p>
                                </div>
                                <div v-if="sessionDetails.session.site_name">
                                    <p class="text-xs text-gray-600 uppercase tracking-wide">Site</p>
                                    <p class="text-lg font-semibold text-gray-900">{{ sessionDetails.session.site_name }}</p>
                                </div>
                                <div v-if="sessionDetails.session.latitude && sessionDetails.session.longitude">
                                    <p class="text-xs text-gray-600 uppercase tracking-wide">Coordinates</p>
                                    <p class="text-sm font-mono text-gray-900">
                                        {{ formatCoordinates(sessionDetails.session.latitude, sessionDetails.session.longitude) }}
                                    </p>
                                </div>
                                <div v-if="sessionDetails.session.elevation">
                                    <p class="text-xs text-gray-600 uppercase tracking-wide">Elevation</p>
                                    <p class="text-lg font-semibold text-gray-900">{{ formatElevation(sessionDetails.session.elevation) }}</p>
                                </div>
                            </div>

                            <!-- Session Statistics -->
                            <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4">
                                <div class="bg-white rounded-lg p-3 text-center shadow-sm">
                                    <div class="text-2xl font-bold text-blue-600">{{ sessionDetails.summary.total_files }}</div>
                                    <div class="text-xs text-gray-600">Total Files</div>
                                </div>
                                <div class="bg-white rounded-lg p-3 text-center shadow-sm">
                                    <div class="text-2xl font-bold text-blue-500">
                                        {{ sessionDetails.summary.frame_types['LIGHT'] || 0 }}
                                    </div>
                                    <div class="text-xs text-gray-600">Light Frames</div>
                                </div>
                                <div class="bg-white rounded-lg p-3 text-center shadow-sm">
                                    <div class="text-2xl font-bold text-gray-600">
                                        {{ sessionDetails.summary.frame_types['DARK'] || 0 }}
                                    </div>
                                    <div class="text-xs text-gray-600">Dark Frames</div>
                                </div>
                                <div class="bg-white rounded-lg p-3 text-center shadow-sm">
                                    <div class="text-2xl font-bold text-yellow-600">
                                        {{ sessionDetails.summary.frame_types['FLAT'] || 0 }}
                                    </div>
                                    <div class="text-xs text-gray-600">Flat Frames</div>
                                </div>
                                <div class="bg-white rounded-lg p-3 text-center shadow-sm">
                                    <div class="text-2xl font-bold text-purple-600">
                                        {{ sessionDetails.summary.frame_types['BIAS'] || 0 }}
                                    </div>
                                    <div class="text-xs text-gray-600">Bias Frames</div>
                                </div>
                            </div>

                            <!-- Total Imaging Time -->
                            <div class="mt-4 bg-white rounded-lg p-3 flex items-center justify-between shadow-sm">
                                <span class="text-sm font-medium text-gray-700">Total Imaging Time:</span>
                                <span class="text-xl font-bold text-indigo-600">{{ getTotalImagingTime() }}</span>
                            </div>

                            <!-- Session ID -->
                            <div class="mt-4 text-xs text-gray-500">
                                <strong>Session ID:</strong> 
                                <code class="bg-white px-2 py-1 rounded font-mono">{{ sessionDetails.session.session_id }}</code>
                            </div>
                        </div>

                        <!-- Object-Level Details -->
                        <div class="space-y-4">
                            <h3 class="text-xl font-bold text-gray-900 flex items-center">
                                <svg class="w-6 h-6 mr-2 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                                          d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01"/>
                                </svg>
                                Objects in Session
                            </h3>

                            <!-- Object Cards -->
                            <div v-for="obj in sessionDetails.summary.objects" :key="obj.name" 
                                 class="bg-white rounded-lg border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
                                <div class="bg-gradient-to-r from-gray-50 to-gray-100 p-4 border-b border-gray-200">
                                    <h4 class="text-lg font-bold text-gray-900">{{ obj.name }}</h4>
                                </div>
                                
                                <div class="p-4 space-y-4">
                                    <!-- Frame Type Breakdown -->
                                    <div>
                                        <p class="text-sm font-semibold text-gray-700 mb-2">Frame Types:</p>
                                        <div class="grid grid-cols-2 md:grid-cols-4 gap-2">
                                            <div v-for="(count, frameType) in obj.frame_types" :key="frameType"
                                                 class="px-3 py-2 rounded text-center"
                                                 :class="getFrameTypeClass(frameType)">
                                                <div class="font-bold">{{ count }}</div>
                                                <div class="text-xs">{{ frameType }}</div>
                                            </div>
                                        </div>
                                    </div>

                                    <!-- Filters Used -->
                                    <div v-if="Object.keys(obj.filters).length > 0">
                                        <p class="text-sm font-semibold text-gray-700 mb-2">Filters:</p>
                                        <div class="flex flex-wrap gap-2">
                                            <span v-for="(count, filter) in obj.filters" :key="filter"
                                                  class="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
                                                {{ filter }} ({{ count }})
                                            </span>
                                        </div>
                                    </div>

                                    <!-- Imaging Time by Filter -->
                                    <div v-if="Object.keys(obj.total_imaging_time).length > 0">
                                        <p class="text-sm font-semibold text-gray-700 mb-2">Imaging Time by Filter:</p>
                                        <div class="bg-gray-50 rounded-lg p-3 space-y-2">
                                            <div v-for="(timeData, filter) in obj.total_imaging_time" :key="filter"
                                                 class="flex justify-between items-center">
                                                <span class="text-sm text-gray-700">{{ filter }}:</span>
                                                <span class="font-mono font-semibold text-indigo-600">
                                                    {{ formatTimeCompact(timeData.seconds) }}
                                                </span>
                                            </div>
                                            <!-- Total row -->
                                            <div class="flex justify-between items-center pt-2 border-t border-gray-300">
                                                <span class="text-sm font-bold text-gray-900">Total:</span>
                                                <span class="font-mono font-bold text-indigo-700">
                                                    {{ getObjectTotalTime(obj) }}
                                                </span>
                                            </div>
                                        </div>
                                    </div>

                                    <!-- Total Files for Object -->
                                    <div class="pt-2 border-t border-gray-200">
                                        <div class="flex justify-between items-center">
                                            <span class="text-sm font-medium text-gray-700">Total Files:</span>
                                            <span class="text-lg font-bold text-gray-900">{{ obj.total_files }}</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Modal Footer -->
                <div class="bg-gray-50 p-4 border-t border-gray-200 flex justify-between items-center">
                    <button @click="viewSessionFiles" class="btn btn-blue">
                        <svg class="w-4 h-4 mr-2 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                        </svg>
                        View All Files
                    </button>
                    <button @click="closeSessionDetails" class="btn btn-gray">Close</button>
                </div>
            </div>
        </div>
    `,
    
    data() {
        return {
            showDetailModal: false,
            loadingDetails: false,
            detailsError: null,
            sessionDetails: null,
            selectedSessionId: null
        };
    },
    
    methods: {
        async viewSessionDetails(sessionId) {
            console.log('viewSessionDetails called with:', sessionId);
            console.log('Before setting modal:', this.showDetailModal);
            this.showDetailModal = true;
            console.log('After setting modal:', this.showDetailModal);
            this.loadingDetails = true;
            this.detailsError = null;
            this.sessionDetails = null;
            this.selectedSessionId = sessionId;
            
            try {
                console.log('Calling API...');
                const response = await ApiService.imagingSessions.getDetails(sessionId);
                console.log('API response:', response.data);
                this.sessionDetails = response.data;
            } catch (error) {
                console.error('Error loading session details:', error);
                this.detailsError = error.response?.data?.detail || error.message;
            } finally {
                this.loadingDetails = false;
            }
        },
        
        closeSessionDetails() {
            this.showDetailModal = false;
            this.sessionDetails = null;
            this.detailsError = null;
            this.selectedSessionId = null;
        },
        
        viewSessionFiles() {
            this.activeTab = 'files';
            this.searchFilters.session_id = this.selectedSessionId;
            this.closeSessionDetails();
            this.loadFiles();
        },
        
        getTotalImagingTime() {
            if (!this.sessionDetails?.summary?.objects) return '0h 0m';
            
            let totalSeconds = 0;
            this.sessionDetails.summary.objects.forEach(obj => {
                Object.values(obj.total_imaging_time || {}).forEach(timeData => {
                    totalSeconds += timeData.seconds || 0;
                });
            });
            
            const hours = Math.floor(totalSeconds / 3600);
            const minutes = Math.floor((totalSeconds % 3600) / 60);
            return `${hours}h ${minutes}m`;
        },
        
        getObjectTotalTime(obj) {
            let totalSeconds = 0;
            Object.values(obj.total_imaging_time || {}).forEach(timeData => {
                totalSeconds += timeData.seconds || 0;
            });
            
            const hours = Math.floor(totalSeconds / 3600);
            const minutes = Math.floor((totalSeconds % 3600) / 60);
            return `${hours}h ${minutes}m`;
        },
        
        formatTimeCompact(seconds) {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            if (hours > 0) {
                return `${hours}h ${minutes}m`;
            }
            return `${minutes}m`;
        },
        
        formatCoordinates(lat, lon) {
            const latDir = lat >= 0 ? 'N' : 'S';
            const lonDir = lon >= 0 ? 'E' : 'W';
            return `${Math.abs(lat).toFixed(2)}°${latDir}, ${Math.abs(lon).toFixed(2)}°${lonDir}`;
        },
        
        formatElevation(elevation) {
            return `${elevation}m`;
        }
    }
};