/**
 * Processing Session Details Modal Component - MINIMAL CHANGES
 * Only adds: 1) Session ID click-to-copy, 2) Imaging Sessions card
 */

const ProcessingSessionDetailsModal = {
    template: `
        <div v-if="showSessionDetailsModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4" style="z-index: 250;">
            <div class="bg-white rounded-lg w-full max-w-6xl max-h-[90vh] overflow-hidden flex flex-col">
                <!-- Modal Header with Starfield -->
                <div class="relative text-white p-4" style="min-height: 80px;">
                    <starfield-background :num-stars="30" :min-size="0.3" :max-size="0.7"></starfield-background>
                    <div class="relative z-10">
                        <div class="flex justify-between items-center">
                            <h2 class="text-xl font-bold">Processing Session Details</h2>
                            <button @click="closeSessionDetailsModal" class="text-white hover:text-gray-200">
                                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                                </svg>
                            </button>
                        </div>
                        <!-- NEW: Session ID (clickable to copy) -->
                        <div v-if="currentSessionDetails" class="mt-2 text-sm">
                            <span class="text-gray-200 mr-2">🆔 Session ID:</span>
                            <code @click="copySessionIdToClipboard" 
                                  class="bg-white bg-opacity-20 px-2 py-1 rounded cursor-pointer hover:bg-opacity-30 transition-colors"
                                  title="Click to copy session ID">
                                {{ currentSessionDetails.id }}
                            </code>
                        </div>
                        <!-- WebDAV Path (clickable to copy) -->
                        <div v-if="webdavStatus && webdavStatus.running && nativeFilePath" class="mt-2 text-sm">
                            <span class="text-gray-200 mr-2">📂 Quick Access:</span>
                            <code @click="copyPathToClipboard" 
                                  class="bg-white bg-opacity-20 px-2 py-1 rounded cursor-pointer hover:bg-opacity-30 transition-colors"
                                  title="Click to copy path">
                                {{ nativeFilePath }}
                            </code>
                        </div>
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

                        <!-- NEW: Imaging Sessions Card -->
                        <div class="bg-gradient-to-br from-purple-50 to-pink-50 p-6 rounded-lg border border-purple-200">
                            <h4 class="text-lg font-semibold text-gray-800 mb-4">📸 Imaging Sessions Used</h4>
                            
                            <!-- Loading State for Sessions -->
                            <div v-if="imagingSessionsLoading" class="text-center py-4">
                                <div class="spinner inline-block"></div>
                                <span class="ml-2 text-gray-600 text-sm">Loading imaging sessions...</span>
                            </div>
                            
                            <!-- Light Frames Section -->
                            <div v-else-if="imagingSessions && (imagingSessions.lights.length > 0 || imagingSessions.calibration.length > 0)">
                                <div v-if="imagingSessions.lights.length > 0" class="mb-6">
                                    <h5 class="font-semibold text-purple-700 mb-2 flex items-center">
                                        <span class="mr-2">🌟</span> Light Frames
                                    </h5>
                                    <div class="bg-white p-3 rounded border border-purple-200 overflow-x-auto">
                                        <table class="w-full text-sm font-mono border-collapse">
                                            <thead>
                                                <tr class="border-b-2 border-purple-300">
                                                    <th class="text-left py-2 px-3 font-semibold text-purple-900">Session ID</th>
                                                    <th class="text-left py-2 px-3 font-semibold text-purple-900">Date</th>
                                                    <th class="text-left py-2 px-3 font-semibold text-purple-900">Camera</th>
                                                    <th class="text-left py-2 px-3 font-semibold text-purple-900">Telescope</th>
                                                    <th class="text-right py-2 px-3 font-semibold text-purple-900">Lights</th>
                                                    <th class="text-right py-2 px-3 font-semibold text-purple-900">Darks</th>
                                                    <th class="text-right py-2 px-3 font-semibold text-purple-900">Flats</th>
                                                    <th class="text-right py-2 px-3 font-semibold text-purple-900">Bias</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                <tr v-for="session in imagingSessions.lights" :key="session.session_id" 
                                                    class="border-b border-purple-100 hover:bg-purple-50">
                                                    <td class="py-2 px-3">
                                                        <a @click="viewImagingSession(session.session_id)" 
                                                           class="text-blue-600 hover:text-blue-800 hover:underline cursor-pointer">
                                                            {{ session.session_id }}
                                                        </a>
                                                    </td>
                                                    <td class="py-2 px-3">{{ session.obs_date }}</td>
                                                    <td class="py-2 px-3">{{ session.camera }}</td>
                                                    <td class="py-2 px-3">{{ session.telescope }}</td>
                                                    <td class="py-2 px-3 text-right">{{ session.lights }}</td>
                                                    <td class="py-2 px-3 text-right">{{ session.darks }}</td>
                                                    <td class="py-2 px-3 text-right">{{ session.flats }}</td>
                                                    <td class="py-2 px-3 text-right">{{ session.bias }}</td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </div>
                                </div>

                                <!-- Calibration Frames Section -->
                                <div v-if="imagingSessions.calibration.length > 0">
                                    <h5 class="font-semibold text-purple-700 mb-2 flex items-center">
                                        <span class="mr-2">⚙️</span> Calibration Frames
                                    </h5>
                                    <div class="bg-white p-3 rounded border border-purple-200 overflow-x-auto">
                                        <table class="w-full text-sm font-mono border-collapse">
                                            <thead>
                                                <tr class="border-b-2 border-purple-300">
                                                    <th class="text-left py-2 px-3 font-semibold text-purple-900">Session ID</th>
                                                    <th class="text-left py-2 px-3 font-semibold text-purple-900">Date</th>
                                                    <th class="text-left py-2 px-3 font-semibold text-purple-900">Camera</th>
                                                    <th class="text-left py-2 px-3 font-semibold text-purple-900">Telescope</th>
                                                    <th class="text-right py-2 px-3 font-semibold text-purple-900">Lights</th>
                                                    <th class="text-right py-2 px-3 font-semibold text-purple-900">Darks</th>
                                                    <th class="text-right py-2 px-3 font-semibold text-purple-900">Flats</th>
                                                    <th class="text-right py-2 px-3 font-semibold text-purple-900">Bias</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                <tr v-for="session in imagingSessions.calibration" :key="session.session_id" 
                                                    class="border-b border-purple-100 hover:bg-purple-50">
                                                    <td class="py-2 px-3">
                                                        <a @click="viewImagingSession(session.session_id)" 
                                                           class="text-blue-600 hover:text-blue-800 hover:underline cursor-pointer">
                                                            {{ session.session_id }}
                                                        </a>
                                                    </td>
                                                    <td class="py-2 px-3">{{ session.obs_date }}</td>
                                                    <td class="py-2 px-3">{{ session.camera }}</td>
                                                    <td class="py-2 px-3">{{ session.telescope }}</td>
                                                    <td class="py-2 px-3 text-right">{{ session.lights }}</td>
                                                    <td class="py-2 px-3 text-right">{{ session.darks }}</td>
                                                    <td class="py-2 px-3 text-right">{{ session.flats }}</td>
                                                    <td class="py-2 px-3 text-right">{{ session.bias }}</td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- No Sessions State -->
                            <div v-else class="text-gray-500 text-sm italic">
                                No imaging sessions found for this processing session.
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

                            <button @click="updateStatusFromDetails" class="btn btn-yellow text-sm">
                                Update Status
                            </button>

                            <button @click="closeSessionDetailsModal" class="btn btn-gray text-sm">Close</button>
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
            webdavInfo: null,
            nativeFilePath: null,
            // NEW: Imaging sessions data
            imagingSessions: null,
            imagingSessionsLoading: false
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
                this.allSessionIds = allSessionIds;
                this.currentSessionIndex = allSessionIds.indexOf(sessionId);
                
                const response = await ApiService.processingSessions.getById(sessionId);
                this.currentSessionDetails = response.data;
                
                // Load WebDAV info for the session
                await this.loadWebDAVInfo(sessionId);
                
                // NEW: Load imaging sessions
                await this.loadImagingSessions(sessionId);
                
            } catch (error) {
                console.error('Error loading session details:', error);
                this.closeSessionDetailsModal();
                alert(`Failed to load session details: ${error.response?.data?.detail || error.message}`);
            } finally {
                this.sessionDetailsLoading = false;
            }
        },

        // NEW: Load imaging sessions from files
        async loadImagingSessions(sessionId) {
            this.imagingSessionsLoading = true;
            try {
                const response = await ApiService.processingSessions.getFiles(sessionId);
                const files = response.data;
                
                // Group by session_id and frame_type
                const sessionMap = new Map();
                
                files.forEach(file => {
                    if (!file.session_id) return;
                    
                    const key = file.session_id;
                    if (!sessionMap.has(key)) {
                        sessionMap.set(key, {
                            session_id: file.session_id,
                            camera: file.camera || 'N/A',
                            telescope: file.telescope || 'N/A',
                            obs_date: file.obs_date || 'N/A',
                            lights: 0,
                            darks: 0,
                            flats: 0,
                            bias: 0
                        });
                    }
                    
                    const session = sessionMap.get(key);
                    const frameType = (file.frame_type || 'UNKNOWN').toLowerCase();
                    
                    if (frameType === 'light') session.lights++;
                    else if (frameType === 'dark') session.darks++;
                    else if (frameType === 'flat') session.flats++;
                    else if (frameType === 'bias') session.bias++;
                });
                
                // Convert to arrays and separate lights from calibration
                const allSessions = Array.from(sessionMap.values());
                
                this.imagingSessions = {
                    lights: allSessions.filter(s => s.lights > 0).sort((a, b) => b.obs_date.localeCompare(a.obs_date)),
                    calibration: allSessions.filter(s => s.darks > 0 || s.flats > 0 || s.bias > 0).sort((a, b) => b.obs_date.localeCompare(a.obs_date))
                };
                
            } catch (error) {
                console.error('Error loading imaging sessions:', error);
                this.imagingSessions = { lights: [], calibration: [] };
            } finally {
                this.imagingSessionsLoading = false;
            }
        },

        // NEW: View imaging session details
        async viewImagingSession(sessionId) {
            const app = this.$root;
            
            try {
                // Get all imaging session IDs for navigation
                const response = await fetch('/api/imaging-sessions/ids');
                const data = await response.json();
                const allSessionIds = data.session_ids || [];
                
                // Close this modal first
                this.closeSessionDetailsModal();
                
                // Small delay to ensure modal is closed before opening new one
                setTimeout(() => {
                    // Open the imaging session modal - ref is sessionDetailModal
                    if (app.$refs.sessionDetailModal) {
                        app.$refs.sessionDetailModal.viewSessionDetails(sessionId, allSessionIds);
                    } else {
                        console.error('Imaging session modal ref not found');
                    }
                }, 100);
                
            } catch (error) {
                console.error('Error opening imaging session modal:', error);
                alert('Failed to open imaging session details');
            }
        },

        async loadWebDAVInfo(sessionId) {
            try {
                const response = await fetch(`/api/webdav/session/${sessionId}`);
                if (response.ok) {
                    this.webdavInfo = await response.json();
                    console.log('WebDAV Info:', this.webdavInfo);
                    
                    // Set native file path based on platform
                    const platform = this.detectPlatform();
                    if (platform === 'windows') {
                        this.nativeFilePath = this.webdavInfo.instructions.windows_explorer;
                    } else if (platform === 'mac') {
                        this.nativeFilePath = this.webdavInfo.webdav_root;
                    } else {
                        // Linux
                        this.nativeFilePath = this.webdavInfo.webdav_root.replace('http://', 'dav://');
                    }
                }
            } catch (error) {
                console.error('Error loading WebDAV info:', error);
            }
        },

        detectPlatform() {
            const userAgent = window.navigator.userAgent.toLowerCase();
            if (userAgent.indexOf('win') !== -1) return 'windows';
            if (userAgent.indexOf('mac') !== -1) return 'mac';
            return 'linux';
        },

        // NEW: Copy session ID to clipboard
        copySessionIdToClipboard() {
            if (!this.currentSessionDetails) return;
            
            const sessionId = this.currentSessionDetails.id;
            
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(sessionId).then(() => {
                    this.showCopyFeedback(sessionId);
                }).catch(err => {
                    console.error('Clipboard API failed:', err);
                    this.fallbackCopy(sessionId);
                });
            } else {
                this.fallbackCopy(sessionId);
            }
        },

        copyPathToClipboard() {
            if (!this.nativeFilePath) return;
            
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(this.nativeFilePath).then(() => {
                    this.showCopyFeedback(this.nativeFilePath);
                }).catch(err => {
                    console.error('Clipboard API failed:', err);
                    this.fallbackCopy(this.nativeFilePath);
                });
            } else {
                this.fallbackCopy(this.nativeFilePath);
            }
        },

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

        getFileUrl() {
            if (!this.nativeFilePath) return '';
            
            const platform = this.detectPlatform();
            
            if (platform === 'windows') {
                const path = this.nativeFilePath.replace(/\\/g, '/');
                return 'file://' + path;
            } else if (platform === 'mac') {
                return this.nativeFilePath;
            } else {
                return this.nativeFilePath;
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
            this.webdavInfo = null;
            this.nativeFilePath = null;
            this.imagingSessions = null;
            this.imagingSessionsLoading = false;
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
            
            await this.viewProcessingSession(sessionId, this.allSessionIds);
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
                
                let message = `Removed ${result.removed_light_frames} light frames`;
                if (result.removed_calibration_frames > 0) {
                    message += ` and ${result.removed_calibration_frames} orphaned calibration frames`;
                }
                
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
                
                await this.viewProcessingSession(this.currentSessionDetails.id, this.allSessionIds);
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
                const url = `/file-browser?session_id=${encodeURIComponent(this.currentSessionDetails.id)}`;
                window.open(url, '_blank');
            }
        }
    },

    async mounted() {
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

        await this.checkWebdavStatus();
        
        window.addEventListener('keydown', this.handleKeypress);
    },

    beforeDestroy() {
        if (this.handleKeypress) {
            window.removeEventListener('keydown', this.handleKeypress);
        }
    },
};

window.ProcessingSessionDetailsModal = ProcessingSessionDetailsModal;