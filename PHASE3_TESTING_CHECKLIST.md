# Phase 3 Migration Testing Checklist

## ✅ Already Tested

- [x] Create new processing session (was broken, now fixed with FK fix)
- [x] Processing Session Details Modal - Source sessions display
- [x] Performance fix - Processing sessions load quickly (~20-50ms)
- [x] Database vacuum - Size reduced from 47MB to proper size

## 🔍 Critical Tests to Perform

### 1. Processing Sessions

#### Create Processing Sessions
- [ ] Create empty processing session (no files)
- [ ] Create processing session from imaging session with light frames only
- [ ] Create processing session with mixed frame types (LIGHT + DARK + FLAT + BIAS)
- [ ] Create processing session with multiple objects
- [ ] Create processing session from Files tab (select files manually)

#### View/Manage Processing Sessions
- [ ] Open Processing Sessions tab - verify list loads
- [ ] Open processing session details modal
- [ ] Verify "Source Imaging Sessions" section shows correct data
- [ ] Verify light frame summary shows correct groups
- [ ] Verify calibration frame counts are correct
- [ ] Click on source imaging session link - should navigate to imaging session details
- [ ] View files list in processing session modal
- [ ] Delete a processing session
- [ ] Update processing session status (In Progress, Completed, Failed)

### 2. Imaging Sessions

#### View Imaging Sessions
- [ ] Open Imaging Sessions tab - verify list loads
- [ ] Click on an imaging session - details modal should open
- [ ] Verify file counts (lights, darks, flats, bias) are correct
- [ ] Verify objects list is correct
- [ ] View files from imaging session (click "View Files" button)

#### Create Processing Session from Imaging Session
- [ ] Click "+ New Session" from imaging session details
- [ ] Select an object
- [ ] Verify correct files are selected
- [ ] Create the session
- [ ] Verify it appears in Processing Sessions tab

### 3. Files Tab

#### Display and Filtering
- [ ] Open Files tab - verify files load
- [ ] Sort by imaging_session_id (click column header)
- [ ] Filter by imaging_session_id (type in filter box)
- [ ] Click on imaging_session_id link - should navigate to imaging session details
- [ ] Verify all columns display correctly (no undefined/null values)

#### File Selection and Processing
- [ ] Select multiple files manually (checkboxes)
- [ ] Select all files on page
- [ ] Filter by object, then "Select Visible Files"
- [ ] Create processing session from selected files
- [ ] Verify file count matches selection

### 4. Data Integrity

#### Counts and Relationships
- [ ] Compare total file count before/after migration (should be same)
- [ ] Compare imaging session count before/after migration (should be same)
- [ ] Verify all files have valid imaging_session_id
- [ ] Verify no orphaned files (files without imaging session)

#### Foreign Key Constraints
- [ ] Try to create processing session with invalid file ID (should fail gracefully)
- [ ] Delete an imaging session - verify files remain (FK is nullable)
- [ ] Delete a processing session - verify processing_session_files are deleted (CASCADE)

### 5. Python Model Backward Compatibility (Synonyms)

#### Test in Python Console
```python
from models import FitsFile, ImagingSession
from database_service import DatabaseService

db = DatabaseService()
session = db.db_manager.get_session()

# Test FitsFile synonyms
file = session.query(FitsFile).first()
print(f"New name: {file.imaging_session_id}")
print(f"Synonym: {file.session_id}")  # Should be same
print(f"Width: {file.width_pixels}")
print(f"x synonym: {file.x}")  # Should be same
print(f"Height: {file.height_pixels}")
print(f"y synonym: {file.y}")  # Should be same

# Test ImagingSession synonyms
img_session = session.query(ImagingSession).first()
print(f"New name: {img_session.id}")
print(f"Synonym: {img_session.session_id}")  # Should be same
print(f"Date: {img_session.date}")
print(f"session_date synonym: {img_session.session_date}")  # Should be same
```

### 6. CLI Commands (if you have them)

- [ ] List imaging sessions: `python main_v2.py list imaging-sessions --recent 10`
- [ ] List files: `python main_v2.py list raw --imaging-session <ID>`
- [ ] Any other CLI commands that query the database

### 7. Performance Tests

#### Load Times (should all be fast)
- [ ] Processing Sessions tab initial load (< 500ms)
- [ ] Processing Session Details Modal with 500+ files (< 200ms)
- [ ] Imaging Sessions tab initial load (< 500ms)
- [ ] Files tab with filters applied (< 1s)

### 8. Edge Cases

#### Empty/Null Values
- [ ] Files without imaging_session_id (if any exist)
- [ ] Files with missing object/filter/telescope/camera
- [ ] Processing sessions with no files
- [ ] Imaging sessions with only calibration frames

#### Large Data Sets
- [ ] Processing session with 2000+ files
- [ ] Imaging session with 1000+ files
- [ ] Filter files by popular object (100+ results)

## 🔧 If Issues Found

### Common Issues and Fixes

1. **"session_id is not defined" error in JavaScript:**
   - Check browser console
   - Look for any JavaScript files we missed
   - Search codebase: `grep -r "session_id" static/js/`

2. **"no such column: session_id" error in Python:**
   - Check if synonym is working
   - Verify models.py has synonyms defined
   - Check query is using correct model attribute

3. **Foreign key constraint errors:**
   - Run: `python scripts/fix_foreign_keys_comprehensive.py` again
   - Verify FK constraints exist: `sqlite3 ~/Astro/fits_catalog.db ".schema processing_session_files"`

4. **Slow query performance:**
   - Run: `python scripts/fix_performance_post_migration.py` again
   - Check indexes: `sqlite3 ~/Astro/fits_catalog.db ".indexes fits_files"`

## 📊 Quick Verification SQL Queries

```sql
-- Verify all tables exist
.tables

-- Check imaging_sessions structure
.schema imaging_sessions

-- Check fits_files structure
.schema fits_files

-- Verify imaging_session_id is PRIMARY KEY
PRAGMA table_info('imaging_sessions');

-- Verify fits_files.id is PRIMARY KEY
PRAGMA table_info('fits_files');

-- Check foreign keys are defined
PRAGMA foreign_key_list('processing_session_files');

-- Verify file counts
SELECT COUNT(*) FROM fits_files;
SELECT COUNT(*) FROM imaging_sessions;
SELECT COUNT(*) FROM processing_sessions;
SELECT COUNT(*) FROM processing_session_files;

-- Check for orphaned files
SELECT COUNT(*) FROM fits_files WHERE imaging_session_id IS NULL;

-- Check for files without valid imaging_session_id
SELECT COUNT(*) FROM fits_files f
WHERE NOT EXISTS (
    SELECT 1 FROM imaging_sessions s WHERE s.id = f.imaging_session_id
);
```

## ✅ Sign-off Criteria

Phase 3 migration is complete when:

1. [ ] All processing session operations work
2. [ ] All imaging session operations work
3. [ ] All file filtering/display works
4. [ ] Source sessions display correctly
5. [ ] No JavaScript errors in browser console
6. [ ] No database errors in server logs
7. [ ] Performance is acceptable (< 500ms for most operations)
8. [ ] Data integrity verified (counts match, no orphans)
9. [ ] Python synonyms work (backward compatibility)
10. [ ] Foreign key constraints enforced

## 📝 Notes

- Test in your actual data environment (not test data)
- Check browser console for JavaScript errors
- Check server terminal for Python/database errors
- If something breaks, note the exact error message and steps to reproduce
