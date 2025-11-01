# Phase 3: Schema Migration Guide

## Overview

Phase 3 completes the refactoring by migrating the database schema to match the new Python naming conventions established in Phase 2. This removes all SQLAlchemy column name mapping, making the code cleaner and more maintainable.

## What Changes

### Tables Renamed
- `sessions` → `imaging_sessions`

### Columns Renamed in imaging_sessions
- `session_id` → `id`
- `session_date` → `date`

### Columns Renamed in fits_files
- `x` → `width_pixels`
- `y` → `height_pixels`
- `session_id` → `imaging_session_id`

### Foreign Keys Updated
- `fits_files.imaging_session_id` → FK to `imaging_sessions.id`

### Code Changes
- All `Column('old_name', ...)` mapping removed from models.py
- Backward compatibility synonyms removed
- `Session = ImagingSession` deprecated alias removed

## Prerequisites

**CRITICAL: You must complete Phase 2 before running Phase 3!**

Check your schema version:
```bash
sqlite3 ~/Astro/fits_catalog.db "SELECT * FROM schema_version ORDER BY version DESC LIMIT 1;"
```

Should show version 1. If schema_version table doesn't exist, run Phase 2 first.

## Migration Process

### Step 1: Pre-Migration Safety

**Stop all services:**
```bash
# Stop web interface
pkill -f run_web.py

# Stop file monitor
pkill -f file_monitor.py

# Stop any other processes using the database
pkill -f main_v2.py
```

**Close all database connections:**
- Close SQLite browser applications
- Exit Python REPL sessions
- Wait 30 seconds

**Verify database is accessible:**
```bash
sqlite3 ~/Astro/fits_catalog.db "SELECT COUNT(*) FROM fits_files;"
```

### Step 2: Run Migration Script

```bash
# Navigate to project directory
cd ~/astro_cat

# Run migration script (creates automatic backup)
python scripts/migrate_schema_phase3.py
```

The script will:
1. ✓ Check prerequisites (schema version, table existence)
2. ✓ Create timestamped backup at `~/Astro/backups/`
3. ✓ Verify backup integrity
4. ⚠️  Prompt for confirmation
5. ✓ Run migration in a transaction
6. ✓ Verify all changes
7. ✓ Report success/failure

**Expected output:**
```
============================================================
FITS Cataloger - Phase 3 Schema Migration
============================================================

Database: /home/user/Astro/fits_catalog.db

This script will:
  • Rename 'sessions' table to 'imaging_sessions'
  • Rename columns: session_id→id, session_date→date
  • Rename fits_files columns: x→width_pixels, y→height_pixels
  • Update foreign key: session_id→imaging_session_id

Creating backup: /home/user/Astro/backups/fits_catalog_pre_phase3_20250101_120000.db
✓ Backup created
✓ Backup verified: 245 sessions, 12456 FITS files

WARNING: This will modify your database schema
A backup has been created at:
  /home/user/Astro/backups/fits_catalog_pre_phase3_20250101_120000.db

Type 'yes' to proceed with migration: yes

Starting Phase 3 schema migration...

[1/5] Creating imaging_sessions table...
      Copying data from sessions...
      ✓ Copied 245 imaging sessions

[2/5] Creating new fits_files table with renamed columns...
      ✓ Copied 12456 FITS files
      Swapping tables...

[3/5] Recreating indexes...
      ✓ Imaging sessions indexes created
      ✓ FITS files indexes created

[4/5] Dropping old sessions table...
      ✓ Old table removed

[5/5] Updating schema version...
      ✓ Schema version updated to 2

✓ Migration completed successfully!

============================================================
Verifying migration...
============================================================
✓ imaging_sessions table exists
✓ Old sessions table removed
✓ Column width_pixels exists
✓ Column height_pixels exists
✓ Column imaging_session_id exists
✓ Data integrity: 245 sessions, 12456 files
✓ Schema version: 2 - Phase 3: Renamed tables and columns
✓ Imaging sessions indexes exist

============================================================
✓ All verification checks passed!
============================================================

============================================================
MIGRATION COMPLETE!
============================================================
```

### Step 3: Run Verification Tests

**Note:** The `models.py` file is already updated in this branch with Phase 3 changes.

