/**
 * Database Query Tab Component
 * Direct database query interface
 */

const DatabaseTab = {
    data() {
        return {
            query: '',
            results: null,
            error: null,
            executing: false,
            queryHistory: [],
            savedQueries: [
                {
                    name: 'All Files',
                    query: 'SELECT * FROM fits_files LIMIT 100'
                },
                {
                    name: 'Recent Files',
                    query: 'SELECT file, obs_date, camera, telescope FROM fits_files ORDER BY obs_date DESC LIMIT 50'
                },
                {
                    name: 'File Count by Camera',
                    query: 'SELECT camera, COUNT(*) as count FROM fits_files GROUP BY camera ORDER BY count DESC'
                },
                {
                    name: 'File Count by Frame Type',
                    query: 'SELECT frame_type, COUNT(*) as count FROM fits_files GROUP BY frame_type'
                },
                {
                    name: 'Imaging Sessions',
                    query: 'SELECT * FROM sessions ORDER BY session_date DESC LIMIT 50'
                },
                {
                    name: 'Processing Sessions',
                    query: 'SELECT * FROM processing_sessions ORDER BY created_at DESC'
                },
                {
                    name: 'All Cameras',
                    query: 'SELECT * FROM cameras'
                },
                {
                    name: 'All Telescopes',
                    query: 'SELECT * FROM telescopes'
                }
            ]
        };
    },
    
    template: `
        <div class="space-y-6">
            <div class="bg-white rounded-lg shadow p-6">
                <h2 class="text-2xl font-bold mb-4">Database Query</h2>
                
                <div class="mb-4 p-4 bg-yellow-50 border border-yellow-200 rounded">
                    <p class="text-sm text-yellow-800">
                        ⚠️ <strong>Warning:</strong> This is a direct database interface. 
                        Only SELECT queries are allowed for safety. 
                        Be careful with your queries as they can impact performance.
                    </p>
                </div>

                <!-- Saved Queries -->
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-2">Quick Queries</label>
                    <div class="flex flex-wrap gap-2">
                        <button 
                            v-for="sq in savedQueries" 
                            :key="sq.name"
                            @click="loadSavedQuery(sq.query)"
                            class="text-sm px-3 py-1 bg-blue-100 hover:bg-blue-200 text-blue-800 rounded">
                            {{ sq.name }}
                        </button>
                    </div>
                </div>

                <!-- Query Editor -->
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-2">SQL Query</label>
                    <textarea 
                        v-model="query" 
                        rows="6"
                        class="w-full px-3 py-2 border border-gray-300 rounded font-mono text-sm resize-y"
                        style="min-height: 120px;"
                        placeholder="SELECT * FROM fits_files LIMIT 10"
                        @keydown.ctrl.enter="executeQuery"
                        @keydown.meta.enter="executeQuery">
                    </textarea>
                    <p class="text-xs text-gray-500 mt-1">
                        Press Ctrl+Enter (Cmd+Enter on Mac) to execute • Drag bottom-right corner to resize
                    </p>
                </div>

                <!-- Execute Button -->
                <div class="flex justify-between items-center mb-4">
                    <button 
                        @click="executeQuery" 
                        :disabled="!query || executing"
                        class="btn btn-green"
                        :class="{ 'opacity-50': !query || executing }">
                        {{ executing ? 'Executing...' : 'Execute Query' }}
                    </button>
                    
                    <button 
                        v-if="results"
                        @click="exportResults"
                        class="btn btn-blue">
                        Export as CSV
                    </button>
                </div>

                <!-- Error Display -->
                <div v-if="error" class="mb-4 p-4 bg-red-50 border border-red-200 rounded">
                    <p class="text-sm text-red-800 font-mono">{{ error }}</p>
                </div>

                <!-- Results Display -->
                <div v-if="results && !error">
                    <div class="mb-2 flex justify-between items-center">
                        <p class="text-sm text-gray-600">
                            {{ results.row_count }} row{{ results.row_count !== 1 ? 's' : '' }} returned
                            <span v-if="results.execution_time">({{ results.execution_time }}ms)</span>
                        </p>
                    </div>

                    <!-- Results Table -->
                    <div class="border rounded-lg overflow-hidden">
                        <div class="overflow-x-auto max-h-96">
                            <table class="w-full text-sm">
                                <thead class="bg-gray-50 sticky top-0">
                                    <tr>
                                        <th 
                                            v-for="column in results.columns" 
                                            :key="column"
                                            class="px-4 py-2 text-left text-xs font-medium text-gray-700 border-b">
                                            {{ column }}
                                        </th>
                                    </tr>
                                </thead>
                                <tbody class="bg-white">
                                    <tr 
                                        v-for="(row, idx) in results.rows" 
                                        :key="idx"
                                        class="border-b hover:bg-gray-50">
                                        <td 
                                            v-for="column in results.columns" 
                                            :key="column"
                                            class="px-4 py-2 text-xs font-mono">
                                            {{ formatValue(row[column]) }}
                                        </td>
                                    </tr>
                                    <tr v-if="results.rows.length === 0">
                                        <td 
                                            :colspan="results.columns.length"
                                            class="px-4 py-8 text-center text-gray-500">
                                            No results
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- Query History -->
                <div v-if="queryHistory.length > 0" class="mt-6">
                    <h3 class="text-lg font-semibold mb-2">Query History</h3>
                    <div class="space-y-2">
                        <div 
                            v-for="(historyItem, idx) in queryHistory.slice().reverse()" 
                            :key="idx"
                            class="p-3 bg-gray-50 rounded cursor-pointer hover:bg-gray-100"
                            @click="loadHistoryQuery(historyItem)">
                            <p class="text-sm font-mono text-gray-700">{{ historyItem.query }}</p>
                            <p class="text-xs text-gray-500 mt-1">
                                {{ new Date(historyItem.timestamp).toLocaleString() }} - 
                                {{ historyItem.row_count }} rows
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Database Schema Reference -->
            <div class="bg-white rounded-lg shadow p-6">
                <h3 class="text-xl font-semibold mb-4">Database Schema</h3>
                
                <div class="space-y-4">
                    <div>
                        <h4 class="font-semibold text-blue-600 mb-2">fits_files</h4>
                        <p class="text-sm text-gray-600 mb-1">Main table storing FITS file metadata</p>
                        <p class="text-xs font-mono text-gray-500">
                            id, file, quarantine_path, registered_path, md5, obs_date, object, 
                            frame_type, exposure, camera, telescope, filter, focal_length, 
                            pixel_scale, fov_x, fov_y, session_id, validation_score, etc.
                        </p>
                    </div>
                    
                    <div>
                        <h4 class="font-semibold text-blue-600 mb-2">sessions</h4>
                        <p class="text-sm text-gray-600 mb-1">Imaging sessions</p>
                        <p class="text-xs font-mono text-gray-500">
                            id, session_id, session_date, camera, telescope, notes
                        </p>
                    </div>
                    
                    <div>
                        <h4 class="font-semibold text-blue-600 mb-2">processing_sessions</h4>
                        <p class="text-sm text-gray-600 mb-1">Processing session tracking</p>
                        <p class="text-xs font-mono text-gray-500">
                            id, name, status, created_at, updated_at, notes
                        </p>
                    </div>
                    
                    <div>
                        <h4 class="font-semibold text-blue-600 mb-2">cameras</h4>
                        <p class="text-sm text-gray-600 mb-1">Camera specifications</p>
                        <p class="text-xs font-mono text-gray-500">
                            id, camera, brand, type, x, y, pixel, bin, rgb, comments
                        </p>
                    </div>
                    
                    <div>
                        <h4 class="font-semibold text-blue-600 mb-2">telescopes</h4>
                        <p class="text-sm text-gray-600 mb-1">Telescope specifications</p>
                        <p class="text-xs font-mono text-gray-500">
                            id, scope, make, type, focal, aperture, subtype, comments
                        </p>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    methods: {
        async executeQuery() {
            if (!this.query.trim()) return;
            
            this.executing = true;
            this.error = null;
            
            try {
                const response = await axios.post('/api/database/query', {
                    query: this.query
                });
                
                this.results = response.data;
                
                // Add to history
                this.queryHistory.push({
                    query: this.query,
                    timestamp: new Date().toISOString(),
                    row_count: response.data.row_count
                });
                
                // Keep only last 10 queries
                if (this.queryHistory.length > 10) {
                    this.queryHistory = this.queryHistory.slice(-10);
                }
                
            } catch (error) {
                console.error('Query error:', error);
                this.error = error.response?.data?.detail || error.message;
                this.results = null;
            } finally {
                this.executing = false;
            }
        },
        
        loadSavedQuery(query) {
            this.query = query;
        },
        
        loadHistoryQuery(historyItem) {
            this.query = historyItem.query;
        },
        
        formatValue(value) {
            if (value === null) return 'NULL';
            if (value === undefined) return '';
            if (typeof value === 'boolean') return value ? 'true' : 'false';
            if (typeof value === 'number') return value.toString();
            if (typeof value === 'string' && value.length > 100) {
                return value.substring(0, 100) + '...';
            }
            return value;
        },
        
        exportResults() {
            if (!this.results || !this.results.rows) return;
            
            // Create CSV content
            const headers = this.results.columns.join(',');
            const rows = this.results.rows.map(row => {
                return this.results.columns.map(col => {
                    const value = row[col];
                    if (value === null) return '';
                    // Escape quotes and wrap in quotes if contains comma
                    const stringValue = String(value).replace(/"/g, '""');
                    return stringValue.includes(',') ? `"${stringValue}"` : stringValue;
                }).join(',');
            });
            
            const csv = [headers, ...rows].join('\n');
            
            // Download
            const blob = new Blob([csv], { type: 'text/csv' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `query_results_${new Date().toISOString().split('T')[0]}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        }
    }
};

window.DatabaseTab = DatabaseTab;