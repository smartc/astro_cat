/**
 * Equipment Tab Component
 * Manage cameras, telescopes, and filters
 */

const EquipmentTab = {
    data() {
        return {
            activeEquipmentType: 'cameras',
            cameras: [],
            telescopes: [],
            filters: [],
            loading: false,
            editingItem: null,
            showEditModal: false,
            newItem: {},
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
                            <thead class="bg-gray-50">
                                <tr>
                                    <th class="header-cell">Name</th>
                                    <th class="header-cell">Brand</th>
                                    <th class="header-cell">X Pixels</th>
                                    <th class="header-cell">Y Pixels</th>
                                    <th class="header-cell">Pixel Size</th>
                                    <th class="header-cell">Type</th>
                                    <th class="header-cell">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="camera in cameras" :key="camera.camera" class="border-b hover:bg-gray-50">
                                    <td class="data-cell">{{ camera.camera }}</td>
                                    <td class="data-cell">{{ camera.brand || '-' }}</td>
                                    <td class="data-cell">{{ camera.x }}</td>
                                    <td class="data-cell">{{ camera.y }}</td>
                                    <td class="data-cell">{{ camera.pixel }}µm</td>
                                    <td class="data-cell">{{ camera.type }}</td>
                                    <td class="data-cell">
                                        <button @click="editCamera(camera)" class="text-blue-600 hover:text-blue-800 mr-2">Edit</button>
                                        <button @click="deleteCamera(camera)" class="text-red-600 hover:text-red-800">Delete</button>
                                    </td>
                                </tr>
                                <tr v-if="cameras.length === 0">
                                    <td colspan="7" class="data-cell text-center text-gray-500">No cameras configured</td>
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
                            <thead class="bg-gray-50">
                                <tr>
                                    <th class="header-cell">Name</th>
                                    <th class="header-cell">Make</th>
                                    <th class="header-cell">Type</th>
                                    <th class="header-cell">Focal Length</th>
                                    <th class="header-cell">Aperture</th>
                                    <th class="header-cell">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="telescope in telescopes" :key="telescope.scope" class="border-b hover:bg-gray-50">
                                    <td class="data-cell">{{ telescope.scope }}</td>
                                    <td class="data-cell">{{ telescope.make || '-' }}</td>
                                    <td class="data-cell">{{ telescope.type || '-' }}</td>
                                    <td class="data-cell">{{ telescope.focal }}mm</td>
                                    <td class="data-cell">{{ telescope.aperture }}mm</td>
                                    <td class="data-cell">
                                        <button @click="editTelescope(telescope)" class="text-blue-600 hover:text-blue-800 mr-2">Edit</button>
                                        <button @click="deleteTelescope(telescope)" class="text-red-600 hover:text-red-800">Delete</button>
                                    </td>
                                </tr>
                                <tr v-if="telescopes.length === 0">
                                    <td colspan="6" class="data-cell text-center text-gray-500">No telescopes configured</td>
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
                        <button @click="addNewFilter" class="btn btn-green">Add Filter Mapping</button>
                    </div>
                    
                    <div class="mb-4 p-4 bg-blue-50 rounded">
                        <p class="text-sm text-gray-700">
                            Filter mappings normalize varying filter names in FITS headers. 
                            For example, map "Ha" and "H-Alpha" to a standard "HA".
                        </p>
                    </div>
                    
                    <div class="table-container">
                        <table class="w-full">
                            <thead class="bg-gray-50">
                                <tr>
                                    <th class="header-cell">Raw Name (in FITS)</th>
                                    <th class="header-cell">Proper Name (standardized)</th>
                                    <th class="header-cell">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="(filter, index) in filters" :key="index" class="border-b hover:bg-gray-50">
                                    <td class="data-cell">{{ filter.raw_name }}</td>
                                    <td class="data-cell">{{ filter.proper_name }}</td>
                                    <td class="data-cell">
                                        <button @click="editFilter(filter, index)" class="text-blue-600 hover:text-blue-800 mr-2">Edit</button>
                                        <button @click="deleteFilter(index)" class="text-red-600 hover:text-red-800">Delete</button>
                                    </td>
                                </tr>
                                <tr v-if="filters.length === 0">
                                    <td colspan="3" class="data-cell text-center text-gray-500">No filter mappings configured</td>
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
        }
    },
    
    mounted() {
        this.loadEquipment();
    }
};

window.EquipmentTab = EquipmentTab;