**What changed in models.py:**
- `ImagingSession.__tablename__` = `'imaging_sessions'` (was `'sessions'`)
- `ImagingSession.id` = `Column(String(50), ...)` (was `Column('session_id', ...)`)
- `ImagingSession.date` = `Column(String(10), ...)` (was `Column('session_date', ...)`)
- `FitsFile.width_pixels` = `Column(Integer)` (was `Column('x', Integer)`)
- `FitsFile.height_pixels` = `Column(Integer)` (was `Column('y', Integer)`)
- `FitsFile.imaging_session_id` = `Column(String(50), ForeignKey('imaging_sessions.id'))` (was `Column('session_id', ...)`)
- **Kept backward compatibility synonyms** for zero-downtime migration
- **Kept `Session = ImagingSession` alias** for compatibility

Run verification tests:

```bash
# Run automated test suite
python scripts/test_phase3_migration.py
```

Expected output:
```
============================================================
Phase 3 Migration Verification Tests
============================================================

============================================================
Testing Database Schema
============================================================

[1/7] Checking table names...
  ✓ imaging_sessions table exists
  ✓ Old sessions table removed

[2/7] Checking imaging_sessions columns...
  ✓ Column 'id' exists
  ✓ Column 'date' exists

[3/7] Checking fits_files columns...
  ✓ Column 'width_pixels' exists
  ✓ Column 'height_pixels' exists
  ✓ Column 'imaging_session_id' exists

[4/7] Checking data integrity...
  ✓ Found 245 imaging sessions
  ✓ Found 12456 FITS files

[5/7] Checking schema version...
  ✓ Schema version: 2
    Description: Phase 3: Renamed tables and columns

[6/7] Checking indexes...
  ✓ Index 'idx_session_date' exists
  ✓ Index 'idx_session_telescope_camera' exists
  ✓ Index 'idx_fits_imaging_session' exists

[7/7] Checking foreign key constraints...
  ✓ Foreign key: fits_files.imaging_session_id -> imaging_sessions.id

============================================================
✓ All schema checks passed!
============================================================

... (more tests)

============================================================
FINAL RESULTS
============================================================
  ✓ PASS: schema
  ✓ PASS: import
  ✓ PASS: queries
  ✓ PASS: service
============================================================

🎉 All verification tests passed!
```

### Step 4: Test CLI Commands

Test all major CLI functions:

```bash
# List imaging sessions
python main_v2.py list imaging-sessions --recent 10

# Get session info
python main_v2.py imaging-session info <SESSION_ID>

# List files in a session
python main_v2.py list raw --imaging-session <SESSION_ID>

# Scan for new files
python main_v2.py scan raw

# Catalog files
python main_v2.py catalog raw

# Get statistics
python main_v2.py stats raw
```

All commands should work exactly as before.

### Step 5: Test Web Interface

```bash
# Start web server
python run_web.py
```

Test these pages:
- http://localhost:8080/ (Dashboard)
- http://localhost:8080/raw-files (Raw files list)
- http://localhost:8080/sessions (Imaging sessions - should still work!)
- http://localhost:8080/processing (Processing sessions)

### Step 6: Test Database Queries Manually

```python
# Quick manual test
python3 << 'EOF'
from models import DatabaseManager, ImagingSession, FitsFile
from pathlib import Path

db_path = Path.home() / 'Astro' / 'fits_catalog.db'
db = DatabaseManager(f'sqlite:///{db_path}')
session = db.get_session()

# Test 1: Query imaging sessions
sessions = session.query(ImagingSession).limit(5).all()
print(f"✓ Found {len(sessions)} imaging sessions")
for s in sessions:
    print(f"  {s.id}: {s.date} - {s.telescope}/{s.camera}")

# Test 2: Query FITS files
files = session.query(FitsFile).limit(5).all()
print(f"\n✓ Found {len(files)} FITS files")
for f in files:
    print(f"  {f.id}: {f.width_pixels}x{f.height_pixels}")

# Test 3: Foreign key relationship
img_session = sessions[0]
file_count = session.query(FitsFile).filter(
    FitsFile.imaging_session_id == img_session.id
).count()
print(f"\n✓ Session {img_session.id} has {file_count} files")

session.close()
print("\n✓ All manual tests passed!")
EOF
```

## Rollback Procedure

If you encounter issues:

### Immediate Rollback

```bash
# Stop all services
pkill -f run_web.py
pkill -f file_monitor.py

# Find your backup
ls -lht ~/Astro/backups/

# Restore from backup (use most recent Phase 3 backup)
cp ~/Astro/backups/fits_catalog_pre_phase3_YYYYMMDD_HHMMSS.db ~/Astro/fits_catalog.db

# Revert to previous commit (before Phase 3)
git checkout HEAD~1 models.py

# Clear Python cache
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -delete

# Restart services
python run_web.py
```

