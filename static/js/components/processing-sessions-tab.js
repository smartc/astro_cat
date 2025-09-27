/**
 * Processing Sessions Tab Component
 */

const ProcessingSessionsTab = {
    template: `
        <div class="space-y-6">
            <!-- Processing Session Controls -->
            <div class="bg-white rounded-lg shadow p-4">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-xl font-bold">Processing Sessions</h2>
                    <div class="flex space-x-4 items-center">
                        <button @click="$root.showCreateProcessingSessionModal()" class="btn btn-green">
                            Create Session
                        </button>
                        <button @click="$root.loadProcessingSessions" class="btn btn-blue">Apply Filters</button>
                    </div>
                </div>
                
                <!-- Status Filter -->
                <div class="mb-4">
                    <label class="block text-xs font-medium text-gray-700 mb-1">Status Filter</label>
                    <select v-model="processingSessionStatusFilter" @change="$root.loadProcessingSessions" class="border border-gray-300 rounded px-3 py-2">
                        <option value="">All Statuses</option>
                        <option value="not_started">Not Started</option>
                        <option value="in_progress">In Progress</option>
                        <option value="complete">Complete</option>
                    </select>
                </div>
            </div>

            <!-- Processing Sessions List -->
            <div class="bg-white rounded-lg shadow">
                <div class="p-6">
                    <div v-if="processingSessions.length === 0" class="text-center py-8 text-gray-500">
                        <div class="text-6xl mb-4">📁</div>
                        <p class="text-lg">No processing sessions found</p>
                        <p class="text-sm">Create your first processing session to get started</p>
                    </div>
                    <div v-else class="space-y-4">
                        <div v-for="session in processingSessions" :key="session.id" 
                             @click="$root.viewProcessingSession(session.id)"
                             class="bg-white rounded-lg shadow hover:shadow-md transition-shadow p-4 cursor-pointer border border-gray-200">
                            <div class="flex justify-between items-start">
                                <div class="flex-grow">
                                    <div class="flex items-center space-x-3">
                                        <h3 class="font-semibold text-lg">{{ session.name }}</h3>
                                        <span :class="getProcessingStatusClass(session.status)" class="processing-status-badge">
                                            {{ formatProcessingStatus(session.status) }}
                                        </span>
                                    </div>
                                    <p class="text-sm text-gray-500 mt-1">{{ session.id }}</p>
                                    <div class="mt-2">
                                        <p class="text-sm text-gray-600">
                                            <strong>Objects:</strong> {{ session.objects.join(', ') || 'None specified' }}
                                        </p>
                                        <p class="text-sm text-gray-600">
                                            <strong>Files:</strong> {{ session.total_files }} total 
                                            ({{ session.lights }}L, {{ session.darks }}D, {{ session.flats }}F, {{ session.bias }}B)
                                        </p>
                                        <p class="text-sm text-gray-500">
                                            Created: {{ formatDate(session.created_at) }}
                                        </p>
                                    </div>
                                    <div v-if="session.notes" class="mt-2">
                                        <p class="text-sm text-gray-700 bg-gray-50 p-2 rounded">
                                            {{ session.notes }}
                                        </p>
                                    </div>
                                </div>
                                <div class="flex flex-col space-y-2 ml-4">
                                    <button @click.stop="$root.findCalibrationFiles(session.id)" class="btn btn-purple text-sm">
                                        🔍 Find Calibration
                                    </button>
                                    <button @click.stop="$root.updateProcessingSessionStatus(session.id)" class="btn btn-yellow text-sm">
                                        Update Status
                                    </button>
                                    <button @click.stop="$root.deleteProcessingSession(session.id)" class="btn btn-red text-sm">
                                        Delete
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Pagination -->
                <div v-if="processingSessions.length > 0" class="pagination-container">
                    <div class="flex items-center justify-between">
                        <div class="text-sm text-gray-700">
                            Showing {{ (processingSessionPagination.page - 1) * processingSessionPagination.limit + 1 }} to 
                            {{ Math.min(processingSessionPagination.page * processingSessionPagination.limit, processingSessionPagination.total) }} 
                            of {{ processingSessionPagination.total }} sessions
                        </div>
                        <div class="flex space-x-2">
                            <button @click="$root.prevProcessingSessionPage" :disabled="processingSessionPagination.page <= 1" class="pagination-button">
                                Previous
                            </button>
                            <span class="px-3 py-1 text-sm text-gray-700">
                                Page {{ processingSessionPagination.page }} of {{ processingSessionPagination.pages }}
                            </span>
                            <button @click="$root.nextProcessingSessionPage" :disabled="processingSessionPagination.page >= processingSessionPagination.pages" class="pagination-button">
                                Next
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    methods: {
        ...ProcessingSessionsComponent.methods,
        
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
        }
    },
    
    computed: {
        processingSessions() { return this.$root.processingSessions; },
        processingSessionPagination() { return this.$root.processingSessionPagination; },
        processingSessionStatusFilter: {
            get() { return this.$root.processingSessionStatusFilter; },
            set(val) { this.$root.processingSessionStatusFilter = val; }
        }
    }
};

window.ProcessingSessionsTab = ProcessingSessionsTab;