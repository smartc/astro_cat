# Cleanup Plan - Remove Extraneous Files

## Files to Remove (Phase 2, 3, 4 migration artifacts)

### Documentation - Completed Phases (9 files)
These docs were useful during migration but are no longer needed:

- [ ] `FK_FIX_NEEDED.md` - Foreign key issue (fixed)
- [ ] `PERFORMANCE_FIX.md` - Performance issue (fixed)
- [ ] `PHASE2_TESTING.md` - Phase 2 testing notes
- [ ] `PHASE3_COMPATIBILITY.md` - Phase 3 compatibility notes
- [ ] `PHASE3_MIGRATION.md` - Phase 3 migration guide
- [ ] `PHASE3_TESTING_CHECKLIST.md` - Phase 3 testing checklist
- [ ] `PHASE4_CLEANUP_PLAN.md` - Phase 4 cleanup plan (superseded by this file)
- [ ] `PHASE4_STATUS.md` - Phase 4 status (superseded by PHASE4_COMPLETE.md)

**Keep:**
- ✅ `PHASE4_COMPLETE.md` - Final summary of all migration work
- ✅ `README.md` - Main project documentation

### Scripts - One-Time Migrations (6 files)
These scripts were for one-time migrations and are no longer needed:

- [ ] `scripts/fix_foreign_keys.py` - Phase 3 FK fix (initial version)
- [ ] `scripts/fix_foreign_keys_comprehensive.py` - Phase 3 FK fix (final version)
- [ ] `scripts/fix_performance_post_migration.py` - Phase 3 ANALYZE fix
- [ ] `scripts/migrate_schema_phase3.py` - Phase 3 migration script
- [ ] `scripts/phase4_auto_update.py` - Phase 4 auto-update script
- [ ] `scripts/test_phase3_migration.py` - Old Phase 3 test

**Keep:**
- ✅ `scripts/verify_phase3.py` - Now verifies Phase 4, useful for validation
- ✅ `scripts/diagnose_db_size.py` - Useful diagnostic tool
- ✅ `scripts/remove_duplicate_indexes.py` - Useful maintenance tool

### Test Files - Old Tests (1 file)

- [ ] `test_phase2_models.py` - Phase 2 backward compatibility tests (obsolete)

**Keep:**
- ✅ `test_phase4_models.py` - Current test suite for Phase 4

### Root Directory - Check These (2 files)
Need to verify if these are still used:

- [ ] `migrate_processed_catalog.py` - Old migration? Check if still needed
- [ ] `fix_s3_data.py` - Old S3 fix? Check if still needed

## Summary

**Total files to remove: ~18 files**
- 8 markdown documentation files
- 6 migration script files
- 1 test file
- 2-3 root directory files (pending verification)

**Expected cleanup: Save ~150-200 KB of source files**

## Verification Before Removal

Before removing these files, verify:
1. ✅ Phase 4 migration is complete
2. ✅ Application is working correctly
3. ✅ Database is functioning properly
4. ✅ No active work references these files

All checks passed - safe to proceed with cleanup.
