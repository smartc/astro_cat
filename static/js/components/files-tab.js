/**
 * Files Tab Component
 */

const FilesTab = {
    template: `
        <div class="space-y-6">
            <!-- Controls -->
            <div class="bg-white rounded-lg shadow p-4">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-xl font-bold">File Browser</h2>
                    <div class="flex space-x-4 items-center">
                        <div class="flex items-center space-x-2 text-sm text-gray-600">
                            <span>Sort:</span>
                            <select v-model="fileSorting.sort_by" @change="$root.loadFiles" class="border border-gray-300 rounded px-2 py-1">
                                <option value="obs_date">Date</option>
                                <option value="file">Filename</option>
                                <option value="object">Object</option>
                                <option value="frame_type">Frame Type</option>
                                <option value="camera">Camera</option>
                                <option value="telescope">Telescope</option>
                                <option value="filter">Filter</option>
                                <option value="exposure">Exposure</option>
                            </select>
                            <select v-model="fileSorting.sort_order" @change="$root.loadFiles" class="border border-gray-300 rounded px-2 py-1">
                                <option value="desc">↓</option>
                                <option value="asc">↑</option>
                            </select>
                        </div>
                        <button @click="$root.resetAllFilters" class="btn btn-red">Reset Filters</button>
                        <button @click="$root.loadFiles" class="btn btn-blue">Apply Filters</button>
                    </div>
                </div>
                
                <div v-if="hasActiveFilters" class="active-filters">
                    <span class="font-medium">Active filters:</span>
                    <span v-for="filter in getActiveFilterSummary()" :key="filter" class="filter-tag">
                        {{ filter }}
                    </span>
                </div>
            </div>

            <!-- File Selection Controls -->
            <div class="bg-white rounded-lg shadow p-4">
                <div class="flex justify-between items-center">
                    <div class="flex items-center space-x-4">
                        <div class="flex items-center space-x-3">
                            <div class="flex items-center space-x-2">
                                <input 
                                    type="checkbox" 
                                    :checked="allFilesSelected" 
                                    @change="$root.toggleSelectAll" 
                                    :indeterminate="selectedFiles.length > 0 && !allFilesSelected"
                                    class="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                                >
                                <span class="text-sm font-medium text-gray-700">
                                    {{ selectionSummaryText }}
                                </span>
                            </div>
                            
                            <div class="relative" v-if="filePagination.total > filePagination.limit">
                                <button @click="$root.showSelectionOptions = !showSelectionOptions" 
                                        class="text-xs text-blue-600 hover:text-blue-800 flex items-center">
                                    <span>Select Options</span>
                                    <svg class="ml-1 h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                                    </svg>
                                </button>
                                
                                <div v-show="showSelectionOptions" class="absolute left-0 mt-1 w-48 bg-white rounded-md shadow-lg border border-gray-200 z-10">
                                    <div class="py-1">
                                        <button @click="$root.selectAllCurrentPage(); showSelectionOptions = false" 
                                                class="block w-full text-left px-3 py-2 text-xs text-gray-700 hover:bg-gray-100">
                                            Select Current Page ({{ files.length }})
                                        </button>
                                        <button @click="$root.selectAllFilteredFiles(); showSelectionOptions = false" 
                                                class="block w-full text-left px-3 py-2 text-xs text-gray-700 hover:bg-gray-100">
                                            Select All Filtered ({{ filePagination.total }})
                                        </button>
                                        <button @click="$root.clearSelection(); showSelectionOptions = false" 
                                                class="block w-full text-left px-3 py-2 text-xs text-gray-700 hover:bg-gray-100">
                                            Clear Selection
                                        </button>
                                    </div>
                                </div>
                            </div>
                            
                            <button @click="$root.clearSelection" 
                                    v-if="selectedFiles.length > 0 && filePagination.total <= filePagination.limit" 
                                    class="text-xs text-gray-500 hover:text-gray-700">
                                Clear
                            </button>
                        </div>
                        
                        <div v-if="selectedFiles.length > 0" class="text-xs text-gray-500">
                            <span v-if="allFilteredFilesSelected">
                                (All {{ filePagination.total }} filtered files)
                            </span>
                            <span v-else-if="filePagination.total > filePagination.limit">
                                ({{ currentPageSelectedCount }}/{{ files.length }} on page, {{ selectedFiles.length }}/{{ filePagination.total }} total)
                            </span>
                        </div>
                    </div>
                    
                    <div class="flex space-x-2" v-if="selectedFiles.length > 0">
                        <button @click="$root.addToNewSession" class="btn btn-green text-sm">
                            Add to New Session
                        </button>
                        <button @click="$root.showAddToExistingModal" class="btn btn-purple text-sm">
                            Add to Existing Session
                        </button>
                    </div>
                </div>
            </div>

            <!-- Files Table -->
            <div class="bg-white rounded-lg shadow overflow-hidden">
                <div class="table-container">
                    <table class="w-full">
                        <thead class="bg-gray-50">
                            <tr>
                                <th class="header-cell w-12 text-center">
                                    <input 
                                        type="checkbox" 
                                        :checked="allFilesSelected" 
                                        @change="$root.toggleSelectAll"
                                        class="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                                    >
                                </th>
                                
                                <th class="header-cell id-col text-left">
                                    <div @click="$root.sortBy('id')" class="sort-header">
                                        <div class="header-title justify-start">
                                            <span>ID</span>
                                            <span v-if="fileSorting.sort_by === 'id'" class="ml-1">
                                                {{ fileSorting.sort_order === 'asc' ? '↑' : '↓' }}
                                            </span>
                                        </div>
                                    </div>
                                </th>
                                
                                <th class="header-cell file-col text-left">
                                    <div @click="$root.sortBy('file')" class="sort-header">
                                        <div class="header-title justify-start">
                                            <span>File</span>
                                            <span v-if="fileSorting.sort_by === 'file'" class="ml-1">
                                                {{ fileSorting.sort_order === 'asc' ? '↑' : '↓' }}
                                            </span>
                                        </div>
                                    </div>
                                    <input v-model="searchFilters.filename" placeholder="Search..." class="filter-input">
                                </th>
                                
                                <th class="header-cell text-left">
                                    <div @click="$root.sortBy('object')" class="sort-header">
                                        <div class="header-title justify-start">
                                            <span>Object</span>
                                            <span v-if="fileSorting.sort_by === 'object'" class="ml-1">
                                                {{ fileSorting.sort_order === 'asc' ? '↑' : '↓' }}
                                            </span>
                                        </div>
                                    </div>
                                    <div class="space-y-1">
                                        <input v-model="objectSearchText" @input="$root.filterObjectOptions" placeholder="Search..." class="filter-input">
                                        <div class="relative">
                                            <button @click="$root.toggleFilter('objects')" class="filter-button">
                                                <span>{{ getFilterText('objects') }}</span>
                                                <span class="text-gray-400">▼</span>
                                            </button>
                                            <div v-show="activeFilter === 'objects'" class="filter-dropdown">
                                                <div class="p-2">
                                                    <label v-for="option in filteredObjectOptions" :key="option" class="filter-option">
                                                        <input type="checkbox" :checked="$root.fileFilters.objects.includes(option)" @change="$root.toggleFilterOption('objects', option)">
                                                        <span>{{ option }}</span>
                                                    </label>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </th>
                                
                                <th class="header-cell type-col text-left">
                                    <div @click="$root.sortBy('frame_type')" class="sort-header">
                                        <div class="header-title justify-start">
                                            <span>Type</span>
                                            <span v-if="fileSorting.sort_by === 'frame_type'" class="ml-1">
                                                {{ fileSorting.sort_order === 'asc' ? '↑' : '↓' }}
                                            </span>
                                        </div>
                                    </div>
                                    <div class="relative">
                                        <button @click="$root.toggleFilter('frame_types')" class="filter-button">
                                            <span>{{ getFilterText('frame_types') }}</span>
                                            <span class="text-gray-400">▼</span>
                                        </button>
                                        <div v-show="activeFilter === 'frame_types'" class="filter-dropdown">
                                            <div class="p-2">
                                                <label v-for="option in filterOptions.frame_types" :key="option" class="filter-option">
                                                    <input type="checkbox" :checked="$root.fileFilters.frame_types.includes(option)" @change="$root.toggleFilterOption('frame_types', option)">
                                                    <span>{{ option }}</span>
                                                </label>
                                            </div>
                                        </div>
                                    </div>
                                </th>
                                
                                <th class="header-cell text-left">
                                    <div @click="$root.sortBy('camera')" class="sort-header">
                                        <div class="header-title justify-start">
                                            <span>Camera</span>
                                            <span v-if="fileSorting.sort_by === 'camera'" class="ml-1">
                                                {{ fileSorting.sort_order === 'asc' ? '↑' : '↓' }}
                                            </span>
                                        </div>
                                    </div>
                                    <div class="relative">
                                        <button @click="$root.toggleFilter('cameras')" class="filter-button">
                                            <span>{{ getFilterText('cameras') }}</span>
                                            <span class="text-gray-400">▼</span>
                                        </button>
                                        <div v-show="activeFilter === 'cameras'" class="filter-dropdown">
                                            <div class="p-2">
                                                <label v-for="option in filterOptions.cameras" :key="option" class="filter-option">
                                                    <input type="checkbox" :checked="$root.fileFilters.cameras.includes(option)" @change="$root.toggleFilterOption('cameras', option)">
                                                    <span>{{ option }}</span>
                                                </label>
                                            </div>
                                        </div>
                                    </div>
                                </th>
                                
                                <th class="header-cell text-left">
                                    <div @click="$root.sortBy('telescope')" class="sort-header">
                                        <div class="header-title justify-start">
                                            <span>Telescope</span>
                                            <span v-if="fileSorting.sort_by === 'telescope'" class="ml-1">
                                                {{ fileSorting.sort_order === 'asc' ? '↑' : '↓' }}
                                            </span>
                                        </div>
                                    </div>
                                    <div class="relative">
                                        <button @click="$root.toggleFilter('telescopes')" class="filter-button">
                                            <span>{{ getFilterText('telescopes') }}</span>
                                            <span class="text-gray-400">▼</span>
                                        </button>
                                        <div v-show="activeFilter === 'telescopes'" class="filter-dropdown">
                                            <div class="p-2">
                                                <label v-for="option in filterOptions.telescopes" :key="option" class="filter-option">
                                                    <input type="checkbox" :checked="$root.fileFilters.telescopes.includes(option)" @change="$root.toggleFilterOption('telescopes', option)">
                                                    <span>{{ option }}</span>
                                                </label>
                                            </div>
                                        </div>
                                    </div>
                                </th>
                                
                                <th class="header-cell filter-col text-left">
                                    <div @click="$root.sortBy('filter')" class="sort-header">
                                        <div class="header-title justify-start">
                                            <span>Filter</span>
                                            <span v-if="fileSorting.sort_by === 'filter'" class="ml-1">
                                                {{ fileSorting.sort_order === 'asc' ? '↑' : '↓' }}
                                            </span>
                                        </div>
                                    </div>
                                    <div class="relative">
                                        <button @click="$root.toggleFilter('filters')" class="filter-button">
                                            <span>{{ getFilterText('filters') }}</span>
                                            <span class="text-gray-400">▼</span>
                                        </button>
                                        <div v-show="activeFilter === 'filters'" class="filter-dropdown">
                                            <div class="p-2">
                                                <label v-for="option in filterOptions.filters" :key="option" class="filter-option">
                                                    <input type="checkbox" :checked="$root.fileFilters.filters.includes(option)" @change="$root.toggleFilterOption('filters', option)">
                                                    <span>{{ option }}</span>
                                                </label>
                                            </div>
                                        </div>
                                    </div>
                                </th>
                                
                                <th class="header-cell exp-col text-right">
                                    <div @click="$root.sortBy('exposure')" class="sort-header">
                                        <div class="header-title justify-end">
                                            <span>Exp</span>
                                            <span v-if="fileSorting.sort_by === 'exposure'" class="ml-1">
                                                {{ fileSorting.sort_order === 'asc' ? '↑' : '↓' }}
                                            </span>
                                        </div>
                                    </div>
                                    <div class="space-y-1">
                                        <input v-model="searchFilters.exposure_min" placeholder="Min" type="number" class="narrow-input">
                                        <input v-model="searchFilters.exposure_max" placeholder="Max" type="number" class="narrow-input">
                                    </div>
                                </th>
                                
                                <th class="header-cell date-col text-right">
                                    <div @click="$root.sortBy('obs_date')" class="sort-header">
                                        <div class="header-title justify-end">
                                            <span>Date</span>
                                            <span v-if="fileSorting.sort_by === 'obs_date'" class="ml-1">
                                                {{ fileSorting.sort_order === 'asc' ? '↑' : '↓' }}
                                            </span>
                                        </div>
                                    </div>
                                    <div class="space-y-1">
                                        <input v-model="searchFilters.date_start" placeholder="Start" type="date" class="narrow-input">
                                        <input v-model="searchFilters.date_end" placeholder="End" type="date" class="narrow-input">
                                    </div>
                                </th>
                                
                                <th class="header-cell text-left">
                                    <div @click="$root.sortBy('session_id')" class="sort-header">
                                        <div class="header-title justify-start">
                                            <span>Session</span>
                                            <span v-if="fileSorting.sort_by === 'session_id'" class="ml-1">
                                                {{ fileSorting.sort_order === 'asc' ? '↑' : '↓' }}
                                            </span>
                                        </div>
                                    </div>
                                    <input v-model="searchFilters.session_id" placeholder="Session..." class="filter-input">
                                </th>
                            </tr>
                        </thead>
                        <tbody class="bg-white divide-y divide-gray-200">
                            <tr v-for="file in files" :key="file.id" class="hover:bg-gray-50">
                                <td class="table-cell-center w-12">
                                    <input 
                                        type="checkbox" 
                                        :value="file.id" 
                                        :checked="selectedFiles.includes(file.id)"
                                        @change="toggleFileSelection(file.id)"
                                        class="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                                    >
                                </td>
                                <td class="table-cell-left id-col text-gray-600">{{ file.id }}</td>
                                <td class="table-cell-left filename-cell file-col">
                                    <div class="filename-tooltip">{{ file.file }}</div>
                                    {{ file.file }}
                                </td>
                                <td class="table-cell-left">{{ file.object || 'N/A' }}</td>
                                <td class="table-cell-left type-col">
                                    <span :class="getFrameTypeClass(file.frame_type)" class="frame-type-badge">
                                        {{ file.frame_type }}
                                    </span>
                                </td>
                                <td class="table-cell-left">{{ file.camera || 'Unknown' }}</td>
                                <td class="table-cell-left">{{ file.telescope || 'Unknown' }}</td>
                                <td class="table-cell-left filter-col">{{ file.filter || 'None' }}</td>
                                <td class="table-cell-right exp-col">{{ file.exposure ? file.exposure + 's' : 'N/A' }}</td>
                                <td class="table-cell-right date-col">{{ file.obs_date || 'N/A' }}</td>
                                <td class="table-cell-left">
                                    <span @click="$root.navigateToSession(file.session_id)" class="session-link">
                                        {{ file.session_id || 'N/A' }}
                                    </span>
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
                
                <div class="pagination-container">
                    <div class="flex items-center justify-between">
                        <div class="text-sm text-gray-700">
                            Showing {{ (filePagination.page - 1) * filePagination.limit + 1 }} to 
                            {{ Math.min(filePagination.page * filePagination.limit, filePagination.total) }} 
                            of {{ filePagination.total }} files
                        </div>
                        <div class="flex space-x-2">
                            <button @click="$root.prevFilePage" :disabled="filePagination.page <= 1" class="pagination-button">
                                Previous
                            </button>
                            <span class="px-3 py-1 text-sm text-gray-700">
                                Page {{ filePagination.page }} of {{ filePagination.pages }}
                            </span>
                            <button @click="$root.nextFilePage" :disabled="filePagination.page >= filePagination.pages" class="pagination-button">
                                Next
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    methods: {
        ...FilesBrowserComponent.methods,
        
        getFrameTypeClass(frameType) {
            const classes = {
                'LIGHT': 'bg-blue-100 text-blue-800',
                'DARK': 'bg-gray-100 text-gray-800',
                'FLAT': 'bg-yellow-100 text-yellow-800',
                'BIAS': 'bg-purple-100 text-purple-800'
            };
            return classes[frameType] || 'bg-gray-100 text-gray-800';
        },
        
        addToNewSession() {
            this.$root.addToNewSession();
        },
        
        showAddToExistingModal() {
            this.$root.showAddToExistingModal();
        },
        
        selectAllCurrentPage() {
            this.$root.selectAllCurrentPage();
        },
        
        async selectAllFilteredFiles() {
            await this.$root.selectAllFilteredFiles();
        }
    },
    
    computed: {
        files() { return this.$root.files; },
        selectedFiles() { return this.$root.selectedFiles; },
        filePagination() { return this.$root.filePagination; },
        fileSorting() { return this.$root.fileSorting; },
        searchFilters() { return this.$root.searchFilters; },
        fileFilters() { return this.$root.fileFilters; },
        filterOptions() { return this.$root.filterOptions; },
        showSelectionOptions: {
            get() { return this.$root.showSelectionOptions; },
            set(val) { this.$root.showSelectionOptions = val; }
        },
        activeFilter: {
            get() { return this.$root.activeFilter; },
            set(val) { this.$root.activeFilter = val; }
        },
        objectSearchText: {
            get() { return this.$root.objectSearchText; },
            set(val) { this.$root.objectSearchText = val; }
        },
        hasActiveFilters() { return this.$root.hasActiveFilters || false; },
        allFilesSelected() { return this.$root.allFilteredFilesSelected || false; },
        allFilteredFilesSelected() { return this.$root.allFilteredFilesSelected; },
        currentPageSelectedCount() { 
            return this.files.filter(f => this.selectedFiles.includes(f.id)).length; 
        },
        selectionSummaryText() {
            if (this.selectedFiles.length === 0) return '';
            return `${this.selectedFiles.length} file${this.selectedFiles.length === 1 ? '' : 's'} selected`;
        },
        filteredObjectOptions() { return this.$root.filteredObjectOptions; }
    }
};

window.FilesTab = FilesTab;