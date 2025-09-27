/**
 * Calibration Modal Component
 * Handles calibration file discovery and selection workflow
 */

const CalibrationModalComponent = {
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
        // ==================
        // Calibration Workflow
        // ==================
        
        async findCalibrationFiles(sessionId) {
            try {
                // Close session details modal if open
                if (this.showSessionDetailsModal) {
                    this.showSessionDetailsModal = false;
                }
                
                this.calibrationLoading = true;
                this.calibrationMatches = {};
                this.selectedCalibrationTypes = {};
                this.showCalibrationModal = true;
                
                const response = await ApiService.processingSessions.getCalibrationMatches(sessionId);
                this.calibrationMatches = response.data;
                this.currentCalibrationSession = this.processingSessions.find(s => s.id === sessionId);
                
            } catch (error) {
                console.error('Error finding calibration files:', error);
                this.errorMessage = `Failed to find calibration files: ${error.response?.data?.detail || error.message}`;
                this.showCalibrationModal = false;
            } finally {
                this.calibrationLoading = false;
            }
        },
        
        async addSelectedCalibrationFiles() {
            try {
                // Collect selected matches
                const selectedMatches = {};
                
                for (const [frameType, isSelected] of Object.entries(this.selectedCalibrationTypes)) {
                    if (isSelected && this.calibrationMatches[frameType]) {
                        selectedMatches[frameType] = this.calibrationMatches[frameType];
                    }
                }
                
                // Extract all file IDs
                const allFileIds = [];
                for (const matches of Object.values(selectedMatches)) {
                    for (const match of matches) {
                        allFileIds.push(...match.file_ids);
                    }
                }
                
                if (allFileIds.length === 0) {
                    this.closeCalibrationModal();
                    alert('No files to add');
                    return;
                }
                
                // Capture values before API call
                const sessionName = this.currentCalibrationSession.name;
                const sessionId = this.currentCalibrationSession.id;
                const fileCount = allFileIds.length;
                const selectedTypes = Object.keys(selectedMatches).join(', ');
                
                // Add files to session
                await ApiService.processingSessions.addFiles(sessionId, allFileIds);
                
                this.closeCalibrationModal();
                alert(`Successfully added ${fileCount} calibration files (${selectedTypes}) to session "${sessionName}"`);
                
                // Refresh if on processing sessions tab
                if (this.activeTab === 'processing-sessions') {
                    this.loadProcessingSessions();
                }
                
            } catch (error) {
                console.error('Error adding calibration files:', error);
                
                let errorMessage = 'Failed to add calibration files';
                if (error.response?.data?.detail) {
                    errorMessage = error.response.data.detail;
                } else if (error.message) {
                    errorMessage = error.message;
                }
                
                this.closeCalibrationModal();
                alert(`Error: ${errorMessage}`);
                
                if (this.activeTab === 'processing-sessions') {
                    this.loadProcessingSessions();
                }
            }
        },
        
        closeCalibrationModal() {
            this.showCalibrationModal = false;
            this.calibrationLoading = false;
            this.calibrationMatches = {};
            this.selectedCalibrationTypes = {};
            this.currentCalibrationSession = null;
            this.errorMessage = '';
        },
        
        // ==================
        // Helper Methods
        // ==================
        
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
        }
    }
};

// Export for use in main app
window.CalibrationModalComponent = CalibrationModalComponent;