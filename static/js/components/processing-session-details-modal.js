/**
 * Processing Session Details Modal Component
 */

const ProcessingSessionDetailsModal = {
    template: `
        <div v-if="showSessionDetailsModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 modal-backdrop">
            <div class="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto modal-content">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-lg font-bold">Processing Session Details</h3>
                    <button @click="closeSessionDetailsModal" class="text-gray-500 hover:text-gray-700">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>
                
                <!-- Loading State -->
                <div v-if="sessionDetailsLoading" class="text-center py-8">
                    <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                    <p class="mt-2 text-gray-600">Loading session details...</p>
                </div>
                
                <!-- Session Details -->
                <div v-else-if="currentSessionDetails" class="space-y-6">
                    <!-- Basic Information -->
                    <div class="bg-gray-50 p-4 rounded-lg">
                        <h4 class="font-semibold text-gray-800 mb-3">Session Information</h4>
                        <div class="grid grid-cols-2 gap-4 text-sm">
                            <div>
                                <strong>Name:</strong> {{ currentSessionDetails.name }}
                            </div>
                            <div>
                                <strong>Session ID:</strong> 
                                <span class="font-mono text-xs">{{ currentSessionDetails.id }}</span>
                            </div>
                            <div>
                                <strong>Status:</strong>
                                <span :class="getProcessingStatusClass(currentSessionDetails.status)" class="processing-status-badge ml-2">
                                    {{ formatProcessingStatus(currentSessionDetails.status) }}
                                </span>
                            </div>
                            <div>
                                <strong>Created:</strong> {{ formatDate(currentSessionDetails.created_at) }}
                            </div>
                            <div class="col-span-2">
                                <strong>Objects:</strong> {{ currentSessionDetails.objects.length > 0 ? currentSessionDetails.objects.join(', ') : 'None specified' }}
                            </div>
                            <div class="col-span-2" v-if="currentSessionDetails.folder_path">
                                <strong>Folder:</strong> 
                                <span class="font-mono text-xs bg-white px-2 py-1 rounded">{{ currentSessionDetails.folder_path }}</span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- File Summary -->
                    <div class="bg-blue-50 p-4 rounded-lg">
                        <h4 class="font-semibold text-blue-800 mb-3">File Summary</h4>
                        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                            <div class="bg-white p-3 rounded">
                                <div class="text-2xl font-bold text-blue-600">{{ currentSessionDetails.total_files }}</div>
                                <div class="text-xs text-gray-600">Total Files</div>
                            </div>
                            <div class="bg-white p-3 rounded">
                                <div class="text-2xl font-bold text-blue-500">{{ currentSessionDetails.lights }}</div>
                                <div class="text-xs text-gray-600">Light Frames</div>
                            </div>
                            <div class="bg-white p-3 rounded">
                                <div class="text-2xl font-bold text-gray-600">{{ currentSessionDetails.darks }}</div>
                                <div class="text-xs text-gray-600">Dark Frames</div>
                            </div>
                            <div class="bg-white p-3 rounded">
                                <div class="text-2xl font-bold text-yellow-600">{{ currentSessionDetails.flats }}</div>
                                <div class="text-xs text-gray-600">Flat Frames</div>
                            </div>
                            <div class="bg-white p-3 rounded">
                                <div class="text-2xl font-bold text-purple-600">{{ currentSessionDetails.bias }}</div>
                                <div class="text-xs text-gray-600">Bias Frames</div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Notes -->
                    <div v-if="currentSessionDetails.notes" class="bg-yellow-50 p-4 rounded-lg">
                        <h4 class="font-semibold text-yellow-800 mb-2">Notes</h4>
                        <p class="text-sm text-yellow-700 whitespace-pre-wrap">{{ currentSessionDetails.notes }}</p>
                    </div>
                    
                    <!-- Action Buttons -->
                    <div class="flex justify-between items-center pt-4 border-t">
                        <div class="text-sm text-gray-500">
                            Last updated: {{ formatDateTime(currentSessionDetails.created_at) }}
                        </div>
                        <div class="flex space-x-3">
                            <button @click="openMarkdownEditor" class="btn btn-blue text-sm">
                                📝 Edit Notes
                            </button>        
                            <button @click="findCalibrationFromDetails" class="btn btn-purple text-sm">
                                🔍 Find Calibration
                            </button>
                            <button @click="updateStatusFromDetails" class="btn btn-yellow text-sm">
                                Update Status
                            </button>
                            <button @click="closeSessionDetailsModal" class="btn btn-blue">
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    data() {
        return {
            showSessionDetailsModal: false,
            currentSessionDetails: null,
            sessionDetailsLoading: false
        };
    },
    
    methods: {
        async viewProcessingSession(sessionId) {
            try {
                this.sessionDetailsLoading = true;
                this.showSessionDetailsModal = true;
                
                const response = await ApiService.processingSessions.getById(sessionId);
                this.currentSessionDetails = response.data;
                
            } catch (error) {
                console.error('Error loading session details:', error);
                this.closeSessionDetailsModal();
                alert(`Failed to load session details: ${error.response?.data?.detail || error.message}`);
            } finally {
                this.sessionDetailsLoading = false;
            }
        },
        
        closeSessionDetailsModal() {
            this.showSessionDetailsModal = false;
            this.currentSessionDetails = null;
            this.sessionDetailsLoading = false;
        },
        
        findCalibrationFromDetails() {
            const app = this.$root;
            app.$refs.calibrationModal.findCalibrationFiles(this.currentSessionDetails.id);
            this.closeSessionDetailsModal();
        },
        
        async updateStatusFromDetails() {
            const app = this.$root;
            const sessionId = this.currentSessionDetails.id;
            await app.updateProcessingSessionStatus(sessionId);
            
            // Reload the session details to show updated status
            await this.viewProcessingSession(sessionId);
            
            // REFRESH STATS AFTER STATUS UPDATE
            await window.refreshStats();
        },
        
        getProcessingStatusClass(status) {
            const classes = {
                'not_started': 'bg-gray-100 text-gray-800',
                'in_progress': 'bg-blue-100 text-blue-800',
                'complete': 'bg-green-100 text-green-800'
            };
            return classes[status] || 'bg-gray-100 text-gray-800';
        },
        
        formatProcessingStatus(status) {
            const labels = {
                'not_started': 'Not Started',
                'in_progress': 'In Progress',
                'complete': 'Complete'
            };
            return labels[status] || status;
        },
        
        formatDate(dateString) {
            if (!dateString) return 'N/A';
            return new Date(dateString).toLocaleDateString();
        },
        
        formatDateTime(dateString) {
            if (!dateString) return 'N/A';
            return new Date(dateString).toLocaleString();
        },

        openMarkdownEditor() {
            const sessionId = this.currentSessionDetails.id.trim();
            const sessionName = this.currentSessionDetails.name.trim();
            const url = `/editor?session_id=${sessionId}&session_name=${encodeURIComponent(sessionName)}`;
            window.open(url, '_blank');
            this.closeSessionDetailsModal();
        }
    }
};

window.ProcessingSessionDetailsModal = ProcessingSessionDetailsModal;