### Verify Rollback

```bash
sqlite3 ~/Astro/fits_catalog.db << 'EOF'
SELECT name FROM sqlite_master WHERE type='table' AND name='sessions';
SELECT MAX(version) FROM schema_version;
EOF
```

Should show:
- `sessions` table exists
- Schema version is 1

## Troubleshooting

### Error: "database is locked"

**Cause:** Another process is accessing the database

**Solution:**
```bash
# Find processes using the database
lsof ~/Astro/fits_catalog.db

# Kill them
pkill -f run_web.py
pkill -f file_monitor.py
pkill -f main_v2.py

# Wait 30 seconds
sleep 30

# Try again
python scripts/migrate_schema_phase3.py
```

### Error: "UNIQUE constraint failed"

**Cause:** Duplicate data in database

**Solution:**
```bash
# Check for duplicates before migration
sqlite3 ~/Astro/fits_catalog.db << 'EOF'
-- Check for duplicate session IDs
SELECT session_id, COUNT(*) FROM sessions GROUP BY session_id HAVING COUNT(*) > 1;

-- Check for duplicate MD5 sums
SELECT md5sum, COUNT(*) FROM fits_files GROUP BY md5sum HAVING COUNT(*) > 1;
EOF

# If duplicates found, clean them up first
# Then re-run migration
```

### Error: "no such column: x"

**Cause:** Migration completed but old models.py still loaded (cache issue)

**Solution:**
```bash
# Clear Python cache
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -delete

# Restart services
python run_web.py
```

### Error: "no such table: sessions"

**Cause:** Migration completed successfully, old code still references old table

**Solution:**
Check for any custom scripts or code using:
```bash
grep -r "sessions" --include="*.py" . | grep -v "imaging_sessions" | grep -v ".git"
```

Update any code still using `sessions` table to use `imaging_sessions`.

### Warning: SQLAlchemy warnings about synonyms

**Cause:** Python cache issue or multiple models loaded

**Solution:**
```bash
# Clear Python cache
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -delete

# Restart Python processes
pkill -f run_web.py
pkill -f file_monitor.py

# Restart services
python run_web.py
```

## Post-Migration Checklist

- [ ] Migration script completed without errors
- [ ] Backup created and verified
- [ ] Verification tests pass
- [ ] CLI commands work
- [ ] Web interface loads correctly
- [ ] No SQLAlchemy warnings in logs
- [ ] Foreign keys function correctly
- [ ] Schema version = 2

## Success Criteria

✅ All verification tests pass
✅ CLI commands execute normally
✅ Web interface displays data correctly
✅ No errors in application logs
✅ Queries execute successfully
✅ Foreign key relationships work

## Final Cleanup (After 30 Days)

After running Phase 3 successfully for at least 30 days:

```bash
# Optimize database
sqlite3 ~/Astro/fits_catalog.db "VACUUM;"

# Optional: Clean old backups (keep at least one!)
cd ~/Astro/backups
ls -lt

# Keep most recent backup, delete older Phase 3 backups
# CAREFUL: Only delete if you're absolutely sure Phase 3 is working!
# rm fits_catalog_pre_phase3_OLD_DATE.db
```

## Files Changed in Phase 3

### New Files
- `scripts/migrate_schema_phase3.py` - Migration script
- `scripts/test_phase3_migration.py` - Verification tests
- `PHASE3_MIGRATION.md` - This documentation
- `PHASE3_COMPATIBILITY.md` - Compatibility analysis

### Modified Files
- `models.py` - Updated from Phase 2 to Phase 3 (column mapping removed, backward compatibility synonyms kept)

### Generated Files
- `~/Astro/backups/fits_catalog_pre_phase3_*.db` - Automatic backup

## Next Steps

After successful Phase 3 migration:

1. ✅ Monitor application for 1 week
2. ✅ Keep backup for 30 days minimum
3. ✅ Update any custom scripts
4. ✅ Document custom workflow changes
5. ✅ Train users on any interface changes (if any)

## Support

If you encounter issues:

1. Check this troubleshooting guide
2. Review migration script output
3. Run verification tests
4. Check database schema manually
5. Restore from backup if needed

## Summary

Phase 3 completes the refactoring journey:

- **Phase 1:** Created new CLI with modern code structure
- **Phase 2:** Consolidated models, added column mapping for compatibility
- **Phase 3:** Migrated database schema, removed column mapping

Your database now matches your Python code perfectly. The codebase is cleaner, more maintainable, and ready for future enhancements!
