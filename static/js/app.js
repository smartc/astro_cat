// FITS Cataloger Vue.js Application - Refactored Phase 2
// Complete file with all methods

const { createApp } = Vue;

createApp({
    data() {
        return {
            // UI State
            activeTab: 'dashboard',
            loading: false,
            errorMessage: '',
            showSelectionOptions: false,
            
            // Data
            stats: {},
            files: [],
            imagingSessions: [],
            
            // Pagination
            filePagination: { page: 1, limit: 50, total: 0, pages: 0 },
            imagingSessionPagination: { page: 1, limit: 20, total: 0, pages: 0 },
            
            // Filters
            fileFilters: {
                frame_types: [],
                cameras: [],
                telescopes: [],
                objects: [],
                filters: []
            },
            imagingSessionFilters: {
                cameras: [],
                telescopes: [],
                date_start: '',
                date_end: ''
            },
            searchFilters: {
                filename: '',
                session_id: '',
                exposure_min: '',
                exposure_max: '',
                date_start: '',
                date_end: ''
            },
            filterOptions: {
                frame_types: [],
                cameras: [],
                telescopes: [],
                objects: [],
                filters: [],
                dates: []
            },
            
            // Filter state
            activeFilter: null,
            activeImagingSessionFilter: null,
            objectSearchText: '',
            
            // Sorting
            fileSorting: {
                sort_by: 'obs_date',
                sort_order: 'desc'
            },
            
            // File Selection
            selectedFiles: [],
            allFilteredFilesSelected: false,
            selectAllMode: 'page',
            
            // Operations State
            activeOperation: null,
            operationStatus: null,
            operationPolling: null,
            
            // Import Processing Sessions Component Data
            ...ProcessingSessionsComponent.data(),
            
            // Import Calibration Modal Component Data
            ...CalibrationModalComponent.data(),
        };
    },
    
    computed: {
        hasActiveFilters() {
            return Object.values(this.fileFilters).some(val => val.length > 0) ||
                   Object.values(this.searchFilters).some(val => val !== '');
        },
        
        hasActiveImagingSessionFilters() {
            return Object.values(this.imagingSessionFilters).some(val => {
                if (Array.isArray(val)) return val.length > 0;
                return val !== '';
            });
        },
        
        isCurrentPageFullySelected() {
            if (this.files.length === 0) return false;
            return this.files.every(file => this.selectedFiles.includes(file.id));
        },
        
        filteredObjectOptions() {
            if (!this.objectSearchText) return this.filterOptions.objects;
            const search = this.objectSearchText.toLowerCase();
            return this.filterOptions.objects.filter(obj => 
                obj.toLowerCase().includes(search)
            );
        }
    },
    
    methods: {
        // ===================
        // API Methods
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
                this.errorMessage = 'Failed to load filter options';
            }
        },
        
        async loadFiles() {
            try {
                this.loading = true;
                this.errorMessage = '';
                
                const params = {
                    page: this.filePagination.page,
                    limit: this.filePagination.limit,
                    sort_by: this.fileSorting.sort_by,
                    sort_order: this.fileSorting.sort_order
                };
                
                // Add filters
                for (const [key, values] of Object.entries(this.fileFilters)) {
                    if (values.length > 0) {
                        params[key] = values.join(',');
                    }
                }
                
                // Add search filters
                for (const [key, value] of Object.entries(this.searchFilters)) {
                    if (value) {
                        params[key] = value;
                    }
                }
                
                const response = await ApiService.files.getFiles(params);
                this.files = response.data.files;
                this.filePagination.total = response.data.pagination.total;
                this.filePagination.pages = response.data.pagination.pages;
                
            } catch (error) {
                console.error('Error loading files:', error);
                this.errorMessage = 'Failed to load files: ' + error.message;
            } finally {
                this.loading = false;
            }
        },
        
        async loadImagingSessions() {
            try {
                this.loading = true;
                
                const params = {
                    page: this.imagingSessionPagination.page,
                    limit: this.imagingSessionPagination.limit
                };
                
                // Add filters
                for (const [key, values] of Object.entries(this.imagingSessionFilters)) {
                    if (Array.isArray(values) && values.length > 0) {
                        params[key] = values.join(',');
                    } else if (!Array.isArray(values) && values) {
                        params[key] = values;
                    }
                }
                
                const response = await ApiService.imagingSessions.getSessions(params);
                this.imagingSessions = response.data.sessions;
                this.imagingSessionPagination.total = response.data.pagination.total;
                this.imagingSessionPagination.pages = response.data.pagination.pages;
                
            } catch (error) {
                console.error('Error loading imaging sessions:', error);
                this.errorMessage = 'Failed to load imaging sessions';
            } finally {
                this.loading = false;
            }
        },
        
        // ===================
        // File Selection Methods
        // ===================
        
        toggleSelectAll() {
            if (this.selectAllMode === 'all') {
                this.toggleSelectAllFiltered();
            } else {
                this.toggleSelectCurrentPage();
            }
        },
        
        toggleSelectCurrentPage() {
            if (this.isCurrentPageFullySelected) {
                // Deselect all files on current page
                const currentPageIds = this.files.map(file => file.id);
                this.selectedFiles = this.selectedFiles.filter(id => !currentPageIds.includes(id));
                this.allFilteredFilesSelected = false;
            } else {
                // Select all files on current page
                const currentPageIds = this.files.map(file => file.id);
                const newSelections = currentPageIds.filter(id => !this.selectedFiles.includes(id));
                this.selectedFiles.push(...newSelections);
            }
        },
        
        async toggleSelectAllFiltered() {
            if (this.allFilteredFilesSelected) {
                this.clearSelection();
            } else {
                try {
                    const params = {};
                    
                    // Add all current filters
                    for (const [key, values] of Object.entries(this.fileFilters)) {
                        if (values.length > 0) {
                            params[key] = values.join(',');
                        }
                    }
                    
                    for (const [key, value] of Object.entries(this.searchFilters)) {
                        if (value) {
                            params[key] = value;
                        }
                    }
                    
                    const response = await ApiService.files.getAllFileIds(params);
                    this.selectedFiles = response.data.file_ids;
                    this.allFilteredFilesSelected = true;
                } catch (error) {
                    console.error('Error selecting all filtered files:', error);
                    this.errorMessage = 'Failed to select all files';
                }
            }
        },
        
        toggleFileSelection(fileId) {
            const index = this.selectedFiles.indexOf(fileId);
            if (index > -1) {
                this.selectedFiles.splice(index, 1);
            } else {
                this.selectedFiles.push(fileId);
            }
            
            // If we're toggling a file that's not on current page, we're no longer "all filtered selected"
            if (!this.files.map(f => f.id).includes(fileId)) {
                this.allFilteredFilesSelected = false;
            }
        },
        
        clearSelection() {
            this.selectedFiles = [];
            this.allFilteredFilesSelected = false;
        },
        
        // ===================
        // Filter Methods
        // ===================
        
        toggleFilter(filterName) {
            this.activeFilter = this.activeFilter === filterName ? null : filterName;
        },
        
        toggleFilterOption(filterName, option) {
            const index = this.fileFilters[filterName].indexOf(option);
            if (index > -1) {
                this.fileFilters[filterName].splice(index, 1);
            } else {
                this.fileFilters[filterName].push(option);
            }
            this.filePagination.page = 1;
            this.clearSelection();
            this.loadFiles();
        },
        
        getFilterText(filterName) {
            const count = this.fileFilters[filterName].length;
            if (count === 0) return `All ${filterName}`;
            if (count === 1) return this.fileFilters[filterName][0];
            return `${count} selected`;
        },
        
        toggleImagingSessionFilter(filterName) {
            this.activeImagingSessionFilter = this.activeImagingSessionFilter === filterName ? null : filterName;
        },
        
        toggleImagingSessionFilterOption(filterName, option) {
            const index = this.imagingSessionFilters[filterName].indexOf(option);
            if (index > -1) {
                this.imagingSessionFilters[filterName].splice(index, 1);
            } else {
                this.imagingSessionFilters[filterName].push(option);
            }
            this.imagingSessionPagination.page = 1;
            this.loadImagingSessions();
        },
        
        getImagingSessionFilterText(filterName) {
            const count = this.imagingSessionFilters[filterName].length;
            if (count === 0) return `All ${filterName}`;
            if (count === 1) return this.imagingSessionFilters[filterName][0];
            return `${count} selected`;
        },
        
        filterObjectOptions() {
            // This triggers the computed property to update
        },
        
        resetAllFilters() {
            for (const key of Object.keys(this.fileFilters)) {
                this.fileFilters[key] = [];
            }
            for (const key of Object.keys(this.searchFilters)) {
                this.searchFilters[key] = '';
            }
            this.objectSearchText = '';
            this.activeFilter = null;
            this.filePagination.page = 1;
            this.clearSelection();
            this.loadFiles();
        },
        
        resetImagingSessionFilters() {
            for (const key of Object.keys(this.imagingSessionFilters)) {
                if (Array.isArray(this.imagingSessionFilters[key])) {
                    this.imagingSessionFilters[key] = [];
                } else {
                    this.imagingSessionFilters[key] = '';
                }
            }
            this.activeImagingSessionFilter = null;
            this.imagingSessionPagination.page = 1;
            this.loadImagingSessions();
        },
        
        getActiveFilterSummary() {
            const summary = [];
            for (const [key, values] of Object.entries(this.fileFilters)) {
                if (values.length > 0) {
                    summary.push(`${key}: ${values.length}`);
                }
            }
            for (const [key, value] of Object.entries(this.searchFilters)) {
                if (value) {
                    summary.push(`${key}: ${value}`);
                }
            }
            return summary;
        },
        
        // ===================
        // Sorting Methods
        // ===================
        
        sortBy(column) {
            if (this.fileSorting.sort_by === column) {
                this.fileSorting.sort_order = this.fileSorting.sort_order === 'asc' ? 'desc' : 'asc';
            } else {
                this.fileSorting.sort_by = column;
                this.fileSorting.sort_order = 'asc';
            }
            this.filePagination.page = 1;
            this.loadFiles();
        },
        
        // ===================
        // Pagination Methods
        // ===================
        
        prevFilePage() {
            if (this.filePagination.page > 1) {
                this.filePagination.page--;
                this.loadFiles();
            }
        },
        
        nextFilePage() {
            if (this.filePagination.page < this.filePagination.pages) {
                this.filePagination.page++;
                this.loadFiles();
            }
        },
        
        nextImagingSessionPage() {
            if (this.imagingSessionPagination.page < this.imagingSessionPagination.pages) {
                this.imagingSessionPagination.page++;
                this.loadImagingSessions();
            }
        },
        
        prevImagingSessionPage() {
            if (this.imagingSessionPagination.page > 1) {
                this.imagingSessionPagination.page--;
                this.loadImagingSessions();
            }
        },
        
        // ===================
        // Navigation Methods
        // ===================
        
        navigateToSession(sessionId) {
            if (sessionId && sessionId !== 'N/A') {
                this.activeTab = 'imaging-sessions';
                this.searchFilters.session_id = sessionId;
                this.loadFiles();
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
                } else if (operationType === 'migrate') {
                    response = await ApiService.operations.startMigrate();
                }
                
                this.activeOperation = {
                    type: operationType,
                    taskId: response.data.task_id,
                    message: response.data.message
                };
                
                // Start polling for status
                this.pollOperationStatus();
                
            } catch (error) {
                console.error('Error starting operation:', error);
                this.errorMessage = `Failed to start ${operationType}: ${error.response?.data?.detail || error.message}`;
            } finally {
                this.loading = false;
            }
        },
        
        async checkOperationStatus() {
            if (!this.activeOperation) return;
            
            try {
                const response = await ApiService.operations.getStatus(this.activeOperation.taskId);
                this.operationStatus = response.data;
                
                // If operation is complete or errored, stop polling
                if (this.operationStatus.status === 'completed' || this.operationStatus.status === 'error') {
                    this.stopOperationPolling();
                    
                    // Refresh stats and files on completion
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
            }, 1000); // Poll every second
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
        
        ...ProcessingSessionsComponent.methods,
        ...CalibrationModalComponent.methods,
    },
    
    // ===================
    // Lifecycle Methods
    // ===================
    
    async mounted() {
        await this.loadStats();
        await this.loadFilterOptions();
        await this.loadFiles();
        await this.loadImagingSessions();
        await this.loadProcessingSessions();
    }
}).mount('#app');