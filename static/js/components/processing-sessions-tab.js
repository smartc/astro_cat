// ============================================================================
// FILE: static/js/components/processing-sessions-tab.js
// ============================================================================
const ProcessingSessionsTab = {
    template: `
        <div class="space-y-6">
            <div class="bg-white rounded-lg shadow p-4">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-xl font-bold">Processing Sessions</h2>
                    <div class="flex space-x-4 items-center">
                        <button @click="showCreateProcessingSessionModal" class="btn btn-green">Create Session</button>
                        <button @click="loadProcessingSessions" class="btn btn-blue">Refresh</button>
                    </div>
                </div>
                
                <div class="mb-4">
                    <label class="block text-xs font-medium text-gray-700 mb-1">Status Filter</label>
                    <select v-model="processingSessionStatusFilter" @change="loadProcessingSessions" class="border border-gray-300 rounded px-3 py-2">
                        <option value="">All Statuses</option>
                        <option value="not_started">Not Started</option>
                        <option value="in_progress">In Progress</option>
                        <option value="complete">Complete</option>
                    </select>
                </div>
            </div>

            <div class="bg-white rounded-lg shadow">
                <div class="p-6">
                    <div v-if="processingSessions.length === 0" class="text-center py-8 text-gray-500">
                        <div class="text-6xl mb-4">📁</div>
                        <p class="text-lg">No processing sessions found</p>
                        <p class="text-sm">Create your first processing session to get started</p>
                    </div>
                    <div v-else class="space-y-4">
                        <div v-for="session in processingSessions" :key="session.id" 
                             @click="viewProcessingSession(session.id)"
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
                                        <p class="text-sm text-gray-700 bg-gray-50 p-2 rounded">{{ session.notes }}</p>
                                    </div>
                                </div>
                                <div class="flex flex-col space-y-2 ml-4">
                                    <button @click.stop="findCalibrationFiles(session.id)" class="btn btn-purple text-sm">🔍 Find Calibration</button>
                                    <button @click.stop="updateProcessingSessionStatus(session.id)" class="btn btn-yellow text-sm">Update Status</button>
                                    <button @click.stop="deleteProcessingSession(session.id)" class="btn btn-red text-sm">Delete</button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div v-if="processingSessions.length > 0" class="pagination-container">
                    <div class="flex items-center justify-between">
                        <div class="text-sm text-gray-700">
                            Showing {{ (processingSessionPagination.page - 1) * processingSessionPagination.limit + 1 }} to 
                            {{ Math.min(processingSessionPagination.page * processingSessionPagination.limit, processingSessionPagination.total) }} 
                            of {{ processingSessionPagination.total }} sessions
                        </div>
                        <div class="flex space-x-2">
                            <button @click="prevProcessingSessionPage" :disabled="processingSessionPagination.page <= 1" class="pagination-button">Previous</button>
                            <span class="px-3 py-1 text-sm text-gray-700">Page {{ processingSessionPagination.page }} of {{ processingSessionPagination.pages }}</span>
                            <button @click="nextProcessingSessionPage" :disabled="processingSessionPagination.page >= processingSessionPagination.pages" class="pagination-button">Next</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    methods: ProcessingSessionsComponent.methods,
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