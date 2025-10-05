/**
 * App Header Component - Shared across all pages
 */

const AppHeader = {
    template: `
        <header style="background-color: #0A1628; flex-shrink: 0;" class="text-white p-4 shadow-lg">
            <div class="flex justify-between items-center px-4">
                <div class="flex items-center space-x-3 cursor-pointer" @click="goToDashboard">
                    <img src="/static/logo.png" alt="AstroCat" style="width: 96px; height: 96px;">
                    <h1 class="text-2xl font-bold">AstroCat</h1>
                </div>
                
                <div class="relative">
                    <button @click="menuOpen = !menuOpen" 
                            class="p-2 rounded hover:bg-gray-700 transition focus:outline-none focus:ring-2 focus:ring-gray-500">
                        <span v-html="icons.bars3"></span>
                    </button>
                
                    <div v-show="menuOpen" 
                         @click.away="menuOpen = false"
                         class="absolute right-0 mt-2 w-56 bg-white rounded-lg shadow-xl z-50 py-2">
                        
                        <!-- Navigation Items -->
                        <a @click="navigateTo('/?tab=dashboard')" class="menu-item">
                            <span v-html="icons.home"></span>
                            Dashboard
                        </a>
                        
                        <a @click="navigateTo('/?tab=files')" class="menu-item">
                            <span v-html="icons.files"></span>
                            Files
                        </a>
                        
                        <a @click="navigateTo('/?tab=imaging-sessions')" class="menu-item">
                            <span v-html="icons.calendar"></span>
                            Imaging Sessions
                        </a>
                        
                        <a @click="navigateTo('/?tab=processing-sessions')" class="menu-item">
                            <span v-html="icons.clipboard"></span>
                            Processing Sessions
                        </a>
                        
                        <a @click="navigateTo('/?tab=operations')" class="menu-item">
                            <span v-html="icons.cog"></span>
                            Operations
                        </a>
                        
                        <div class="border-t border-gray-200 my-2"></div>
                        
                        <!-- Additional Items -->
                        <a @click="navigateTo('/?tab=equipment')" class="menu-item">
                            <span v-html="icons.monitor"></span>
                            Equipment
                        </a>
                        
                        <a @click="navigateTo('/database-viewer')" class="menu-item">
                            <span v-html="icons.database"></span>
                            Database Browser
                        </a>
                        
                        <a @click="navigateTo('/?tab=configuration')" class="menu-item">
                            <span v-html="icons.settings"></span>
                            Configuration
                        </a>
                    </div>
                </div>
            </div>
        </header>
    `,
    
    data() {
        return {
            menuOpen: false
        }
    },
    
    computed: {
        icons() {
            return window.Icons;
        },
        databaseUrl() {
            return `http://${window.location.hostname}:8081`;
        }
    },

    methods: {
        goToDashboard() {
            window.location.href = '/';
        },
        navigateTo(path) {
            window.location.href = path;
            this.menuOpen = false;
        },
        openDatabaseDirectly() {
            window.open(this.databaseUrl, '_blank', 'width=1400,height=900');
            this.menuOpen = false;
        }
    }
};

window.AppHeader = AppHeader;