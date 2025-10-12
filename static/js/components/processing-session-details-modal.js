/**
 * Processing Session Details Modal Component
 */

const ProcessingSessionDetailsModal = {
    template: `
        <div v-if="showSessionDetailsModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4" style="z-index: 250;">
            <div class="bg-white rounded-lg w-full max-w-6xl max-h-[90vh] overflow-hidden flex flex-col">
                <!-- Modal Header with Starfield -->
                <div class="relative text-white p-4 flex justify-between items-center" style="min-height: 64px;">
                    <starfield-background :num-stars="30" :min-size="0.3" :max-size="0.7"></starfield-background>
                    <div class="relative z-10 flex justify-between items-center w-full">
                        <h2 class="text-xl font-bold">Processing Session Details</h2>
                        <button @click="closeSessionDetailsModal" class="text-white hover:text-gray-200">
                            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                            </svg>
                        </button>
                    </div>
                </div>
                <!-- Modal Body -->
                <div class="flex-1 overflow-y-auto p-6" style="max-height: calc(90vh - 200px);">
                    <!-- Loading State -->
                    <div v-if="sessionDetailsLoading" class="flex justify-center items-center py-12">
                        <div class="spinner"></div>
                        <span class="ml-3 text-gray-600">Loading session details...</span>
                    </div>
                    
                    <!-- Session Details -->
                    <div v-else-if="currentSessionDetails" class="space-y-6">
                        <!-- Session-Level Summary -->
                        <div class="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-6 border border-blue-200">
                            <h3 class="text-xl font-bold text-blue-900 mb-4">Session Summary</h3>
                            
                            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
                                <div>
                                    <p class="text-xs text-gray-600 uppercase tracking-wide">Name</p>
                                    <p class="text-lg font-semibold text-gray-900">{{ currentSessionDetails.name }}</p>
                                </div>
                                <div>
                                    <p class="text-xs text-gray-600 uppercase tracking-wide">Status</p>
                                    <span :class="getProcessingStatusClass(currentSessionDetails.status)" class="inline-block px-3 py-1 rounded-full text-sm font-semibold">
                                        {{ formatProcessingStatus(currentSessionDetails.status) }}
                                    </span>
                                </div>
                                <div>
                                    <p class="text-xs text-gray-600 uppercase tracking-wide">Created</p>
                                    <p class="text-lg font-semibold text-gray-900">{{ formatDate(currentSessionDetails.created_at) }}</p>
                                </div>
                            </div>

                            <!-- Statistics Cards -->
                            <div class="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4">
                                <div class="bg-white rounded-lg p-3 text-center shadow-sm">
                                    <div class="text-2xl font-bold text-blue-600">{{ currentSessionDetails.total_files }}</div>
                                    <div class="text-xs text-gray-600">Total Files</div>
                                </div>
                                <div class="bg-white rounded-lg p-3 text-center shadow-sm">
                                    <div class="text-2xl font-bold text-blue-500">{{ currentSessionDetails.lights }}</div>
                                    <div class="text-xs text-gray-600">Light Frames</div>
                                </div>
                                <div class="bg-white rounded-lg p-3 text-center shadow-sm">
                                    <div class="text-2xl font-bold text-gray-600">{{ currentSessionDetails.darks }}</div>
                                    <div class="text-xs text-gray-600">Dark Frames</div>
                                </div>
                                <div class="bg-white rounded-lg p-3 text-center shadow-sm">
                                    <div class="text-2xl font-bold text-yellow-600">{{ currentSessionDetails.flats }}</div>
                                    <div class="text-xs text-gray-600">Flat Frames</div>
                                </div>
                                <div class="bg-white rounded-lg p-3 text-center shadow-sm">
                                    <div class="text-2xl font-bold text-purple-600">{{ currentSessionDetails.bias }}</div>
                                    <div class="text-xs text-gray-600">Bias Frames</div>
                                </div>
                            </div>
                        </div>

                        <!-- Objects Section -->
                        <div v-if="currentSessionDetails.objects_detail && currentSessionDetails.objects_detail.length > 0">
                            <div v-for="obj in currentSessionDetails.objects_detail" :key="obj.name" 
                                 class="bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm mb-4">
                                <div class="bg-gradient-to-r from-gray-50 to-gray-100 px-6 py-4 border-b border-gray-200">
                                    <div class="flex justify-between items-center">
                                        <h4 class="text-lg font-bold text-gray-900">📷 {{ obj.name }}</h4>
                                        <button @click="removeObjectFromSession(obj.name)" 
                                                class="px-3 py-1 bg-red-500 hover:bg-red-600 text-white text-sm rounded transition">
                                            Remove Object
                                        </button>
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
                        </div>

                        <!-- Notes -->
                        <div v-if="currentSessionDetails.notes" class="bg-yellow-50 p-4 rounded-lg border border-yellow-200">
                            <h4 class="font-semibold text-yellow-800 mb-2">Notes</h4>
                            <p class="text-sm text-yellow-700 whitespace-pre-wrap">{{ currentSessionDetails.notes }}</p>
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
                            <button @click="openMarkdownEditor" class="btn btn-green text-sm">
                                📝 Edit Notes
                            </button>

                            <button @click="findCalibrationFromDetails" class="btn btn-purple text-sm">
                                🔍 Find Calibration
                            </button>

                            <!-- WebDAV File Access Button -->
                            <button v-if="webdavStatus && webdavStatus.running" 
                                    @click="openFileBrowser" 
                                    class="btn btn-success">
                                <i class="fas fa-folder-open"></i> Browse Files
                            </button>
                            
                            <button v-if="webdavStatus && webdavStatus.running" 
                                    @click="showWebdavInstructions" 
                                    class="btn btn-info">
                                <i class="fas fa-question-circle"></i> How to Access
                            </button>

                            <button @click="updateStatusFromDetails" class="btn btn-yellow text-sm">
                                Update Status
                            </button>

                            <button @click="closeSessionDetailsModal" class="btn btn-gray text-sm">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <!-- WebDAV Instructions Modal -->
        <div v-if="showWebdavModal" class="modal" @click.self="closeWebdavModal">
            <div class="modal-content" style="max-width: 700px;">
                <div class="modal-header">
                    <h3>File Access Instructions</h3>
                    <button @click="closeWebdavModal" class="close-btn">&times;</button>
                </div>
                
                <div class="modal-body" v-if="webdavInfo">
                    <div class="webdav-instructions">
                        <h4>📂 Quick Access</h4>
                        <p>Click "Browse Files" to view files in your browser, or use one of these methods to access files directly from your computer:</p>
                        
                        <div class="instruction-section">
                            <h5>💻 Windows</h5>
                            <p><strong>Option 1: Quick Browse</strong></p>
                            <div class="code-box">
                                <code>{{ webdavInfo.instructions.windows_explorer }}</code>
                                <button @click="copyToClipboard(webdavInfo.instructions.windows_explorer)" class="copy-btn">
                                    <i class="fas fa-copy"></i> Copy
                                </button>
                            </div>
                            <p class="hint">Paste this into Windows Explorer address bar</p>

                            <p><strong>Option 2: Map Network Drive</strong></p>
                            <ol>
                                <li>Open File Explorer</li>
                                <li>Right-click "This PC" → "Map network drive"</li>
                                <li>Choose drive letter (e.g., Z:)</li>
                                <li>Enter: <code>{{ webdavInfo.webdav_base }}</code></li>
                                <li>Check "Reconnect at sign-in"</li>
                                <li>Click Finish</li>
                            </ol>

                            <p><strong>Command Line:</strong></p>
                            <div class="code-box">
                                <code>{{ webdavInfo.instructions.windows_cmd }}</code>
                                <button @click="copyToClipboard(webdavInfo.instructions.windows_cmd)" class="copy-btn">
                                    <i class="fas fa-copy"></i> Copy
                                </button>
                            </div>
                        </div>

                        <div class="instruction-section">
                            <h5>🍎 macOS</h5>
                            <ol>
                                <li>Open Finder</li>
                                <li>Go → Connect to Server (⌘K)</li>
                                <li>Enter: <code>{{ webdavInfo.webdav_base }}</code></li>
                                <li>Click Connect</li>
                            </ol>
                        </div>

                        <div class="instruction-section">
                            <h5>🐧 Linux</h5>
                            <p>Use your file manager's "Connect to Server" feature:</p>
                            <div class="code-box">
                                <code>{{ webdavInfo.instructions.linux }}</code>
                                <button @click="copyToClipboard(webdavInfo.instructions.linux)" class="copy-btn">
                                    <i class="fas fa-copy"></i> Copy
                                </button>
                            </div>
                        </div>

                        <div class="benefits-section">
                            <h5>✨ Benefits</h5>
                            <ul>
                                <li>✅ Drag files directly into PixInsight, DeepSkyStacker, etc.</li>
                                <li>✅ Open files with double-click from Explorer</li>
                                <li>✅ No need to download - work with files in place</li>
                                <li>✅ Changes sync automatically</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </div>

    `,
    
    data() {
        return {
            showSessionDetailsModal: false,
            currentSessionDetails: null,
            sessionDetailsLoading: false,
            allSessionIds: [],  
            currentSessionIndex: -1,
            webdavStatus: null,
            showWebdavModal: false,
            webdavInfo: null
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
        async viewProcessingSession(sessionId, allSessionIds = []) {
            try {
                this.sessionDetailsLoading = true;
                this.showSessionDetailsModal = true;
                this.allSessionIds = allSessionIds;  // ADD THIS
                this.currentSessionIndex = allSessionIds.indexOf(sessionId);  // ADD THIS
                
                const response = await ApiService.processingSessions.getById(sessionId);
                this.currentSessionDetails = response.data;
                
            } catch (error) {
                console.error('Error loading session details:', error);
                this.closeSessionDetailsModal();
                alert(`Failed to load session details: ${error.response?.data?.detail || error.message}`);
            } finally {
                this.sessionDetailsLoading = false;
            }
        },
        async navigateToPrevSession() {
            if (this.hasPreviousSession) {
                this.sessionDetailsLoading = true;
                const prevSessionId = this.allSessionIds[this.currentSessionIndex - 1];
                await this.viewProcessingSession(prevSessionId, this.allSessionIds);
            }
        },
        
        async navigateToNextSession() {
            if (this.hasNextSession) {
                this.sessionDetailsLoading = true;
                const nextSessionId = this.allSessionIds[this.currentSessionIndex + 1];
                await this.viewProcessingSession(nextSessionId, this.allSessionIds);
            }
        },
        
        closeSessionDetailsModal() {
            this.showSessionDetailsModal = false;
            this.currentSessionDetails = null;
            this.sessionDetailsLoading = false;
        },
        
        findCalibrationFromDetails() {
            const app = this.$root;
            app.$refs.calibrationModal.findCalibrationFiles(this.currentSessionDetails.id);
            this.closeSessionDetailsModal();
        },
        
        async updateStatusFromDetails() {
            const app = this.$root;
            const sessionId = this.currentSessionDetails.id;
            await app.updateProcessingSessionStatus(sessionId);
            
            // Reload the session details to show updated status
            await this.viewProcessingSession(sessionId);
            
            // REFRESH STATS AFTER STATUS UPDATE
            await window.refreshStats();
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
        },

        openMarkdownEditor() {
            const sessionId = this.currentSessionDetails.id.trim();
            const sessionName = this.currentSessionDetails.name.trim();
            const url = `/editor?session_id=${sessionId}&session_name=${encodeURIComponent(sessionName)}`;
            window.open(url, '_blank');
            this.closeSessionDetailsModal();
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

        async removeObjectFromSession(objectName) {
            try {
                if (!confirm(`Remove all "${objectName}" light frames and associated calibration files from this session?`)) {
                    return;
                }
                
                const response = await ApiService.processingSessions.removeObject(
                    this.currentSessionDetails.id,
                    objectName
                );
                
                const result = response.data;
                
                // Show summary of what was removed
                let message = `Removed ${result.removed_light_frames} light frames`;
                if (result.removed_calibration_frames > 0) {
                    message += ` and ${result.removed_calibration_frames} orphaned calibration frames`;
                }
                
                // If session is now empty, offer to delete it
                if (result.session_empty) {
                    const deleteSession = confirm(
                        `${message}.\n\nNo objects remain in this session. Delete the entire processing session?`
                    );
                    
                    if (deleteSession) {
                        await this.$root.deleteProcessingSession(this.currentSessionDetails.id);
                        this.closeSessionDetailsModal();
                        return;
                    }
                } else {
                    alert(message);
                }
                
                // Reload session details
                await this.viewProcessingSession(this.currentSessionDetails.id);
                
                // Refresh stats
                await window.refreshStats();
                
            } catch (error) {
                console.error('Error removing object from session:', error);
                alert(`Failed to remove object: ${error.response?.data?.detail || error.message}`);
            }
        },

        formatExposureTime(seconds) {
            if (!seconds) return '0m';
            
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            
            if (hours > 0) {
                return `${hours}h ${minutes}m`;
            }
            return `${minutes}m`;
        },

        async checkWebdavStatus() {
            try {
                const response = await fetch('/api/webdav/status');
                this.webdavStatus = await response.json();
            } catch (error) {
                console.error('Error checking WebDAV status:', error);
                this.webdavStatus = { running: false };
            }
        },

        openFileBrowser() {
            if (this.currentSessionDetails && this.currentSessionDetails.id) {
                // Open file browser in new tab
                const url = `/file-browser?session_id=${encodeURIComponent(this.currentSessionDetails.id)}`;
                window.open(url, '_blank');
            }
        },

        async showWebdavInstructions() {
            try {
                if (!this.currentSessionDetails || !this.currentSessionDetails.id) {
                    alert('No session selected');
                    return;
                }
                
                const response = await fetch(`/api/webdav/session/${this.currentSessionDetails.id}`);
                if (!response.ok) {
                    throw new Error('Failed to load WebDAV information');
                }
                
                this.webdavInfo = await response.json();
                this.showWebdavModal = true;
            } catch (error) {
                console.error('Error loading WebDAV info:', error);
                alert('Failed to load WebDAV information: ' + error.message);
            }
        },

        closeWebdavModal() {
            this.showWebdavModal = false;
        },

        copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                // Show brief success message - use a better visual feedback
                const btn = event.target;
                const originalText = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-check"></i> Copied!';
                btn.style.background = '#4CAF50';
                
                setTimeout(() => {
                    btn.innerHTML = originalText;
                    btn.style.background = '';
                }, 2000);
            }).catch(err => {
                console.error('Failed to copy:', err);
                alert('Failed to copy to clipboard');
            });
        }
    },

    async mounted() {
        // Add keyboard event listener for arrow navigation
        this.handleKeypress = (e) => {
            if (!this.showSessionDetailsModal) return;
            
            if (e.key === 'ArrowLeft' && this.hasPreviousSession) {
                this.navigateToPrevSession();
            } else if (e.key === 'ArrowRight' && this.hasNextSession) {
                this.navigateToNextSession();
            } else if (e.key === 'Escape') {
                this.closeSessionDetailsModal();
            }
        };

        // Check WebDAV status
        await this.checkWebdavStatus();
        
        window.addEventListener('keydown', this.handleKeypress);
    },

    beforeDestroy() {
        // Clean up event listener
        if (this.handleKeypress) {
            window.removeEventListener('keydown', this.handleKeypress);
        }
    },
};

window.ProcessingSessionDetailsModal = ProcessingSessionDetailsModal;