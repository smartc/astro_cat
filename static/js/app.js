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
            sessionPagination: { page: 1, limit: 20, total: 0, pages: 0 },
            fileFilters: {
                frame_types: [],
                cameras: [],
                telescopes: [],
                objects: [],
                filters: []
            },
            sessionFilters: {
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
            activeSessionFilter: null,
            fileSorting: {
                sort_by: 'obs_date',
                sort_order: 'desc'
            },
            objectSearchText: '',
            loading: false,
            errorMessage: ''
        }
    },
    
    computed: {
        hasActiveFilters() {
            return Object.values(this.fileFilters).some(arr => arr.length > 0) ||
                   Object.values(this.searchFilters).some(val => val !== '');
        },
        
        hasActiveSessionFilters() {
            return Object.values(this.sessionFilters).some(val => {
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
        
        async loadSessions() {
            try {
                this.loading = true;
                const params = {
                    page: this.sessionPagination.page,
                    limit: this.sessionPagination.limit
                };
                
                // Add session filters
                for (const [key, values] of Object.entries(this.sessionFilters)) {
                    if (Array.isArray(values) && values.length > 0) {
                        params[key] = values.join(',');
                    } else if (!Array.isArray(values) && values) {
                        params[key] = values;
                    }
                }
                
                const response = await axios.get('/api/sessions', { params });
                this.sessions = response.data.sessions;
                this.sessionPagination = response.data.pagination;
            } catch (error) {
                console.error('Error loading sessions:', error);
                this.errorMessage = 'Failed to load sessions: ' + error.message;
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
        
        // Session Filter Methods
        toggleSessionFilter(filterName) {
            this.activeSessionFilter = this.activeSessionFilter === filterName ? null : filterName;
        },
        
        toggleSessionFilterOption(filterName, option) {
            const index = this.sessionFilters[filterName].indexOf(option);
            if (index > -1) {
                this.sessionFilters[filterName].splice(index, 1);
            } else {
                this.sessionFilters[filterName].push(option);
            }
        },
        
        getSessionFilterText(filterName) {
            const count = this.sessionFilters[filterName].length;
            if (count === 0) return `All ${filterName}`;
            if (count === 1) return this.sessionFilters[filterName][0];
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
        
        resetSessionFilters() {
            for (const key of Object.keys(this.sessionFilters)) {
                if (Array.isArray(this.sessionFilters[key])) {
                    this.sessionFilters[key] = [];
                } else {
                    this.sessionFilters[key] = '';
                }
            }
            this.activeSessionFilter = null;
            this.sessionPagination.page = 1;
            this.loadSessions();
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
        
        // Session Pagination Methods
        prevSessionPage() {
            if (this.sessionPagination.page > 1) {
                this.sessionPagination.page--;
                this.loadSessions();
            }
        },
        
        nextSessionPage() {
            if (this.sessionPagination.page < this.sessionPagination.pages) {
                this.sessionPagination.page++;
                this.loadSessions();
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
        
        // Event Handlers
        handleDocumentClick(e) {
            // Close dropdowns when clicking outside
            if (!e.target.closest('.relative')) {
                this.activeFilter = null;
                this.activeSessionFilter = null;
            }
        },
        
        handleKeydown(event) {
            // ESC to close dropdowns
            if (event.key === 'Escape') {
                this.activeFilter = null;
                this.activeSessionFilter = null;
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
        },
        
        sessionFilters: {
            handler() {
                this.sessionPagination.page = 1;
                this.loadSessions();
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