/**
 * Calibration Scoring Modal Component
 *
 * Runs the calibration scoring analysis for a processing session and displays:
 *   - Per-light-group match quality (darks / flats / bias)
 *   - Colour-coded status table
 *   - Markdown report (rendered as plain text; downloadable)
 *   - JSON download for FITS header script
 */

const CalibrationScoringModal = {
    template: `
        <div v-if="show" class="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center p-4" style="z-index: 300;">
            <div class="bg-white rounded-lg w-full max-w-6xl flex flex-col" style="max-height: 92vh;">

                <!-- Header -->
                <div class="relative text-white p-4 rounded-t-lg flex-shrink-0" style="background: linear-gradient(135deg, #1e3a5f 0%, #2d5986 100%); min-height: 72px;">
                    <starfield-background :num-stars="25" :min-size="0.3" :max-size="0.6"></starfield-background>
                    <div class="relative z-10 flex justify-between items-center">
                        <div>
                            <h2 class="text-xl font-bold">📊 Calibration Scoring</h2>
                            <p v-if="sessionName" class="text-sm text-blue-200 mt-1">{{ sessionName }}</p>
                        </div>
                        <div class="flex items-center space-x-3">
                            <!-- Download buttons (shown after results load) -->
                            <template v-if="matchData && !loading">
                                <button @click="downloadJson"
                                        class="px-3 py-1.5 bg-white bg-opacity-20 hover:bg-opacity-30 text-white text-sm rounded border border-white border-opacity-40 transition">
                                    ⬇ JSON
                                </button>
                                <button @click="downloadMarkdown"
                                        class="px-3 py-1.5 bg-white bg-opacity-20 hover:bg-opacity-30 text-white text-sm rounded border border-white border-opacity-40 transition">
                                    ⬇ Report (MD)
                                </button>
                            </template>
                            <button @click="close" class="text-white hover:text-gray-200 ml-2">
                                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Body -->
                <div class="flex-1 overflow-y-auto p-6">

                    <!-- Loading -->
                    <div v-if="loading" class="flex flex-col items-center justify-center py-16 text-gray-500">
                        <div class="inline-block animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mb-4"></div>
                        <p class="text-lg">Running calibration scoring…</p>
                        <p class="text-sm mt-1 text-gray-400">Analysing FITS metadata for all frame groups</p>
                    </div>

                    <!-- Error -->
                    <div v-else-if="error" class="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
                        <div class="text-4xl mb-3">❌</div>
                        <p class="text-red-700 font-semibold">Scoring failed</p>
                        <p class="text-red-600 text-sm mt-2">{{ error }}</p>
                    </div>

                    <!-- Results -->
                    <div v-else-if="matchData">

                        <!-- Diagnosis banner -->
                        <div v-if="warnings.length || errors.length" class="mb-6 space-y-2">
                            <div v-for="msg in errors" :key="msg"
                                 class="flex items-start space-x-2 bg-red-50 border border-red-200 rounded p-3 text-sm text-red-700">
                                <span class="flex-shrink-0">❌</span><span>{{ msg }}</span>
                            </div>
                            <div v-for="msg in warnings" :key="msg"
                                 class="flex items-start space-x-2 bg-yellow-50 border border-yellow-200 rounded p-3 text-sm text-yellow-800">
                                <span class="flex-shrink-0">⚠️</span><span>{{ msg }}</span>
                            </div>
                        </div>
                        <div v-if="oks.length && !warnings.length && !errors.length"
                             class="mb-6 bg-green-50 border border-green-200 rounded p-3 text-sm text-green-700">
                            ✅ All calibration matches look good.
                        </div>

                        <!-- Per-group cards -->
                        <div v-for="(lg, idx) in matchData.light_group_matches" :key="idx" class="mb-6 border border-gray-200 rounded-lg overflow-hidden shadow-sm">

                            <!-- Group header -->
                            <div class="bg-gradient-to-r from-indigo-50 to-blue-50 px-5 py-3 border-b border-gray-200">
                                <div class="flex justify-between items-center flex-wrap gap-2">
                                    <div>
                                        <span class="font-bold text-indigo-900 text-base">
                                            {{ lg.light_key.filter || 'No Filter' }} · {{ lg.light_key.exposure }}s · {{ lg.light_count }} frames
                                        </span>
                                        <span class="ml-3 text-xs text-gray-500">
                                            {{ lg.light_key.camera }} | gain={{ lg.light_key.gain }} offset={{ lg.light_key.offset }}
                                            binning={{ lg.light_key.binning_x }}×{{ lg.light_key.binning_y }}
                                        </span>
                                    </div>
                                    <div class="text-xs text-gray-400">{{ (lg.obs_dates || []).join(', ') }}</div>
                                </div>
                            </div>

                            <!-- Match table -->
                            <div class="p-4">
                                <table class="w-full text-sm border-collapse">
                                    <thead>
                                        <tr class="border-b-2 border-gray-200">
                                            <th class="text-left py-2 px-3 font-semibold text-gray-700 w-16">Type</th>
                                            <th class="text-left py-2 px-3 font-semibold text-gray-700">Status</th>
                                            <th class="text-right py-2 px-3 font-semibold text-gray-700 w-20">Score</th>
                                            <th class="text-right py-2 px-3 font-semibold text-gray-700 w-16">Frames</th>
                                            <th class="text-left py-2 px-3 font-semibold text-gray-700">Dates</th>
                                            <th class="text-left py-2 px-3 font-semibold text-gray-700">Issues</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr v-for="ct in ['dark','flat','bias']" :key="ct"
                                            :class="rowClass(lg['best_'+ct])"
                                            class="border-b border-gray-100">
                                            <td class="py-2 px-3 font-mono font-bold uppercase text-xs">{{ ct }}</td>
                                            <td class="py-2 px-3">
                                                <span :class="statusBadgeClass(lg['best_'+ct])" class="px-2 py-0.5 rounded-full text-xs font-semibold">
                                                    {{ statusLabel(lg['best_'+ct]) }}
                                                </span>
                                            </td>
                                            <td class="py-2 px-3 text-right font-mono text-xs">
                                                <span v-if="lg['best_'+ct]">{{ lg['best_'+ct].score.toFixed(0) }}</span>
                                                <span v-else class="text-gray-400">—</span>
                                            </td>
                                            <td class="py-2 px-3 text-right font-mono text-xs">
                                                <span v-if="lg['best_'+ct]">{{ lg['best_'+ct].count }}</span>
                                                <span v-else class="text-gray-400">—</span>
                                            </td>
                                            <td class="py-2 px-3 text-xs text-gray-600">
                                                <span v-if="lg['best_'+ct]">{{ (lg['best_'+ct].obs_dates||[]).slice(0,2).join(', ') }}</span>
                                                <span v-else class="text-gray-400">—</span>
                                            </td>
                                            <td class="py-2 px-3 text-xs">
                                                <span v-if="!lg['best_'+ct]" class="text-red-600">No candidates</span>
                                                <span v-else>
                                                    <span v-for="f in issueFlags(lg['best_'+ct].flags)" :key="f"
                                                          :class="f.startsWith('MISMATCH') ? 'text-yellow-700' : 'text-gray-500'"
                                                          class="block">{{ f }}</span>
                                                    <span v-if="issueFlags(lg['best_'+ct].flags).length === 0" class="text-green-600">Perfect match</span>
                                                </span>
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>

                                <!-- Recommendations -->
                                <div v-if="recommendations(lg).length" class="mt-3 pt-3 border-t border-gray-100">
                                    <p class="text-xs font-semibold text-gray-600 mb-1">Recommendations:</p>
                                    <ul class="text-xs text-gray-700 space-y-1 list-disc list-inside">
                                        <li v-for="r in recommendations(lg)" :key="r">{{ r }}</li>
                                    </ul>
                                </div>
                            </div>
                        </div>

                        <!-- Markdown report (collapsible) -->
                        <div class="mt-4 border border-gray-200 rounded-lg overflow-hidden">
                            <div @click="showRawReport = !showRawReport"
                                 class="flex justify-between items-center px-4 py-3 bg-gray-50 cursor-pointer hover:bg-gray-100 transition">
                                <span class="font-semibold text-gray-700 text-sm">📄 Full Markdown Report</span>
                                <svg :class="{'rotate-180': showRawReport}"
                                     class="w-5 h-5 text-gray-500 transition-transform"
                                     fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                                </svg>
                            </div>
                            <div v-show="showRawReport" class="p-4 bg-gray-900 overflow-x-auto">
                                <pre class="text-green-300 text-xs whitespace-pre-wrap font-mono">{{ markdownText }}</pre>
                            </div>
                        </div>

                    </div>
                </div>

                <!-- Footer -->
                <div class="flex-shrink-0 px-6 py-3 bg-gray-50 border-t border-gray-200 rounded-b-lg flex justify-between items-center">
                    <span v-if="savedNote" class="text-xs text-green-600">{{ savedNote }}</span>
                    <span v-else class="text-xs text-gray-400">
                        Files saved to Session_Notes when scoring completes.
                    </span>
                    <button @click="close" class="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded text-sm transition">Close</button>
                </div>

            </div>
        </div>
    `,

    data() {
        return {
            show:           false,
            loading:        false,
            error:          null,
            sessionId:      null,
            sessionName:    null,
            matchData:      null,
            markdownText:   '',
            jsonFilename:   '',
            mdFilename:     '',
            showRawReport:  false,
            savedNote:      '',
        };
    },

    components: {
        'starfield-background': StarfieldBackground
    },

    computed: {
        diagnosis() {
            return this.matchData?.diagnosis || [];
        },
        errors() {
            return this.diagnosis.filter(d => d.startsWith('ERROR'));
        },
        warnings() {
            return this.diagnosis.filter(d => d.startsWith('WARNING'));
        },
        oks() {
            return this.diagnosis.filter(d => d.startsWith('OK'));
        },
    },

    methods: {
        async runScoring(sessionId, sessionName) {
            this.show        = true;
            this.loading     = true;
            this.error       = null;
            this.matchData   = null;
            this.markdownText = '';
            this.sessionId   = sessionId;
            this.sessionName = sessionName || sessionId;
            this.savedNote   = '';

            try {
                const response = await fetch(`/api/processing-sessions/${sessionId}/calibration-scoring`);
                if (!response.ok) {
                    const err = await response.json().catch(() => ({}));
                    throw new Error(err.detail || `HTTP ${response.status}`);
                }
                const data = await response.json();
                this.matchData    = data.match_data;
                this.markdownText = data.markdown;
                this.jsonFilename = data.json_filename;
                this.mdFilename   = data.md_filename;
                this.savedNote    = `Saved: ${data.json_filename}, ${data.md_filename}`;
            } catch (err) {
                this.error = err.message || 'Unknown error';
            } finally {
                this.loading = false;
            }
        },

        close() {
            this.show = false;
        },

        // ---- status helpers ----

        statusLabel(best) {
            if (!best) return 'No data';
            const flags = best.flags || [];
            if (flags.some(f => f.startsWith('DISQUALIFIED'))) return 'Disqualified';
            if (flags.some(f => f.startsWith('MISMATCH')))     return 'Mismatch';
            if (flags.some(f => f.includes('UNKNOWN')))        return 'Unknown fields';
            return 'Perfect';
        },

        statusBadgeClass(best) {
            const label = this.statusLabel(best);
            if (label === 'Perfect')        return 'bg-green-100 text-green-800';
            if (label === 'Unknown fields') return 'bg-blue-100 text-blue-700';
            if (label === 'Mismatch')       return 'bg-yellow-100 text-yellow-800';
            return 'bg-red-100 text-red-700';
        },

        rowClass(best) {
            const label = this.statusLabel(best);
            if (label === 'Perfect')        return 'bg-green-50';
            if (label === 'Unknown fields') return 'bg-blue-50';
            if (label === 'Mismatch')       return 'bg-yellow-50';
            return 'bg-red-50';
        },

        issueFlags(flags) {
            return (flags || []).filter(f => f.startsWith('MISMATCH') || f.includes('UNKNOWN'));
        },

        recommendations(lg) {
            const recs = [];
            for (const ct of ['dark', 'flat', 'bias']) {
                const best = lg['best_' + ct];
                if (!best) {
                    recs.push(`No ${ct} frames in this session — add ${ct} calibration frames.`);
                    continue;
                }
                const mismatches = (best.flags || []).filter(f => f.startsWith('MISMATCH'));
                mismatches.forEach(f => {
                    recs.push(`${ct.toUpperCase()}: ${f.replace('MISMATCH: ', '')} — acquire new ${ct} frames matching the light frame settings.`);
                });
            }
            return recs;
        },

        // ---- downloads ----

        downloadJson() {
            if (!this.matchData) return;
            const blob = new Blob([JSON.stringify(this.matchData, null, 2)], { type: 'application/json' });
            this._download(blob, this.jsonFilename || `${this.sessionId}_calibration_scoring.json`);
        },

        downloadMarkdown() {
            if (!this.markdownText) return;
            const blob = new Blob([this.markdownText], { type: 'text/markdown' });
            this._download(blob, this.mdFilename || `${this.sessionId}_calibration_scoring.md`);
        },

        _download(blob, filename) {
            const url = URL.createObjectURL(blob);
            const a   = document.createElement('a');
            a.href     = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);
        },
    },
};

window.CalibrationScoringModal = CalibrationScoringModal;
