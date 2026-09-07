# Review Queue Feature — Implementation Specification

## Context

**astro_cat** is a Python/FastAPI + Vue.js 3 app for managing astrophotography FITS files.
Key facts needed for this implementation:

- Backend: FastAPI, SQLAlchemy ORM, SQLite at path from `config.paths.database_path`
- Frontend: Vue.js 3 SPA components in `static/js/components/`, loaded as ES modules (no build step, no bundler)
- Styling: Tailwind CSS 2 utility classes throughout; follow the pattern in `monitoring-panel.js`
- Existing operations pattern: `web/routes/operations.py` — uses `sys.modules['web.app']` to access globals
- All routers registered in `web/app.py` via `app.include_router(...)`
- Global app state lives in `sys.modules['web.app']`:
  - `app_module.config` — Config object; `config.equipment.{cameras_file, telescopes_file, filters_file}` give JSON paths
  - `app_module.cameras` — list of `equipment_manager.Camera` Pydantic objects (`.camera` = name, `.rgb` = OSC flag)
  - `app_module.telescopes` — list of `equipment_manager.Telescope` Pydantic objects (`.scope` = name)
  - `app_module.filter_mappings` — `dict[str, str]` mapping raw_name → proper_name
  - `app_module.db_service` — `DatabaseService` instance
- Quarantine path: `config.paths.quarantine_dir`
- `validation.py` contains `FitsValidator`; the method to call is `validator.validate_record(record_dict)`
  (not `validate_file` — that method does not exist)

### Equipment JSON schemas (must match exactly when writing new entries)

**`cameras.json`** — array of:
```json
{
  "camera": "ASI2600",      // name stored in fits_files.camera — required
  "bin": 1,
  "x": 6248,                // sensor width pixels — pre-fill from DB
  "y": 4176,                // sensor height pixels — pre-fill from DB
  "type": "CMOS",           // CMOS / CCD / DSLR
  "brand": "ZWO",
  "pixel": 3.76,            // pixel size in microns
  "rgb": true,              // TRUE = OSC/color, FALSE = mono — CRITICAL for filter scoring
  "comments": ""
}
```

**`telescopes.json`** — array of:
```json
{
  "scope": "FF130",         // name stored in fits_files.telescope — required
  "focal": 1000,            // focal length mm — pre-fill from DB fits_files.focal_length
  "aperture": 130,          // aperture mm
  "make": "ZWO",
  "type": "Refractor",      // Refractor / Reflector / Lens
  "subtype": "Petzval",
  "comments": ""
}
```

**`filters.json`** — array of:
```json
{
  "raw_name": "SPECTRAL-PRO",   // value stored in fits_files.filter — required
  "proper_name": "Spectral-Pro" // canonical display name — user-editable before save
}
```

### How the DB equipment tables relate to the JSON files

On startup, `db_service.initialize_equipment()` syncs the JSON files into the `cameras`,
`telescopes`, and `filter_mappings` DB tables. `FitsValidator` scores files using these DB tables
(via `db_service.get_cameras()` etc.). After writing a new entry to a JSON file, you must:

1. Write the JSON file (atomic: write to `.tmp`, then rename)
2. Reload the app_module globals so scan/catalog operations pick up the change:
   ```python
   app_module = sys.modules['web.app']
   from equipment_manager import EquipmentManager
   em = EquipmentManager(config.equipment)
   app_module.cameras, app_module.telescopes, app_module.filter_mappings = em.load_all()
   ```
3. Re-sync the DB tables:
   ```python
   from cli.utils import convert_equipment_for_db
   cameras_dict, telescopes_dict, fm_dict = convert_equipment_for_db(
       app_module.cameras, app_module.telescopes, app_module.filter_mappings
   )
   app_module.db_service.initialize_equipment(cameras_dict, telescopes_dict, fm_dict)
   ```
4. Invalidate the `FitsValidator` equipment cache: the validator caches `_cameras`, `_telescopes`,
   `_filter_mappings` on first use. When building the validator for re-validation, create a fresh
   instance — `FitsValidator(db_service)` — so it reloads from the updated DB tables.

---

## Part 1 — Bug Fixes to `web/routes/stats.py`

