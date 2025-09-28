/**
 * Processing Sessions Component
 * Handles processing session list and operations (not modals)
 */

const ProcessingSessionsComponent = {
    data() {
        return {
            // Processing Sessions Data
            processingSessions: [],
            processingSessionPagination: { page: 1, limit: 20, total: 0, pages: 0 },
            processingSessionStatusFilter: '',
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
        
        // ==================
        // CRUD Operations
        // ==================
        
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
                await refreshStats();
                //this.loadProcessingSessions();
                
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
        }
    }
};

// Export for use in main app
window.ProcessingSessionsComponent = ProcessingSessionsComponent;