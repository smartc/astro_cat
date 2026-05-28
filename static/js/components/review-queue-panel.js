/**
 * Review Queue Panel - surfaces quarantine files needing manual fixes
 */

const ReviewQueuePanel = {
    template: `
        <div class="bg-white rounded-lg shadow">
            <!-- Header row (always visible) -->
            <div
                class="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 transition-colors"
                @click="toggleExpanded"
            >
                <div class="flex items-center space-x-3">
                    <svg
                        class="w-5 h-5 text-gray-400 transition-transform"
                        :class="{'rotate-90': expanded}"
                        fill="none" stroke="currentColor" viewBox="0 0 24 24"
                    >
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                              d="M9 5l7 7-7 7"/>
                    </svg>
                    <h3 class="text-lg font-semibold text-gray-800">Review Queue</h3>
                </div>
                <div class="flex items-center space-x-2">
                    <span v-if="loading" class="text-sm text-gray-400">Loading…</span>
                    <span v-else-if="totalFiles === 0"
                          class="px-2 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-800">
                        ✓ No files need review
                    </span>
                    <span v-else
                          class="px-2 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-800">
                        {{ totalFiles }} {{ totalFiles === 1 ? 'file needs' : 'files need' }} review
                    </span>
                </div>
            </div>

            <!-- Expanded body -->
            <div v-show="expanded" class="border-t">
                <div v-if="error" class="px-4 py-3 text-red-600 text-sm">{{ error }}</div>

                <!-- Empty state -->
                <div v-else-if="!loading && groups.length === 0" class="px-4 py-6 text-center text-gray-500 text-sm">
                    No files need review.
                </div>

                <!-- Group cards -->
                <div v-else class="p-4 space-y-4">
                    <div
                        v-for="group in groups"
                        :key="group.group_id"
                        class="border rounded-lg overflow-hidden"
                        :class="groupBorderClass(group.severity)"
                    >
                        <!-- Group header -->
                        <div class="flex items-center justify-between px-4 py-3"
                             :class="groupHeaderClass(group.severity)">
                            <div class="flex items-center space-x-2">
                                <span>{{ severityIcon(group.severity) }}</span>
                                <span class="font-semibold text-sm">{{ group.issue_summary }}</span>
                            </div>
                            <span class="text-xs font-medium ml-4 whitespace-nowrap">
                                [{{ group.file_count }} {{ group.file_count === 1 ? 'file' : 'files' }}]
                            </span>
                        </div>

                        <!-- Group body -->
                        <div class="px-4 py-3 space-y-3">
                            <p class="text-sm text-gray-600">{{ group.detail }}</p>

                            <!-- Success banner -->
                            <div v-if="groupResults[group.group_id] && !groupResults[group.group_id].error"
                                 class="text-sm text-green-700 bg-green-50 border border-green-200 rounded px-3 py-2">
                                ✓ Fixed {{ groupResults[group.group_id].fixed_count }} files — re-validated.
                                <span v-if="dominantNewScore(group.group_id)">
                                    New score: {{ dominantNewScore(group.group_id) }}.
                                </span>
                                <div v-if="groupResults[group.group_id].warnings && groupResults[group.group_id].warnings.length"
                                     class="mt-1 text-amber-700">
                                    <div v-for="(w, i) in groupResults[group.group_id].warnings" :key="i">⚠ {{ w }}</div>
                                </div>
                            </div>
                            <div v-if="groupResults[group.group_id] && groupResults[group.group_id].error"
                                 class="text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
                                ✗ {{ groupResults[group.group_id].error }}
                            </div>

                            <!-- File list toggle -->
                            <div>
                                <button
                                    @click="toggleFiles(group.group_id)"
                                    class="text-sm text-blue-600 hover:text-blue-800 underline"
                                >
                                    {{ expandedFiles[group.group_id] ? '▼' : '▶' }}
                                    {{ expandedFiles[group.group_id] ? 'Hide' : 'Show' }} {{ group.file_count }} {{ group.file_count === 1 ? 'file' : 'files' }}
                                </button>
                                <div v-if="expandedFiles[group.group_id]" class="mt-2 overflow-x-auto">
                                    <table class="w-full text-xs text-left border-collapse">
                                        <thead>
                                            <tr class="bg-gray-50 text-gray-500 uppercase tracking-wide">
                                                <th class="px-2 py-1 border-b">Filename</th>
                                                <th class="px-2 py-1 border-b">Type</th>
                                                <th class="px-2 py-1 border-b">Score</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <tr v-for="f in group.files" :key="f.id"
                                                class="border-b hover:bg-gray-50">
                                                <td class="px-2 py-1 font-mono text-gray-700 max-w-xs truncate"
                                                    :title="f.folder + '/' + f.file">{{ f.file }}</td>
                                                <td class="px-2 py-1 text-gray-600">{{ f.frame_type }}</td>
                                                <td class="px-2 py-1" :class="scoreClass(f.validation_score)">
                                                    {{ f.validation_score !== null ? f.validation_score.toFixed(1) : '—' }}
                                                </td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                            </div>

                            <!-- Fix buttons / inline forms -->
                            <div v-if="group.available_fixes.length > 0" class="flex flex-wrap gap-2">
                                <template v-for="fix in group.available_fixes" :key="fix.fix_id">
                                    <!-- Show form if this fix is active for this group -->
                                    <div v-if="activeForm[group.group_id] && activeForm[group.group_id].fix_id === fix.fix_id"
                                         class="w-full border border-blue-200 rounded-lg p-3 bg-blue-50 space-y-3">

                                        <!-- add_filter_to_list form -->
                                        <template v-if="fix.fix_id === 'add_filter_to_list'">
                                            <div class="text-sm font-semibold text-blue-800">Add filter to list</div>
                                            <div class="grid grid-cols-2 gap-3">
                                                <div>
                                                    <label class="block text-xs text-gray-600 mb-1">Raw name (from FITS header)</label>
                                                    <input type="text" :value="activeForm[group.group_id].formData.raw_name"
                                                           readonly
                                                           class="w-full px-2 py-1 text-sm border border-gray-300 rounded bg-gray-100 text-gray-500"/>
                                                </div>
                                                <div>
                                                    <label class="block text-xs text-gray-600 mb-1">Display name</label>
                                                    <input type="text" v-model="activeForm[group.group_id].formData.proper_name"
                                                           class="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-400"/>
                                                </div>
                                            </div>
                                        </template>

                                        <!-- add_camera_to_list form -->
                                        <template v-else-if="fix.fix_id === 'add_camera_to_list'">
                                            <div class="text-sm font-semibold text-blue-800">Add camera to list</div>
                                            <div class="grid grid-cols-2 gap-3">
                                                <div>
                                                    <label class="block text-xs text-gray-600 mb-1">Camera name (from FITS)</label>
                                                    <input type="text" :value="activeForm[group.group_id].formData.camera"
                                                           readonly
                                                           class="w-full px-2 py-1 text-sm border border-gray-300 rounded bg-gray-100 text-gray-500"/>
                                                </div>
                                                <div>
                                                    <label class="block text-xs text-gray-600 mb-1">Brand</label>
                                                    <input type="text" v-model="activeForm[group.group_id].formData.brand"
                                                           class="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-400"/>
                                                </div>
                                                <div>
                                                    <label class="block text-xs text-gray-600 mb-1">Type</label>
                                                    <select v-model="activeForm[group.group_id].formData.type"
                                                            class="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-400">
                                                        <option>CMOS</option>
                                                        <option>CCD</option>
                                                        <option>DSLR</option>
                                                    </select>
                                                </div>
                                                <div>
                                                    <label class="block text-xs text-gray-600 mb-1">Pixel size (µm)</label>
                                                    <input type="number" step="0.01" v-model.number="activeForm[group.group_id].formData.pixel"
                                                           class="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-400"/>
                                                </div>
                                                <div>
                                                    <label class="block text-xs text-gray-600 mb-1">Sensor X (px)</label>
                                                    <input type="number" v-model.number="activeForm[group.group_id].formData.x"
                                                           class="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-400"/>
                                                </div>
                                                <div>
                                                    <label class="block text-xs text-gray-600 mb-1">Sensor Y (px)</label>
                                                    <input type="number" v-model.number="activeForm[group.group_id].formData.y"
                                                           class="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-400"/>
                                                </div>
                                            </div>
                                            <!-- OSC/mono — prominent -->
                                            <div class="border border-amber-200 bg-amber-50 rounded p-3">
                                                <div class="text-xs font-semibold text-amber-800 mb-1">
                                                    Camera type — affects filter scoring
                                                </div>
                                                <div class="text-xs text-amber-700 mb-2">
                                                    OSC/colour cameras receive full points for any known filter.
                                                    Mono cameras are penalised for missing or broadband-only filters.
                                                </div>
                                                <label class="flex items-center space-x-2 cursor-pointer mb-1">
                                                    <input type="radio" :value="true"
                                                           v-model="activeForm[group.group_id].formData.rgb"/>
                                                    <span class="text-sm font-medium">OSC / Colour</span>
                                                </label>
                                                <label class="flex items-center space-x-2 cursor-pointer">
                                                    <input type="radio" :value="false"
                                                           v-model="activeForm[group.group_id].formData.rgb"/>
                                                    <span class="text-sm font-medium">Mono</span>
                                                </label>
                                            </div>
                                            <div>
                                                <label class="block text-xs text-gray-600 mb-1">Comments</label>
                                                <input type="text" v-model="activeForm[group.group_id].formData.comments"
                                                       class="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-400"/>
                                            </div>
                                        </template>

                                        <!-- add_telescope_to_list form -->
                                        <template v-else-if="fix.fix_id === 'add_telescope_to_list'">
                                            <div class="text-sm font-semibold text-blue-800">Add telescope to list</div>
                                            <div class="grid grid-cols-2 gap-3">
                                                <div>
                                                    <label class="block text-xs text-gray-600 mb-1">Telescope name (from FITS)</label>
                                                    <input type="text" :value="activeForm[group.group_id].formData.scope"
                                                           readonly
                                                           class="w-full px-2 py-1 text-sm border border-gray-300 rounded bg-gray-100 text-gray-500"/>
                                                </div>
                                                <div>
                                                    <label class="block text-xs text-gray-600 mb-1">Manufacturer</label>
                                                    <input type="text" v-model="activeForm[group.group_id].formData.make"
                                                           class="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-400"/>
                                                </div>
                                                <div>
                                                    <label class="block text-xs text-gray-600 mb-1">Type</label>
                                                    <select v-model="activeForm[group.group_id].formData.type"
                                                            class="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-400">
                                                        <option>Refractor</option>
                                                        <option>Reflector</option>
                                                        <option>Lens</option>
                                                    </select>
                                                </div>
                                                <div>
                                                    <label class="block text-xs text-gray-600 mb-1">Subtype</label>
                                                    <input type="text" v-model="activeForm[group.group_id].formData.subtype"
                                                           class="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-400"/>
                                                </div>
                                                <div>
                                                    <label class="block text-xs text-gray-600 mb-1">Focal length (mm)</label>
                                                    <input type="number" v-model.number="activeForm[group.group_id].formData.focal"
                                                           class="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-400"/>
                                                </div>
                                                <div>
                                                    <label class="block text-xs text-gray-600 mb-1">Aperture (mm)</label>
                                                    <input type="number" v-model.number="activeForm[group.group_id].formData.aperture"
                                                           class="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-400"/>
                                                </div>
                                            </div>
                                            <div>
                                                <label class="block text-xs text-gray-600 mb-1">Comments</label>
                                                <input type="text" v-model="activeForm[group.group_id].formData.comments"
                                                       class="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-400"/>
                                            </div>
                                        </template>

                                        <!-- rename_value_in_db form -->
                                        <template v-else-if="fix.fix_id === 'rename_value_in_db'">
                                            <div class="text-sm font-semibold text-blue-800">
                                                Rename '{{ fix.params.current_value }}' to existing
                                                {{ fix.params.field }}
                                            </div>
                                            <div>
                                                <label class="block text-xs text-gray-600 mb-1">
                                                    Rename to
                                                </label>
                                                <select v-model="activeForm[group.group_id].formData.new_value"
                                                        class="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-400">
                                                    <option value="">— select —</option>
                                                    <option v-for="opt in renameOptions(fix.params.field)"
                                                            :key="opt" :value="opt">{{ opt }}</option>
                                                </select>
                                            </div>
                                        </template>

                                        <!-- change_frame_type form -->
                                        <template v-else-if="fix.fix_id === 'change_frame_type'">
                                            <div class="text-sm font-semibold text-blue-800">Change frame type</div>
                                            <div>
                                                <label class="block text-xs text-gray-600 mb-1">New frame type</label>
                                                <select v-model="activeForm[group.group_id].formData.new_frame_type"
                                                        class="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:ring-1 focus:ring-blue-400">
                                                    <option value="">— select —</option>
                                                    <option>LIGHT</option>
                                                    <option>FLAT</option>
                                                    <option>DARK</option>
                                                    <option>BIAS</option>
                                                </select>
                                            </div>
                                        </template>

                                        <!-- Form action buttons -->
                                        <div class="flex gap-2 pt-1">
                                            <button
                                                @click.stop="cancelForm(group.group_id)"
                                                class="px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-100 transition">
                                                Cancel
                                            </button>
                                            <button
                                                @click.stop="submitForm(group)"
                                                :disabled="applying[group.group_id]"
                                                class="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition disabled:opacity-50">
                                                {{ applying[group.group_id] ? 'Applying…' : applyLabel(fix.fix_id, group) }}
                                            </button>
                                        </div>
                                    </div>

                                    <!-- Show button only when no form is open for this fix -->
                                    <button
                                        v-else-if="!activeForm[group.group_id]"
                                        @click.stop="openForm(group, fix)"
                                        :disabled="applying[group.group_id]"
                                        class="px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-50 transition disabled:opacity-50">
                                        {{ fix.label }} ▾
                                    </button>
                                </template>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,

    emits: ['fix-applied'],

    data() {
        return {
            expanded: false,
            loading: false,
            error: null,
            groups: [],
            knownFilters: [],
            knownCameras: [],
            knownTelescopes: [],
            totalFiles: 0,
            expandedFiles: {},
            activeForm: {},
            applying: {},
            groupResults: {},
        };
    },

    methods: {
        async toggleExpanded() {
            this.expanded = !this.expanded;
            if (this.expanded && this.groups.length === 0 && !this.loading) {
                await this.loadQueue();
            }
        },

        async loadQueue() {
            this.loading = true;
            this.error = null;
            try {
                const data = await fetch('/api/review-queue').then(r => r.json());
                this.groups = data.groups;
                this.totalFiles = data.total_files;
                this.knownFilters = data.known_filters;
                this.knownCameras = data.known_cameras;
                this.knownTelescopes = data.known_telescopes;
            } catch (e) {
                this.error = 'Failed to load review queue';
            } finally {
                this.loading = false;
            }
        },

        toggleFiles(groupId) {
            this.expandedFiles = {
                ...this.expandedFiles,
                [groupId]: !this.expandedFiles[groupId],
            };
        },

        openForm(group, fix) {
            // Deep-copy the fix params as initial form data
            const formData = JSON.parse(JSON.stringify(fix.params));
            this.activeForm = {
                ...this.activeForm,
                [group.group_id]: { fix_id: fix.fix_id, formData },
            };
        },

        cancelForm(groupId) {
            const updated = { ...this.activeForm };
            delete updated[groupId];
            this.activeForm = updated;
        },

        async submitForm(group) {
            const form = this.activeForm[group.group_id];
            if (!form) return;
            await this.applyFix(group, form.fix_id, form.formData);
        },

        async applyFix(group, fix_id, formData) {
            this.applying = { ...this.applying, [group.group_id]: true };
            this.groupResults = { ...this.groupResults, [group.group_id]: null };
            try {
                const body = {
                    fix_id,
                    params: formData,
                    file_ids: group.files.map(f => f.id),
                };
                const resp = await fetch('/api/review-queue/apply-fix', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
                const result = await resp.json();
                if (!resp.ok) throw new Error(result.detail || 'Fix failed');
                this.groupResults = { ...this.groupResults, [group.group_id]: result };
                this.$emit('fix-applied');
                await this.loadQueue();
            } catch (e) {
                this.groupResults = {
                    ...this.groupResults,
                    [group.group_id]: { error: e.message },
                };
            } finally {
                this.applying = { ...this.applying, [group.group_id]: false };
                this.cancelForm(group.group_id);
            }
        },

        renameOptions(field) {
            if (field === 'filter') return this.knownFilters;
            if (field === 'camera') return this.knownCameras;
            if (field === 'telescope') return this.knownTelescopes;
            return [];
        },

        dominantNewScore(groupId) {
            const result = this.groupResults[groupId];
            if (!result || !result.new_scores) return null;
            const scores = Object.values(result.new_scores).filter(s => s !== null);
            if (scores.length === 0) return null;
            const max = Math.max(...scores);
            return max.toFixed(1);
        },

        applyLabel(fixId, group) {
            const count = group.file_count;
            const n = `${count} ${count === 1 ? 'file' : 'files'}`;
            if (fixId === 'add_filter_to_list') return 'Add to Filter List';
            if (fixId === 'add_camera_to_list') return 'Add Camera';
            if (fixId === 'add_telescope_to_list') return 'Add Telescope';
            if (fixId === 'rename_value_in_db') return `Rename in ${n}`;
            if (fixId === 'change_frame_type') return `Change Frame Type`;
            return 'Apply';
        },

        // ── styling helpers ──────────────────────────────────────────────

        severityIcon(severity) {
            if (severity === 'error') return '✖';
            if (severity === 'warning') return '⚠';
            return 'ℹ';
        },

        groupBorderClass(severity) {
            if (severity === 'error') return 'border-red-300';
            if (severity === 'warning') return 'border-amber-300';
            return 'border-blue-200';
        },

        groupHeaderClass(severity) {
            if (severity === 'error') return 'bg-red-50 text-red-800';
            if (severity === 'warning') return 'bg-amber-50 text-amber-800';
            return 'bg-blue-50 text-blue-800';
        },

        scoreClass(score) {
            if (score === null || score === undefined) return 'text-gray-400';
            if (score >= 95) return 'text-green-600 font-semibold';
            if (score >= 80) return 'text-amber-600';
            return 'text-red-600';
        },
    },

    async mounted() {
        // Load queue counts without expanding, so the badge populates on tab open
        await this.loadQueue();
    },
};

window.ReviewQueuePanel = ReviewQueuePanel;