Fix these three issues in the existing stats route **before** building the new review queue feature.

### Fix 1: `between(80, 95)` double-counts files at score=95 (line ~537)

SQLAlchemy `.between(80, 95)` is inclusive on both ends. Any file scoring exactly 95.0 (achievable
for a LIGHT frame missing only focal_length or only RA/Dec) appears in both `auto_migrate` and
`needs_review`. Replace the `needs_review` query:

```python
# BEFORE (buggy — inclusive upper bound double-counts score=95):
needs_review = session.query(FitsFile).filter(
    FitsFile.validation_score.between(80, 95)
).count()

# AFTER:
needs_review = session.query(FitsFile).filter(
    FitsFile.validation_score >= 80,
    FitsFile.validation_score < 95,
    FitsFile.folder.like(f"%{config.paths.quarantine_dir}%")
).count()
```

### Fix 2: `needs_review` and `manual_only` are not scoped to quarantine (lines ~537–544)

`auto_migrate` correctly filters by quarantine folder, but `needs_review` and `manual_only` query
the entire database. If equipment is renamed or removed from a JSON file and re-validation is run,
library files would flood the review counter. Add the quarantine filter to both:

```python
manual_only = session.query(FitsFile).filter(
    FitsFile.validation_score < 80,
    FitsFile.validation_score >= 0,          # see Fix 3
    FitsFile.folder.like(f"%{config.paths.quarantine_dir}%")
).count()
```

### Fix 3: `validation_score > 0` hides unknown-frame-type files (line ~542)

Files with an unrecognised `frame_type` (e.g. "BIAS FRAME", "MASTER FLAT") score exactly 0.
The current `> 0` filter excludes them from `manual_only`, and since score=0 is not NULL they also
miss `no_score`. They become invisible in all four counters. Change `> 0` to `>= 0`.

---

## Part 2 — Backend: `web/routes/review_queue.py`

### `GET /api/review-queue`

Query **all quarantine files with `validation_score < 95`** (not just 80–94 — unknown frame types
score 0 and must surface here too). Group by specific issue. Return grouped results plus the
current known equipment lists for use in fix forms.

**Response shape:**
```json
{
  "total_files": 41,
  "known_filters": ["Ha-3nm", "L-Pro", "L-Xtreme", "None"],
  "known_cameras": ["ASI2600", "ASI1600", "QSI683"],
  "known_telescopes": ["FF130", "ES127", "ROKINON_135"],
  "groups": [
    {
      "group_id": "non_standard_filter__SPECTRAL-PRO",
      "issue_type": "non_standard_filter",
      "severity": "warning",
      "issue_summary": "Filter 'SPECTRAL-PRO' is not in the filter list",
      "detail": "This filter name is not recognised. Adding it will restore full scoring and allow these files to auto-migrate.",
      "file_count": 30,
      "files": [
        {
          "id": 123,
          "file": "FlatWizard_Spectral-Pro_0.23sec_0000.fits",
          "folder": "/mnt/ganymede/Astro/Quarantine/...",
          "frame_type": "FLAT",
          "filter": "SPECTRAL-PRO",
          "object": "CALIBRATION",
          "camera": "ASI2600",
          "telescope": "FF130",
          "obs_date": "2026-04-27",
          "validation_score": 81.25,
          "validation_notes": "..."
        }
      ],
      "available_fixes": [
        {
          "fix_id": "add_filter_to_list",
          "label": "Add 'SPECTRAL-PRO' to the filter list",
          "description": "Registers this as a known filter. Files will be re-validated and will reach 100/100.",
          "params": {
            "raw_name": "SPECTRAL-PRO",
            "proper_name": "Spectral-Pro"
          }
        },
        {
          "fix_id": "rename_value_in_db",
          "label": "Rename to an existing filter",
          "description": "Use if this is a typo or alias for a filter already in the list.",
          "params": {
            "field": "filter",
            "current_value": "SPECTRAL-PRO",
            "new_value": null
          }
        }
      ]
    }
  ]
}
```

**Grouping logic** — implement as `_build_review_groups(files, filter_mappings, cameras, telescopes)`:

