// FITS Cataloger Vue.js Application
const { createApp } = Vue;

createApp({
    data() {
        return {
            activeTab: 'dashboard',
            stats: {},
            files: [],
            sessions: [],
            filePagination: { page: 1, limit: 50, total: 0, pages: 0 },
            fileFilters: {
                frame_types: [],
                cameras: [],
                telescopes: [],
                objects: [],
                filters: []
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
            fileSorting: {
                sort_by: 'obs_date',
                sort_order: 'desc'
            },
            fileSearchText: '',
            objectSearchText: '',
            loading: false
        }
    },
    
    computed: {
        hasActiveFilters() {
            return Object.values(this.fileFilters).some(arr => arr.length > 0) ||
                   Object.values(this.searchFilters).some(val => val !== '');
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
                this.showError('Failed to load statistics');
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
                this.showError('Failed to load filter options');
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
                this.showError('Failed to load files');
            } finally {
                this.loading = false;
            }
        },
        
        async loadSessions() {
            try {
                this.loading = true;
                const response = await axios.get('/api/sessions');
                this.sessions = response.data.sessions;
            } catch (error) {
                console.error('Error loading sessions:', error);
                this.showError('Failed to load sessions');
            } finally {
                this.loading = false;
            }
        },
        
        async startOperation(type) {
            try {
                await axios.post(`/api/operations/${type}`);
                this.showSuccess(`${type} operation started`);
            } catch (error) {
                console.error(`Error starting ${type}:`, error);
                this.showError(`Failed to start ${type}: ${error.response?.data?.detail || error.message}`);
            }
        },
        
        // Filter Methods
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
        
        filterFileOptions() {
            this.searchFilters.filename = this.fileSearchText;
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
            this.fileSearchText = '';
            this.objectSearchText = '';
            this.activeFilter = null;
            this.filePagination.page = 1;
            this.loadFiles();
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
                this.activeTab = 'sessions';
                // Could add session filtering here in the future
            }
        },
        
        // Pagination Methods
        prevPage() {
            if (this.filePagination.page > 1) {
                this.filePagination.page--;
                this.loadFiles();
            }
        },
        
        nextPage() {
            if (this.filePagination.page < this.filePagination.pages) {
                this.filePagination.page++;
                this.loadFiles();
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
        
        formatDate(dateString) {
            if (!dateString) return 'N/A';
            return new Date(dateString).toLocaleDateString();
        },
        
        formatExposure(exposure) {
            if (!exposure) return 'N/A';
            return `${exposure}s`;
        },
        
        // Notification Methods
        showError(message) {
            // Simple alert for now - could be replaced with toast notifications
            alert(`Error: ${message}`);
        },
        
        showSuccess(message) {
            // Simple alert for now - could be replaced with toast notifications
            alert(`Success: ${message}`);
        },
        
        // Keyboard shortcuts
        handleKeydown(event) {
            // ESC to close dropdowns
            if (event.key === 'Escape') {
                this.activeFilter = null;
            }
            
            // Ctrl/Cmd + R to refresh
            if ((event.ctrlKey || event.metaKey) && event.key === 'r') {
                event.preventDefault();
                if (this.activeTab === 'files') {
                    this.loadFiles();
                } else if (this.activeTab === 'sessions') {
                    this.loadSessions();
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
            } else if (newTab === 'sessions') {
                this.loadSessions();
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
        }
        
        // Set up event listeners
        document.addEventListener('click', this.handleDocumentClick);
        document.addEventListener('keydown', this.handleKeydown);
    },
    
    beforeUnmount() {
        // Clean up event listeners
        document.removeEventListener('click', this.handleDocumentClick);
        document.removeEventListener('keydown', this.handleKeydown);
    },
    
    methods: {
        ...this.methods,
        
        // Additional event handlers
        handleDocumentClick(e) {
            // Close dropdowns when clicking outside
            if (!e.target.closest('.relative')) {
                this.activeFilter = null;
            }
        }
    }
}).mount('#app');