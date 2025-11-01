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

Run this script to recreate `processing_session_files` with correct foreign key constraints:

```bash
python scripts/fix_foreign_keys.py
```

This script will:
1. Check current foreign key definitions
2. Create a backup of your database
3. Recreate `processing_session_files` with proper foreign keys
4. Verify the fix worked
5. Show test results

## Expected Output

```
============================================================
FOREIGN KEY CONSTRAINT FIX
============================================================

Database: /home/user/Astro/fits_catalog.db

Creating backup: /home/user/Astro/fits_catalog_backup_fk_fix.db
✓ Backup created

============================================================
Checking Foreign Key Constraints
============================================================

Current foreign keys on processing_session_files:
  ID: 0, Seq: 0, Table: processing_sessions, From: processing_session_id, To: id
  ID: 1, Seq: 0, Table: fits_files, From: fits_file_id, To: id

fits_files primary key:
  Column: id, Type: INTEGER, PK: 0

⚠ NOTE: fits_files.id is NOT marked as PRIMARY KEY (PK: 0)!

============================================================
Recreating processing_session_files Table
============================================================

Current rows: 1737

Creating processing_session_files_new...
Copying data...
Copied 1737 rows
Replacing old table...
Creating indexes...
✓ Table recreated successfully

============================================================
Verifying Fix
============================================================

New foreign keys on processing_session_files:
  ID: 0, Seq: 0, Table: processing_sessions, From: processing_session_id, To: id
  ID: 1, Seq: 0, Table: fits_files, From: fits_file_id, To: id

Final row count: 1737

Testing foreign key constraints...
  Rows with valid fits_file_id: 1737
  Rows with valid processing_session_id: 1737

✓ Foreign keys verified

============================================================
✓ FOREIGN KEY FIX COMPLETE
============================================================

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
