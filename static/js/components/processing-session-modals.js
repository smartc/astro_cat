/**
 * Processing Session Create/Edit Modals Component
 */

const ProcessingSessionModals = {
    template: `
        <div>
            <!-- Create Processing Session Modal -->
            <div v-if="showCreateModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                <div class="bg-white rounded-lg p-6 max-w-md w-full mx-4">
                    <h3 class="text-lg font-bold mb-4">Create Processing Session</h3>
                    <div class="space-y-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Session Name</label>
                            <input v-model="newProcessingSession.name" type="text" placeholder="e.g., NGC7000 LRGB" class="w-full border border-gray-300 rounded px-3 py-2">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">File IDs</label>
                            <input v-model="newProcessingSession.fileIds" type="text" placeholder="Comma-separated file IDs" class="w-full border border-gray-300 rounded px-3 py-2">
                            <p class="text-xs text-gray-500 mt-1">Use the Files tab to find IDs to include</p>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Notes (optional)</label>
                            <textarea v-model="newProcessingSession.notes" placeholder="Processing notes..." class="w-full border border-gray-300 rounded px-3 py-2 h-24"></textarea>
                        </div>
                    </div>
                    <div class="flex space-x-3 mt-6">
                        <button @click="createProcessingSession" class="btn btn-green flex-1">Create</button>
                        <button @click="showCreateModal = false" class="btn btn-red flex-1">Cancel</button>
                    </div>
                </div>
            </div>

            <!-- Add to New Session Modal -->
            <div v-if="showAddToNewModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                <div class="bg-white rounded-lg p-6 max-w-md w-full mx-4">
                    <h3 class="text-lg font-bold mb-4">Create New Processing Session</h3>
                    <div class="mb-4 p-3 bg-blue-50 rounded">
                        <p class="text-sm text-blue-700">
                            <strong>{{ getSelectedFilesCount() }}</strong> files selected for processing session
                        </p>
                    </div>
                    <div class="space-y-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Session Name</label>
                            <input v-model="newSessionFromFiles.name" type="text" placeholder="e.g., NGC7000 LRGB" class="w-full border border-gray-300 rounded px-3 py-2">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Notes (optional)</label>
                            <textarea v-model="newSessionFromFiles.notes" placeholder="Processing notes..." class="w-full border border-gray-300 rounded px-3 py-2 h-24"></textarea>
                        </div>
                    </div>
                    <div class="flex space-x-3 mt-6">
                        <button @click="createSessionFromSelectedFiles" class="btn btn-green flex-1">Create Session</button>
                        <button @click="showAddToNewModal = false" class="btn btn-red flex-1">Cancel</button>
                    </div>
                </div>
            </div>

            <!-- Add to Existing Session Modal -->
            <div v-if="showAddToExistingSessionModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                <div class="bg-white rounded-lg p-6 max-w-md w-full mx-4">
                    <h3 class="text-lg font-bold mb-4">Add to Existing Processing Session</h3>
                    <div class="mb-4 p-3 bg-blue-50 rounded">
                        <p class="text-sm text-blue-700">
                            <strong>{{ getSelectedFilesCount() }}</strong> files selected to add to session
                        </p>
                    </div>
                    <div class="space-y-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Select Session</label>
                            <select v-model="selectedExistingSession" class="w-full border border-gray-300 rounded px-3 py-2">
                                <option value="">Choose an existing session...</option>
                                <option v-for="session in existingSessions" :key="session.id" :value="session.id">
                                    {{ session.name }} ({{ session.total_files }} files)
                                </option>
                            </select>
                        </div>
                    </div>
                    <div class="flex space-x-3 mt-6">
                        <button @click="addToExistingSession" :disabled="!selectedExistingSession" class="btn btn-green flex-1">Add Files</button>
                        <button @click="showAddToExistingSessionModal = false" class="btn btn-red flex-1">Cancel</button>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    data() {
        return {
            showCreateModal: false,
            newProcessingSession: { name: '', fileIds: '', notes: '' },
            
            showAddToNewModal: false,
            newSessionFromFiles: { name: '', notes: '' },
            
            showAddToExistingSessionModal: false,
            selectedExistingSession: '',
            existingSessions: []
        };
    },
    
    methods: {
        showCreateProcessingSessionModal() {
            this.newProcessingSession = { name: '', fileIds: '', notes: '' };
            this.showCreateModal = true;
        },
        
        async createProcessingSession() {
            try {
                if (!this.newProcessingSession.name.trim()) {
                    alert('Session name is required');
                    return;
                }
                
                // File IDs are now optional - allow empty sessions
                let fileIds = [];
                if (this.newProcessingSession.fileIds && this.newProcessingSession.fileIds.trim()) {
                    fileIds = this.newProcessingSession.fileIds
                        .split(',')
                        .map(id => parseInt(id.trim()))
                        .filter(id => !isNaN(id));
                }
                
                const payload = {
                    name: this.newProcessingSession.name.trim(),
                    file_ids: fileIds,  // Can be empty array
                    notes: this.newProcessingSession.notes.trim() || null
                };
                
                await ApiService.processingSessions.create(payload);
                
                this.showCreateModal = false;
                const app = this.$root;
                await app.loadProcessingSessions();
                
                if (fileIds.length === 0) {
                    alert(`Empty processing session "${this.newProcessingSession.name}" created successfully! You can now add files to it.`);
                } else {
                    alert(`Processing session "${this.newProcessingSession.name}" created successfully with ${fileIds.length} files!`);
                }

                // REFRESH STATS AFTER CREATING SESSION
                await window.refreshStats();
            } catch (error) {
                console.error('Error creating processing session:', error);
                alert(`Failed to create processing session: ${error.response?.data?.detail || error.message}`);
            }
        },
        
        addToNewSession() {
            const app = this.$root;
            if (app.selectedFiles.length === 0) {
                alert('No files selected');
                return;
            }
            
            this.newSessionFromFiles = { name: '', notes: '' };
            this.showAddToNewModal = true;
        },
        
        async createSessionFromSelectedFiles() {
            try {
                const app = this.$root;
                
                if (!this.newSessionFromFiles.name.trim()) {
                    alert('Session name is required');
                    return;
                }
                
                if (app.selectedFiles.length === 0) {
                    alert('No files selected');
                    return;
                }
                
                const payload = {
                    name: this.newSessionFromFiles.name.trim(),
                    file_ids: app.selectedFiles,
                    notes: this.newSessionFromFiles.notes.trim() || null
                };
                
                await ApiService.processingSessions.create(payload);
                
                this.showAddToNewModal = false;
                app.clearSelection();
                alert(`Processing session "${this.newSessionFromFiles.name}" created successfully with ${payload.file_ids.length} files!`);
                await app.loadProcessingSessions();

                // REFRESH STATS AFTER ADDING FILES
                await window.refreshStats();                
                
            } catch (error) {
                console.error('Error creating processing session from files:', error);
                alert(`Failed to create processing session: ${error.response?.data?.detail || error.message}`);
            }
        },
        
        async showAddToExistingModal() {
            const app = this.$root;
            if (app.selectedFiles.length === 0) {
                alert('No files selected');
                return;
            }
            
            await this.loadExistingSessions();
            this.selectedExistingSession = '';
            this.showAddToExistingSessionModal = true;
        },
        
        async loadExistingSessions() {
            try {
                const response = await ApiService.processingSessions.getAll({ page: 1, limit: 100 });
                this.existingSessions = response.data.sessions;
            } catch (error) {
                console.error('Error loading existing sessions:', error);
                alert('Failed to load existing sessions');
            }
        },
        
        async addToExistingSession() {
            try {
                const app = this.$root;
                
                if (!this.selectedExistingSession) {
                    alert('Please select a session');
                    return;
                }
                
                await ApiService.processingSessions.addFiles(
                    this.selectedExistingSession, 
                    app.selectedFiles
                );
                
                this.showAddToExistingSessionModal = false;
                const fileCount = app.selectedFiles.length;
                app.clearSelection();
                alert(`Added ${fileCount} files to session!`);
                await app.loadProcessingSessions();

                // REFRESH STATS AFTER ADDING FILES
                await window.refreshStats();
                
            } catch (error) {
                console.error('Error adding files to session:', error);
                alert(`Failed to add files: ${error.response?.data?.detail || error.message}`);
            }
        },
        
        /**
         * Pre-select files for adding to a processing session
         * Called from imaging session detail modal
         * @param {Array} fileIds - Array of file IDs to pre-select
         * @param {String} suggestedName - Suggested name for the session
         */
        preSelectFiles(fileIds, suggestedName) {
            // Update root app's selected files
            const app = this.$root;
            app.selectedFiles = fileIds;
            
            // Pre-populate the session name based on which modal is open
            if (this.showAddToNewModal) {
                this.newSessionFromFiles.name = suggestedName;
            } else if (this.showCreateModal) {
                this.newProcessingSession.name = suggestedName;
                this.newProcessingSession.fileIds = fileIds.join(', ');
            }
        },
        
        getSelectedFilesCount() {
            const app = this.$root;
            return app.selectedFiles?.length || 0;
        }
    }
};

window.ProcessingSessionModals = ProcessingSessionModals;