Parse `validation_notes` (semicolon-separated) and field values for each file. Build one group per
distinct (issue_type, offending_value) pair. A file may belong to multiple groups if it has
multiple issues — that is intentional and correct.

| Detection condition | `issue_type` | `severity` | `group_id` | `available_fixes` |
|---|---|---|---|---|
| `notes` contains `"non-standard filter"` | `non_standard_filter` | `warning` | `non_standard_filter__{filter}` | `add_filter_to_list`, `rename_value_in_db` |
| `notes` contains `"Camera: non-standard"` | `non_standard_camera` | `warning` | `non_standard_camera__{camera}` | `add_camera_to_list`, `rename_value_in_db` |
| `notes` contains `"Telescope: non-standard"` | `non_standard_telescope` | `warning` | `non_standard_telescope__{telescope}` | `add_telescope_to_list`, `rename_value_in_db` |
| `frame_type == "LIGHT"` and `object.lower()` contains `flat`, `dark`, `bias`, or `adhoc` | `suspect_frame_type` | `warning` | `suspect_frame_type__LIGHT__{object}` | `change_frame_type` |
| `notes` contains `"Unknown frame type"` (i.e. score=0) | `unknown_frame_type` | `error` | `unknown_frame_type__{frame_type}` | `change_frame_type` |
| `notes` contains `"Missing/invalid object name"` | `missing_object` | `info` | `missing_object` | *(inform only — no automated fix)* |

