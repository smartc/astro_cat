// FITS Cataloger Vue.js Application - Complete with Processing Sessions
const { createApp } = Vue;

createApp({
    data() {
        return {
            activeTab: 'dashboard',
            stats: {},
            files: [],
            imagingSessions: [],
            processingSessions: [],
            filePagination: { page: 1, limit: 50, total: 0, pages: 0 },
            imagingSessionPagination: { page: 1, limit: 20, total: 0, pages: 0 },
            processingSessionPagination: { page: 1, limit: 20, total: 0, pages: 0 },
            fileFilters: {
                frame_types: [],
                cameras: [],
                telescopes: [],
                objects: [],
                filters: []
            },
        
        // File Selection Methods
        toggleFileSelection(fileId) {
            const index = this.selectedFiles.indexOf(fileId);
            if (index > -1) {
                this.selectedFiles.splice(index, 1);
            } else {
                this.selectedFiles.push(fileId);
            }
        },
        
        toggleSelectAll() {
            if (this.allFilesSelected) {
                this.selectedFiles = [];
            } else {
                this.selectedFiles = this.files.map(file => file.id);
            }
        },
        
        clearSelection() {
            this.selectedFiles = [];
        },
        
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
            this.showAddToExistingModal = true;
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
                
                const payload = {
                    name: this.newSessionFromFiles.name.trim(),
                    file_ids: this.selectedFiles,
                    notes: this.newSessionFromFiles.notes.trim() || null
                };
                
                await axios.post('/api/processing-sessions', payload);
                
                this.showAddToNewModal = false;
                this.clearSelection();
                alert(`Processing session "${this.newSessionFromFiles.name}" created successfully with ${this.selectedFiles.length} files!`);
                
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
                
                await axios.post(`/api/processing-sessions/${this.selectedExistingSession}/add-files`, {
                    file_ids: this.selectedFiles
                });
                
                this.showAddToExistingModal = false;
                this.clearSelection();
                
                const sessionName = this.existingSessions.find(s => s.id === this.selectedExistingSession)?.name || 'session';
                alert(`${this.selectedFiles.length} files added to "${sessionName}" successfully!`);
                
            } catch (error) {
                console.error('Error adding files to existing session:', error);
                this.errorMessage = `Failed to add files to session: ${error.response?.data?.detail || error.message}`;
            }
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
            activeFilter: null,
            activeImagingSessionFilter: null,
            fileSorting: {
                sort_by: 'obs_date',
                sort_order: 'desc'
            },
            objectSearchText: '',
            processingSessionStatusFilter: '',
            showCreateModal: false,
            showAddToNewModal: false,
            showAddToExistingModal: false,
            selectedFiles: [],
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
            loading: false,
            errorMessage: ''
        }
    },
    
    computed: {
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
                const params = {
                    page: this.filePagination.page,
                    limit: this.filePagination.limit,
                    sort_by: this.fileSorting.sort_by,
                    sort_order: this.fileSorting.sort_order
                };
                
                // Add multi-select filters
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
                
                const response = await axios.get('/api/files', { params });
                this.files = response.data.files;
                this.filePagination = response.data.pagination;
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
                
                // Add session filters
                for (const [key, values] of Object.entries(this.imagingSessionFilters)) {
                    if (Array.isArray(values) && values.length > 0) {
                        params[key] = values.join(',');
                    } else if (!Array.isArray(values) && values) {
                        params[key] = values;
                    }
                }
                
                const response = await axios.get('/api/imaging-sessions', { params });
                this.imagingSessions = response.data.sessions;
                this.imagingSessionPagination = response.data.pagination;
            } catch (error) {
                console.error('Error loading imaging sessions:', error);
                this.errorMessage = 'Failed to load imaging sessions: ' + error.message;
            } finally {
                this.loading = false;
            }
        },
        
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
                
                const response = await axios.get('/api/processing-sessions', { params });
                this.processingSessions = response.data.sessions;
                this.processingSessionPagination = response.data.pagination;
            } catch (error) {
                console.error('Error loading processing sessions:', error);
                this.errorMessage = 'Failed to load processing sessions: ' + error.message;
            } finally {
                this.loading = false;
            }
        },
        
        async startOperation(type) {
            try {
                const response = await axios.post(`/api/operations/${type}`);
                alert(`${type} operation started successfully`);
            } catch (error) {
                console.error(`Error starting ${type}:`, error);
                this.errorMessage = `Failed to start ${type}: ${error.response?.data?.detail || error.message}`;
            }
        },
        
        // File Filter Methods
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
        },
        
        getImagingSessionFilterText(filterName) {
            const count = this.imagingSessionFilters[filterName].length;
            if (count === 0) return `All ${filterName}`;
            if (count === 1) return this.imagingSessionFilters[filterName][0];
            return `${count} selected`;
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
        
        // Processing Session Methods
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
                
                // Parse file IDs
                const fileIds = this.newProcessingSession.fileIds
                    .split(',')
                    .map(id => parseInt(id.trim()))
                    .filter(id => !isNaN(id));
                
                if (fileIds.length === 0) {
                    this.errorMessage = 'Please provide valid file IDs';
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
                alert('Processing session created successfully!');
                
            } catch (error) {
                console.error('Error creating processing session:', error);
                this.errorMessage = `Failed to create processing session: ${error.response?.data?.detail || error.message}`;
            }
        },
        
        async viewProcessingSession(sessionId) {
            try {
                const response = await axios.get(`/api/processing-sessions/${sessionId}`);
                const session = response.data;
                
                let message = `Processing Session: ${session.name}\n\n`;
                message += `Status: ${this.formatProcessingStatus(session.status)}\n`;
                message += `Objects: ${session.objects.join(', ') || 'None'}\n`;
                message += `Files: ${session.total_files} total (${session.lights}L, ${session.darks}D, ${session.flats}F, ${session.bias}B)\n`;
                message += `Folder: ${session.folder_path}\n`;
                message += `Created: ${this.formatDate(session.created_at)}\n`;
                if (session.notes) {
                    message += `\nNotes: ${session.notes}`;
                }
                
                alert(message);
                
            } catch (error) {
                console.error('Error viewing processing session:', error);
                this.errorMessage = `Failed to load processing session details: ${error.message}`;
            }
        },
        
        async updateProcessingSessionStatus(sessionId) {
            try {
                const statuses = ['not_started', 'in_progress', 'complete'];
                const statusLabels = ['Not Started', 'In Progress', 'Complete'];
                
                let choice = prompt(
                    'Select new status:\n' + 
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
        
        // Sorting Methods
        sortBy(column) {
            if (this.fileSorting.sort_by === column) {
                this.fileSorting.sort_order = this.fileSorting.sort_order === 'asc' ? 'desc' : 'asc';
            } else {
                this.fileSorting.sort_by = column;
                this.fileSorting.sort_order = 'desc';
            }
            this.filePagination.page = 1;
            this.loadFiles();
        },
        
        // Navigation Methods
        navigateToSession(sessionId) {
            if (sessionId && sessionId !== 'N/A') {
                this.activeTab = 'imaging-sessions';
            }
        },
        
        // File Pagination Methods
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
        
        // Imaging Session Pagination Methods
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
        
        // Processing Session Pagination Methods
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
        
        formatExposure(exposure) {
            if (!exposure) return 'N/A';
            return `${exposure}s`;
        },
        
        // Event Handlers
        handleDocumentClick(e) {
            // Close dropdowns when clicking outside
            if (!e.target.closest('.relative')) {
                this.activeFilter = null;
                this.activeImagingSessionFilter = null;
            }
        },
        
        handleKeydown(event) {
            // ESC to close dropdowns and modals
            if (event.key === 'Escape') {
                this.activeFilter = null;
                this.activeImagingSessionFilter = null;
                this.showCreateModal = false;
            }
            
            // Ctrl/Cmd + R to refresh
            if ((event.ctrlKey || event.metaKey) && event.key === 'r') {
                event.preventDefault();
                if (this.activeTab === 'files') {
                    this.loadFiles();
                } else if (this.activeTab === 'imaging-sessions') {
                    this.loadImagingSessions();
                } else if (this.activeTab === 'processing-sessions') {
                    this.loadProcessingSessions();
                } else if (this.activeTab === 'dashboard') {
                    this.loadStats();
                }
            }
        }
    },
    
    // Watchers
    watch: {
        activeTab(newTab) {
            if (newTab === 'files') {
                this.loadFiles();
            } else if (newTab === 'imaging-sessions') {
                this.loadImagingSessions();
            } else if (newTab === 'processing-sessions') {
                this.loadProcessingSessions();
            } else if (newTab === 'dashboard') {
                this.loadStats();
            }
        },
        
        fileFilters: {
            handler() {
                this.filePagination.page = 1;
                this.loadFiles();
            },
            deep: true
        },
        
        searchFilters: {
            handler() {
                this.filePagination.page = 1;
                this.loadFiles();
            },
            deep: true
        },
        
        imagingSessionFilters: {
            handler() {
                this.imagingSessionPagination.page = 1;
                this.loadImagingSessions();
            },
            deep: true
        }
    },
    
    // Lifecycle Methods
    async mounted() {
        try {
            // Load initial data
            await Promise.all([
                this.loadStats(),
                this.loadFilterOptions()
            ]);
        } catch (error) {
            console.error('Error during app initialization:', error);
            this.errorMessage = 'Failed to initialize application';
        }
        
        // Set up event listeners
        document.addEventListener('click', this.handleDocumentClick);
        document.addEventListener('keydown', this.handleKeydown);
    },
    
    beforeUnmount() {
        // Clean up event listeners
        document.removeEventListener('click', this.handleDocumentClick);
        document.removeEventListener('keydown', this.handleKeydown);
    }
}).mount('#app');