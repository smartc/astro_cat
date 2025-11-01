# Foreign Key Fix Required After Phase 3 Migration

## ⚠️ CRITICAL: Must run after Phase 3 migration

If you've already run Phase 3 migration and are getting this error when creating processing sessions:

```
sqlite3.OperationalError: foreign key mismatch - "processing_session_files" referencing "fits_files"
```

## Root Cause

The Phase 3 migration script used `CREATE TABLE AS SELECT` to recreate the `fits_files` table. This SQLite command **does not preserve**:

1. PRIMARY KEY constraints
2. AUTOINCREMENT properties
3. Explicit column types
4. Foreign key definitions

When `fits_files` was recreated, its `id` column lost the `PRIMARY KEY` constraint. This caused the foreign key from `processing_session_files.fits_file_id` to become invalid, resulting in "foreign key mismatch" errors.

## The Fix

Run this comprehensive fix script:

```bash
python scripts/fix_foreign_keys_comprehensive.py
```

This script will:
1. Check current table structure and identify the issue
2. Create a backup of your database
3. Recreate `fits_files` with proper PRIMARY KEY on id column
4. Recreate `processing_session_files` with correct foreign keys
5. Verify the fix worked with test queries
6. Show detailed results

## Expected Output

```
============================================================
COMPREHENSIVE FOREIGN KEY FIX
============================================================

Database: /home/user/Astro/fits_catalog.db

Creating backup: /home/user/Astro/fits_catalog_backup_fk_comprehensive.db
✓ Backup created

============================================================
Checking Current Database State
============================================================

fits_files columns:
  id: Type=INTEGER, PK=0
  ⚠ WARNING: 'id' is NOT a PRIMARY KEY!

fits_files rows: 25285
processing_session_files rows: 1737

============================================================
Step 1: Recreating fits_files with PRIMARY KEY
============================================================

Found 70+ columns in fits_files
Creating fits_files_new with proper schema...
Copying data...
✓ Copied 25285 rows
Getting indexes to recreate...
Swapping tables...
Recreating indexes...
  ✓ idx_fits_imaging_session
  ✓ idx_fits_frame_type
  ✓ idx_fits_object
  ✓ idx_fits_telescope_camera
✓ fits_files recreated with proper PRIMARY KEY

============================================================
Step 2: Recreating processing_session_files
============================================================

Current rows: 1737

Creating processing_session_files_new...
Copying data...
✓ Copied 1737 rows
Swapping tables...
Creating indexes...
✓ processing_session_files recreated with proper foreign keys

============================================================
Step 3: Verifying Fix
============================================================

fits_files.id:
  ✓ Type=INTEGER, PRIMARY KEY

processing_session_files foreign keys:
  ✓ fits_file_id → fits_files.id
  ✓ processing_session_id → processing_sessions.id

Testing foreign key constraints...
  ✓ Rows with valid fits_file_id: 1737
  ✓ Rows with valid processing_session_id: 1737

Testing foreign key enforcement...
  ✓ Foreign key constraints are enforced

✓ All verifications passed

============================================================
✓ COMPREHENSIVE FIX COMPLETE
============================================================

Summary:
  - Recreated fits_files with PRIMARY KEY on id
  - Recreated processing_session_files with proper foreign keys
  - Preserved all 25285 FITS files
  - Preserved all 1737 processing session files
  - Foreign key constraints now enforced

Next steps:
1. Restart your web server
2. Try creating a new processing session
3. It should now work without foreign key errors
```

## After Running the Fix

1. **Restart your web server** (if running)
2. **Test creating a processing session** - should work without errors
3. **Keep the backup** - `fits_catalog_backup_fk_fix.db` in case you need to roll back

## Why This Happened

The Phase 3 migration script has been updated to prevent this issue for future users, but if you already ran the migration, you need to run this fix manually.

## Related Error Messages

If you see any of these errors, run the fix script:

- `foreign key mismatch - "processing_session_files" referencing "fits_files"`
- `FOREIGN KEY constraint failed` when creating processing sessions
- `Cannot add or update a child row: a foreign key constraint fails`

## Technical Details

**Before fix:**
- `fits_files.id` created by `CREATE TABLE AS SELECT` (no PRIMARY KEY)
- `processing_session_files.fits_file_id` references non-PK column
- SQLite rejects INSERT operations due to FK mismatch

**After fix:**
- `processing_session_files` recreated with explicit schema
- Foreign keys properly defined: `FOREIGN KEY (fits_file_id) REFERENCES fits_files(id)`
- SQLite enforces FK constraints correctly

## If the Fix Doesn't Work

1. Check your database path is correct: `~/Astro/fits_catalog.db`
2. Make sure foreign keys are enabled: `PRAGMA foreign_keys = ON;`
3. Check the migration actually ran: Look for `imaging_sessions` table
4. Report the issue with full error output

## Rollback

If something goes wrong, restore from backup:

```bash
cp ~/Astro/fits_catalog_backup_fk_fix.db ~/Astro/fits_catalog.db
```