For `add_camera_to_list`, pre-populate the params form with values inferrable from the DB:
- `camera`: the unrecognised camera name (from `fits_files.camera`)
- `x`: from `fits_files.width_pixels` (take mode across the group's files)
- `y`: from `fits_files.height_pixels` (take mode)
- `focal_length_hint`: from `fits_files.focal_length` (for user reference, not in camera JSON)

For `add_telescope_to_list`:
- `scope`: the unrecognised telescope name
- `focal`: from `fits_files.focal_length` (take mode)

Include `"prefill"` dict in the fix params so the frontend can pre-populate the form without
doing its own DB queries.

`known_filters` should be the **proper_names** from the current filter_mappings (deduplicated).
`known_cameras` should be the `.camera` values from `app_module.cameras`.
`known_telescopes` should be the `.scope` values from `app_module.telescopes`.

---

### `POST /api/review-queue/apply-fix`

**Request body:**
```json
{
  "fix_id": "add_filter_to_list",
  "params": {
    "raw_name": "SPECTRAL-PRO",
    "proper_name": "Spectral-Pro"
  },
  "file_ids": [123, 124, 125]
}
```

`file_ids` is always required. The frontend sends the IDs of all files in the group
(or a user-selected subset). Return a consistent response for all fix types:

```json
{
  "fixed_count": 30,
  "revalidated_count": 30,
  "new_scores": {"123": 100.0, "124": 100.0},
  "warnings": []
}
```

---

#### Fix: `add_filter_to_list`

Params: `{"raw_name": "SPECTRAL-PRO", "proper_name": "Spectral-Pro"}`

1. Read `filters.json`; refuse with HTTP 409 if `raw_name` already present (case-insensitive check)
2. Append `{"raw_name": ..., "proper_name": ...}`; write atomically (temp file + rename)
3. Reload equipment in app_module and DB (see reload sequence in Context above)
4. Re-validate **all** files in the DB with `filter == raw_name` (not only the provided file_ids),
   since the fix applies globally. Use the provided file_ids to compute `fixed_count`.
5. Return result

---

#### Fix: `add_camera_to_list`

Params (all user-supplied from the form, but `camera`, `x`, `y` pre-filled):
```json
{
  "camera": "NewCam2600",
  "bin": 1,
  "x": 6248,
  "y": 4176,
  "type": "CMOS",
  "brand": "ZWO",
  "pixel": 3.76,
  "rgb": true,
  "comments": ""
}
```

The `rgb` field is the most important: it determines whether this camera is treated as OSC (full
filter score for any known filter) or mono (penalised for "no filter"). The UI **must** make this
field prominent and explain its effect on scoring.

1. Validate required fields (`camera`, `x`, `y`, `brand`); refuse with HTTP 422 if missing
2. Read `cameras.json`; refuse with HTTP 409 if camera name already present
3. Append entry; write atomically
4. Reload equipment in app_module and DB
5. Re-validate all files with `camera == params["camera"]`
6. Return result

---

#### Fix: `add_telescope_to_list`

Params (all user-supplied, `scope` and `focal` pre-filled):
```json
{
  "scope": "NewScope",
  "focal": 1000,
  "aperture": 130,
  "make": "ZWO",
  "type": "Refractor",
  "subtype": "Petzval",
  "comments": ""
}
```

1. Read `telescopes.json`; refuse with HTTP 409 if scope name already present
2. Append entry; write atomically
3. Reload equipment in app_module and DB
4. Re-validate all files with `telescope == params["scope"]`
5. Return result

---

#### Fix: `rename_value_in_db`

A single unified fix for renaming filter, camera, or telescope values in the DB.
Params: `{"field": "filter", "current_value": "SPETRAL-PRO", "new_value": "SPECTRAL-PRO"}`

Supported `field` values: `"filter"`, `"camera"`, `"telescope"`.

1. Validate `field` is one of the three supported values
2. For `filter`: validate `new_value` is in `filter_mappings` (raw or proper names); reject with 422 otherwise
3. For `camera`: validate `new_value` is a known camera name; reject with 422 otherwise
4. For `telescope`: validate `new_value` is a known telescope name; reject with 422 otherwise
5. `UPDATE fits_files SET {field} = new_value WHERE id IN (file_ids)`
   Do **not** apply globally — only to the explicitly provided file_ids; the user may have files
   elsewhere where the current value is intentional.
6. Re-validate updated files; return result

---

#### Fix: `change_frame_type`

Params: `{"new_frame_type": "FLAT"}` — must be one of LIGHT, FLAT, DARK, BIAS

1. Validate `new_frame_type`
2. `UPDATE fits_files SET frame_type = new_frame_type WHERE id IN (file_ids)`
3. If changing away from LIGHT to a calibration type, check each file for `imaging_session_id`.
   If set, include a warning per file in the response but do **not** automatically clear it.
4. Re-validate updated files using the correct scorer for the new frame type
5. Return result (include any warnings about imaging_session_id)

---

#### Re-validation helper

Extract into a shared function in the route file. Note the correct method name is
`validate_record`, not `validate_file`:

```python
def _revalidate_files(db_session, file_ids: list[int], db_service) -> dict:
    """Re-run validation on given file IDs, update DB, return {str(id): new_score}."""
    validator = FitsValidator(db_service)  # fresh instance — clears equipment cache
    results = {}
    for file_id in file_ids:
        fits_file = db_session.get(FitsFile, file_id)
        if not fits_file:
            continue
        record = {
            'object': fits_file.object,
            'obs_date': fits_file.obs_date,
            'camera': fits_file.camera,
            'telescope': fits_file.telescope,
            'filter': fits_file.filter,
            'exposure': fits_file.exposure,
            'frame_type': fits_file.frame_type,
            'focal_length': fits_file.focal_length,
            'ra': fits_file.ra,
            'dec': fits_file.dec,
        }
        result = validator.validate_record(record)
        fits_file.validation_score = result.score
        fits_file.validation_notes = "; ".join(result.notes) if result.notes else None
        fits_file.migration_ready = result.migration_ready
        results[str(file_id)] = result.score
    db_session.commit()
    return results
```

**Error handling:**
- HTTP 409 if an "add to list" entry already exists
- HTTP 422 if required params are missing or a rename target is not a known value
- HTTP 500 if JSON file write fails; do not leave partial state (write to `.tmp` then `os.replace`)

---

## Part 3 — Frontend: `static/js/components/review-queue-panel.js`

A Vue.js 3 component following the collapsible-panel pattern of `monitoring-panel.js`.
When the review queue is empty (total_files == 0) show a compact "✓ No files need review" state.

### Visual Layout

```
┌─────────────────────────────────────────────────────────────┐
│ ▶  Review Queue                    [41 files need review]   │
└─────────────────────────────────────────────────────────────┘

Expanded — one card per group, ordered: errors first, then warnings, then info:

┌─────────────────────────────────────────────────────────────┐
│ ▼  Review Queue                    [41 files need review]   │
│ ─────────────────────────────────────────────────────────── │
│                                                             │
│ ┌ ⚠ Non-standard filter: SPECTRAL-PRO ──────── [30 files] ┐│
│ │ Filter not in filter list. Add it to allow auto-migrate.  ││
│ │ [▶ Show 30 files]                                         ││
│ │ [Add to filter list ▾]  [Rename to existing filter ▾]    ││
│ └───────────────────────────────────────────────────────────┘│
│                                                             │
│ ┌ ⚠ Non-standard filter: SPETRAL-PRO ────────── [10 files] ┐│
│ │ Filter not in filter list. Looks like a typo.             ││
│ │ [▶ Show 10 files]                                         ││
│ │ [Add to filter list ▾]  [Rename to existing filter ▾]    ││
│ └───────────────────────────────────────────────────────────┘│
│                                                             │
│ ┌ ⚠ Suspect frame type: LIGHT / "Adhoc Flat" ─── [1 file] ┐│
│ │ Frame type is LIGHT but object name suggests a flat.      ││
│ │ [▶ Show 1 file]                                           ││
│ │ [Change frame type ▾]                                     ││
│ └───────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

**Inline action forms** (shown when a button is clicked, replacing it):

*Add filter to list:*
```
  Raw name (from FITS header): [SPECTRAL-PRO   ] (read-only)
  Display name:                [Spectral-Pro   ] (editable)
  [Cancel]  [Add to Filter List]
```

*Add camera to list:*
```
  Camera name (from FITS): [NewCam2600  ] (read-only)
  Brand:     [ZWO    ]   Type: [CMOS ▼]   Pixel size (µm): [3.76]
  Sensor:    X [6248 ]   Y [4176]  (pre-filled from files)
  Camera type: ● OSC/Color  ○ Mono   ← prominent, explains filter scoring impact
  Comments:  [              ]
  [Cancel]  [Add Camera]
```

*Add telescope to list:*
```
  Telescope name (from FITS): [NewScope   ] (read-only)
  Manufacturer: [ZWO  ]  Type: [Refractor ▼]  Subtype: [Petzval]
  Focal length: [1000 ] mm (pre-filled)   Aperture: [130] mm
  Comments:  [              ]
  [Cancel]  [Add Telescope]
```

*Rename to existing:*
```
  Rename 'SPETRAL-PRO' to: [── select ──▼]  (dropdown from known_filters)
  [Cancel]  [Rename in 10 files]
```

*Change frame type:*
```
  Change frame type to: [FLAT ▼]  (LIGHT / FLAT / DARK / BIAS)
  [Cancel]  [Change Frame Type]
```

**File list** (expandable, lazy — don't render until opened):
```
  ▼ 30 files
  Filename                                   Type  Score
  FlatWizard_Spectral-Pro_0.23sec_0000.fits  FLAT  81.25
  FlatWizard_Spectral-Pro_0.23sec_0001.fits  FLAT  81.25
  ...
```

### Component State

```javascript
{
  expanded: false,
  loading: false,
  error: null,
  groups: [],
  knownFilters: [],
  knownCameras: [],
  knownTelescopes: [],
  totalFiles: 0,
  expandedFiles: {},     // { group_id: bool }
  activeForm: {},        // { group_id: { fix_id, formData } } — at most one open at a time per group
  applying: {},          // { group_id: bool }
  groupResults: {},      // { group_id: { fixed_count, warnings, error } }
}
```

### API Calls

```javascript
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

async applyFix(group, fix_id, formData) {
  this.applying[group.group_id] = true;
  this.groupResults[group.group_id] = null;
  try {
    const body = {
      fix_id,
      params: formData,
      file_ids: group.files.map(f => f.id)
    };
    const resp = await fetch('/api/review-queue/apply-fix', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    });
    const result = await resp.json();
    if (!resp.ok) throw new Error(result.detail || 'Fix failed');
    this.groupResults[group.group_id] = result;
    this.$emit('fix-applied');  // parent refreshes dashboard stats
    await this.loadQueue();     // refresh — resolved groups disappear
  } catch (e) {
    this.groupResults[group.group_id] = { error: e.message };
  } finally {
    this.applying[group.group_id] = false;
    delete this.activeForm[group.group_id];
  }
}
```

### Post-fix success message

Per group, after a successful fix:
`"✓ Fixed 30 files — re-validated, new score: 100.0. Ready to migrate."`

If the result includes warnings (e.g., imaging_session_id present on changed frames), show them
below the success message in amber text.

---

## Part 4 — Integration

### `web/app.py`

```python
from web.routes import review_queue
# add alongside existing include_router calls:
app.include_router(review_queue.router)
```

### `static/js/components/operations-tab.js`

1. Import `ReviewQueuePanel` (same pattern as other panel imports in the file)
2. Register in `components: { ReviewQueuePanel, ... }`
3. Place in template immediately above or below `MonitoringPanel`:
   ```html
   <review-queue-panel @fix-applied="onFixApplied" />
   ```
4. Implement `onFixApplied()` to reload whatever dashboard stats the tab already tracks

### `static/js/app.js`

Check how `MonitoringPanel` is registered (globally or locally) and follow the same pattern
for `ReviewQueuePanel`.

---

## Implementation Order

1. **Fix `web/routes/stats.py`** — the three bug fixes (boundary, quarantine scope, score=0). Verify
   the "needs review" count on the dashboard still shows 41 for the current data.
2. **`web/routes/review_queue.py` GET** — grouping logic only, no fixes yet. Verify with curl that
   the three expected groups are returned for the current 41 quarantine files.
3. **Register router in `web/app.py`**
4. **`web/routes/review_queue.py` POST** — implement all fix types with re-validation.
5. **`static/js/components/review-queue-panel.js`** — full component.
6. **`static/js/components/operations-tab.js`** — integrate the panel.
7. **End-to-end test** (in order):
   a. Apply `change_frame_type` FLAT to the 1 adhoc flat file → verify it disappears from queue, score updates
   b. Apply `add_filter_to_list` for SPECTRAL-PRO → verify 30 files disappear (or reach 100), filter appears in known_filters
   c. Apply `rename_value_in_db` SPETRAL-PRO → SPECTRAL-PRO for the 10 files → verify queue empties
   d. Confirm dashboard "needs review" counter reaches 0

---

## Edge Cases to Handle

- **File in multiple groups**: A file with a non-standard camera AND a non-standard filter appears
  in both groups. Applying one fix will not remove it from the other. After `loadQueue()` refresh,
  it should still appear in the remaining group. This is correct behaviour.
- **`add_*_to_list` re-validates globally**: After adding a filter/camera/telescope to the list,
  re-validate ALL files in the DB with that value (not just the provided `file_ids`). Library files
  that were migrated before the equipment was registered will also get their scores corrected.
  They won't reappear in the queue (they're not in quarantine), but their scores in the DB will be
  accurate, which matters for any future statistics or reports.
- **`rename_value_in_db` is scoped to `file_ids`**: Do not apply globally. A different batch of
  files may use the same raw name intentionally (e.g., genuinely different filters that happen to
  share a name).
- **Atomic JSON writes**: All JSON file writes must use write-to-temp + `os.replace()`. If the
  write fails partway, the original file is untouched.
- **`rgb` field in new cameras**: If the user does not explicitly set this, default to `true` (OSC).
  Explain in the UI that mono cameras should set this to false, and that it affects whether
  narrowband/broadband filters score correctly.
- **Unknown frame type files (score=0)**: These appear in the review queue with severity `error`
  and offer only `change_frame_type` as a fix. The `change_frame_type` fix accepts any of the
  four standard values; validate server-side and reject anything else with HTTP 422.
- **`imaging_session_id` on frame-type changes**: If a file had `frame_type=LIGHT` and is
  changed to FLAT/DARK/BIAS, its `imaging_session_id` FK may now be semantically wrong (calibration
  frames don't belong to imaging sessions). Include a warning in the API response listing affected
  file IDs, but do not clear the FK automatically — leave that decision to the user.
