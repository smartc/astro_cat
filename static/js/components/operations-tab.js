/**
 * Operations Tab Component - Enhanced with Cleanup Operations
 */

const OperationsTab = {
    template: `
        <div class="space-y-6">
            <!-- Main Operations -->
            <div class="bg-white rounded-lg shadow p-6">
                <h2 class="text-xl font-bold mb-4">File Operations</h2>
                <p class="text-gray-600 mb-6">Manage file operations and migrations</p>
                
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <button @click="startOperation('scan')" class="operation-button bg-blue-500 hover:bg-blue-600">
                        <div class="text-center">
                            <div class="text-2xl mb-2">🔍</div>
                            <div>Scan Quarantine</div>
                            <div class="text-sm opacity-75">Find new FITS files</div>
                        </div>
                    </button>
                    <button @click="startOperation('validate')" class="operation-button bg-green-500 hover:bg-green-600">
                        <div class="text-center">
                            <div class="text-2xl mb-2">✓</div>
                            <div>Run Validation</div>
                            <div class="text-sm opacity-75">Score files for migration</div>
                        </div>
                    </button>
                    <button @click="startOperation('migrate')" class="operation-button bg-purple-500 hover:bg-purple-600">
                        <div class="text-center">
                            <div class="text-2xl mb-2">📁</div>
                            <div>Migrate Files</div>
                            <div class="text-sm opacity-75">Move files to library</div>
                        </div>
                    </button>
                </div>
            </div>

            <!-- Cleanup Operations -->
            <div class="bg-white rounded-lg shadow p-6">
                <h2 class="text-xl font-bold mb-4">Cleanup Operations</h2>
                <p class="text-gray-600 mb-6">Remove duplicate, bad, and missing files</p>
                
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <!-- Duplicates -->
                    <div class="border rounded-lg p-4">
                        <div class="flex items-center justify-between mb-3">
                            <h3 class="font-semibold text-gray-700">Duplicate Files</h3>
                            <span class="text-2xl font-bold text-orange-600">
                                {{ (stats.cleanup && stats.cleanup.duplicates) || 0 }}
                            </span>
                        </div>
                        <p class="text-sm text-gray-500 mb-3">Files in quarantine/Duplicates</p>
                        <button 
                            @click="cleanupDuplicates"
                            :disabled="!(stats.cleanup && stats.cleanup.duplicates > 0)"
                            class="w-full text-white px-4 py-2 rounded transition"
                            :style="(stats.cleanup && stats.cleanup.duplicates > 0) ? 'background-color: #f97316' : 'background-color: #d1d5db; cursor: not-allowed'">
                            Delete Duplicates
                        </button>
                    </div>
                    
                    <!-- Bad Files -->
                    <div class="border rounded-lg p-4">
                        <div class="flex items-center justify-between mb-3">
                            <h3 class="font-semibold text-gray-700">Bad Files</h3>
                            <span class="text-2xl font-bold text-red-600">
                                {{ (stats.cleanup && stats.cleanup.bad_files) || 0 }}
                            </span>
                        </div>
                        <p class="text-sm text-gray-500 mb-3">Files in quarantine/Bad</p>
                        <button 
                            @click="cleanupBadFiles"
                            :disabled="!(stats.cleanup && stats.cleanup.bad_files > 0)"
                            class="w-full text-white px-4 py-2 rounded transition"
                            :style="(stats.cleanup && stats.cleanup.bad_files > 0) ? 'background-color: #ef4444' : 'background-color: #d1d5db; cursor: not-allowed'">
                            Delete Bad Files
                        </button>
                    </div>
                    
                    <!-- Missing Files -->
                    <div class="border rounded-lg p-4">
                        <div class="flex items-center justify-between mb-3">
                            <h3 class="font-semibold text-gray-700">Missing Files</h3>
                            <span class="text-2xl font-bold text-gray-600">
                                {{ (stats.cleanup && stats.cleanup.missing_files) || 0 }}
                            </span>
                        </div>
                        <p class="text-sm text-gray-500 mb-3">DB records, files not found</p>
                        <button 
                            @click="removeMissingFiles"
                            :disabled="!(stats.cleanup && stats.cleanup.missing_files > 0)"
                            class="w-full text-white px-4 py-2 rounded transition"
                            :style="(stats.cleanup && stats.cleanup.missing_files > 0) ? 'background-color: #6b7280' : 'background-color: #d1d5db; cursor: not-allowed'">
                            Remove from DB
                        </button>
                    </div>
                </div>
            </div>

            <!-- Operation Status -->
            <div v-if="activeOperation && operationStatus" class="bg-white rounded-lg shadow p-6">
                <h2 class="text-xl font-bold mb-4">Operation Status</h2>
                
                <div class="space-y-4">
                    <div class="flex items-center justify-between">
                        <div>
                            <h3 class="font-semibold text-lg capitalize">{{ activeOperation }}</h3>
                            <p class="text-sm text-gray-600">{{ operationStatus.message }}</p>
                        </div>
                        <button 
                            @click="clearOperation" 
                            class="px-4 py-2 bg-gray-200 hover:bg-gray-300 rounded transition">
                            Clear
                        </button>
                    </div>
                    
                    <div class="space-y-2">
                        <div class="flex justify-between text-sm">
                            <span class="font-medium capitalize">{{ operationStatus.status }}</span>
                            <span>{{ operationStatus.progress || 0 }}%</span>
                        </div>
                        <div class="w-full bg-gray-200 rounded-full h-4">
                            <div class="bg-blue-600 h-4 rounded-full transition-all duration-300" 
                                 :style="\`width: \${operationStatus.progress || 0}%\`"></div>
                        </div>
                        <p class="text-xs text-gray-500 mt-1">{{ operationStatus.progress || 0 }}%</p>
                    </div>
                    
                    <!-- Results for completed operations -->
                    <div v-if="operationStatus.status === 'completed' && operationStatus.results" class="mt-3">
                        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                            <div v-if="operationStatus.results.added !== undefined" class="bg-green-50 p-2 rounded">
                                <div class="font-semibold text-green-700">{{ operationStatus.results.added }}</div>
                                <div class="text-green-600">Added</div>
                            </div>
                            <div v-if="operationStatus.results.duplicates !== undefined" class="bg-yellow-50 p-2 rounded">
                                <div class="font-semibold text-yellow-700">{{ operationStatus.results.duplicates }}</div>
                                <div class="text-yellow-600">Duplicates</div>
                            </div>
                            <div v-if="operationStatus.results.moved !== undefined" class="bg-blue-50 p-2 rounded">
                                <div class="font-semibold text-blue-700">{{ operationStatus.results.moved }}</div>
                                <div class="text-blue-600">Moved</div>
                            </div>
                            <div v-if="operationStatus.results.errors !== undefined" class="bg-red-50 p-2 rounded">
                                <div class="font-semibold text-red-700">{{ operationStatus.results.errors }}</div>
                                <div class="text-red-600">Errors</div>
                            </div>
                            <div v-if="operationStatus.results.sessions !== undefined" class="bg-blue-50 p-2 rounded">
                                <div class="font-semibold text-blue-700">{{ operationStatus.results.sessions }}</div>
                                <div class="text-blue-600">Sessions</div>
                            </div>
                            <div v-if="operationStatus.results.auto_migrate !== undefined" class="bg-green-50 p-2 rounded">
                                <div class="font-semibold text-green-700">{{ operationStatus.results.auto_migrate }}</div>
                                <div class="text-green-600">Auto-migrate</div>
                            </div>
                            <div v-if="operationStatus.results.needs_review !== undefined" class="bg-yellow-50 p-2 rounded">
                                <div class="font-semibold text-yellow-700">{{ operationStatus.results.needs_review }}</div>
                                <div class="text-yellow-600">Needs Review</div>
                            </div>
                            <div v-if="operationStatus.results.manual_only !== undefined" class="bg-red-50 p-2 rounded">
                                <div class="font-semibold text-red-700">{{ operationStatus.results.manual_only }}</div>
                                <div class="text-red-600">Manual Only</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    computed: {
        stats() {
            return this.$root.stats;
        },
        activeOperation() {
            return this.$root.activeOperation;
        },
        operationStatus() {
            return this.$root.operationStatus;
        }
    },
    
    methods: {
        startOperation(type) {
            this.$root.startOperation(type);
        },
        
        clearOperation() {
            this.$root.clearOperation();
        },
        
        async cleanupDuplicates() {
            const count = this.stats.cleanup && this.stats.cleanup.duplicates;
            if (!count) return;
            
            if (!confirm(`Delete ${count} duplicate file(s) from quarantine/Duplicates? This cannot be undone.`)) {
                return;
            }
            
            try {
                const response = await fetch('/api/operations/cleanup-duplicates', {
                    method: 'DELETE'
                });
                
                if (response.ok) {
                    const result = await response.json();
                    alert(result.message);
                    await this.$root.loadStats();
                } else {
                    const error = await response.json();
                    alert(`Error: ${error.detail}`);
                }
            } catch (error) {
                console.error('Error cleaning up duplicates:', error);
                alert('Failed to cleanup duplicates');
            }
        },
        
        async cleanupBadFiles() {
            const count = this.stats.cleanup && this.stats.cleanup.bad_files;
            if (!count) return;
            
            if (!confirm(`Delete ${count} bad file(s) from quarantine/Bad? This cannot be undone.`)) {
                return;
            }
            
            try {
                const response = await fetch('/api/operations/cleanup-bad-files', {
                    method: 'DELETE'
                });
                
                if (response.ok) {
                    const result = await response.json();
                    alert(result.message);
                    await this.$root.loadStats();
                } else {
                    const error = await response.json();
                    alert(`Error: ${error.detail}`);
                }
            } catch (error) {
                console.error('Error cleaning up bad files:', error);
                alert('Failed to cleanup bad files');
            }
        },
        
        async removeMissingFiles() {
            const count = this.stats.cleanup && this.stats.cleanup.missing_files;
            if (!count) return;
            
            if (!confirm(`Remove ${count} missing file record(s) from database? This cannot be undone.`)) {
                return;
            }
            
            try {
                const response = await fetch('/api/operations/remove-missing?dry_run=false', {
                    method: 'DELETE'
                });
                
                if (response.ok) {
                    const result = await response.json();
                    alert(`Removed ${result.stats.removed} missing file records`);
                    await this.$root.loadStats();
                } else {
                    const error = await response.json();
                    alert(`Error: ${error.detail}`);
                }
            } catch (error) {
                console.error('Error removing missing files:', error);
                alert('Failed to remove missing files');
            }
        }
    }
};

window.OperationsTab = OperationsTab;