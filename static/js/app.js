// FITS Cataloger Vue.js Application - Complete with Enhanced File Selection
// This is the complete updated app.js with all enhancements

const { createApp } = Vue;

createApp({
    data() {
        return {
            // UI State
            activeTab: 'dashboard',
            loading: false,
            errorMessage: '',
            showSelectionOptions: false, // For selection dropdown
            
            // Data
            stats: {},
            files: [],
            imagingSessions: [],
            processingSessions: [],
            
            // Pagination
            filePagination: { page: 1, limit: 50, total: 0, pages: 0 },
            imagingSessionPagination: { page: 1, limit: 20, total: 0, pages: 0 },
            processingSessionPagination: { page: 1, limit: 20, total: 0, pages: 0 },
            
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
            processingSessionStatusFilter: '',
            
            // Sorting
            fileSorting: {
                sort_by: 'obs_date',
                sort_order: 'desc'
            },
            
            // Enhanced File Selection
            selectedFiles: [],
            allFilteredFilesSelected: false,
            selectAllMode: 'page',
            
            // Session Management
            existingSessions: [],
            selectedExistingSession: '',
            newProcessingSession: {
                name: '',
                fileIds: '',
                notes: ''
            },
            newSessionFromFiles: {
                name: '',
                notes: ''
            },
            
            // Modal States
            showCreateModal: false,
            showAddToNewModal: false,
            showAddToExistingSessionModal: false,
            showCalibrationModal: false,
            calibrationLoading: false,
            calibrationMatches: {},
            selectedCalibrationTypes: {},
            currentCalibrationSession: null,
            showSessionDetailsModal: false,
            currentSessionDetails: null,
            sessionDetailsLoading: false,
        }
    },
    
    computed: {
        allFilesSelected() {
            if (this.selectAllMode === 'all') {
                return this.allFilteredFilesSelected;
            } else {
                return this.files.length > 0 && this.currentPageSelectedCount === this.files.length;
            }
        },
        
        currentPageSelectedCount() {
            return this.files.filter(file => this.selectedFiles.includes(file.id)).length;
        },
        
        isCurrentPageFullySelected() {
            return this.files.length > 0 && this.currentPageSelectedCount === this.files.length;
        },
        
        selectionSummaryText() {
            if (this.allFilteredFilesSelected) {
                return `All ${this.filePagination.total} filtered files selected`;
            } else if (this.selectedFiles.length === 0) {
                return 'Select files';
            } else if (this.selectedFiles.length === 1) {
                return '1 file selected';
            } else {
                return `${this.selectedFiles.length} files selected`;
            }
        },
        
        hasActiveFilters() {
            return Object.values(this.fileFilters).some(arr => arr.length > 0) ||
                   Object.values(this.searchFilters).some(val => val !== '');
        },
        
        hasActiveImagingSessionFilters() {
            return Object.values(this.imagingSessionFilters).some(val => {
                if (Array.isArray(val)) {
                    return val.length > 0;
                }
                return val !== '';
            });
        },
        
        filteredObjectOptions() {
            if (!this.objectSearchText) {
                return this.filterOptions.objects;
            }
            return this.filterOptions.objects.filter(obj => 
                obj.toLowerCase().includes(this.objectSearchText.toLowerCase())
            );
        }
    },
    
    methods: {
        // Enhanced File Selection Methods
        toggleFileSelection(fileId) {
            const index = this.selectedFiles.indexOf(fileId);
            if (index > -1) {
                this.selectedFiles.splice(index, 1);
            } else {
                this.selectedFiles.push(fileId);
            }
            
            // If we were in "all selected" mode and deselected something, turn that off
            if (this.allFilteredFilesSelected && index > -1) {
                this.allFilteredFilesSelected = false;
            }
        },
        
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
                // Deselect all
                this.selectedFiles = [];
                this.allFilteredFilesSelected = false;
            } else {
                // Select all filtered files
                try {
                    this.loading = true;
                    
                    // Build the same parameters as the current filter
                    const params = new URLSearchParams({
                        page: 1,
                        limit: this.filePagination.total, // Get all files
                        sort_by: this.fileSorting.sort_by,
                        sort_order: this.fileSorting.sort_order
                    });
                    
                    // Add current filters
                    for (const [key, values] of Object.entries(this.fileFilters)) {
                        if (values.length > 0) {
                            params.append(key, values.join(','));
                        }
                    }
                    
                    for (const [key, value] of Object.entries(this.searchFilters)) {
                        if (value) {
                            params.append(key, value);
                        }
                    }
                    
                    const response = await axios.get(`/api/files?${params}`);
                    const allFilteredFiles = response.data.files;
                    
                    // Select all file IDs
                    this.selectedFiles = allFilteredFiles.map(file => file.id);
                    this.allFilteredFilesSelected = true;
                    
                    console.log(`Selected all ${this.selectedFiles.length} filtered files`);
                    
                } catch (error) {
                    console.error('Error loading all filtered files:', error);
                    this.errorMessage = 'Failed to select all files: ' + error.message;
                } finally {
                    this.loading = false;
                }
            }
        },
        
        selectAllCurrentPage() {
            const currentPageIds = this.files.map(file => file.id);
            const newSelections = currentPageIds.filter(id => !this.selectedFiles.includes(id));
            this.selectedFiles.push(...newSelections);
            this.allFilteredFilesSelected = false;
            this.selectAllMode = 'page';
        },
        
        selectAllFilteredFiles() {
            this.selectAllMode = 'all';
            this.toggleSelectAllFiltered();
        },
        
        clearSelection() {
            this.selectedFiles = [];
            this.allFilteredFilesSelected = false;
            this.selectAllMode = 'page';
            this.showSelectionOptions = false;
        },
        
        // Session Management Methods
        async loadExistingSessions() {
            try {
                const response = await axios.get('/api/processing-sessions');
                this.existingSessions = response.data.sessions;
            } catch (error) {
                console.error('Error loading existing sessions:', error);
                this.errorMessage = 'Failed to load existing sessions';
            }
        },
        
        addToNewSession() {
            if (this.selectedFiles.length === 0) {
                this.errorMessage = 'No files selected';
                return;
            }
            
            this.newSessionFromFiles = {
                name: '',
                notes: ''
            };
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
                
                // Capture the count BEFORE clearing selection
                const selectedCount = this.selectedFiles.length;
                const sessionName = this.newSessionFromFiles.name.trim();
                
                const payload = {
                    name: sessionName,
                    file_ids: this.selectedFiles,
                    notes: this.newSessionFromFiles.notes.trim() || null
                };
                
                await axios.post('/api/processing-sessions', payload);
                
                this.showAddToNewModal = false;
                this.clearSelection(); // Clear selection AFTER capturing count
                this.errorMessage = '';
                
                // Use captured values for correct message
                alert(`Processing session "${sessionName}" created successfully with ${selectedCount} files!`);
                
                // Refresh processing sessions if on that tab
                if (this.activeTab === 'processing-sessions') {
                    this.loadProcessingSessions();
                }
                
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
                
                // Capture values BEFORE clearing selection
                const selectedCount = this.selectedFiles.length;
                const sessionName = this.existingSessions.find(s => s.id === this.selectedExistingSession)?.name || 'session';
                
                // Convert file IDs to integers and send as direct array (not wrapped in object)
                const fileIds = this.selectedFiles.map(id => parseInt(id, 10));
                
                console.log('Sending file IDs:', fileIds);
                
                // Send file IDs directly as array, not wrapped in object
                await axios.post(`/api/processing-sessions/${this.selectedExistingSession}/add-files`, fileIds, {
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                
                this.showAddToExistingSessionModal = false;
                this.clearSelection();
                this.errorMessage = '';
                
                // Use captured values for correct message
                alert(`${selectedCount} files added to "${sessionName}" successfully!`);
                
                // Refresh processing sessions if on that tab
                if (this.activeTab === 'processing-sessions') {
                    this.loadProcessingSessions();
                }
                
            } catch (error) {
                console.error('Error adding files to existing session:', error);
                
                // Provide more detailed error message
                let errorMsg = 'Failed to add files to session';
                if (error.response?.data?.detail) {
                    errorMsg += `: ${error.response.data.detail}`;
                } else if (error.message) {
                    errorMsg += `: ${error.message}`;
                }
                
                this.errorMessage = errorMsg;
            }
        },

        // Calibration Workflow Methods
        async findCalibrationFiles(sessionId) {
            try {
                // Close the session details modal if it's open
                if (this.showSessionDetailsModal) {
                    this.showSessionDetailsModal = false;
                }
                
                this.calibrationLoading = true;
                this.calibrationMatches = {};
                this.selectedCalibrationTypes = {};
                
                // Get session details
                const sessionResponse = await axios.get(`/api/processing-sessions/${sessionId}`);
                this.currentCalibrationSession = sessionResponse.data;
                
                // Find calibration matches
                const response = await axios.get(`/api/processing-sessions/${sessionId}/calibration-matches`);
                this.calibrationMatches = response.data;
                
                // Initialize selection state - default all types to selected
                Object.keys(this.calibrationMatches).forEach(frameType => {
                    this.selectedCalibrationTypes[frameType] = true;
                });
                
                this.showCalibrationModal = true;
                
            } catch (error) {
                console.error('Error finding calibration files:', error);
                this.errorMessage = `Failed to find calibration files: ${error.response?.data?.detail || error.message}`;
            } finally {
                this.calibrationLoading = false;
            }
        },
        
        async addSelectedCalibrationFiles() {
            try {
                if (this.getSelectedCalibrationCount() === 0) {
                    // Close modal and show error popup
                    this.closeCalibrationModal();
                    alert('No calibration files selected');
                    return;
                }
                
                // Clear any previous errors
                this.errorMessage = '';
                
                // Prepare selected matches for API
                const selectedMatches = {};
                Object.keys(this.selectedCalibrationTypes).forEach(frameType => {
                    if (this.selectedCalibrationTypes[frameType]) {
                        selectedMatches[frameType] = this.calibrationMatches[frameType];
                    }
                });
                
                // Collect all file IDs from selected matches
                const allFileIds = [];
                Object.values(selectedMatches).forEach(matches => {
                    matches.forEach(match => {
                        allFileIds.push(...match.file_ids);
                    });
                });
                
                if (allFileIds.length === 0) {
                    // Close modal and show error popup
                    this.closeCalibrationModal();
                    alert('No files to add');
                    return;
                }
                
                // CAPTURE VALUES BEFORE MAKING API CALL (before modal can be closed)
                const sessionName = this.currentCalibrationSession.name;
                const sessionId = this.currentCalibrationSession.id;
                const fileCount = allFileIds.length;
                const selectedTypes = Object.keys(selectedMatches).join(', ');
                
                // Add files to session using existing API
                await axios.post(`/api/processing-sessions/${sessionId}/add-files`, allFileIds);
                
                // Close modal BEFORE showing success message
                this.closeCalibrationModal();
                
                // Show success message using captured values
                alert(`Successfully added ${fileCount} calibration files (${selectedTypes}) to session "${sessionName}"`);
                
                // Refresh processing sessions if on that tab
                if (this.activeTab === 'processing-sessions') {
                    this.loadProcessingSessions();
                }
                
            } catch (error) {
                console.error('Error adding calibration files:', error);
                
                // Extract the specific error message from the response
                let errorMessage = 'Failed to add calibration files';
                if (error.response?.data?.detail) {
                    errorMessage = error.response.data.detail;
                } else if (error.message) {
                    errorMessage = error.message;
                }
                
                // Close modal and show error as popup alert (like success case)
                this.closeCalibrationModal();
                alert(`Error: ${errorMessage}`);
                
                // Refresh processing sessions to show current state
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

        // Helper methods for calibration modal
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

        async viewProcessingSession(sessionId) {
            try {
                this.sessionDetailsLoading = true;
                this.currentSessionDetails = null;
                this.showSessionDetailsModal = true;
                
                // Get detailed session information
                const response = await axios.get(`/api/processing-sessions/${sessionId}`);
                this.currentSessionDetails = response.data;
                
            } catch (error) {
                console.error('Error loading session details:', error);
                this.errorMessage = `Failed to load session details: ${error.response?.data?.detail || error.message}`;
                this.showSessionDetailsModal = false;
            } finally {
                this.sessionDetailsLoading = false;
            }
        },

        closeSessionDetailsModal() {
            this.showSessionDetailsModal = false;
            this.currentSessionDetails = null;
            this.sessionDetailsLoading = false;
            this.errorMessage = '';
        },
        
        // API Methods
        async loadStats() {
            try {
                this.loading = true;
                const response = await axios.get('/api/stats');
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
                const response = await axios.get('/api/filter-options');
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
                
                const params = new URLSearchParams({
                    page: this.filePagination.page,
                    limit: this.filePagination.limit,
                    sort_by: this.fileSorting.sort_by,
                    sort_order: this.fileSorting.sort_order
                });
                
                // Add filters
                for (const [key, values] of Object.entries(this.fileFilters)) {
                    if (values.length > 0) {
                        params.append(key, values.join(','));
                    }
                }
                
                for (const [key, value] of Object.entries(this.searchFilters)) {
                    if (value) {
                        params.append(key, value);
                    }
                }
                
                const response = await axios.get(`/api/files?${params}`);
                this.files = response.data.files;
                this.filePagination.total = response.data.pagination.total;
                this.filePagination.pages = response.data.pagination.pages;
                
                // Don't clear selection when navigating pages
                // Selection is maintained across page changes
                
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
                
                const params = new URLSearchParams({
                    page: this.imagingSessionPagination.page,
                    limit: this.imagingSessionPagination.limit
                });
                
                // Add filters
                for (const [key, values] of Object.entries(this.imagingSessionFilters)) {
                    if (Array.isArray(values) && values.length > 0) {
                        params.append(key, values.join(','));
                    } else if (!Array.isArray(values) && values) {
                        params.append(key, values);
                    }
                }
                
                const response = await axios.get(`/api/imaging-sessions?${params}`);
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
        
        async loadProcessingSessions() {
            try {
                this.loading = true;
                
                const params = new URLSearchParams({
                    page: this.processingSessionPagination.page,
                    limit: this.processingSessionPagination.limit
                });
                
                if (this.processingSessionStatusFilter) {
                    params.append('status', this.processingSessionStatusFilter);
                }
                
                const response = await axios.get(`/api/processing-sessions?${params}`);
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
        
        // Filter Methods
        toggleFilterOption(filterName, option) {
            const index = this.fileFilters[filterName].indexOf(option);
            if (index > -1) {
                this.fileFilters[filterName].splice(index, 1);
            } else {
                this.fileFilters[filterName].push(option);
            }
            this.filePagination.page = 1;
            
            // Clear selection when filters change
            this.clearSelection();
            
            this.loadFiles();
        },
        
        toggleFilter(filterName) {
            this.activeFilter = this.activeFilter === filterName ? null : filterName;
        },
        
        getFilterText(filterName) {
            const count = this.fileFilters[filterName].length;
            if (count === 0) return `All ${filterName}`;
            if (count === 1) return this.fileFilters[filterName][0];
            return `${count} selected`;
        },
        
        // Imaging Session Filter Methods
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
        
        // Filter utility methods
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
            
            // Clear selection when filters reset
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
        
        // Sorting Methods
        sortBy(column) {
            if (this.fileSorting.sort_by === column) {
                this.fileSorting.sort_order = this.fileSorting.sort_order === 'asc' ? 'desc' : 'asc';
            } else {
                this.fileSorting.sort_by = column;
                this.fileSorting.sort_order = 'desc';
            }
            this.loadFiles();
        },
        
        // Navigation Methods
        navigateToSession(sessionId) {
            if (sessionId && sessionId !== 'N/A') {
                this.activeTab = 'imaging-sessions';
                this.searchFilters.session_id = sessionId;
                this.loadFiles();
            }
        },
        
        // Pagination Methods
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
        
        prevImagingSessionPage() {
            if (this.imagingSessionPagination.page > 1) {
                this.imagingSessionPagination.page--;
                this.loadImagingSessions();
            }
        },
        
        nextImagingSessionPage() {
            if (this.imagingSessionPagination.page < this.imagingSessionPagination.pages) {
                this.imagingSessionPagination.page++;
                this.loadImagingSessions();
            }
        },
        
        prevProcessingSessionPage() {
            if (this.processingSessionPagination.page > 1) {
                this.processingSessionPagination.page--;
                this.loadProcessingSessions();
            }
        },
        
        nextProcessingSessionPage() {
            if (this.processingSessionPagination.page < this.processingSessionPagination.pages) {
                this.processingSessionPagination.page++;
                this.loadProcessingSessions();
            }
        },
        
        // Processing Session Management
        showCreateProcessingSessionModal() {
            this.newProcessingSession = {
                name: '',
                fileIds: '',
                notes: ''
            };
            this.showCreateModal = true;
        },
        
        async createProcessingSession() {
            try {
                if (!this.newProcessingSession.name.trim()) {
                    this.errorMessage = 'Session name is required';
                    return;
                }
                
                if (!this.newProcessingSession.fileIds.trim()) {
                    this.errorMessage = 'File IDs are required';
                    return;
                }
                
                const fileIds = this.newProcessingSession.fileIds
                    .split(',')
                    .map(id => parseInt(id.trim()))
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
                
                await axios.post('/api/processing-sessions', payload);
                
                this.showCreateModal = false;
                this.loadProcessingSessions();
                this.errorMessage = '';
                alert(`Processing session "${this.newProcessingSession.name}" created successfully with ${fileIds.length} files!`);
                
            } catch (error) {
                console.error('Error creating processing session:', error);
                this.errorMessage = `Failed to create processing session: ${error.response?.data?.detail || error.message}`;
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
                
                await axios.put(`/api/processing-sessions/${sessionId}/status`, payload);
                
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
                
                await axios.delete(`/api/processing-sessions/${sessionId}?remove_files=${removeFiles}`);
                
                this.loadProcessingSessions();
                alert('Processing session deleted successfully');
                
            } catch (error) {
                console.error('Error deleting processing session:', error);
                this.errorMessage = `Failed to delete processing session: ${error.response?.data?.detail || error.message}`;
            }
        },
        
        // Utility Methods
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
        }
    },
    
    // Lifecycle Methods
    async mounted() {
        // Load initial data
        await this.loadStats();
        await this.loadFilterOptions();
        
        // Load data based on active tab
        if (this.activeTab === 'files') {
            await this.loadFiles();
        } else if (this.activeTab === 'imaging-sessions') {
            await this.loadImagingSessions();
        } else if (this.activeTab === 'processing-sessions') {
            await this.loadProcessingSessions();
        }
        
        // Close selection dropdown when clicking elsewhere
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.relative')) {
                this.showSelectionOptions = false;
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                // Close any open modals
                this.showCreateModal = false;
                this.showAddToNewModal = false;
                this.showAddToExistingSessionModal = false;
                this.showCalibrationModal = false;
                this.showSessionDetailsModal = false;
            }
        });
    },
    
    watch: {
        // Watch for tab changes and load appropriate data
        activeTab(newTab) {
            this.errorMessage = ''; // Clear any errors when switching tabs
            
            if (newTab === 'files' && this.files.length === 0) {
                this.loadFiles();
            } else if (newTab === 'imaging-sessions' && this.imagingSessions.length === 0) {
                this.loadImagingSessions();
            } else if (newTab === 'processing-sessions' && this.processingSessions.length === 0) {
                this.loadProcessingSessions();
            }
        },
        
        // Watch for search filter changes and reload files
        searchFilters: {
            handler() {
                this.filePagination.page = 1;
                this.clearSelection(); // Clear selection when search changes
                this.loadFiles();
            },
            deep: true
        },
        
        // Watch for processing session status filter changes
        processingSessionStatusFilter() {
            this.processingSessionPagination.page = 1;
            this.loadProcessingSessions();
        }
    }
}).mount('#app');