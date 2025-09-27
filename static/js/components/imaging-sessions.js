// Imaging Sessions Component
// Handles imaging session list, filtering, and pagination

window.ImagingSessionsComponent = {
    data() {
        return {
            // Imaging Sessions
            imagingSessions: [],
            imagingSessionPagination: { page: 1, limit: 20, total: 0, pages: 0 },
            imagingSessionFilters: {
                date_start: '',
                date_end: '',
                cameras: [],
                telescopes: []
            },
            activeImagingSessionFilter: null,
        };
    },

    computed: {
        // Filter text helpers
        getImagingSessionFilterText() {
            return (filterType) => {
                const selected = this.imagingSessionFilters[filterType];
                if (!selected || selected.length === 0) {
                    return filterType === 'cameras' ? 'All Cameras' : 'All Telescopes';
                }
                if (selected.length === 1) {
                    return selected[0];
                }
                return `${selected.length} selected`;
            };
        },

        hasActiveImagingSessionFilters() {
            return this.imagingSessionFilters.date_start !== '' ||
                   this.imagingSessionFilters.date_end !== '' ||
                   this.imagingSessionFilters.cameras.length > 0 ||
                   this.imagingSessionFilters.telescopes.length > 0;
        },
    },

    methods: {
        // ===================
        // Imaging Sessions Methods
        // ===================
        
        async loadImagingSessions() {
            try {
                const params = {
                    page: this.imagingSessionPagination.page,
                    limit: this.imagingSessionPagination.limit,
                    date_start: this.imagingSessionFilters.date_start || undefined,
                    date_end: this.imagingSessionFilters.date_end || undefined,
                    cameras: this.imagingSessionFilters.cameras.length > 0 
                        ? this.imagingSessionFilters.cameras.join(',') 
                        : undefined,
                    telescopes: this.imagingSessionFilters.telescopes.length > 0 
                        ? this.imagingSessionFilters.telescopes.join(',') 
                        : undefined
                };

                const response = await ApiService.imagingSessions.getAll(params);  // USE getSessions
                this.imagingSessions = response.data.sessions;
                this.imagingSessionPagination = response.data.pagination;
                
            } catch (error) {
                console.error('Error loading imaging sessions:', error);
                this.errorMessage = 'Failed to load imaging sessions: ' + error.message;
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

        toggleImagingSessionFilter(filterType) {
            this.activeImagingSessionFilter = 
                this.activeImagingSessionFilter === filterType ? null : filterType;
        },

        toggleImagingSessionFilterOption(filterType, option) {
            const index = this.imagingSessionFilters[filterType].indexOf(option);
            if (index > -1) {
                this.imagingSessionFilters[filterType].splice(index, 1);
            } else {
                this.imagingSessionFilters[filterType].push(option);
            }
            this.imagingSessionPagination.page = 1;
            this.loadImagingSessions();
        },

        resetImagingSessionFilters() {
            this.imagingSessionFilters = {
                date_start: '',
                date_end: '',
                cameras: [],
                telescopes: []
            };
            this.imagingSessionPagination.page = 1;
            this.loadImagingSessions();
        },

        viewSessionDetails(sessionId) {
            // Access the component via ref
            this.$refs.sessionDetailModal.viewSessionDetails(sessionId);
        },

    }
};

// Export for use in main app
if (typeof module !== 'undefined' && module.exports) {
    module.exports = window.ImagingSessionsComponent;
}