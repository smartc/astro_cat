/**
 * Calibration Modal Component
 * Handles calibration file discovery and selection workflow
 */

const CalibrationModalComponent = {
    template: `
        <div v-if="showCalibrationModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 modal-backdrop">
            <div class="bg-white rounded-lg p-6 max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto modal-content">
                <div class="flex justify-between items-center mb-4">
                    <h3 class="text-lg font-bold">Calibration Files for {{ currentCalibrationSession?.name }}</h3>
                    <button @click="closeCalibrationModal" class="text-gray-500 hover:text-gray-700">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>
                
                <!-- Loading State -->
                <div v-if="calibrationLoading" class="text-center py-8">
                    <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                    <p class="mt-2 text-gray-600">Finding calibration matches...</p>
                </div>
                
                <!-- No Matches Found -->
                <div v-else-if="Object.keys(calibrationMatches).length === 0" class="text-center py-8">
                    <div class="text-4xl mb-4">🔍</div>
                    <p class="text-gray-600 text-lg">No matching calibration files found for this session.</p>
                    <p class="text-sm text-gray-500 mt-2">Calibration files are matched based on camera, telescope, and capture date proximity.</p>
                    <div class="mt-4">
                        <button @click="closeCalibrationModal" class="btn btn-blue">
                            Close
                        </button>
                    </div>
                </div>
                
                <!-- Calibration Results -->
                <div v-else class="space-y-6">
                    <div class="bg-blue-50 p-4 rounded-lg">
                        <h4 class="font-semibold text-blue-800 mb-2">📋 Review Calibration Matches</h4>
                        <p class="text-sm text-blue-700">
                            Select which calibration types to add to your processing session. Files are automatically matched based on camera, telescope, and capture date.
                        </p>
                    </div>
                    
                    <!-- Calibration Type Sections -->
                    <div v-for="(matches, frameType) in calibrationMatches" :key="frameType" class="border rounded-lg p-4 calibration-match-card">
                        <div class="flex items-center justify-between mb-3">
                            <div class="flex items-center space-x-3">
                                <input 
                                    type="checkbox" 
                                    :id="'select-' + frameType"
                                    v-model="selectedCalibrationTypes[frameType]"
                                    class="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 calibration-checkbox"
                                >
                                <label :for="'select-' + frameType" class="text-lg font-semibold capitalize cursor-pointer">
                                    {{ frameType }} Frames
                                </label>
                                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800 frame-type-badge">
                                    {{ getTotalFilesForFrameType(matches) }} files
                                </span>
                            </div>
                        </div>
                        
                        <!-- Match Details -->
                        <div class="space-y-3">
                            <div v-for="(match, index) in matches" :key="index" class="bg-gray-50 p-3 rounded border-l-4 border-blue-400">
                                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                                    <div>
                                        <strong>Session:</strong> {{ match.capture_session_id }}<br>
                                        <strong>Camera:</strong> {{ match.camera }}<br>
                                        <strong>Telescope:</strong> {{ match.telescope }}
                                    </div>
                                    <div>
                                        <strong>Date:</strong> {{ formatDate(match.capture_date) }}<br>
                                        <strong>Files:</strong> {{ match.file_count }}<br>
                                        <strong v-if="match.exposure_times && match.exposure_times.length">
                                            Exposures:</strong> 
                                        <span v-if="match.exposure_times && match.exposure_times.length">
                                            {{ match.exposure_times.join(', ') }}s
                                        </span>
                                    </div>
                                </div>
                                <div v-if="match.filters && match.filters.length" class="mt-2 text-sm">
                                    <strong>Filters:</strong> {{ match.filters.join(', ') }}
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Action Buttons -->
                    <div class="flex justify-between items-center pt-4 border-t">
                        <div class="text-sm text-gray-600">
                            <span v-if="getSelectedCalibrationCount() > 0" class="text-green-600 font-medium">
                                ✓ {{ getSelectedCalibrationCount() }} calibration files selected
                            </span>
                            <span v-else class="text-gray-500">
                                No calibration files selected
                            </span>
                        </div>
                        <div class="flex space-x-3">
                            <button @click="closeCalibrationModal" class="btn btn-gray">
                                Cancel
                            </button>
                            <button 
                                @click="addSelectedCalibrationFiles" 
                                :disabled="getSelectedCalibrationCount() === 0"
                                class="btn btn-green"
                            >
                                Add Selected Files
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    data() {
        return {
            showCalibrationModal: false,
            calibrationLoading: false,
            calibrationMatches: {},
            selectedCalibrationTypes: {},
            currentCalibrationSession: null,
        };
    },
    
    methods: {
        async findCalibrationFiles(sessionId) {
            try {
                this.calibrationLoading = true;
                this.calibrationMatches = {};
                this.selectedCalibrationTypes = {};
                this.showCalibrationModal = true;
                
                const response = await ApiService.processingSessions.getCalibrationMatches(sessionId);
                this.calibrationMatches = response.data;
                
                // Access parent's processingSessions
                const app = this.$root;
                this.currentCalibrationSession = app.processingSessions.find(s => s.id === sessionId);
                
            } catch (error) {
                console.error('Error finding calibration files:', error);
                this.showCalibrationModal = false;
                alert(`Failed to find calibration files: ${error.response?.data?.detail || error.message}`);
            } finally {
                this.calibrationLoading = false;
            }
        },
        
        async addSelectedCalibrationFiles() {
            try {
                const fileIds = [];
                
                // Extract file IDs from selected calibration types
                Object.keys(this.selectedCalibrationTypes).forEach(frameType => {
                    if (this.selectedCalibrationTypes[frameType]) {
                        this.calibrationMatches[frameType].forEach(match => {
                            // Each match has a file_ids array
                            if (match.file_ids && Array.isArray(match.file_ids)) {
                                fileIds.push(...match.file_ids);
                            }
                        });
                    }
                });
                
                if (fileIds.length === 0) {
                    return;
                }
                
                console.log('Sending file IDs:', fileIds);
                
                const app = this.$root;
                await ApiService.processingSessions.addFiles(
                    this.currentCalibrationSession.id,
                    fileIds
                );
                
                this.closeCalibrationModal();
                alert(`Added ${fileIds.length} calibration files to session!`);
                
                await app.loadProcessingSessions();

                // REFRESH STATS AFTER ADDING CALIBRATION
                await window.refreshStats();
                
            } catch (error) {
                console.error('Error adding calibration files:', error);
                this.closeCalibrationModal();
                alert(`Error: ${error.response?.data?.detail || error.message}`);
            }
        },
        
        closeCalibrationModal() {
            this.showCalibrationModal = false;
            this.calibrationLoading = false;
            this.calibrationMatches = {};
            this.selectedCalibrationTypes = {};
            this.currentCalibrationSession = null;
        },
        
        getTotalFilesForFrameType(matches) {
            return matches.reduce((total, match) => total + match.file_count, 0);
        },
        
        getSelectedCalibrationCount() {
            let total = 0;
            Object.keys(this.selectedCalibrationTypes).forEach(frameType => {
                if (this.selectedCalibrationTypes[frameType]) {
                    total += this.getTotalFilesForFrameType(this.calibrationMatches[frameType]);
                }
            });
            return total;
        },
        
        formatDate(dateString) {
            if (!dateString) return 'N/A';
            return new Date(dateString).toLocaleDateString();
        }
    }
};

window.CalibrationModalComponent = CalibrationModalComponent;