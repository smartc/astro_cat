// FITS Cataloger Vue.js Application - Fully Refactored
// All modals extracted to components

const { createApp } = Vue;

createApp({
    // Register all modal components
    components: {
        'imaging-session-detail-modal': ImagingSessionDetailModal,
        'calibration-modal': CalibrationModalComponent,
        'processing-session-details-modal': ProcessingSessionDetailsModal,
        'processing-session-modals': ProcessingSessionModals
    },
    
    data() {
        return {
            // Core UI State
            activeTab: 'dashboard',
            loading: false,
            errorMessage: '',
            
            // Dashboard Data
            stats: {},
            
            // Operations State
            activeOperation: null,
            operationStatus: null,
            operationPolling: null,
            
            // Import Component Data (only non-modal components)
            ...FilesBrowserComponent.data(),
            ...ImagingSessionsComponent.data(),
            ...ProcessingSessionsComponent.data(),
        };
    },
    
    computed: {
        // Import Component Computed Properties
        ...FilesBrowserComponent.computed,
        ...ImagingSessionsComponent.computed,
    },
    
    methods: {
        // ===================
        // Core Methods
        // ===================
        
        async loadStats() {
            try {
                this.loading = true;
                const response = await ApiService.stats.getStats();
                this.stats = response.data;
            } catch (error) {
                console.error('Error loading stats:', error);
                this.errorMessage = 'Failed to load statistics: ' + error.message;
            } finally {
                this.loading = false;
            }
        },
        
        // ===================
        // Utility Methods
        // ===================
        
        getFrameTypeClass(frameType) {
            const classes = {
                'LIGHT': 'bg-blue-100 text-blue-800',
                'DARK': 'bg-gray-100 text-gray-800',
                'FLAT': 'bg-yellow-100 text-yellow-800',
                'BIAS': 'bg-purple-100 text-purple-800'
            };
            return classes[frameType] || 'bg-gray-100 text-gray-800';
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
        
        // ===================
        // Modal Interaction Methods
        // ===================
        
        viewSessionDetails(sessionId) {
            this.$refs.sessionDetailModal.viewSessionDetails(sessionId);
        },
        
        findCalibrationFiles(sessionId) {
            this.$refs.calibrationModal.findCalibrationFiles(sessionId);
        },
        
        viewProcessingSession(sessionId) {
            this.$refs.processingDetailsModal.viewProcessingSession(sessionId);
        },
        
        showCreateProcessingSessionModal() {
            this.$refs.processingModals.showCreateProcessingSessionModal();
        },
        
        addToNewSession() {
            this.$refs.processingModals.addToNewSession();
        },
        
        async showAddToExistingModal() {
            await this.$refs.processingModals.showAddToExistingModal();
        },
        
        // ===================
        // Operations Methods (ORIGINAL - UNCHANGED)
        // ===================
        
        async startOperation(operationType) {
            try {
                this.loading = true;
                this.errorMessage = '';
                
                let response;
                if (operationType === 'scan') {
                    response = await ApiService.operations.startScan();
                } else if (operationType === 'validate') {
                    response = await ApiService.operations.startValidate();
                } else if (operationType === 'organize') {
                    response = await ApiService.operations.startOrganize();
                } else if (operationType === 'migrate') {
                    response = await ApiService.operations.startMigrate();
                }
                
                this.activeOperation = operationType;
                this.operationStatus = response.data;
                this.pollOperationStatus();
                
            } catch (error) {
                console.error('Error starting operation:', error);
                this.errorMessage = `Failed to start ${operationType}: ${error.response?.data?.detail || error.message}`;
            } finally {
                this.loading = false;
            }
        },
        
        async checkOperationStatus() {
            if (!this.operationStatus?.task_id) return;
            
            try {
                const response = await ApiService.operations.getStatus(this.operationStatus.task_id);
                this.operationStatus = response.data;
                
                if (this.operationStatus.status === 'completed' || this.operationStatus.status === 'failed') {
                    this.stopOperationPolling();
                    
                    if (this.operationStatus.status === 'completed') {
                        await this.loadStats();
                        if (this.activeTab === 'files') {
                            await this.loadFiles();
                        }
                    }
                }
                
            } catch (error) {
                console.error('Error checking operation status:', error);
                this.stopOperationPolling();
            }
        },
        
        pollOperationStatus() {
            this.operationPolling = setInterval(() => {
                this.checkOperationStatus();
            }, 1000);
        },
        
        stopOperationPolling() {
            if (this.operationPolling) {
                clearInterval(this.operationPolling);
                this.operationPolling = null;
            }
        },
        
        clearOperation() {
            this.stopOperationPolling();
            this.activeOperation = null;
            this.operationStatus = null;
        },
        
        // ===================
        // Import Component Methods
        // ===================
        
        ...FilesBrowserComponent.methods,
        ...ImagingSessionsComponent.methods,
        ...ProcessingSessionsComponent.methods,
    },
    
    async mounted() {
        await this.loadStats();
        await this.loadFilterOptions();
        await this.loadFiles();
        await this.loadImagingSessions();
        await this.loadProcessingSessions();
    }
}).mount('#app');