/**
 * Configuration Tab Component
 * View and modify system configuration
 */

const ConfigurationTab = {
    data() {
        return {
            config: {
                paths: {},
                file_monitoring: {},
                database: {},
                logging: {}
            },
            originalConfig: null,
            loading: false,
            saving: false,
            hasChanges: false,
            // Monitoring state
            monitoringEnabled: false,
            monitoringStatus: null,
            statusPolling: null
        };
    },
    
    template: `
        <div class="space-y-6">
            <div class="bg-white rounded-lg shadow p-6">
                <div class="flex justify-between items-center mb-6">
                    <h2 class="text-2xl font-bold">System Configuration</h2>
                    <div class="flex space-x-2">
                        <button 
                            @click="resetChanges" 
                            :disabled="!hasChanges"
                            class="btn btn-gray"
                            :class="{ 'opacity-50': !hasChanges }">
                            Reset Changes
                        </button>
                        <button 
                            @click="saveConfiguration" 
                            :disabled="!hasChanges || saving"
                            class="btn btn-green"
                            :class="{ 'opacity-50': !hasChanges || saving }">
                            {{ saving ? 'Saving...' : 'Save Configuration' }}
                        </button>
                    </div>
                </div>

                <div v-if="hasChanges" class="mb-4 p-4 bg-yellow-50 border border-yellow-200 rounded">
                    <p class="text-sm text-yellow-800">
                        ⚠️ You have unsaved changes. Click "Save Configuration" to apply them.
                    </p>
                </div>

                <!-- Paths Section -->
                <div class="mb-8">
                    <h3 class="text-xl font-semibold mb-4 pb-2 border-b">File Paths</h3>
                    <div class="grid grid-cols-1 gap-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">
                                Quarantine Directory
                                <span class="text-gray-500 text-xs">(where new files are monitored)</span>
                            </label>
                            <input 
                                v-model="config.paths.quarantine_dir" 
                                @input="markChanged"
                                type="text" 
                                class="w-full px-3 py-2 border border-gray-300 rounded"
                                placeholder="/path/to/quarantine">
                        </div>
                        
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">
                                Image Directory
                                <span class="text-gray-500 text-xs">(long-term storage)</span>
                            </label>
                            <input 
                                v-model="config.paths.image_dir" 
                                @input="markChanged"
                                type="text" 
                                class="w-full px-3 py-2 border border-gray-300 rounded"
                                placeholder="/path/to/images">
                        </div>
                        
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">
                                Processing Directory
                                <span class="text-gray-500 text-xs">(active processing sessions)</span>
                            </label>
                            <input 
                                v-model="config.paths.processing_dir" 
                                @input="markChanged"
                                type="text" 
                                class="w-full px-3 py-2 border border-gray-300 rounded"
                                placeholder="/path/to/processing">
                        </div>
                        
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">
                                Database Path
                                <span class="text-gray-500 text-xs">(SQLite database file)</span>
                            </label>
                            <input 
                                v-model="config.paths.database_path" 
                                @input="markChanged"
                                type="text" 
                                class="w-full px-3 py-2 border border-gray-300 rounded"
                                placeholder="/path/to/database.db">
                        </div>
                        
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">
                                Restore Folder
                                <span class="text-gray-500 text-xs">(temporary folder for restore operations)</span>
                            </label>
                            <input 
                                v-model="config.paths.restore_folder" 
                                @input="markChanged"
                                type="text" 
                                class="w-full px-3 py-2 border border-gray-300 rounded"
                                placeholder="/path/to/restore">
                        </div>
                    </div>
                </div>

                <!-- File Monitoring Section -->
                <div class="mb-8">
                    <h3 class="text-xl font-semibold mb-4 pb-2 border-b">File Monitoring</h3>
                    
                    <!-- Live Monitoring Panel -->
                    <div class="mb-6 p-4 border-2 rounded-lg" :class="monitoringEnabled ? 'border-green-500 bg-green-50' : 'border-gray-300 bg-gray-50'">
                        <div class="flex justify-between items-center mb-4">
                            <div>
                                <h4 class="text-lg font-semibold flex items-center">
                                    <span class="mr-2">📡</span>
                                    Automatic Monitoring
                                    <span v-if="monitoringEnabled" class="ml-3 px-2 py-1 bg-green-600 text-white text-xs rounded">ACTIVE</span>
                                    <span v-else class="ml-3 px-2 py-1 bg-gray-400 text-white text-xs rounded">INACTIVE</span>
                                </h4>
                                <p class="text-sm text-gray-600 mt-1">
                                    Automatically scan quarantine folder and process new files
                                </p>
                            </div>
                            <button 
                                @click="toggleMonitoring" 
                                :disabled="loading"
                                class="btn text-white px-6 py-2"
                                :class="monitoringEnabled ? 'bg-red-600 hover:bg-red-700' : 'bg-green-600 hover:bg-green-700'">
                                {{ monitoringEnabled ? 'Stop Monitoring' : 'Start Monitoring' }}
                            </button>
                        </div>
                        
                        <div v-if="monitoringStatus" class="mt-4 p-3 bg-white rounded border">
                            <div class="grid grid-cols-2 gap-4 text-sm">
                                <div>
                                    <span class="font-semibold">Last Scan:</span>
                                    {{ monitoringStatus.last_scan ? formatDateTime(monitoringStatus.last_scan) : 'Never' }}
                                </div>
                                <div>
                                    <span class="font-semibold">Files Detected:</span>
                                    {{ monitoringStatus.files_detected || 0 }}
                                </div>
                                <div>
                                    <span class="font-semibold">Scan Interval:</span>
                                    {{ monitoringStatus.interval_minutes || 0 }} minutes
                                </div>
                                <div>
                                    <span class="font-semibold">Next Scan:</span>
                                    {{ monitoringStatus.next_scan ? formatTime(monitoringStatus.next_scan) : 'N/A' }}
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">
                                Scan Interval (minutes)
                            </label>
                            <input 
                                v-model.number="config.file_monitoring.scan_interval_minutes" 
                                @input="markChanged"
                                type="number" 
                                min="1"
                                class="w-full px-3 py-2 border border-gray-300 rounded">
                        </div>
                        
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">
                                Ignore files newer than (minutes)
                            </label>
                            <input 
                                v-model.number="config.file_monitoring.ignore_newer_than_minutes" 
                                @input="markChanged"
                                type="number" 
                                min="0"
                                class="w-full px-3 py-2 border border-gray-300 rounded">
                            <p class="text-xs text-gray-500 mt-1">
                                Wait before processing files (allows file writes to complete)
                            </p>
                        </div>
                    </div>
                    
                    <div class="mt-4">
                        <label class="block text-sm font-medium text-gray-700 mb-1">
                            File Extensions
                            <span class="text-gray-500 text-xs">(comma-separated)</span>
                        </label>
                        <input 
                            :value="extensionsString" 
                            @input="updateExtensions"
                            type="text" 
                            class="w-full px-3 py-2 border border-gray-300 rounded"
                            placeholder=".fits, .fit, .fts">
                    </div>
                </div>

                <!-- Database Section -->
                <div class="mb-8">
                    <h3 class="text-xl font-semibold mb-4 pb-2 border-b">Database</h3>
                    <div class="grid grid-cols-1 gap-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">
                                Database Type
                            </label>
                            <input 
                                :value="config.database.type" 
                                type="text" 
                                class="form-input bg-gray-100" 
                                readonly>
                            <p class="text-xs text-gray-500 mt-1">
                                Currently only SQLite is supported
                            </p>
                        </div>
                        
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">
                                Connection String
                            </label>
                            <input 
                                :value="config.database.connection_string" 
                                type="text" 
                                class="w-full px-3 py-2 border border-gray-300 rounded bg-gray-100 font-mono text-sm" 
                                readonly>
                            <p class="text-xs text-gray-500 mt-1">
                                Auto-generated from database path
                            </p>
                        </div>
                    </div>
                </div>

                <!-- Logging Section -->
                <div class="mb-8">
                    <h3 class="text-xl font-semibold mb-4 pb-2 border-b">Logging</h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">
                                Log Level
                            </label>
                            <select 
                                v-model="config.logging.level" 
                                @change="markChanged"
                                class="form-input">
                                <option value="DEBUG">DEBUG</option>
                                <option value="INFO">INFO</option>
                                <option value="WARNING">WARNING</option>
                                <option value="ERROR">ERROR</option>
                                <option value="CRITICAL">CRITICAL</option>
                            </select>
                        </div>
                        
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">
                                Log File
                            </label>
                            <input 
                                v-model="config.logging.file" 
                                @input="markChanged"
                                type="text" 
                                class="w-full px-3 py-2 border border-gray-300 rounded">
                        </div>
                        
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">
                                Max File Size (bytes)
                            </label>
                            <input 
                                v-model.number="config.logging.max_bytes" 
                                @input="markChanged"
                                type="number" 
                                class="w-full px-3 py-2 border border-gray-300 rounded">
                        </div>
                        
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">
                                Backup Count
                            </label>
                            <input 
                                v-model.number="config.logging.backup_count" 
                                @input="markChanged"
                                type="number" 
                                min="1"
                                class="w-full px-3 py-2 border border-gray-300 rounded">
                        </div>
                    </div>
                </div>

                <!-- Warning -->
                <div class="p-4 bg-red-50 border border-red-200 rounded">
                    <p class="text-sm text-red-800">
                        ⚠️ <strong>Warning:</strong> Changing configuration requires restarting the application to take effect.
                    </p>
                </div>
            </div>
        </div>
    `,
    
    computed: {
        extensionsString() {
            return (this.config.file_monitoring.extensions || []).join(', ');
        }
    },
    
    methods: {
        async loadConfiguration() {
            try {
                this.loading = true;
                const response = await axios.get('/api/config');
                this.config = response.data;
                this.originalConfig = JSON.parse(JSON.stringify(response.data));
                this.hasChanges = false;
            } catch (error) {
                console.error('Error loading configuration:', error);
                this.$root.errorMessage = 'Failed to load configuration';
            } finally {
                this.loading = false;
            }
        },
        
        async saveConfiguration() {
            if (!confirm('Save configuration? This will require restarting the application.')) {
                return;
            }
            
            try {
                this.saving = true;
                await axios.put('/api/config', this.config);
                this.originalConfig = JSON.parse(JSON.stringify(this.config));
                this.hasChanges = false;
                alert('Configuration saved successfully. Please restart the application.');
            } catch (error) {
                console.error('Error saving configuration:', error);
                this.$root.errorMessage = error.response?.data?.detail || 'Failed to save configuration';
            } finally {
                this.saving = false;
            }
        },
        
        resetChanges() {
            if (confirm('Discard all changes?')) {
                this.config = JSON.parse(JSON.stringify(this.originalConfig));
                this.hasChanges = false;
            }
        },
        
        markChanged() {
            this.hasChanges = true;
        },
        
        updateExtensions(event) {
            const value = event.target.value;
            this.config.file_monitoring.extensions = value
                .split(',')
                .map(ext => ext.trim())
                .filter(ext => ext.length > 0);
            this.markChanged();
        },
        
        // Monitoring methods
        async loadMonitoringStatus() {
            try {
                const response = await axios.get('/api/monitoring/status');
                this.monitoringEnabled = response.data.enabled;
                this.monitoringStatus = response.data;
            } catch (error) {
                console.error('Error loading monitoring status:', error);
            }
        },
        
        async toggleMonitoring() {
            try {
                this.loading = true;
                if (this.monitoringEnabled) {
                    await axios.post('/api/monitoring/stop');
                    this.monitoringEnabled = false;
                } else {
                    await axios.post('/api/monitoring/start', {
                        enabled: true,
                        interval_minutes: this.config.file_monitoring.scan_interval_minutes || 5,
                        ignore_files_newer_than_minutes: this.config.file_monitoring.ignore_newer_than_minutes || 2
                    });
                    this.monitoringEnabled = true;
                }
                await this.loadMonitoringStatus();
            } catch (error) {
                console.error('Error toggling monitoring:', error);
                this.$root.errorMessage = error.response?.data?.detail || 'Failed to toggle monitoring';
            } finally {
                this.loading = false;
            }
        },
        
        startStatusPolling() {
            if (this.statusPolling) {
                clearInterval(this.statusPolling);
            }
            this.statusPolling = setInterval(async () => {
                await this.loadMonitoringStatus();
            }, 10000); // Poll every 10 seconds
        },
        
        formatTime(isoString) {
            return new Date(isoString).toLocaleTimeString();
        },
        
        formatDateTime(isoString) {
            return new Date(isoString).toLocaleString();
        }
    },
    
    async mounted() {
        await this.loadConfiguration();
        await this.loadMonitoringStatus();
        this.startStatusPolling();
    },
    
    beforeUnmount() {
        if (this.statusPolling) {
            clearInterval(this.statusPolling);
        }
    }
};

window.ConfigurationTab = ConfigurationTab;