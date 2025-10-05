// Imaging Session Detail Modal Component - Enhanced
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
                <div class="flex-1 overflow-y-auto p-6" style="max-height: calc(90vh - 200px);">
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
                                    <p class="text-xs text-gray-600 uppercase tracking-wide">Camera</p>
                                    <p class="text-lg font-semibold text-gray-900">{{ sessionDetails.session.camera || 'N/A' }}</p>
                                </div>
                                <div>
                                    <p class="text-xs text-gray-600 uppercase tracking-wide">Telescope</p>
                                    <p class="text-lg font-semibold text-gray-900">{{ sessionDetails.session.telescope || 'N/A' }}</p>
                                </div>
                            </div>

                            <!-- Statistics Cards -->
                            <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4">
                                <div class="bg-white rounded-lg p-3 text-center shadow-sm">
                                    <div class="text-2xl font-bold text-blue-600">{{ sessionDetails.summary.total_files }}</div>
                                    <div class="text-xs text-gray-600">Total Files</div>
                                </div>
                                <div class="bg-white rounded-lg p-3 text-center shadow-sm">
                                    <div class="text-2xl font-bold text-blue-500">{{ sessionDetails.summary.frame_types['LIGHT'] || 0 }}</div>
                                    <div class="text-xs text-gray-600">Light Frames</div>
                                </div>
                                <div class="bg-white rounded-lg p-3 text-center shadow-sm">
                                    <div class="text-2xl font-bold text-gray-600">{{ sessionDetails.summary.frame_types['DARK'] || 0 }}</div>
                                    <div class="text-xs text-gray-600">Dark Frames</div>
                                </div>
                                <div class="bg-white rounded-lg p-3 text-center shadow-sm">
                                    <div class="text-2xl font-bold text-yellow-600">{{ sessionDetails.summary.frame_types['FLAT'] || 0 }}</div>
                                    <div class="text-xs text-gray-600">Flat Frames</div>
                                </div>
                                <div class="bg-white rounded-lg p-3 text-center shadow-sm">
                                    <div class="text-2xl font-bold text-purple-600">{{ sessionDetails.summary.frame_types['BIAS'] || 0 }}</div>
                                    <div class="text-xs text-gray-600">Bias Frames</div>
                                </div>
                            </div>

                            <!-- Total Imaging Time -->
                            <div class="mt-4 bg-white rounded-lg p-3 flex items-center justify-between shadow-sm">
                                <span class="text-sm font-medium text-gray-700">Total Imaging Time:</span>
                                <span class="text-xl font-bold text-indigo-600">{{ getTotalImagingTime() }}</span>
                            </div>
                        </div>

                        <!-- Objects Section -->
                        <div v-for="obj in sessionDetails.objects" :key="obj.name" class="bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm">
                            <div class="bg-gradient-to-r from-gray-50 to-gray-100 px-6 py-4 border-b border-gray-200">
                                <div class="flex justify-between items-center">
                                    <h4 class="text-lg font-bold text-gray-900">📷 {{ obj.name }}</h4>
                                    <div class="flex space-x-2">
                                        <button @click="addObjectToNewSession(obj)" 
                                                class="px-3 py-1 bg-green-500 hover:bg-green-600 text-white text-sm rounded transition">
                                            ➕ New Session
                                        </button>
                                        <button @click="addObjectToExistingSession(obj)" 
                                                class="px-3 py-1 bg-blue-500 hover:bg-blue-600 text-white text-sm rounded transition">
                                            📋 Add to Existing
                                        </button>
                                    </div>
                                </div>
                            </div>

                            <div class="p-6">
                                <!-- Filters Breakdown -->
                                <div class="space-y-4">
                                    <div v-for="filter in obj.filters" :key="filter.filter" 
                                         class="bg-gray-50 rounded-lg p-4 border border-gray-200">
                                        <div class="flex justify-between items-start mb-3">
                                            <div>
                                                <span class="inline-block px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-semibold">
                                                    {{ filter.filter }}
                                                </span>
                                            </div>
                                            <div class="text-right">
                                                <div class="text-2xl font-bold text-blue-600">{{ formatExposureTime(filter.total_exposure) }}</div>
                                                <div class="text-xs text-gray-500">Total Exposure</div>
                                            </div>
                                        </div>

                                        <!-- Exposure Breakdown -->
                                        <div class="mt-3 space-y-2">
                                            <div class="text-xs font-medium text-gray-600 uppercase">Exposure Breakdown:</div>
                                            <div class="grid grid-cols-2 md:grid-cols-3 gap-2">
                                                <div v-for="exp in filter.exposure_breakdown" :key="exp.exposure" 
                                                     class="bg-white rounded px-3 py-2 text-sm border border-gray-200">
                                                    <span class="font-bold text-gray-900">{{ exp.count }}×</span>
                                                    <span class="text-gray-600">{{ exp.exposure }}s</span>
                                                    <span class="text-gray-400 text-xs ml-1">({{ formatExposureTime(exp.total) }})</span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <!-- Total Files for Object -->
                                <div class="pt-4 mt-4 border-t border-gray-200">
                                    <div class="flex justify-between items-center">
                                        <span class="text-sm font-medium text-gray-700">Total Light Frames:</span>
                                        <span class="text-lg font-bold text-gray-900">{{ obj.total_files }}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Modal Footer with Navigation -->
                <div class="bg-gray-50 p-4 border-t border-gray-200">
                    <div class="flex justify-between items-center">
                        <!-- Navigation Buttons -->
                        <div class="flex space-x-2">
                            <button @click="navigateToPrevSession" 
                                    :disabled="!hasPreviousSession"
                                    :class="hasPreviousSession ? 'btn btn-blue' : 'btn btn-gray cursor-not-allowed'"
                                    class="text-sm">
                                ← Previous Session
                            </button>
                            <button @click="navigateToNextSession" 
                                    :disabled="!hasNextSession"
                                    :class="hasNextSession ? 'btn btn-blue' : 'btn btn-gray cursor-not-allowed'"
                                    class="text-sm">
                                Next Session →
                            </button>
                        </div>

                        <!-- Action Buttons -->
                        <div class="flex space-x-3">
                            <button @click="openMarkdownEditor" class="btn btn-green text-sm">
                                📝 Edit Notes
                            </button>
                            <button @click="viewSessionFiles" class="btn btn-blue text-sm">
                                View All Files
                            </button>
                            <button @click="closeSessionDetails" class="btn btn-gray text-sm">Close</button>
                        </div>
                    </div>
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
            selectedSessionId: null,
            allSessionIds: [],  // List of all session IDs for navigation
            currentSessionIndex: -1
        };
    },
    
    computed: {
        hasPreviousSession() {
            return this.currentSessionIndex > 0;
        },
        hasNextSession() {
            return this.currentSessionIndex < this.allSessionIds.length - 1;
        }
    },
    
    methods: {
        async viewSessionDetails(sessionId, allSessionIds = []) {
            this.showDetailModal = true;
            this.loadingDetails = true;
            this.detailsError = null;
            this.sessionDetails = null;
            this.selectedSessionId = sessionId;
            this.allSessionIds = allSessionIds;
            this.currentSessionIndex = allSessionIds.indexOf(sessionId);
            
            try {
                const response = await fetch(`/api/imaging-sessions/${sessionId}/details`);
                
                if (!response.ok) {
                    throw new Error(`Failed to load session details: ${response.statusText}`);
                }
                
                this.sessionDetails = await response.json();
            } catch (error) {
                console.error('Error loading session details:', error);
                this.detailsError = error.message || 'Failed to load session details';
            } finally {
                this.loadingDetails = false;
            }
        },
        
        closeSessionDetails() {
            this.showDetailModal = false;
            this.sessionDetails = null;
            this.selectedSessionId = null;
        },
        
        openMarkdownEditor() {
            if (this.selectedSessionId) {
                window.open(`/imaging-editor?session_id=${this.selectedSessionId}&session_name=${encodeURIComponent(this.selectedSessionId)}`, '_blank');
            }
        },
        
        viewSessionFiles() {
            if (this.selectedSessionId) {
                this.closeSessionDetails();
                this.$root.activeTab = 'files';
                this.$root.searchFilters.session_id = this.selectedSessionId;
                this.$root.loadFiles();
            }
        },
        
        // Navigation methods
        async navigateToPrevSession() {
            if (this.hasPreviousSession) {
                const prevSessionId = this.allSessionIds[this.currentSessionIndex - 1];
                await this.viewSessionDetails(prevSessionId, this.allSessionIds);
            }
        },
        
        async navigateToNextSession() {
            if (this.hasNextSession) {
                const nextSessionId = this.allSessionIds[this.currentSessionIndex + 1];
                await this.viewSessionDetails(nextSessionId, this.allSessionIds);
            }
        },
        
        // Add to processing session methods
        async addObjectToNewSession(obj) {
            // Get all file IDs for this object in this session
            const fileIds = await this.getObjectFileIds(obj.name);
            if (fileIds.length === 0) {
                alert('No files found for this object');
                return;
            }
            
            // Call the root app's method to show create modal with pre-filled data
            this.$root.addToNewSession();
            // Wait for modal to initialize then set the selected files
            this.$nextTick(() => {
                if (this.$root.$refs.processingModals) {
                    this.$root.$refs.processingModals.preSelectFiles(fileIds, obj.name);
                }
            });
        },
        
        async addObjectToExistingSession(obj) {
            // Get all file IDs for this object in this session
            const fileIds = await this.getObjectFileIds(obj.name);
            if (fileIds.length === 0) {
                alert('No files found for this object');
                return;
            }
            
            // Call the root app's method to show add to existing modal
            await this.$root.showAddToExistingModal();
            // Wait for modal to initialize then set the selected files
            this.$nextTick(() => {
                if (this.$root.$refs.processingModals) {
                    this.$root.$refs.processingModals.preSelectFiles(fileIds, obj.name);
                }
            });
        },
        
        async getObjectFileIds(objectName) {
            try {
                const params = new URLSearchParams({
                    session_id: this.selectedSessionId,
                    objects: objectName,
                    frame_types: 'LIGHT'
                });
                
                const response = await fetch(`/api/files/ids?${params}`);
                if (response.ok) {
                    const data = await response.json();
                    return data.file_ids || [];
                }
            } catch (error) {
                console.error('Error fetching object file IDs:', error);
            }
            return [];
        },
        
        // Utility methods
        getTotalImagingTime() {
            if (!this.sessionDetails || !this.sessionDetails.summary) return '0h 0m';
            
            const totalSeconds = this.sessionDetails.summary.total_exposure || 0;
            return this.formatExposureTime(totalSeconds);
        },
        
        formatExposureTime(seconds) {
            if (!seconds) return '0m';
            
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            
            if (hours > 0) {
                return `${hours}h ${minutes}m`;
            }
            return `${minutes}m`;
        }
    }
};