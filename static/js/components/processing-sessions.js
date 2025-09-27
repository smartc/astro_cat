/**
 * Processing Sessions Component
 * Handles all processing session related logic and state management
 */

const ProcessingSessionsComponent = {
    data() {
        return {
            // Processing Sessions Data
            processingSessions: [],
            existingSessions: [],
            processingSessionPagination: { page: 1, limit: 20, total: 0, pages: 0 },
            processingSessionStatusFilter: '',
            
            // Session Modals State
            showCreateModal: false,
            showAddToNewModal: false,
            showAddToExistingSessionModal: false,
            showSessionDetailsModal: false,
            showCalibrationModal: false,
            
            // Session Form Data
            newProcessingSession: { name: '', fileIds: '', notes: '' },
            newSessionFromFiles: { name: '', notes: '' },
            selectedExistingSession: '',
            
            // Session Details & Calibration
            currentSessionDetails: null,
            sessionDetailsLoading: false,
            calibrationLoading: false,
            calibrationMatches: {},
            selectedCalibrationTypes: {},
            currentCalibrationSession: null,
        };
    },
    
    methods: {
        // ==================
        // Loading Methods
        // ==================
        
        async loadProcessingSessions() {
            try {
                this.loading = true;
                
                const params = {
                    page: this.processingSessionPagination.page,
                    limit: this.processingSessionPagination.limit
                };
                
                if (this.processingSessionStatusFilter) {
                    params.status = this.processingSessionStatusFilter;
                }
                
                const response = await ApiService.processingSessions.getAll(params);
                this.processingSessions = response.data.sessions;
                this.processingSessionPagination.total = response.data.pagination.total;
                this.processingSessionPagination.pages = response.data.pagination.pages;
                
            } catch (error) {
                console.error('Error loading processing sessions:', error);
                this.errorMessage = 'Failed to load processing sessions';
            } finally {
                this.loading = false;
            }
        },
        
        async loadExistingSessions() {
            try {
                const response = await ApiService.processingSessions.getAll({});
                this.existingSessions = response.data.sessions;
            } catch (error) {
                console.error('Error loading existing sessions:', error);
                this.errorMessage = 'Failed to load existing sessions';
            }
        },
        
        // ==================
        // Session Details
        // ==================
        
        async viewProcessingSession(sessionId) {
            try {
                this.sessionDetailsLoading = true;
                this.currentSessionDetails = null;
                this.showSessionDetailsModal = true;
                
                const response = await ApiService.processingSessions.getById(sessionId);
                this.currentSessionDetails = response.data;
                
            } catch (error) {
                console.error('Error loading session details:', error);
                this.errorMessage = `Failed to load session details: ${error.response?.data?.detail || error.message}`;
                this.showSessionDetailsModal = false;
            } finally {
                this.sessionDetailsLoading = false;
            }
        },
        
        // ==================
        // Calibration Workflow
        // ==================
        
        async findCalibrationFiles(sessionId) {
            try {
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
                const selectedMatches = {};
                
                for (const [frameType, isSelected] of Object.entries(this.selectedCalibrationTypes)) {
                    if (isSelected && this.calibrationMatches[frameType]) {
                        selectedMatches[frameType] = this.calibrationMatches[frameType];
                    }
                }
                
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
                
                const sessionName = this.currentCalibrationSession.name;
                const sessionId = this.currentCalibrationSession.id;
                const fileCount = allFileIds.length;
                const selectedTypes = Object.keys(selectedMatches).join(', ');
                
                await ApiService.processingSessions.addFiles(sessionId, allFileIds);
                
                this.closeCalibrationModal();
                alert(`Successfully added ${fileCount} calibration files (${selectedTypes}) to session "${sessionName}"`);
                
                await this.loadProcessingSessions();
                
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
                
                await this.loadProcessingSessions();
                
            }
        },
        
        // ==================
        // CRUD Operations
        // ==================
        
        async createProcessingSession() {
            try {
                if (!this.newProcessingSession.name.trim()) {
                    this.errorMessage = 'Session name is required';
                    return;
                }
                
                const fileIds = this.newProcessingSession.fileIds
                    .split(',')
                    .map(id => parseInt(id.trim(), 10))
                    .filter(id => !isNaN(id));
                
                if (fileIds.length === 0) {
                    this.errorMessage = 'No valid file IDs found';
                    return;
                }
                
                const payload = {
                    name: this.newProcessingSession.name.trim(),
                    file_ids: fileIds,
                    notes: this.newProcessingSession.notes.trim() || null
                };
                
                await ApiService.processingSessions.create(payload);
                
                this.showCreateModal = false;
                this.loadProcessingSessions();
                this.errorMessage = '';
                alert(`Processing session "${this.newProcessingSession.name}" created successfully with ${fileIds.length} files!`);
                
            } catch (error) {
                console.error('Error creating processing session:', error);
                this.errorMessage = `Failed to create processing session: ${error.response?.data?.detail || error.message}`;
            }
        },
        
        async createSessionFromSelectedFiles() {
            try {
                if (!this.newSessionFromFiles.name.trim()) {
                    this.errorMessage = 'Session name is required';
                    return;
                }
                
                if (this.selectedFiles.length === 0) {
                    this.errorMessage = 'No files selected';
                    return;
                }
                
                const selectedCount = this.selectedFiles.length;
                const sessionName = this.newSessionFromFiles.name.trim();
                
                const payload = {
                    name: sessionName,
                    file_ids: this.selectedFiles,
                    notes: this.newSessionFromFiles.notes.trim() || null
                };
                
                await ApiService.processingSessions.create(payload);
                
                this.showAddToNewModal = false;
                this.clearSelection();
                this.errorMessage = '';
                
                alert(`Processing session "${sessionName}" created successfully with ${selectedCount} files!`);
                
                await this.loadProcessingSessions();
                
                
            } catch (error) {
                console.error('Error creating processing session from files:', error);
                this.errorMessage = `Failed to create processing session: ${error.response?.data?.detail || error.message}`;
            }
        },
        
        async addToExistingSession() {
            try {
                if (!this.selectedExistingSession) {
                    this.errorMessage = 'Please select a session';
                    return;
                }
                
                if (this.selectedFiles.length === 0) {
                    this.errorMessage = 'No files selected';
                    return;
                }
                
                const selectedCount = this.selectedFiles.length;
                const sessionName = this.existingSessions.find(s => s.id === this.selectedExistingSession)?.name || 'session';
                
                const fileIds = this.selectedFiles.map(id => parseInt(id, 10));
                
                await ApiService.processingSessions.addFiles(this.selectedExistingSession, fileIds);
                
                this.showAddToExistingSessionModal = false;
                this.clearSelection();
                this.errorMessage = '';
                
                alert(`${selectedCount} files added to "${sessionName}" successfully!`);
                
                await this.loadProcessingSessions();
                
                
            } catch (error) {
                console.error('Error adding files to existing session:', error);
                
                let errorMsg = 'Failed to add files to session';
                if (error.response?.data?.detail) {
                    errorMsg += `: ${error.response.data.detail}`;
                } else if (error.message) {
                    errorMsg += `: ${error.message}`;
                }
                
                this.errorMessage = errorMsg;
            }
        },
        
        async updateProcessingSessionStatus(sessionId) {
            try {
                const statuses = ['not_started', 'in_progress', 'complete'];
                const statusLabels = ['Not Started', 'In Progress', 'Complete'];
                
                const choice = prompt(
                    'Select new status:\n\n' +
                    '1. Not Started\n' + 
                    '2. In Progress\n' + 
                    '3. Complete\n\n' +
                    'Enter number (1-3):'
                );
                
                if (!choice) return;
                
                const index = parseInt(choice) - 1;
                if (index < 0 || index >= statuses.length) {
                    this.errorMessage = 'Invalid status selection';
                    return;
                }
                
                const newStatus = statuses[index];
                const notes = prompt('Add notes (optional):');
                
                const payload = {
                    status: newStatus,
                    notes: notes || null
                };
                
                await ApiService.processingSessions.updateStatus(sessionId, payload);
                
                this.loadProcessingSessions();
                alert(`Status updated to: ${statusLabels[index]}`);
                
            } catch (error) {
                console.error('Error updating processing session status:', error);
                this.errorMessage = `Failed to update status: ${error.response?.data?.detail || error.message}`;
            }
        },
        
        async deleteProcessingSession(sessionId) {
            try {
                if (!confirm('Are you sure you want to delete this processing session? This action cannot be undone.')) {
                    return;
                }
                
                const removeFiles = confirm('Also remove staged files from disk?');
                
                await ApiService.processingSessions.delete(sessionId, removeFiles);
                
                this.loadProcessingSessions();
                alert('Processing session deleted successfully');
                
            } catch (error) {
                console.error('Error deleting processing session:', error);
                this.errorMessage = `Failed to delete processing session: ${error.response?.data?.detail || error.message}`;
            }
        },
        
        // ==================
        // Pagination
        // ==================
        
        nextProcessingSessionPage() {
            if (this.processingSessionPagination.page < this.processingSessionPagination.pages) {
                this.processingSessionPagination.page++;
                this.loadProcessingSessions();
            }
        },
        
        prevProcessingSessionPage() {
            if (this.processingSessionPagination.page > 1) {
                this.processingSessionPagination.page--;
                this.loadProcessingSessions();
            }
        },
        
        // ==================
        // Modal Management
        // ==================
        
        showCreateProcessingSessionModal() {
            this.newProcessingSession = { name: '', fileIds: '', notes: '' };
            this.showCreateModal = true;
        },
        
        addToNewSession() {
            if (this.selectedFiles.length === 0) {
                this.errorMessage = 'No files selected';
                return;
            }
            
            this.newSessionFromFiles = { name: '', notes: '' };
            this.showAddToNewModal = true;
        },
        
        async showAddToExistingModal() {
            if (this.selectedFiles.length === 0) {
                this.errorMessage = 'No files selected';
                return;
            }
            
            await this.loadExistingSessions();
            this.selectedExistingSession = '';
            this.showAddToExistingSessionModal = true;
        },
        
        closeCalibrationModal() {
            this.showCalibrationModal = false;
            this.calibrationLoading = false;
            this.calibrationMatches = {};
            this.selectedCalibrationTypes = {};
            this.currentCalibrationSession = null;
            this.errorMessage = '';
        },
        
        closeSessionDetailsModal() {
            this.showSessionDetailsModal = false;
            this.currentSessionDetails = null;
            this.sessionDetailsLoading = false;
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
window.ProcessingSessionsComponent = ProcessingSessionsComponent;