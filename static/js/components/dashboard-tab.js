/**
 * Dashboard Tab Component
 */

const DashboardTab = {
    template: `
        <div class="space-y-6">
            <!-- Main Stats Grid -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
                <div class="stats-card">
                    <h3 class="text-lg font-semibold text-gray-700 mb-2">Total Files</h3>
                    <p class="text-3xl font-bold text-blue-600">{{ stats.total_files || 0 }}</p>
                </div>
                <div class="stats-card">
                    <h3 class="text-lg font-semibold text-gray-700 mb-2">Registered</h3>
                    <p class="text-3xl font-bold text-green-600">{{ (stats.validation && stats.validation.registered) || 0 }}</p>
                    <p class="text-sm text-gray-500">≥95 points</p>
                </div>
                <div class="stats-card">
                    <h3 class="text-lg font-semibold text-gray-700 mb-2">Ready</h3>
                    <p class="text-3xl font-bold text-green-600">{{ (stats.validation && stats.validation.auto_migrate) || 0 }}</p>
                    <p class="text-sm text-gray-500">≥95 points</p>
                </div>
                <div class="stats-card">
                    <h3 class="text-lg font-semibold text-gray-700 mb-2">Needs Review</h3>
                    <p class="text-3xl font-bold text-yellow-600">{{ (stats.validation && stats.validation.needs_review) || 0 }}</p>
                    <p class="text-sm text-gray-500">80-94 points</p>
                </div>
                <div class="stats-card">
                    <h3 class="text-lg font-semibold text-gray-700 mb-2">Manual Only</h3>
                    <p class="text-3xl font-bold text-red-600">{{ (stats.validation && stats.validation.manual_only) || 0 }}</p>
                    <p class="text-sm text-gray-500">&lt;80 points</p>
                </div>
            </div>

            <!-- Session Statistics - Three Column Layout -->
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <!-- Imaging Sessions Card - Clickable -->
                <div class="bg-white rounded-lg shadow-md p-6 cursor-pointer hover:shadow-lg transition" @click="goToImagingSessions">
                    <div class="flex justify-between items-center mb-4">
                        <h2 class="text-xl font-bold text-gray-800">Imaging Sessions</h2>
                        <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                        </svg>
                    </div>
                    <div class="space-y-3">
                        <div class="border-l-4 border-blue-500 pl-4 h-20">
                            <h3 class="text-sm font-semibold text-gray-600 mb-1">Total Sessions</h3>
                            <p class="text-2xl font-bold text-blue-600">{{ (stats.imaging_sessions && stats.imaging_sessions.total) || 0 }}</p>
                            <p class="text-xs text-gray-500 mt-1">Observation nights</p>
                        </div>
                        <div class="border-l-4 border-purple-500 pl-4 h-20">
                            <h3 class="text-sm font-semibold text-gray-600 mb-1">Unique Cameras</h3>
                            <p class="text-2xl font-bold text-purple-600">{{ (stats.imaging_sessions && stats.imaging_sessions.unique_cameras) || 0 }}</p>
                            <p class="text-xs text-gray-500 mt-1">Used in sessions</p>
                        </div>
                        <div class="border-l-4 border-indigo-500 pl-4 h-20">
                            <h3 class="text-sm font-semibold text-gray-600 mb-1">Unique Telescopes</h3>
                            <p class="text-2xl font-bold text-indigo-600">{{ (stats.imaging_sessions && stats.imaging_sessions.unique_telescopes) || 0 }}</p>
                            <p class="text-xs text-gray-500 mt-1">Used in sessions</p>
                        </div>
                    </div>
                </div>

                <!-- Processing Sessions Card - Clickable -->
                <div class="bg-white rounded-lg shadow-md p-6 cursor-pointer hover:shadow-lg transition" @click="goToProcessingSessions">
                    <div class="flex justify-between items-center mb-4">
                        <h2 class="text-xl font-bold text-gray-800">Processing Sessions</h2>
                        <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                        </svg>
                    </div>
                    <div class="space-y-3">
                        <div class="border-l-4 border-blue-500 pl-4 h-20">
                            <h3 class="text-sm font-semibold text-gray-600 mb-1">Total Sessions</h3>
                            <p class="text-2xl font-bold text-blue-600">{{ (stats.processing_sessions && stats.processing_sessions.total) || 0 }}</p>
                            <p class="text-xs text-gray-500 mt-1">&nbsp;</p>
                        </div>
                        <div class="border-l-4 border-yellow-500 pl-4 h-20">
                            <h3 class="text-sm font-semibold text-gray-600 mb-1">In Progress</h3>
                            <p class="text-2xl font-bold text-yellow-600">{{ (stats.processing_sessions && stats.processing_sessions.in_progress) || 0 }}</p>
                            <p class="text-xs text-gray-500 mt-1">&nbsp;</p>
                        </div>
                        <div class="border-l-4 border-green-500 pl-4 h-20">
                            <h3 class="text-sm font-semibold text-gray-600 mb-1">Active Sessions</h3>
                            <p class="text-2xl font-bold text-green-600">{{ (stats.processing_sessions && stats.processing_sessions.active) || 0 }}</p>
                            <p class="text-xs text-gray-500 mt-1">Not started or in progress</p>
                        </div>
                    </div>
                </div>

                <!-- File Management Card - Clickable -->
                <div class="bg-white rounded-lg shadow-md p-6 cursor-pointer hover:shadow-lg transition" @click="goToOperations">
                    <div class="flex justify-between items-center mb-4">
                        <h2 class="text-xl font-bold text-gray-800">File Management</h2>
                        <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                        </svg>
                    </div>
                    <div class="space-y-3">
                        <div class="border-l-4 border-orange-500 pl-4 h-20">
                            <h3 class="text-sm font-semibold text-gray-600 mb-1">Quarantine</h3>
                            <p class="text-2xl font-bold text-orange-600">{{ stats.quarantine_files || 0 }}</p>
                            <p class="text-xs text-gray-500 mt-1">Awaiting processing</p>
                        </div>
                        <div class="border-l-4 border-purple-500 pl-4 h-20">
                            <h3 class="text-sm font-semibold text-gray-600 mb-1">Staged</h3>
                            <p class="text-2xl font-bold text-purple-600">{{ stats.staged_files || 0 }}</p>
                            <p class="text-xs text-gray-500 mt-1">In processing sessions</p>
                        </div>
                        <div class="border-l-4 border-red-500 pl-4 h-20">
                            <h3 class="text-sm font-semibold text-gray-600 mb-1">Needs Attention</h3>
                            <p class="text-2xl font-bold text-red-600">{{ cleanupTotal }}</p>
                            <p class="text-xs text-gray-500 mt-1">Duplicates, bad, missing</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Frame Type Distribution -->
            <div class="bg-white rounded-lg shadow-md p-6">
                <h2 class="text-xl font-bold text-gray-800 mb-4">Frame Type Distribution</h2>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div class="text-center p-4 bg-blue-50 rounded-lg">
                        <p class="text-sm font-semibold text-gray-600 mb-1">LIGHT</p>
                        <p class="text-2xl font-bold text-blue-600">{{ (stats.by_frame_type && stats.by_frame_type.LIGHT) || 0 }}</p>
                    </div>
                    <div class="text-center p-4 bg-gray-50 rounded-lg">
                        <p class="text-sm font-semibold text-gray-600 mb-1">DARK</p>
                        <p class="text-2xl font-bold text-gray-600">{{ (stats.by_frame_type && stats.by_frame_type.DARK) || 0 }}</p>
                    </div>
                    <div class="text-center p-4 bg-green-50 rounded-lg">
                        <p class="text-sm font-semibold text-gray-600 mb-1">FLAT</p>
                        <p class="text-2xl font-bold text-green-600">{{ (stats.by_frame_type && stats.by_frame_type.FLAT) || 0 }}</p>
                    </div>
                    <div class="text-center p-4 bg-purple-50 rounded-lg">
                        <p class="text-sm font-semibold text-gray-600 mb-1">BIAS</p>
                        <p class="text-2xl font-bold text-purple-600">{{ (stats.by_frame_type && stats.by_frame_type.BIAS) || 0 }}</p>
                    </div>
                </div>
            </div>

            <!-- Cleanup Information -->
            <div v-if="cleanupTotal > 0" class="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
                <h2 class="text-xl font-bold text-yellow-800 mb-4">⚠️ Items Needing Attention</h2>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div v-if="(stats.cleanup && stats.cleanup.duplicates) > 0" class="text-center">
                        <p class="text-3xl font-bold text-yellow-600">{{ stats.cleanup.duplicates }}</p>
                        <p class="text-sm text-gray-600">Duplicate Files</p>
                    </div>
                    <div v-if="(stats.cleanup && stats.cleanup.bad_files) > 0" class="text-center">
                        <p class="text-3xl font-bold text-red-600">{{ stats.cleanup.bad_files }}</p>
                        <p class="text-sm text-gray-600">Bad Files</p>
                    </div>
                    <div v-if="(stats.cleanup && stats.cleanup.missing_files) > 0" class="text-center">
                        <p class="text-3xl font-bold text-orange-600">{{ stats.cleanup.missing_files }}</p>
                        <p class="text-sm text-gray-600">Missing Files</p>
                    </div>
                </div>
            </div>

            <!-- Integration Time Summary -->
            <div class="bg-white rounded-lg shadow-md p-6">
                <h2 class="text-xl font-bold text-gray-800 mb-4">Integration Time Summary (LIGHT Frames)</h2>

                <!-- Total Integration Time -->
                <div class="mb-6 p-4 bg-blue-50 rounded-lg">
                    <h3 class="text-lg font-semibold text-gray-700 mb-2">Total Integration Time</h3>
                    <p class="text-3xl font-bold text-blue-600">{{ integrationTimeTotal }}</p>
                </div>

                <!-- By Year, Telescope, Camera - Bar Graphs -->
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <!-- By Year -->
                    <div>
                        <h3 class="text-md font-semibold text-gray-700 mb-3 border-b pb-2">By Year</h3>
                        <div v-if="integrationTimeGraphByYear && integrationTimeGraphByYear.length > 0">
                            <svg :height="integrationTimeGraphByYear.length * 30 + 10" class="w-full">
                                <g v-for="(item, index) in integrationTimeGraphByYear" :key="item.label">
                                    <!-- Background bar -->
                                    <rect :y="index * 30 + 5" x="80" width="calc(100% - 200px)" height="18" fill="#e5e7eb" rx="4"/>
                                    <!-- Data bar -->
                                    <rect :y="index * 30 + 5" x="80" :width="`calc((100% - 200px) * ${item.percentage / 100})`" height="18" fill="#2563eb" rx="4"/>
                                    <!-- Label -->
                                    <text :y="index * 30 + 17" x="5" class="text-sm font-medium fill-gray-700">{{ item.label }}</text>
                                    <!-- Value -->
                                    <text :y="index * 30 + 17" :x="`calc(100% - 110px)`" class="text-sm font-semibold fill-blue-600">{{ formatIntegrationTime()(item.value) }}</text>
                                </g>
                            </svg>
                        </div>
                        <div v-else class="text-gray-500 text-sm italic">No data</div>
                    </div>

                    <!-- By Telescope -->
                    <div>
                        <h3 class="text-md font-semibold text-gray-700 mb-3 border-b pb-2">By Telescope</h3>
                        <div v-if="integrationTimeGraphByTelescope && integrationTimeGraphByTelescope.length > 0">
                            <svg :height="integrationTimeGraphByTelescope.length * 30 + 10" class="w-full">
                                <g v-for="(item, index) in integrationTimeGraphByTelescope" :key="item.label">
                                    <rect :y="index * 30 + 5" x="100" width="calc(100% - 220px)" height="18" fill="#e5e7eb" rx="4"/>
                                    <rect :y="index * 30 + 5" x="100" :width="`calc((100% - 220px) * ${item.percentage / 100})`" height="18" fill="#2563eb" rx="4"/>
                                    <text :y="index * 30 + 17" x="5" class="text-sm font-medium fill-gray-700" style="max-width: 90px; overflow: hidden; text-overflow: ellipsis;">{{ item.label }}</text>
                                    <text :y="index * 30 + 17" :x="`calc(100% - 110px)`" class="text-sm font-semibold fill-blue-600">{{ formatIntegrationTime()(item.value) }}</text>
                                </g>
                            </svg>
                        </div>
                        <div v-else class="text-gray-500 text-sm italic">No data</div>
                    </div>

                    <!-- By Camera -->
                    <div>
                        <h3 class="text-md font-semibold text-gray-700 mb-3 border-b pb-2">By Camera</h3>
                        <div v-if="integrationTimeGraphByCamera && integrationTimeGraphByCamera.length > 0">
                            <svg :height="integrationTimeGraphByCamera.length * 30 + 10" class="w-full">
                                <g v-for="(item, index) in integrationTimeGraphByCamera" :key="item.label">
                                    <rect :y="index * 30 + 5" x="100" width="calc(100% - 220px)" height="18" fill="#e5e7eb" rx="4"/>
                                    <rect :y="index * 30 + 5" x="100" :width="`calc((100% - 220px) * ${item.percentage / 100})`" height="18" fill="#2563eb" rx="4"/>
                                    <text :y="index * 30 + 17" x="5" class="text-sm font-medium fill-gray-700">{{ item.label }}</text>
                                    <text :y="index * 30 + 17" :x="`calc(100% - 110px)`" class="text-sm font-semibold fill-blue-600">{{ formatIntegrationTime()(item.value) }}</text>
                                </g>
                            </svg>
                        </div>
                        <div v-else class="text-gray-500 text-sm italic">No data</div>
                    </div>
                </div>
            </div>

            <!-- Object Count Summary -->
            <div class="bg-white rounded-lg shadow-md p-6">
                <h2 class="text-xl font-bold text-gray-800 mb-4">Object Count Summary (LIGHT Frames)</h2>

                <!-- Total Objects -->
                <div class="mb-6 p-4 bg-purple-50 rounded-lg">
                    <h3 class="text-lg font-semibold text-gray-700 mb-2">Total Unique Objects</h3>
                    <p class="text-3xl font-bold text-purple-600">{{ objectCountTotal }}</p>
                </div>

                <!-- By Year, Telescope, Camera - Bar Graphs -->
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <!-- By Year -->
                    <div>
                        <h3 class="text-md font-semibold text-gray-700 mb-3 border-b pb-2">By Year</h3>
                        <div v-if="objectCountGraphByYear && objectCountGraphByYear.length > 0">
                            <svg :height="objectCountGraphByYear.length * 30 + 10" class="w-full">
                                <g v-for="(item, index) in objectCountGraphByYear" :key="item.label">
                                    <!-- Background bar -->
                                    <rect :y="index * 30 + 5" x="80" width="calc(100% - 200px)" height="18" fill="#e5e7eb" rx="4"/>
                                    <!-- Data bar -->
                                    <rect :y="index * 30 + 5" x="80" :width="`calc((100% - 200px) * ${item.percentage / 100})`" height="18" fill="#9333ea" rx="4"/>
                                    <!-- Label -->
                                    <text :y="index * 30 + 17" x="5" class="text-sm font-medium fill-gray-700">{{ item.label }}</text>
                                    <!-- Value -->
                                    <text :y="index * 30 + 17" :x="`calc(100% - 110px)`" class="text-sm font-semibold fill-purple-600">{{ item.value }}</text>
                                </g>
                            </svg>
                        </div>
                        <div v-else class="text-gray-500 text-sm italic">No data</div>
                    </div>

                    <!-- By Telescope -->
                    <div>
                        <h3 class="text-md font-semibold text-gray-700 mb-3 border-b pb-2">By Telescope</h3>
                        <div v-if="objectCountGraphByTelescope && objectCountGraphByTelescope.length > 0">
                            <svg :height="objectCountGraphByTelescope.length * 30 + 10" class="w-full">
                                <g v-for="(item, index) in objectCountGraphByTelescope" :key="item.label">
                                    <rect :y="index * 30 + 5" x="100" width="calc(100% - 220px)" height="18" fill="#e5e7eb" rx="4"/>
                                    <rect :y="index * 30 + 5" x="100" :width="`calc((100% - 220px) * ${item.percentage / 100})`" height="18" fill="#9333ea" rx="4"/>
                                    <text :y="index * 30 + 17" x="5" class="text-sm font-medium fill-gray-700" style="max-width: 90px; overflow: hidden; text-overflow: ellipsis;">{{ item.label }}</text>
                                    <text :y="index * 30 + 17" :x="`calc(100% - 110px)`" class="text-sm font-semibold fill-purple-600">{{ item.value }}</text>
                                </g>
                            </svg>
                        </div>
                        <div v-else class="text-gray-500 text-sm italic">No data</div>
                    </div>

                    <!-- By Camera -->
                    <div>
                        <h3 class="text-md font-semibold text-gray-700 mb-3 border-b pb-2">By Camera</h3>
                        <div v-if="objectCountGraphByCamera && objectCountGraphByCamera.length > 0">
                            <svg :height="objectCountGraphByCamera.length * 30 + 10" class="w-full">
                                <g v-for="(item, index) in objectCountGraphByCamera" :key="item.label">
                                    <rect :y="index * 30 + 5" x="100" width="calc(100% - 220px)" height="18" fill="#e5e7eb" rx="4"/>
                                    <rect :y="index * 30 + 5" x="100" :width="`calc((100% - 220px) * ${item.percentage / 100})`" height="18" fill="#9333ea" rx="4"/>
                                    <text :y="index * 30 + 17" x="5" class="text-sm font-medium fill-gray-700">{{ item.label }}</text>
                                    <text :y="index * 30 + 17" :x="`calc(100% - 110px)`" class="text-sm font-semibold fill-purple-600">{{ item.value }}</text>
                                </g>
                            </svg>
                        </div>
                        <div v-else class="text-gray-500 text-sm italic">No data</div>
                    </div>
                </div>
            </div>

            <!-- New Imaging Sessions Summary -->
            <div class="bg-white rounded-lg shadow-md p-6">
                <h2 class="text-xl font-bold text-gray-800 mb-4">New Imaging Sessions</h2>
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    <!-- Year to Date -->
                    <div class="border-2 border-green-200 rounded-lg p-4 bg-green-50">
                        <h3 class="text-lg font-semibold text-green-800 mb-3">Year to Date</h3>
                        <div class="space-y-2">
                            <div class="flex justify-between">
                                <span class="text-sm text-gray-600">Sessions:</span>
                                <span class="font-bold text-green-700">{{ newSessionsYTD.session_count || 0 }}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-sm text-gray-600">Total Frames:</span>
                                <span class="font-bold text-green-700">{{ (newSessionsYTD.frame_counts && newSessionsYTD.frame_counts.total) || 0 }}</span>
                            </div>
                            <div class="text-xs text-gray-500 mt-2">
                                L: {{ (newSessionsYTD.frame_counts && newSessionsYTD.frame_counts.light) || 0 }} /
                                D: {{ (newSessionsYTD.frame_counts && newSessionsYTD.frame_counts.dark) || 0 }} /
                                F: {{ (newSessionsYTD.frame_counts && newSessionsYTD.frame_counts.flat) || 0 }} /
                                B: {{ (newSessionsYTD.frame_counts && newSessionsYTD.frame_counts.bias) || 0 }}
                            </div>
                            <div class="flex justify-between mt-2">
                                <span class="text-sm text-gray-600">Integration:</span>
                                <span class="font-semibold text-green-700 text-xs">{{ (newSessionsYTD.integration_time && newSessionsYTD.integration_time.formatted) || '0h' }}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-sm text-gray-600">File Size:</span>
                                <span class="font-semibold text-green-700">{{ newSessionsYTD.total_file_size_gb || 0 }} GB</span>
                            </div>
                        </div>
                    </div>

                    <!-- Past 30 Days -->
                    <div class="border-2 border-blue-200 rounded-lg p-4 bg-blue-50">
                        <h3 class="text-lg font-semibold text-blue-800 mb-3">Past 30 Days</h3>
                        <div class="space-y-2">
                            <div class="flex justify-between">
                                <span class="text-sm text-gray-600">Sessions:</span>
                                <span class="font-bold text-blue-700">{{ newSessions30d.session_count || 0 }}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-sm text-gray-600">Total Frames:</span>
                                <span class="font-bold text-blue-700">{{ (newSessions30d.frame_counts && newSessions30d.frame_counts.total) || 0 }}</span>
                            </div>
                            <div class="text-xs text-gray-500 mt-2">
                                L: {{ (newSessions30d.frame_counts && newSessions30d.frame_counts.light) || 0 }} /
                                D: {{ (newSessions30d.frame_counts && newSessions30d.frame_counts.dark) || 0 }} /
                                F: {{ (newSessions30d.frame_counts && newSessions30d.frame_counts.flat) || 0 }} /
                                B: {{ (newSessions30d.frame_counts && newSessions30d.frame_counts.bias) || 0 }}
                            </div>
                            <div class="flex justify-between mt-2">
                                <span class="text-sm text-gray-600">Integration:</span>
                                <span class="font-semibold text-blue-700 text-xs">{{ (newSessions30d.integration_time && newSessions30d.integration_time.formatted) || '0h' }}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-sm text-gray-600">File Size:</span>
                                <span class="font-semibold text-blue-700">{{ newSessions30d.total_file_size_gb || 0 }} GB</span>
                            </div>
                        </div>
                    </div>

                    <!-- Past 7 Days -->
                    <div class="border-2 border-purple-200 rounded-lg p-4 bg-purple-50">
                        <h3 class="text-lg font-semibold text-purple-800 mb-3">Past 7 Days</h3>
                        <div class="space-y-2">
                            <div class="flex justify-between">
                                <span class="text-sm text-gray-600">Sessions:</span>
                                <span class="font-bold text-purple-700">{{ newSessions7d.session_count || 0 }}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-sm text-gray-600">Total Frames:</span>
                                <span class="font-bold text-purple-700">{{ (newSessions7d.frame_counts && newSessions7d.frame_counts.total) || 0 }}</span>
                            </div>
                            <div class="text-xs text-gray-500 mt-2">
                                L: {{ (newSessions7d.frame_counts && newSessions7d.frame_counts.light) || 0 }} /
                                D: {{ (newSessions7d.frame_counts && newSessions7d.frame_counts.dark) || 0 }} /
                                F: {{ (newSessions7d.frame_counts && newSessions7d.frame_counts.flat) || 0 }} /
                                B: {{ (newSessions7d.frame_counts && newSessions7d.frame_counts.bias) || 0 }}
                            </div>
                            <div class="flex justify-between mt-2">
                                <span class="text-sm text-gray-600">Integration:</span>
                                <span class="font-semibold text-purple-700 text-xs">{{ (newSessions7d.integration_time && newSessions7d.integration_time.formatted) || '0h' }}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-sm text-gray-600">File Size:</span>
                                <span class="font-semibold text-purple-700">{{ newSessions7d.total_file_size_gb || 0 }} GB</span>
                            </div>
                        </div>
                    </div>

                    <!-- Past 24 Hours -->
                    <div class="border-2 border-orange-200 rounded-lg p-4 bg-orange-50">
                        <h3 class="text-lg font-semibold text-orange-800 mb-3">Past 24 Hours</h3>
                        <div class="space-y-2">
                            <div class="flex justify-between">
                                <span class="text-sm text-gray-600">Sessions:</span>
                                <span class="font-bold text-orange-700">{{ newSessions24h.session_count || 0 }}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-sm text-gray-600">Total Frames:</span>
                                <span class="font-bold text-orange-700">{{ (newSessions24h.frame_counts && newSessions24h.frame_counts.total) || 0 }}</span>
                            </div>
                            <div class="text-xs text-gray-500 mt-2">
                                L: {{ (newSessions24h.frame_counts && newSessions24h.frame_counts.light) || 0 }} /
                                D: {{ (newSessions24h.frame_counts && newSessions24h.frame_counts.dark) || 0 }} /
                                F: {{ (newSessions24h.frame_counts && newSessions24h.frame_counts.flat) || 0 }} /
                                B: {{ (newSessions24h.frame_counts && newSessions24h.frame_counts.bias) || 0 }}
                            </div>
                            <div class="flex justify-between mt-2">
                                <span class="text-sm text-gray-600">Integration:</span>
                                <span class="font-semibold text-orange-700 text-xs">{{ (newSessions24h.integration_time && newSessions24h.integration_time.formatted) || '0h' }}</span>
                            </div>
                            <div class="flex justify-between">
                                <span class="text-sm text-gray-600">File Size:</span>
                                <span class="font-semibold text-orange-700">{{ newSessions24h.total_file_size_gb || 0 }} GB</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Disk Space Utilization -->
            <div class="bg-white rounded-lg shadow-md p-6">
                <h2 class="text-xl font-bold text-gray-800 mb-4">Disk Space Utilization</h2>

                <!-- Overall Disk Usage -->
                <div class="mb-6 p-4 bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg">
                    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                        <div class="text-center">
                            <h3 class="text-sm font-semibold text-gray-600 mb-1">Total Space</h3>
                            <p class="text-2xl font-bold text-gray-700">{{ diskSpaceTotal }} GB</p>
                        </div>
                        <div class="text-center">
                            <h3 class="text-sm font-semibold text-gray-600 mb-1">Used</h3>
                            <p class="text-2xl font-bold text-orange-600">{{ diskSpaceUsed }} GB</p>
                            <p class="text-xs text-gray-500">{{ diskSpaceUsedPercent }}%</p>
                        </div>
                        <div class="text-center">
                            <h3 class="text-sm font-semibold text-gray-600 mb-1">Free</h3>
                            <p class="text-2xl font-bold text-green-600">{{ diskSpaceFree }} GB</p>
                        </div>
                        <div class="text-center">
                            <h3 class="text-sm font-semibold text-gray-600 mb-1">Cataloged Files</h3>
                            <p class="text-2xl font-bold text-blue-600">{{ catalogedFilesSize }} GB</p>
                        </div>
                    </div>
                </div>

                <!-- Space by Category - Totals -->
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                    <div class="flex justify-between items-center p-4 bg-gradient-to-r from-blue-100 to-blue-50 rounded-lg border-2 border-blue-200">
                        <span class="font-bold text-gray-800">Raw FITS Total</span>
                        <span class="text-2xl font-bold text-blue-700">{{ catalogedFilesSize }} GB</span>
                    </div>
                    <div class="flex justify-between items-center p-4 bg-gradient-to-r from-orange-100 to-orange-50 rounded-lg border-2 border-orange-200">
                        <span class="font-bold text-gray-800">Processed Total</span>
                        <span class="text-2xl font-bold text-orange-700">{{ processedFilesTotal }} GB</span>
                    </div>
                    <div class="flex justify-between items-center p-4 bg-gradient-to-r from-purple-100 to-purple-50 rounded-lg border-2 border-purple-200">
                        <span class="font-bold text-gray-800">Other Data Total</span>
                        <span class="text-2xl font-bold text-purple-700">{{ otherDataTotalMB }} MB</span>
                    </div>
                </div>

                <!-- Space by Category - Details -->
                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <!-- Raw FITS Files -->
                    <div>
                        <h3 class="text-md font-semibold text-gray-700 mb-3 border-b-2 border-blue-200 pb-2">Raw FITS Files</h3>
                        <div class="space-y-2">
                            <div class="flex justify-between items-center p-2 bg-blue-50 rounded">
                                <span class="font-medium text-gray-700">LIGHT</span>
                                <span class="text-blue-600 font-semibold">{{ diskSpaceLightFrames }} GB</span>
                            </div>
                            <div class="flex justify-between items-center p-2 bg-blue-50 rounded">
                                <span class="font-medium text-gray-700">DARK</span>
                                <span class="text-blue-600 font-semibold">{{ diskSpaceDarkFrames }} GB</span>
                            </div>
                            <div class="flex justify-between items-center p-2 bg-blue-50 rounded">
                                <span class="font-medium text-gray-700">FLAT</span>
                                <span class="text-blue-600 font-semibold">{{ diskSpaceFlatFrames }} GB</span>
                            </div>
                            <div class="flex justify-between items-center p-2 bg-blue-50 rounded">
                                <span class="font-medium text-gray-700">BIAS</span>
                                <span class="text-blue-600 font-semibold">{{ diskSpaceBiasFrames }} GB</span>
                            </div>
                        </div>
                    </div>

                    <!-- Processed Files -->
                    <div>
                        <h3 class="text-md font-semibold text-gray-700 mb-3 border-b-2 border-orange-200 pb-2">Processed Files</h3>
                        <div class="space-y-2">
                            <div class="flex justify-between items-center p-2 bg-orange-50 rounded">
                                <span class="font-medium text-gray-700">Intermediate</span>
                                <span class="text-orange-600 font-semibold">{{ processedFilesIntermediate }} GB</span>
                            </div>
                            <div class="flex justify-between items-center p-2 bg-orange-50 rounded">
                                <span class="font-medium text-gray-700">Final</span>
                                <span class="text-orange-600 font-semibold">{{ processedFilesFinal }} GB</span>
                            </div>
                        </div>
                    </div>

                    <!-- Other Data -->
                    <div>
                        <h3 class="text-md font-semibold text-gray-700 mb-3 border-b-2 border-purple-200 pb-2">Other Data</h3>
                        <div class="space-y-2">
                            <div class="flex justify-between items-center p-2 bg-purple-50 rounded">
                                <span class="font-medium text-gray-700">Imaging Session Notes</span>
                                <span class="text-purple-600 font-semibold">{{ sessionNotesImaging }} KB</span>
                            </div>
                            <div class="flex justify-between items-center p-2 bg-purple-50 rounded">
                                <span class="font-medium text-gray-700">Processing Session Notes</span>
                                <span class="text-purple-600 font-semibold">{{ sessionNotesProcessing }} KB</span>
                            </div>
                            <div class="flex justify-between items-center p-2 bg-purple-50 rounded">
                                <span class="font-medium text-gray-700">Database</span>
                                <span class="text-purple-600 font-semibold">{{ databaseSize }} MB</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,
    
    data() {
        return {
            operationInProgress: false,
            operationType: '',
            monitoringEnabled: false,
            lastScan: null,
            monitoringPollInterval: null
        };
    },
    
    computed: {
        stats() {
            return this.$root.stats;
        },
        cleanupTotal() {
            if (!this.stats.cleanup) return 0;
            return (this.stats.cleanup.duplicates || 0) +
                   (this.stats.cleanup.bad_files || 0) +
                   (this.stats.cleanup.missing_files || 0);
        },
        lastUpdated() {
            if (!this.stats.last_updated) return 'Never';
            const date = new Date(this.stats.last_updated);
            return date.toLocaleString();
        },

        // Integration Time
        integrationTimeTotal() {
            return this.stats.integration_time?.total?.formatted || '0h 0m 0s';
        },
        integrationTimeByYear() {
            return this.stats.integration_time?.by_year || {};
        },
        integrationTimeByTelescope() {
            return this.stats.integration_time?.by_telescope || {};
        },
        integrationTimeByCamera() {
            return this.stats.integration_time?.by_camera || {};
        },

        // Object Counts
        objectCountTotal() {
            return this.stats.object_counts?.total || 0;
        },
        objectCountByYear() {
            return this.stats.object_counts?.by_year || {};
        },
        objectCountByTelescope() {
            return this.stats.object_counts?.by_telescope || {};
        },
        objectCountByCamera() {
            return this.stats.object_counts?.by_camera || {};
        },

        integrationTimeGraphByYear() {
            return this.convertToBarGraphData(this.integrationTimeByYear, 'total_seconds', true); // Sort by year
        },
        integrationTimeGraphByTelescope() {
            return this.convertToBarGraphData(this.integrationTimeByTelescope, 'total_seconds', false); // Sort by value
        },
        integrationTimeGraphByCamera() {
            return this.convertToBarGraphData(this.integrationTimeByCamera, 'total_seconds', false); // Sort by value
        },

        objectCountGraphByYear() {
            return this.convertToBarGraphData(this.objectCountByYear, null, true); // Sort by year
        },
        objectCountGraphByTelescope() {
            return this.convertToBarGraphData(this.objectCountByTelescope, null, false); // Sort by value
        },
        objectCountGraphByCamera() {
            return this.convertToBarGraphData(this.objectCountByCamera, null, false); // Sort by value
        },

        // New Sessions
        newSessionsYTD() {
            return this.stats.new_sessions?.year_to_date || {};
        },
        newSessions30d() {
            return this.stats.new_sessions?.past_30_days || {};
        },
        newSessions7d() {
            return this.stats.new_sessions?.past_7_days || {};
        },
        newSessions24h() {
            return this.stats.new_sessions?.past_24_hours || {};
        },

        // Disk Space
        diskSpaceTotal() {
            return this.stats.disk_space?.disk_usage?.total_gb || 0;
        },
        diskSpaceUsed() {
            return this.stats.disk_space?.disk_usage?.used_gb || 0;
        },
        diskSpaceFree() {
            return this.stats.disk_space?.disk_usage?.free_gb || 0;
        },
        diskSpaceUsedPercent() {
            return this.stats.disk_space?.disk_usage?.used_percent || 0;
        },
        catalogedFilesSize() {
            return this.stats.disk_space?.cataloged_files?.total_gb || 0;
        },
        diskSpaceLightFrames() {
            return this.stats.disk_space?.cataloged_files?.by_frame_type?.LIGHT?.gb || 0;
        },
        diskSpaceDarkFrames() {
            return this.stats.disk_space?.cataloged_files?.by_frame_type?.DARK?.gb || 0;
        },
        diskSpaceFlatFrames() {
            return this.stats.disk_space?.cataloged_files?.by_frame_type?.FLAT?.gb || 0;
        },
        diskSpaceBiasFrames() {
            return this.stats.disk_space?.cataloged_files?.by_frame_type?.BIAS?.gb || 0;
        },
        sessionNotesImaging() {
            return this.stats.disk_space?.session_notes?.imaging_kb || 0;
        },
        sessionNotesProcessing() {
            return this.stats.disk_space?.session_notes?.processing_kb || 0;
        },
        databaseSize() {
            return this.stats.disk_space?.database?.mb || 0;
        },
        processedFilesIntermediate() {
            return this.stats.disk_space?.processed_files?.intermediate_gb || 0;
        },
        processedFilesFinal() {
            return this.stats.disk_space?.processed_files?.final_gb || 0;
        },
        processedFilesTotal() {
            return this.stats.disk_space?.processed_files?.total_gb || 0;
        },
        otherDataTotalMB() {
            // Calculate total: session notes (KB) + database (MB) converted to MB
            const notesKB = (this.sessionNotesImaging || 0) + (this.sessionNotesProcessing || 0);
            const notesMB = notesKB / 1024;
            const dbMB = this.databaseSize || 0;
            const total = notesMB + dbMB;
            // Format to 3 significant digits
            if (total >= 100) return Math.round(total);
            if (total >= 10) return Math.round(total * 10) / 10;
            return Math.round(total * 100) / 100;
        }
    },

    methods: {
        // Helper to convert object to sorted array with percentages for bar graphs
        convertToBarGraphData(dataObj, valueKey = null, sortByLabel = false) {
            if (!dataObj || Object.keys(dataObj).length === 0) return [];

            const entries = Object.entries(dataObj).map(([label, value]) => {
                // If value is an object (like integration time), extract the seconds
                const numValue = valueKey && typeof value === 'object'
                    ? value[valueKey]
                    : (typeof value === 'number' ? value : 0);
                return { label, value: numValue };
            });

            // Sort by label (for years) or by value descending
            if (sortByLabel) {
                entries.sort((a, b) => a.label.localeCompare(b.label));
            } else {
                entries.sort((a, b) => b.value - a.value);
            }

            // Calculate max for scaling
            const maxValue = Math.max(...entries.map(e => e.value), 1);

            // Add percentage for bar width
            return entries.map(e => ({
                ...e,
                percentage: (e.value / maxValue) * 100
            }));
        },

        // Format integration time for display
        formatIntegrationTime() {
            return (seconds) => {
                if (!seconds) return '0h';
                const hours = Math.floor(seconds / 3600);
                const minutes = Math.floor((seconds % 3600) / 60);
                if (hours > 0) {
                    return `${hours}h ${minutes}m`;
                }
                return `${minutes}m`;
            };
        },

        async checkOperationStatus() {
            try {
                const response = await fetch('/api/operations/current');
                const data = await response.json();
                this.operationInProgress = data.current_operation !== null;
                this.operationType = data.current_operation || '';
            } catch (error) {
                console.error('Error checking operation status:', error);
            }
        },
        
        
        formatLastScan(timestamp) {
            if (!timestamp) return 'Never';
            const date = new Date(timestamp);
            const now = new Date();
            const diff = now - date;
            const minutes = Math.floor(diff / 60000);
            
            if (minutes < 1) return 'Just now';
            if (minutes < 60) return `${minutes}m ago`;
            const hours = Math.floor(minutes / 60);
            if (hours < 24) return `${hours}h ago`;
            const days = Math.floor(hours / 24);
            return `${days}d ago`;
        },
        
        goToOperations() {
            this.$root.changeTab('operations');
        },
        
        goToImagingSessions() {
            this.$root.changeTab('imaging-sessions');
        },
        
        goToProcessingSessions() {
            this.$root.changeTab('processing-sessions');
        }
    },
    
    mounted() {
        this.checkOperationStatus();
        
        this.statusInterval = setInterval(() => {
            this.checkOperationStatus();
        }, 5000);
    },
    
    beforeUnmount() {
        if (this.statusInterval) {
            clearInterval(this.statusInterval);
        }
    }
};

window.DashboardTab = DashboardTab;