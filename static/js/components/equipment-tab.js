/**
 * Equipment Tab Component
 * Manage cameras, telescopes, and filters
 */

const EquipmentTab = {
    data() {
        return {
            cameras: [],
            telescopes: [],
            filters: [],
            showEditModal: false,
            editingItem: null,
            editType: '',
            newItem: {},
            activeEquipmentType: 'cameras',  // ADD THIS LINE
            cameraSortBy: 'camera',
            cameraSortOrder: 'asc',
            telescopeSortBy: 'scope',
            telescopeSortOrder: 'asc',
            filterSortBy: 'raw_name',
            filterSortOrder: 'asc'
        };
    },

    template: `
        <div class="space-y-6">
            <!-- Equipment Type Selector -->
            <div class="bg-white rounded-lg shadow p-4">
                <div class="flex space-x-4">
                    <button 
                        @click="activeEquipmentType = 'cameras'" 
                        :class="activeEquipmentType === 'cameras' ? 'btn-blue' : 'btn-gray'"
                        class="btn">
                        📷 Cameras
                    </button>
                    <button 
                        @click="activeEquipmentType = 'telescopes'" 
                        :class="activeEquipmentType === 'telescopes' ? 'btn-blue' : 'btn-gray'"
                        class="btn">
                        🔭 Telescopes
                    </button>
                    <button 
                        @click="activeEquipmentType = 'filters'" 
                        :class="activeEquipmentType === 'filters' ? 'btn-blue' : 'btn-gray'"
                        class="btn">
                        🎨 Filters
                    </button>
                </div>
            </div>

            <!-- Cameras Section -->
            <div v-if="activeEquipmentType === 'cameras'" class="bg-white rounded-lg shadow">
                <div class="p-6">
                    <div class="flex justify-between items-center mb-4">
                        <h2 class="text-xl font-bold">Cameras</h2>
                        <button @click="addNewCamera" class="btn btn-green">Add Camera</button>
                    </div>
                    
                    <div class="table-container">
                        <table class="w-full">
                             <thead>
                                <tr class="bg-gray-50">
                                    <th @click="sortCameras('camera')" class="px-4 py-2 text-left text-sm font-semibold text-gray-700 cursor-pointer hover:bg-gray-100">
                                        Camera {{ getSortIcon('camera', 'camera') }}
                                    </th>
                                    <th @click="sortCameras('type')" class="px-4 py-2 text-left text-sm font-semibold text-gray-700 cursor-pointer hover:bg-gray-100">
                                        Type {{ getSortIcon('camera', 'type') }}
                                    </th>
                                    <th @click="sortCameras('x')" class="px-4 py-2 text-right text-sm font-semibold text-gray-700 cursor-pointer hover:bg-gray-100">
                                        X Pixels {{ getSortIcon('camera', 'x') }}
                                    </th>
                                    <th @click="sortCameras('y')" class="px-4 py-2 text-right text-sm font-semibold text-gray-700 cursor-pointer hover:bg-gray-100">
                                        Y Pixels {{ getSortIcon('camera', 'y') }}
                                    </th>
                                    <th @click="sortCameras('pixel')" class="px-4 py-2 text-right text-sm font-semibold text-gray-700 cursor-pointer hover:bg-gray-100">
                                        Pixel (µm) {{ getSortIcon('camera', 'pixel') }}
                                    </th>
                                    <th class="px-4 py-2 text-center text-sm font-semibold text-gray-700">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="camera in sortedCameras" :key="camera.camera" class="border-t hover:bg-gray-50">
                                    <td class="px-4 py-2 text-left">{{ camera.camera }}</td>
                                    <td class="px-4 py-2 text-left">{{ camera.type }}</td>
                                    <td class="px-4 py-2 text-right">{{ camera.x }}</td>
                                    <td class="px-4 py-2 text-right">{{ camera.y }}</td>
                                    <td class="px-4 py-2 text-right">{{ camera.pixel }}</td>
                                    <td class="px-4 py-2 text-center">
                                        <button @click="editCamera(camera)" class="text-blue-600 hover:text-blue-800 mr-2">Edit</button>
                                        <button @click="deleteCamera(camera)" class="text-red-600 hover:text-red-800">Delete</button>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- Telescopes Section -->
            <div v-if="activeEquipmentType === 'telescopes'" class="bg-white rounded-lg shadow">
                <div class="p-6">
                    <div class="flex justify-between items-center mb-4">
                        <h2 class="text-xl font-bold">Telescopes</h2>
                        <button @click="addNewTelescope" class="btn btn-green">Add Telescope</button>
                    </div>
                    
                    <div class="table-container">
                        <table class="w-full">
                            <thead>
                                <tr class="bg-gray-50">
                                    <th @click="sortTelescopes('scope')" class="px-4 py-2 text-left text-sm font-semibold text-gray-700 cursor-pointer hover:bg-gray-100">
                                        Telescope {{ getSortIcon('telescope', 'scope') }}
                                    </th>
                                    <th @click="sortTelescopes('focal')" class="px-4 py-2 text-right text-sm font-semibold text-gray-700 cursor-pointer hover:bg-gray-100">
                                        Focal (mm) {{ getSortIcon('telescope', 'focal') }}
                                    </th>
                                    <th @click="sortTelescopes('aperture')" class="px-4 py-2 text-right text-sm font-semibold text-gray-700 cursor-pointer hover:bg-gray-100">
                                        Aperture (mm) {{ getSortIcon('telescope', 'aperture') }}
                                    </th>
                                    <th class="px-4 py-2 text-center text-sm font-semibold text-gray-700">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="telescope in sortedTelescopes" :key="telescope.scope" class="border-t hover:bg-gray-50">
                                    <td class="px-4 py-2 text-left">{{ telescope.scope }}</td>
                                    <td class="px-4 py-2 text-right">{{ telescope.focal }}</td>
                                    <td class="px-4 py-2 text-right">{{ telescope.aperture }}</td>
                                    <td class="px-4 py-2 text-center">
                                        <button @click="editTelescope(telescope)" class="text-blue-600 hover:text-blue-800 mr-2">Edit</button>
                                        <button @click="deleteTelescope(telescope)" class="text-red-600 hover:text-red-800">Delete</button>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- Filters Section -->
            <div v-if="activeEquipmentType === 'filters'" class="bg-white rounded-lg shadow">
                <div class="p-6">
                    <div class="flex justify-between items-center mb-4">
                        <h2 class="text-xl font-bold">Filter Mappings</h2>
                        <div class="flex space-x-2">
                            <a href="/static/astrobin-filter-mapper.html" target="_blank" class="btn btn-blue">
                                🔗 AstroBin Filter Mapper
                            </a>
                            <button @click="addNewFilter" class="btn btn-green">Add Filter Mapping</button>
                        </div>
                    </div>

                    <div class="mb-4 p-4 bg-blue-50 rounded">
                        <p class="text-sm text-gray-700">
                            Filter mappings normalize varying filter names in FITS headers.
                            For example, map "Ha" and "H-Alpha" to a standard "HA".
                        </p>
                        <p class="text-sm text-gray-700 mt-2">
                            <strong>Tip:</strong> Use the <a href="/static/astrobin-filter-mapper.html" target="_blank" class="text-blue-600 hover:text-blue-800 underline">AstroBin Filter Mapper</a> to import filter data from AstroBin CSV exports.
                        </p>
                    </div>
                    
                    <div class="table-container">
                        <table class="w-full">
                            <thead>
                                <tr class="bg-gray-50">
                                    <th @click="sortFilters('raw_name')" class="px-4 py-2 text-left text-sm font-semibold text-gray-700 cursor-pointer hover:bg-gray-100">
                                        Raw Name {{ getSortIcon('filter', 'raw_name') }}
                                    </th>
                                    <th @click="sortFilters('proper_name')" class="px-4 py-2 text-left text-sm font-semibold text-gray-700 cursor-pointer hover:bg-gray-100">
                                        Proper Name {{ getSortIcon('filter', 'proper_name') }}
                                    </th>
                                    <th class="px-4 py-2 text-center text-sm font-semibold text-gray-700">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="(filter, index) in sortedFilters" :key="index" class="border-t hover:bg-gray-50">
                                    <td class="px-4 py-2 text-left">{{ filter.raw_name }}</td>
                                    <td class="px-4 py-2 text-left">{{ filter.proper_name }}</td>
                                    <td class="px-4 py-2 text-center">
                                        <button @click="editFilter(index)" class="text-blue-600 hover:text-blue-800 mr-2">Edit</button>
                                        <button @click="deleteFilter(index)" class="text-red-600 hover:text-red-800">Delete</button>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <!-- Edit Modal -->
            <div v-if="showEditModal" class="modal-overlay" @click.self="closeEditModal">
                <div class="modal-content max-w-2xl">
                    <div class="modal-header">
                        <h3 class="modal-title">{{ editingItem ? 'Edit' : 'Add' }} {{ activeEquipmentType.slice(0, -1) }}</h3>
                        <button @click="closeEditModal" class="modal-close">&times;</button>
                    </div>
                    
                    <div class="modal-body">
                        <!-- Camera Form -->
                        <div v-if="activeEquipmentType === 'cameras'" class="space-y-4">
                            <div>
                                <label class="block text-sm font-medium mb-1">Camera Name *</label>
                                <input v-model="newItem.camera" type="text" class="form-input" required>
                            </div>
                            <div class="grid grid-cols-2 gap-4">
                                <div>
                                    <label class="block text-sm font-medium mb-1">Brand</label>
                                    <input v-model="newItem.brand" type="text" class="form-input">
                                </div>
                                <div>
                                    <label class="block text-sm font-medium mb-1">Type *</label>
                                    <select v-model="newItem.type" class="form-input">
                                        <option>CMOS</option>
                                        <option>CCD</option>
                                        <option>DSLR</option>
                                    </select>
                                </div>
                            </div>
                            <div class="grid grid-cols-3 gap-4">
                                <div>
                                    <label class="block text-sm font-medium mb-1">X Pixels *</label>
                                    <input v-model.number="newItem.x" type="number" class="form-input" required>
                                </div>
                                <div>
                                    <label class="block text-sm font-medium mb-1">Y Pixels *</label>
                                    <input v-model.number="newItem.y" type="number" class="form-input" required>
                                </div>
                                <div>
                                    <label class="block text-sm font-medium mb-1">Pixel Size (µm) *</label>
                                    <input v-model.number="newItem.pixel" type="number" step="0.1" class="form-input" required>
                                </div>
                            </div>
                            <div>
                                <label class="block text-sm font-medium mb-1">Comments</label>
                                <textarea v-model="newItem.comments" class="form-input" rows="3"></textarea>
                            </div>
                        </div>

                        <!-- Telescope Form -->
                        <div v-if="activeEquipmentType === 'telescopes'" class="space-y-4">
                            <div>
                                <label class="block text-sm font-medium mb-1">Telescope Name *</label>
                                <input v-model="newItem.scope" type="text" class="form-input" required>
                            </div>
                            <div class="grid grid-cols-2 gap-4">
                                <div>
                                    <label class="block text-sm font-medium mb-1">Make</label>
                                    <input v-model="newItem.make" type="text" class="form-input">
                                </div>
                                <div>
                                    <label class="block text-sm font-medium mb-1">Type</label>
                                    <input v-model="newItem.type" type="text" class="form-input" placeholder="Refractor, Reflector, etc.">
                                </div>
                            </div>
                            <div class="grid grid-cols-2 gap-4">
                                <div>
                                    <label class="block text-sm font-medium mb-1">Focal Length (mm) *</label>
                                    <input v-model.number="newItem.focal" type="number" class="form-input" required>
                                </div>
                                <div>
                                    <label class="block text-sm font-medium mb-1">Aperture (mm) *</label>
                                    <input v-model.number="newItem.aperture" type="number" class="form-input" required>
                                </div>
                            </div>
                            <div>
                                <label class="block text-sm font-medium mb-1">Comments</label>
                                <textarea v-model="newItem.comments" class="form-input" rows="3"></textarea>
                            </div>
                        </div>

                        <!-- Filter Form -->
                        <div v-if="activeEquipmentType === 'filters'" class="space-y-4">
                            <div>
                                <label class="block text-sm font-medium mb-1">Raw Name (as it appears in FITS) *</label>
                                <input v-model="newItem.raw_name" type="text" class="form-input" required>
                            </div>
                            <div>
                                <label class="block text-sm font-medium mb-1">Proper Name (standardized) *</label>
                                <input v-model="newItem.proper_name" type="text" class="form-input" required>
                            </div>
                        </div>
                    </div>
                    
                    <div class="modal-footer">
                        <button @click="closeEditModal" class="btn btn-gray">Cancel</button>
                        <button @click="saveItem" class="btn btn-green">Save</button>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    methods: {
        async loadEquipment() {
            try {
                this.loading = true;
                const response = await axios.get('/api/equipment/all');
                this.cameras = response.data.cameras || [];
                this.telescopes = response.data.telescopes || [];
                this.filters = response.data.filters || [];
            } catch (error) {
                console.error('Error loading equipment:', error);
                this.$root.errorMessage = 'Failed to load equipment data';
            } finally {
                this.loading = false;
            }
        },
        
        addNewCamera() {
            this.newItem = { camera: '', brand: '', type: 'CMOS', x: 0, y: 0, pixel: 0, bin: 1, rgb: false, comments: '' };
            this.editingItem = null;
            this.showEditModal = true;
        },
        
        addNewTelescope() {
            this.newItem = { scope: '', make: '', type: '', focal: 0, aperture: 0, subtype: '', comments: '' };
            this.editingItem = null;
            this.showEditModal = true;
        },
        
        addNewFilter() {
            this.newItem = { raw_name: '', proper_name: '' };
            this.editingItem = null;
            this.showEditModal = true;
        },
        
        editCamera(camera) {
            this.newItem = { ...camera };
            this.editingItem = camera;
            this.showEditModal = true;
        },
        
        editTelescope(telescope) {
            this.newItem = { ...telescope };
            this.editingItem = telescope;
            this.showEditModal = true;
        },
        
        editFilter(filter, index) {
            this.newItem = { ...filter };
            this.editingItem = { ...filter, index };
            this.showEditModal = true;
        },
        
        async saveItem() {
            try {
                const endpoint = `/api/equipment/${this.activeEquipmentType}`;
                if (this.editingItem) {
                    await axios.put(endpoint, this.newItem);
                } else {
                    await axios.post(endpoint, this.newItem);
                }
                await this.loadEquipment();
                this.closeEditModal();
            } catch (error) {
                console.error('Error saving item:', error);
                this.$root.errorMessage = error.response?.data?.detail || 'Failed to save equipment';
            }
        },
        
        async deleteCamera(camera) {
            if (!confirm(`Delete camera ${camera.camera}?`)) return;
            try {
                await axios.delete(`/api/equipment/cameras/${encodeURIComponent(camera.camera)}`);
                await this.loadEquipment();
            } catch (error) {
                console.error('Error deleting camera:', error);
                this.$root.errorMessage = 'Failed to delete camera';
            }
        },
        
        async deleteTelescope(telescope) {
            if (!confirm(`Delete telescope ${telescope.scope}?`)) return;
            try {
                await axios.delete(`/api/equipment/telescopes/${encodeURIComponent(telescope.scope)}`);
                await this.loadEquipment();
            } catch (error) {
                console.error('Error deleting telescope:', error);
                this.$root.errorMessage = 'Failed to delete telescope';
            }
        },
        
        async deleteFilter(index) {
            const filter = this.filters[index];
            if (!confirm(`Delete filter mapping ${filter.raw_name} → ${filter.proper_name}?`)) return;
            try {
                await axios.delete(`/api/equipment/filters/${index}`);
                await this.loadEquipment();
            } catch (error) {
                console.error('Error deleting filter:', error);
                this.$root.errorMessage = 'Failed to delete filter mapping';
            }
        },
        
        closeEditModal() {
            this.showEditModal = false;
            this.editingItem = null;
            this.newItem = {};
        },

        sortCameras(column) {
            if (this.cameraSortBy === column) {
                this.cameraSortOrder = this.cameraSortOrder === 'asc' ? 'desc' : 'asc';
            } else {
                this.cameraSortBy = column;
                this.cameraSortOrder = 'asc';
            }
        },
        
        sortTelescopes(column) {
            if (this.telescopeSortBy === column) {
                this.telescopeSortOrder = this.telescopeSortOrder === 'asc' ? 'desc' : 'asc';
            } else {
                this.telescopeSortBy = column;
                this.telescopeSortOrder = 'asc';
            }
        },
        
        sortFilters(column) {
            if (this.filterSortBy === column) {
                this.filterSortOrder = this.filterSortOrder === 'asc' ? 'desc' : 'asc';
            } else {
                this.filterSortBy = column;
                this.filterSortOrder = 'asc';
            }
        },
        
        getSortIcon(type, column) {
            let sortBy, sortOrder;
            if (type === 'camera') {
                sortBy = this.cameraSortBy;
                sortOrder = this.cameraSortOrder;
            } else if (type === 'telescope') {
                sortBy = this.telescopeSortBy;
                sortOrder = this.telescopeSortOrder;
            } else {
                sortBy = this.filterSortBy;
                sortOrder = this.filterSortOrder;
            }
            
            if (sortBy !== column) return '↕';
            return sortOrder === 'asc' ? '↑' : '↓';
        },
    },

    computed: {
        sortedCameras() {
            return [...this.cameras].sort((a, b) => {
                let aVal = a[this.cameraSortBy];
                let bVal = b[this.cameraSortBy];
                
                // Handle numeric fields
                if (['x', 'y', 'pixel'].includes(this.cameraSortBy)) {
                    aVal = Number(aVal) || 0;
                    bVal = Number(bVal) || 0;
                }
                
                if (aVal < bVal) return this.cameraSortOrder === 'asc' ? -1 : 1;
                if (aVal > bVal) return this.cameraSortOrder === 'asc' ? 1 : -1;
                return 0;
            });
        },
        sortedTelescopes() {
            return [...this.telescopes].sort((a, b) => {
                let aVal = a[this.telescopeSortBy];
                let bVal = b[this.telescopeSortBy];
                
                // Handle numeric fields
                if (['focal', 'aperture'].includes(this.telescopeSortBy)) {
                    aVal = Number(aVal) || 0;
                    bVal = Number(bVal) || 0;
                }
                
                if (aVal < bVal) return this.telescopeSortOrder === 'asc' ? -1 : 1;
                if (aVal > bVal) return this.telescopeSortOrder === 'asc' ? 1 : -1;
                return 0;
            });
        },
        sortedFilters() {
            return [...this.filters].sort((a, b) => {
                let aVal = a[this.filterSortBy];
                let bVal = b[this.filterSortBy];
                
                if (aVal < bVal) return this.filterSortOrder === 'asc' ? -1 : 1;
                if (aVal > bVal) return this.filterSortOrder === 'asc' ? 1 : -1;
                return 0;
            });
        }
    },
    
    mounted() {
        this.loadEquipment();
    }
};

window.EquipmentTab = EquipmentTab;