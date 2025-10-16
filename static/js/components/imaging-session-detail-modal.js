// Imaging Session Detail Modal Component - Enhanced
// MINIMAL CHANGES: Added Session ID click-to-copy and Processing Sessions section

window.ImagingSessionDetailModal = {
    template: `
        <div v-if="showDetailModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4" style="z-index: 250;">
            <div class="bg-white rounded-lg w-full max-w-6xl max-h-[90vh] overflow-hidden flex flex-col">
                <!-- Modal Header with Starfield -->
                <div class="relative text-white p-4" style="min-height: 100px;">
                    <starfield-background :num-stars="30" :min-size="0.3" :max-size="0.7"></starfield-background>
                    <div class="relative z-10">
                        <div class="flex justify-between items-center">
                            <h2 class="text-xl font-bold">Imaging Session Details</h2>
                            <button @click="closeSessionDetails" class="text-white hover:text-gray-200">
                                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                                </svg>
                            </button>
                        </div>
                        <!-- NEW: Session ID (clickable to copy) -->
                        <div v-if="selectedSessionId" class="mt-2 text-sm">
                            <span class="text-gray-200 mr-2">🆔 Session ID:</span>
                            <code @click="copySessionIdToClipboard" 
                                  class="bg-white bg-opacity-20 px-2 py-1 rounded cursor-pointer hover:bg-opacity-30 transition-colors"
                                  title="Click to copy session ID">
                                {{ selectedSessionId }}
                            </code>
                        </div>
                    </div>
                </div>

                <!-- Modal Body -->
                <div class="flex-1 overflow-y-auto p-6" style="max-height: calc(90vh - 200px);">
                    <!-- Loading State -->
                    <div v-if="loadingDetails" class="flex justify-center items-center py-12">
                        <div class="spinner"></div>
                        <span class="ml-3 text-gray-600">Loading session details...</span>
                    </div>

                    <!-- Error State -->
                    <div v-else-if="detailsError" class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
                        <strong>Error:</strong> {{ detailsError }}
                    </div>

                    <!-- Session Details Content -->
                    <div v-else-if="sessionDetails" class="space-y-6">
                        <!-- Session-Level Summary -->
                        <div class="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-6 border border-blue-200">
                            <div class="flex justify-between items-start mb-4">
                                <h3 class="text-xl font-bold text-blue-900">Session Summary</h3>
                                <button @click="openMarkdownEditor" class="btn btn-green text-sm">
                                    📝 Edit Notes
                                </button>
                            </div>
                            
                            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
                                <div>
                                    <p class="text-xs text-gray-600 uppercase tracking-wide">Date</p>
                                    <p class="text-lg font-semibold text-gray-900">{{ sessionDetails.session.session_date }}</p>
                                </div>
                                <div>
                                    <p class="text-xs text-gray-600 uppercase tracking-wide">Camera</p>
                                    <p class="text-lg font-semibold text-gray-900">{{ sessionDetails.session.camera || 'N/A' }}</p>
                                </div>
                                <div>
                                    <p class="text-xs text-gray-600 uppercase tracking-wide">Telescope</p>
                                    <p class="text-lg font-semibold text-gray-900">{{ sessionDetails.session.telescope || 'N/A' }}</p>
                                </div>
                            </div>
        
                            <!-- Statistics Cards -->
                            <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4">
                                <div class="bg-white rounded-lg p-3 text-center shadow-sm">
                                    <div class="text-2xl font-bold text-blue-600">{{ sessionDetails.summary.total_files }}</div>
                                    <div class="text-xs text-gray-600">Total Files</div>
                                </div>
                                <div class="bg-white rounded-lg p-3 text-center shadow-sm">
                                    <div class="text-2xl font-bold text-blue-500">{{ sessionDetails.summary.frame_types['LIGHT'] || 0 }}</div>
                                    <div class="text-xs text-gray-600">Light Frames</div>
                                </div>
                                <div class="bg-white rounded-lg p-3 text-center shadow-sm">
                                    <div class="text-2xl font-bold text-gray-600">{{ sessionDetails.summary.frame_types['DARK'] || 0 }}</div>
                                    <div class="text-xs text-gray-600">Dark Frames</div>
                                </div>
                                <div class="bg-white rounded-lg p-3 text-center shadow-sm">
                                    <div class="text-2xl font-bold text-yellow-600">{{ sessionDetails.summary.frame_types['FLAT'] || 0 }}</div>
                                    <div class="text-xs text-gray-600">Flat Frames</div>
                                </div>
                                <div class="bg-white rounded-lg p-3 text-center shadow-sm">
                                    <div class="text-2xl font-bold text-purple-600">{{ sessionDetails.summary.frame_types['BIAS'] || 0 }}</div>
                                    <div class="text-xs text-gray-600">Bias Frames</div>
                                </div>
                            </div>

                            <!-- Total Imaging Time -->
                            <div class="mt-4 bg-white rounded-lg p-3 flex items-center justify-between shadow-sm">
                                <span class="text-sm font-medium text-gray-700">Total Imaging Time:</span>
                                <span class="text-xl font-bold text-indigo-600">{{ getTotalImagingTime() }}</span>
                            </div>
                        </div>

                        <!-- Objects Section -->
                        <div v-for="obj in sessionDetails.summary.objects" :key="obj.name" class="bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm">
                            <div class="bg-gradient-to-r from-gray-50 to-gray-100 px-6 py-4 border-b border-gray-200">
                                <div class="flex justify-between items-center">
                                    <h4 class="text-lg font-bold text-gray-900">📷 {{ obj.name }}</h4>
                                    <div class="flex space-x-2">
                                        <button @click="addObjectToNewSession(obj)" 
                                                class="px-3 py-1 bg-green-500 hover:bg-green-600 text-white text-sm rounded transition">
                                            ➕ New Session
                                        </button>
                                        <button @click="addObjectToExistingSession(obj)" 
                                                class="px-3 py-1 bg-blue-500 hover:bg-blue-600 text-white text-sm rounded transition">
                                            📋 Add to Existing
                                        </button>
                                    </div>
                                </div>
                            </div>

                            <div class="p-6">
                                <!-- Filters Breakdown -->
                                <div class="font-mono text-sm space-y-3">
                                    <div v-for="filter in obj.filters" :key="filter.filter">
                                        <!-- First exposure on same line as filter name -->
                                        <div v-if="filter.exposure_breakdown.length > 0" class="flex justify-between">
                                            <span class="font-bold text-blue-800 w-32 flex-shrink-0 text-base">{{ filter.filter }}</span>
                                            <span class="flex-1 text-gray-700">
                                                {{ filter.exposure_breakdown[0].count }} × {{ filter.exposure_breakdown[0].exposure }}s
                                            </span>
                                            <span class="font-semibold text-gray-900 w-20 text-right">
                                                {{ formatExposureTime(filter.exposure_breakdown[0].total) }}
                                            </span>
                                        </div>
                                        
                                        <!-- Subsequent exposures indented -->
                                        <div v-for="(exp, index) in filter.exposure_breakdown.slice(1)" :key="exp.exposure" 
                                             class="flex justify-between">
                                            <span class="w-32 flex-shrink-0"></span>
                                            <span class="flex-1 text-gray-700">
                                                {{ exp.count }} × {{ exp.exposure }}s
                                            </span>
                                            <span class="font-semibold text-gray-900 w-20 text-right">
                                                {{ formatExposureTime(exp.total) }}
                                            </span>
                                        </div>
                                    </div>
                                </div>

                                <!-- Total for Object -->
                                <div class="mt-4 pt-3 border-t-2 border-gray-400 font-mono text-sm">
                                    <div class="flex justify-between items-center">
                                        <span class="font-bold text-gray-800">TOTAL</span>
                                        <div class="text-right">
                                            <span class="text-gray-600 text-xs mr-3">{{ obj.total_files }} files</span>
                                            <span class="font-bold text-indigo-700">{{ getTotalObjectTime(obj) }}</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- NEW: Processing Sessions Card -->
                        <div class="bg-gradient-to-br from-green-50 to-teal-50 p-6 rounded-lg border border-green-200">
                            <h4 class="text-lg font-semibold text-gray-800 mb-4">🎯 Used in Processing Sessions</h4>
                            
                            <!-- Loading State -->
                            <div v-if="processingSessionsLoading" class="text-center py-4">
                                <div class="spinner inline-block"></div>
                                <span class="ml-2 text-gray-600 text-sm">Loading processing sessions...</span>
                            </div>
                            
                            <!-- Processing Sessions Table -->
                            <div v-else-if="processingSessions && processingSessions.length > 0">
                                <div class="bg-white p-3 rounded border border-green-200 overflow-x-auto">
                                    <table class="w-full text-sm font-mono border-collapse">
                                        <thead>
                                            <tr class="border-b-2 border-green-300">
                                                <th class="text-left py-2 px-3 font-semibold text-green-900">Processing Session</th>
                                                <th class="text-left py-2 px-3 font-semibold text-green-900">Status</th>
                                                <th class="text-left py-2 px-3 font-semibold text-green-900">Objects</th>
                                                <th class="text-right py-2 px-3 font-semibold text-green-900">Lights</th>
                                                <th class="text-right py-2 px-3 font-semibold text-green-900">Darks</th>
                                                <th class="text-right py-2 px-3 font-semibold text-green-900">Flats</th>
                                                <th class="text-right py-2 px-3 font-semibold text-green-900">Bias</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <tr v-for="ps in processingSessions" :key="ps.session_id" 
                                                class="border-b border-green-100 hover:bg-green-50">
                                                <td class="py-2 px-3">
                                                    <a @click="viewProcessingSession(ps.session_id)" 
                                                       class="text-blue-600 hover:text-blue-800 hover:underline cursor-pointer">
                                                        {{ ps.name }}
                                                    </a>
                                                </td>
                                                <td class="py-2 px-3">
                                                    <span :class="getStatusBadgeClass(ps.status)" 
                                                          class="inline-block px-2 py-0.5 rounded text-xs">
                                                        {{ formatStatus(ps.status) }}
                                                    </span>
                                                </td>
                                                <td class="py-2 px-3">{{ ps.objects }}</td>
                                                <td class="py-2 px-3 text-right">{{ ps.lights }}</td>
                                                <td class="py-2 px-3 text-right">{{ ps.darks }}</td>
                                                <td class="py-2 px-3 text-right">{{ ps.flats }}</td>
                                                <td class="py-2 px-3 text-right">{{ ps.bias }}</td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                            
                            <!-- No Processing Sessions State -->
                            <div v-else class="text-gray-500 text-sm italic">
                                Files from this imaging session are not used in any processing sessions yet.
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Modal Footer with Navigation -->
                <div class="bg-gray-50 p-4 border-t border-gray-200">
                    <div class="flex justify-between items-center">
                        <!-- Navigation Buttons -->
                        <div class="flex space-x-2">
                            <button @click="navigateToPrevSession" 
                                    :disabled="!hasPreviousSession"
                                    :class="hasPreviousSession ? 'btn btn-blue' : 'btn btn-gray cursor-not-allowed'"
                                    class="text-sm">
                                ← Previous Session
                            </button>
                            <button @click="navigateToNextSession" 
                                    :disabled="!hasNextSession"
                                    :class="hasNextSession ? 'btn btn-blue' : 'btn btn-gray cursor-not-allowed'"
                                    class="text-sm">
                                Next Session →
                            </button>
                        </div>

                        <!-- Action Buttons -->
                        <div class="flex space-x-3">
                            <button @click="closeSessionDetails" class="btn btn-gray text-sm">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,        

    data() {
        return {
            showDetailModal: false,
            loadingDetails: false,
            detailsError: null,
            sessionDetails: null,
            selectedSessionId: null,
            allSessionIds: [],
            currentSessionIndex: -1,
            // NEW: Processing sessions data
            processingSessions: null,
            processingSessionsLoading: false
        };
    },

    components: {
        'starfield-background': StarfieldBackground
    },
    
    computed: {
        hasPreviousSession() {
            return this.currentSessionIndex > 0;
        },
        hasNextSession() {
            return this.currentSessionIndex < this.allSessionIds.length - 1;
        }
    },
    
    methods: {
        async viewSessionDetails(sessionId, allSessionIds = []) {
            this.showDetailModal = true;
            this.loadingDetails = true;
            this.detailsError = null;
            this.sessionDetails = null;
            this.selectedSessionId = sessionId;
            this.allSessionIds = allSessionIds;
            this.currentSessionIndex = allSessionIds.indexOf(sessionId);
            
            try {
                const response = await fetch(`/api/imaging-sessions/${sessionId}/details`);
                
                if (!response.ok) {
                    throw new Error(`Failed to load session details: ${response.statusText}`);
                }
                
                this.sessionDetails = await response.json();
                
                // NEW: Load processing sessions that use files from this imaging session
                // Don't let this fail the whole modal if it errors
                try {
                    await this.loadProcessingSessions(sessionId);
                } catch (psError) {
                    console.error('Error loading processing sessions (non-fatal):', psError);
                    this.processingSessions = [];
                }
                
            } catch (error) {
                console.error('Error loading session details:', error);
                this.detailsError = error.message || 'Failed to load session details';
            } finally {
                this.loadingDetails = false;
            }
        },
        
        // NEW: Load processing sessions
        async loadProcessingSessions(sessionId) {
            this.processingSessionsLoading = true;
            try {
                const response = await fetch(`/api/imaging-sessions/${sessionId}/processing-sessions`);
                if (response.ok) {
                    this.processingSessions = await response.json();
                } else {
                    this.processingSessions = [];
                }
            } catch (error) {
                console.error('Error loading processing sessions:', error);
                this.processingSessions = [];
            } finally {
                this.processingSessionsLoading = false;
            }
        },
        
        // NEW: Copy session ID to clipboard
        copySessionIdToClipboard() {
            if (!this.selectedSessionId) return;
            
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(this.selectedSessionId).then(() => {
                    this.showCopyFeedback(this.selectedSessionId);
                }).catch(err => {
                    console.error('Clipboard API failed:', err);
                    this.fallbackCopy(this.selectedSessionId);
                });
            } else {
                this.fallbackCopy(this.selectedSessionId);
            }
        },
        
        // NEW: Fallback copy method
        fallbackCopy(text) {
            const textarea = document.createElement('textarea');
            textarea.value = text;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            
            try {
                document.execCommand('copy');
                this.showCopyFeedback(text);
            } catch (err) {
                console.error('Fallback copy failed:', err);
                alert('Failed to copy to clipboard. Please copy manually: ' + text);
            } finally {
                document.body.removeChild(textarea);
            }
        },
        
        // NEW: Show copy feedback
        showCopyFeedback(originalText) {
            if (event && event.target) {
                const element = event.target;
                const originalBg = element.style.background;
                const originalColor = element.style.color;
                
                element.style.background = '#10b981';
                element.style.color = 'white';
                element.textContent = '✓ Copied!';
                
                setTimeout(() => {
                    element.style.background = originalBg;
                    element.style.color = originalColor;
                    element.textContent = originalText;
                }, 1500);
            }
        },
        
        // NEW: View processing session
        async viewProcessingSession(sessionId) {
            const app = this.$root;
            
            try {
                // Get all processing session IDs for navigation
                const response = await fetch('/api/processing-sessions/ids');
                const data = await response.json();
                const allSessionIds = data.session_ids || [];
                
                // Close this modal first
                this.closeSessionDetails();
                
                // Small delay to ensure modal is closed
                setTimeout(() => {
                    if (app.$refs.processingDetailsModal) {
                        app.$refs.processingDetailsModal.viewProcessingSession(sessionId, allSessionIds);
                    }
                }, 100);
                
            } catch (error) {
                console.error('Error opening processing session modal:', error);
                alert('Failed to open processing session details');
            }
        },
        
        // NEW: Format status badge
        getStatusBadgeClass(status) {
            const classes = {
                'not_started': 'bg-gray-100 text-gray-700',
                'in_progress': 'bg-blue-100 text-blue-700',
                'complete': 'bg-green-100 text-green-700'
            };
            return classes[status] || 'bg-gray-100 text-gray-700';
        },
        
        // NEW: Format status text
        formatStatus(status) {
            const labels = {
                'not_started': 'Not Started',
                'in_progress': 'In Progress',
                'complete': 'Complete'
            };
            return labels[status] || status;
        },
        
        closeSessionDetails() {
            this.showDetailModal = false;
            this.sessionDetails = null;
            this.selectedSessionId = null;
            this.processingSessions = null;
            this.processingSessionsLoading = false;
        },
        
        openMarkdownEditor() {
            if (this.selectedSessionId) {
                window.open(`/imaging-editor?session_id=${this.selectedSessionId}&session_name=${encodeURIComponent(this.selectedSessionId)}`, '_blank');
            }
        },
        
        viewSessionFiles() {
            if (this.selectedSessionId) {
                this.closeSessionDetails();
                this.$root.activeTab = 'files';
                this.$root.searchFilters.session_id = this.selectedSessionId;
                this.$root.loadFiles();
            }
        },
        
        async navigateToPrevSession() {
            if (this.hasPreviousSession) {
                this.loadingDetails = true;
                const prevSessionId = this.allSessionIds[this.currentSessionIndex - 1];
                await this.viewSessionDetails(prevSessionId, this.allSessionIds);
            }
        },

        async navigateToNextSession() {
            if (this.hasNextSession) {
                this.loadingDetails = true;
                const nextSessionId = this.allSessionIds[this.currentSessionIndex + 1];
                await this.viewSessionDetails(nextSessionId, this.allSessionIds);
            }
        },
        
        async addObjectToNewSession(obj) {
            const fileIds = await this.getObjectFileIds(obj.name);
            if (fileIds.length === 0) {
                alert('No files found for this object');
                return;
            }
            
            this.$root.selectedFiles = fileIds;
            this.$root.$refs.processingModals.newSessionFromFiles = { 
                name: obj.name, 
                notes: '' 
            };
            this.$root.$refs.processingModals.showAddToNewModal = true;
        },

        async addObjectToExistingSession(obj) {
            const fileIds = await this.getObjectFileIds(obj.name);
            if (fileIds.length === 0) {
                alert('No files found for this object');
                return;
            }
            
            this.$root.selectedFiles = fileIds;
            await this.$root.$refs.processingModals.loadExistingSessions();
            this.$root.$refs.processingModals.selectedExistingSession = '';
            this.$root.$refs.processingModals.showAddToExistingSessionModal = true;
        },
        
        async getObjectFileIds(objectName) {
            try {
                const params = new URLSearchParams({
                    session_id: this.selectedSessionId,
                    objects: objectName,
                    frame_types: 'LIGHT'
                });
                
                const response = await fetch(`/api/files/ids?${params}`);
                if (response.ok) {
                    const data = await response.json();
                    return data.file_ids || [];
                }
            } catch (error) {
                console.error('Error fetching object file IDs:', error);
            }
            return [];
        },

        getTotalObjectTime(obj) {
            let totalSeconds = 0;
            if (obj.filters) {
                obj.filters.forEach(filter => {
                    totalSeconds += filter.total_exposure || 0;
                });
            }
            return this.formatExposureTime(totalSeconds);
        },
        
        getTotalImagingTime() {
            if (!this.sessionDetails || !this.sessionDetails.summary) return '0h 0m';
            
            const totalSeconds = this.sessionDetails.summary.total_exposure || 0;
            return this.formatExposureTime(totalSeconds);
        },
        
        formatExposureTime(seconds) {
            if (!seconds) return '0m';
            
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            
            if (hours > 0) {
                return `${hours}h ${minutes}m`;
            }
            return `${minutes}m`;
        }
    },

    mounted() {
        this.handleKeypress = (e) => {
            if (!this.showDetailModal) return;
            
            if (e.key === 'ArrowLeft' && this.hasPreviousSession) {
                this.navigateToPrevSession();
            } else if (e.key === 'ArrowRight' && this.hasNextSession) {
                this.navigateToNextSession();
            } else if (e.key === 'Escape') {
                this.closeSessionDetails();
            }
        };
        
        window.addEventListener('keydown', this.handleKeypress);
    },

    beforeDestroy() {
        if (this.handleKeypress) {
            window.removeEventListener('keydown', this.handleKeypress);
        }
    },
};