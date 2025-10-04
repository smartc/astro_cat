// FITS Cataloger Vue.js Application - Fully Refactored with Navigation

window.refreshStats = async function() {
    const app = window.vueApp;
    if (app) {
        await app.loadStats();
    }
};

const { createApp } = Vue;

createApp({
    components: {
        'dashboard-tab': DashboardTab,
        'files-tab': FilesTab,
        'imaging-sessions-tab': ImagingSessionsTab,
        'processing-sessions-tab': ProcessingSessionsTab,
        'operations-tab': OperationsTab,
        'equipment-tab': EquipmentTab,
        'database-tab': DatabaseTab,
        'configuration-tab': ConfigurationTab,
        'imaging-session-detail-modal': ImagingSessionDetailModal,
        'calibration-modal': CalibrationModalComponent,
        'processing-session-details-modal': ProcessingSessionDetailsModal,
        'processing-session-modals': ProcessingSessionModals,
    },
    
    data() {
        return {
            // Core UI State
            activeTab: 'dashboard',
            menuOpen: false,
            loading: false,
            errorMessage: '',
            
            // Tab navigation
            tabs: ['dashboard', 'files', 'imaging-sessions', 'processing-sessions', 'operations', 'equipment', 'database', 'configuration'],
            keyboardHandler: null,
            popstateHandler: null,
            
            // Dashboard Data
            stats: {},
            
            // Operations State
            activeOperation: null,
            operationStatus: null,
            operationPolling: null,
            
            // Import Component Data
            ...FilesBrowserComponent.data(),
            ...ImagingSessionsComponent.data(),
            ...ProcessingSessionsComponent.data(),
        };
    },
    
    computed: {
        ...FilesBrowserComponent.computed,
        ...ImagingSessionsComponent.computed,
    },
    
    methods: {
        // ===================
        // Menu Navigation
        // ===================
        
        navigateTo(tab) {
            this.changeTab(tab);
            this.menuOpen = false;
        },
        
        changeTab(tab) {
            if (this.activeTab === tab) return;
            
            this.activeTab = tab;
            
            // Update browser history
            const url = new URL(window.location);
            url.searchParams.set('tab', tab);
            window.history.pushState({ tab }, '', url);
            
            // Load data for specific tabs when navigated to
            if (tab === 'files' && this.files.length === 0) {
                this.loadFiles();
            } else if (tab === 'imaging-sessions' && this.imagingSessions.length === 0) {
                this.loadImagingSessions();
            } else if (tab === 'processing-sessions' && this.processingSessions.length === 0) {
                this.loadProcessingSessions();
            }
        },
        
        openDatabaseBrowser() {
            const dbUrl = `http://${window.location.hostname}:8081`;
            window.open(dbUrl, '_blank', 'width=1400,height=900');
            this.menuOpen = false;
        },
        
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
        
        async loadFilterOptions() {
            try {
                const response = await ApiService.files.getFilterOptions();
                this.filterOptions = response.data;
            } catch (error) {
                console.error('Error loading filter options:', error);
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
        // Operations Methods
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
                
                if (this.operationStatus.status === 'completed' || 
                    this.operationStatus.status === 'error') {

                    if (window.operationsTabInstance) {
                        console.log('Notifying operations tab of completion');
                        window.operationsTabInstance.onOperationCompleted(
                            this.activeOperation,
                            this.operationStatus
                        );
                    }

                    clearInterval(this.operationPolling);
                    this.operationPolling = null;
                    this.activeOperation = null;
                    
                    await this.loadStats();
                    
                    if (this.operationStatus.status === 'completed') {
                        if (this.activeTab === 'files') {
                            await this.loadFiles();
                        } else if (this.activeTab === 'imaging-sessions') {
                            await this.loadImagingSessions();
                        }
                    }
                }
            } catch (error) {
                console.error('Error checking operation status:', error);
            }
        },
        
        pollOperationStatus() {
            if (this.operationPolling) {
                clearInterval(this.operationPolling);
            }
            
            this.operationPolling = setInterval(async () => {
                await this.checkOperationStatus();
            }, 2000);
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
        console.log('App mounted, activeTab:', this.activeTab);
        
        // Initialize from URL if present
        const urlParams = new URLSearchParams(window.location.search);
        const urlTab = urlParams.get('tab');
        if (urlTab && this.tabs.includes(urlTab)) {
            this.activeTab = urlTab;
        }
        
        // Test keyboard directly
        document.addEventListener('keydown', (e) => {
            console.log('ANY key pressed:', e.key, 'Alt:', e.altKey, 'Target:', e.target.tagName);
        });
        
        // Store bound handlers
        this.keyboardHandler = (e) => {
            console.log('Keyboard handler fired');
            if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) {
                console.log('Ignoring - in input field');
                return;
            }
            
            console.log('Key pressed:', e.key, 'Alt:', e.altKey);
            
            if (e.altKey && e.key >= '1' && e.key <= '8') {
                console.log('Alt+Number detected');
                e.preventDefault();
                e.stopPropagation();
                const tabIndex = parseInt(e.key) - 1;
                if (this.tabs[tabIndex]) {
                    console.log('Switching to tab:', this.tabs[tabIndex]);
                    this.changeTab(this.tabs[tabIndex]);
                }
                return;
            }
            
            if (e.altKey && (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) {
                console.log('Alt+Arrow detected');
                e.preventDefault();
                e.stopPropagation();
                const currentIndex = this.tabs.indexOf(this.activeTab);
                if (e.key === 'ArrowLeft') {
                    const prevIndex = currentIndex > 0 ? currentIndex - 1 : this.tabs.length - 1;
                    this.changeTab(this.tabs[prevIndex]);
                } else {
                    const nextIndex = (currentIndex + 1) % this.tabs.length;
                    this.changeTab(this.tabs[nextIndex]);
                }
                return;
            }
        };
        
        this.popstateHandler = (e) => {
            console.log('Popstate event:', e.state);
            if (e.state && e.state.tab) {
                this.activeTab = e.state.tab;
                console.log('Tab changed to:', this.activeTab);
            } else {
                const urlParams = new URLSearchParams(window.location.search);
                const urlTab = urlParams.get('tab');
                if (urlTab && this.tabs.includes(urlTab)) {
                    this.activeTab = urlTab;
                    console.log('Tab changed from URL:', this.activeTab);
                }
            }
        };
        
        window.addEventListener('keydown', this.keyboardHandler);
        window.addEventListener('popstate', this.popstateHandler);
        console.log('Event listeners attached');
        
        document.addEventListener('click', (e) => {
            if (this.menuOpen && !e.target.closest('header')) {
                this.menuOpen = false;
            }
            
            const isDropdownButton = e.target.closest('.filter-button');
            if (!isDropdownButton) {
                this.activeFilter = null;
                this.activeImagingSessionFilter = null;
            }
        });

        await this.loadFilterOptions();
        await this.loadStats();
        await this.loadFiles();
        await this.loadImagingSessions();
        await this.loadProcessingSessions();

        window.vueApp = this;
        
        this.statsRefreshInterval = setInterval(() => {
            this.loadStats();
        }, 30000);
    },
    
    beforeUnmount() {
        if (this.keyboardHandler) {
            window.removeEventListener('keydown', this.keyboardHandler);
        }
        if (this.popstateHandler) {
            window.removeEventListener('popstate', this.popstateHandler);
        }
        if (this.statsRefreshInterval) {
            clearInterval(this.statsRefreshInterval);
        }
        if (this.operationPolling) {
            clearInterval(this.operationPolling);
        }
    }
}).mount('#app');