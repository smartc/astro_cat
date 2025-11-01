# Phase 4 Status - Removing Backward Compatibility

## ✅ Completed

1. **models.py** - Removed all synonym() declarations:
   - ✓ Removed `FitsFile.x`, `FitsFile.y`, `FitsFile.session_id`
   - ✓ Removed `ImagingSession.session_id`, `ImagingSession.session_date`
   - ✓ Removed `Session = ImagingSession` alias

2. **processing_session_manager.py** - Updated all FitsFile references:
   - ✓ All `f.session_id` → `f.imaging_session_id` (9 instances)

## ⚠️ Remaining Work

### Critical Files (Need Updates)

These files have many references to old attribute names and need to be updated:

#### 1. file_selector.py
- `FitsFile.session_id` → `FitsFile.imaging_session_id` (6 instances)
- Used in query filters and grouping

#### 2. web/routes/imaging_sessions.py
- `SessionModel.session_id` → `SessionModel.id` (10+ instances)
- `SessionModel.session_date` → `SessionModel.date` (8+ instances)
- `FitsFile.session_id` → `FitsFile.imaging_session_id` (4 instances)

#### 3. web/utils.py
- `SessionModel.session_id` → `SessionModel.id` (2 instances)
- `imaging_session.session_date` → `imaging_session.date` (1 instance)
- `FitsFile.session_id` → `FitsFile.imaging_session_id` (1 instance)

#### 4. cli/list_commands.py
- `s.session_id` → `s.id` (1 instance)
- `s.session_date` → `s.date` (1 instance)

#### 5. cli/imaging_session_commands.py
- `Session.session_id` → `ImagingSession.id` (2 instances)
- `session.session_id` → `session.id` (1 instance)
- `session.session_date` → `session.date` (1 instance)

### S3 Backup Module (Extensive Updates)

The S3 backup module has ~50+ references to old names:

#### 6. s3_backup/manager.py
- `SessionModel.session_id` → `SessionModel.id` (multiple instances)
- `session.session_date` → `session.date` (multiple instances)
- `FitsFile.session_id` → `FitsFile.imaging_session_id` (multiple instances)

#### 7. s3_backup/cli.py
- Similar updates needed (~30 instances)

#### 8. s3_backup/web_app.py
- Similar updates needed (~20 instances)

#### 9. s3_backup/cleanup_orphan_notes.py
- Minor updates needed

### Test Files

#### 10. test_phase2_models.py
- Update or remove backward compatibility tests

#### 11. scripts/verify_phase3.py
- Remove tests for synonyms (they no longer exist)

### Other Files

#### 12. web/routes/stats.py
- `ImagingSession.session_date` → `ImagingSession.date` (1 instance)

#### 13. processed_catalog/cli.py
- May need updates if it uses session_id

## Update Strategy

### Option 1: Manual Updates (Recommended for Understanding)

Update files one by one:

```bash
# For each file, find uses of old names:
grep -n "\.session_id\|\.session_date\|\.x\b\|\.y\b" file_selector.py

# Update manually with context
# Test after each file
```

**Pros:** You understand each change, safer
**Cons:** Time-consuming (~2-3 hours)

### Option 2: Automated Script

Use the provided script with caution:

```bash
python scripts/phase4_auto_update.py
```

**Pros:** Fast, consistent
**Cons:** May miss edge cases, needs review

### Option 3: Find & Replace

Use your IDE's search and replace:

1. Search: `FitsFile\.session_id`
   Replace: `FitsFile.imaging_session_id`

2. Search: `f\.session_id`
   Replace: `f.imaging_session_id`

3. Search: `SessionModel\.session_id`
   Replace: `SessionModel.id`

4. Search: `SessionModel\.session_date`
   Replace: `SessionModel.date`

**Caution:** Be careful with context - not all `.session_id` should change!

## Testing After Updates

### 1. Run Verification Script

```bash
python scripts/verify_phase3.py
```

This will fail with AttributeError if any code still uses old names.

### 2. Test Web Interface

```bash
python run_web.py
```

Test:
- Imaging Sessions tab
- Processing Sessions tab
- Files tab
- Creating processing sessions

### 3. Check for Errors

Watch terminal for:
- `AttributeError: 'FitsFile' object has no attribute 'session_id'`
- `AttributeError: 'ImagingSession' object has no attribute 'session_date'`

Each error tells you exactly what file/line needs updating.

## Progress Tracking

Use this checklist:

- [x] models.py - synonyms removed
- [x] processing_session_manager.py - updated
- [ ] file_selector.py
- [ ] web/routes/imaging_sessions.py
- [ ] web/utils.py
- [ ] cli/list_commands.py
- [ ] cli/imaging_session_commands.py
- [ ] s3_backup/manager.py
- [ ] s3_backup/cli.py
- [ ] s3_backup/web_app.py
- [ ] s3_backup/cleanup_orphan_notes.py
- [ ] test_phase2_models.py
- [ ] scripts/verify_phase3.py
- [ ] web/routes/stats.py
- [ ] processed_catalog/cli.py

## Estimated Time

- **Manual approach:** 2-3 hours
- **Semi-automated:** 30-60 minutes (script + review + fixes)
- **Testing:** 30 minutes

**Total:** 1-4 hours depending on approach

## Current State

⚠️ **Application is currently broken** - synonyms removed but many files not yet updated.

**DO NOT deploy** until all files are updated and tested.

## Next Steps

1. Choose update strategy (manual, script, or IDE find/replace)
2. Update remaining files systematically
3. Test after each major file or batch
4. Run full test suite when complete
5. Create PR for review

## Rollback

If needed, restore synonyms temporarily:

```python
# In models.py FitsFile class:
x = synonym('width_pixels')
y = synonym('height_pixels')
session_id = synonym('imaging_session_id')

# In models.py ImagingSession class:
session_id = synonym('id')
session_date = synonym('date')

# At module level:
Session = ImagingSession
```
