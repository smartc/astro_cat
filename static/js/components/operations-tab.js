/**
 * Operations Tab Component
 * Save as: static/js/components/operations-tab.js
 */

const OperationsTab = {
    template: `
        <div class="space-y-6">
            <!-- Operations Dashboard -->
            <div class="bg-white rounded-lg shadow p-6">
                <h2 class="text-xl font-bold mb-4">Operations</h2>
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
            
            <!-- Operation Status Display -->
            <div v-if="activeOperation" class="bg-white rounded-lg shadow p-6">
                <div class="flex justify-between items-start mb-4">
                    <h3 class="text-lg font-bold">Operation Status</h3>
                    <button @click="clearOperation" class="text-gray-500 hover:text-gray-700">✕</button>
                </div>
                
                <div class="space-y-3">
                    <div class="flex items-center space-x-3">
                        <div class="text-lg">{{ activeOperation.toUpperCase() }}</div>
                        <div v-if="operationStatus" 
                             :class="{
                                 'bg-blue-100 text-blue-800': operationStatus.status === 'running',
                                 'bg-green-100 text-green-800': operationStatus.status === 'completed',
                                 'bg-red-100 text-red-800': operationStatus.status === 'error'
                             }" 
                             class="px-2 py-1 rounded text-sm font-medium">
                            {{ operationStatus.status }}
                        </div>
                    </div>
                    
                    <div v-if="operationStatus">
                        <p class="text-sm text-gray-600">{{ operationStatus.message }}</p>
                        
                        <!-- Progress bar for running operations -->
                        <div v-if="operationStatus.status === 'running'" class="mt-2">
                            <div class="w-full bg-gray-200 rounded-full h-2">
                                <div class="bg-blue-600 h-2 rounded-full transition-all duration-300" 
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
        </div>
    `,
    
    computed: {
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
        }
    }
};

window.OperationsTab = OperationsTab;