/**
 * Files Browser Component
 * Handles file browsing, filtering, selection, and sorting
 */

const FilesBrowserComponent = {
    data() {
        return {
            // Files Data
            files: [],
            filePagination: { page: 1, limit: 50, total: 0, pages: 0 },
            
            // Filters
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
            
            // Filter UI State
            activeFilter: null,
            objectSearchText: '',
            
            // Sorting
            fileSorting: {
                sort_by: 'obs_date',
                sort_order: 'desc'
            },
            
            // Selection
            selectedFiles: [],
            allFilteredFilesSelected: false,
            selectAllMode: 'page',
            showSelectionOptions: false,
        };
    },
    
    computed: {
        hasActiveFilters() {
            return Object.values(this.fileFilters).some(val => val.length > 0) ||
                   Object.values(this.searchFilters).some(val => val !== '');
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
        },

        allFilesSelected() {
            return this.allFilteredFilesSelected;
        },
        
        currentPageSelectedCount() {
            return this.files.filter(f => this.selectedFiles.includes(f.id)).length;
        },
        
        selectionSummaryText() {
            if (this.selectedFiles.length === 0) return '';
            if (this.allFilteredFilesSelected) {
                return `All ${this.selectedFiles.length} filtered files selected`;
            }
            return `${this.selectedFiles.length} file${this.selectedFiles.length === 1 ? '' : 's'} selected`;
        }
    },
    
    methods: {
        // ==================
        // Loading Methods
        // ==================
        
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
        
        // ==================
        // Filter Methods
        // ==================
        
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
        
        filterObjectOptions() {
            // Triggers computed property update
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
        
        // ==================
        // Selection Methods
        // ==================
        
        toggleSelectAll() {
            if (this.selectAllMode === 'all') {
                this.toggleSelectAllFiltered();
            } else {
                this.toggleSelectCurrentPage();
            }
        },
        
        toggleSelectCurrentPage() {
            if (this.isCurrentPageFullySelected) {
                const currentPageIds = this.files.map(file => file.id);
                this.selectedFiles = this.selectedFiles.filter(id => !currentPageIds.includes(id));
                this.allFilteredFilesSelected = false;
            } else {
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
            
            if (!this.files.map(f => f.id).includes(fileId)) {
                this.allFilteredFilesSelected = false;
            }
        },
        
        clearSelection() {
            this.selectedFiles = [];
            this.allFilteredFilesSelected = false;
        },
        
        // ==================
        // Sorting Methods
        // ==================
        
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
        
        // ==================
        // Pagination Methods
        // ==================
        
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
        
        // ==================
        // Navigation Methods
        // ==================
        
        navigateToSession(sessionId) {
            if (sessionId && sessionId !== 'N/A') {
                this.activeTab = 'imaging-sessions';
                this.searchFilters.session_id = sessionId;
                this.loadFiles();
            }
        }
    }
};

// Export for use in main app
window.FilesBrowserComponent = FilesBrowserComponent;