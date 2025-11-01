# Phase 4: Remove Backward Compatibility

## ⚠️ IMPORTANT: This phase contains BREAKING CHANGES

Phase 3 is complete and stable. Phase 4 removes all backward compatibility layers.

**Before starting Phase 4:**
- ✅ Merge Phase 3 to main branch (stable checkpoint)
- ✅ Create new branch for Phase 4
- ✅ Ensure Phase 3 is working correctly in production

## What Phase 4 Removes

### 1. Model Synonyms (models.py)

Remove all `synonym()` declarations that provide backward compatibility:

#### FitsFile class:
```python
# REMOVE these lines:
x = synonym('width_pixels')
y = synonym('height_pixels')
session_id = synonym('imaging_session_id')
```

#### ImagingSession class:
```python
# REMOVE these lines:
session_id = synonym('id')
session_date = synonym('date')
```

**Impact:** Any Python code using old names (`.x`, `.y`, `.session_id`, `.session_date`) will break.

### 2. Search for Code Using Old Names

Need to search entire codebase and update:

#### Old FitsFile attributes:
- `.x` → `.width_pixels`
- `.y` → `.height_pixels`
- `.session_id` → `.imaging_session_id`

#### Old ImagingSession attributes:
- `.session_id` → `.id`
- `.session_date` → `.date`

**Search commands:**
```bash
# Find Python files using old FitsFile attributes
grep -r "\.x\b" --include="*.py" .
grep -r "\.y\b" --include="*.py" .
grep -r "\.session_id" --include="*.py" .

# Find Python files using old ImagingSession attributes
grep -r "\.session_date" --include="*.py" .
```

**Note:** Be careful not to change:
- ProcessingSession uses (they have their own `id`)
- Dictionary keys in JSON responses (already updated in Phase 3)
- JavaScript code (already updated in Phase 3)

### 3. Update Comments and Docstrings

Search for comments/docs referencing old names:
```bash
grep -r "session_id" --include="*.py" . | grep "#"
grep -r "session_date" --include="*.py" . | grep "#"
```

Update to use new names.

### 4. CLI Commands (if applicable)

Check if any CLI commands accept old parameter names:
- `--session-id` → `--imaging-session-id`
- `--session-date` → `--date`

### 5. Remove Migration Scripts (Optional)

Once Phase 4 is stable, optionally remove:
- `scripts/migrate_schema_phase3.py` (no longer needed)
- `scripts/fix_foreign_keys_comprehensive.py` (no longer needed)
- Backup documentation (phase 2, phase 3 docs)

**Keep:**
- `scripts/verify_phase3.py` (useful for verifying database state)
- `scripts/fix_performance_post_migration.py` (useful for ANALYZE operations)

## Testing Phase 4

### 1. Remove Synonyms First

Edit `models.py` and remove all synonym declarations.

### 2. Run Verification

```bash
# This will FAIL if any code uses old names
python scripts/verify_phase3.py
```

**Expected errors:**
```
AttributeError: 'FitsFile' object has no attribute 'x'
AttributeError: 'FitsFile' object has no attribute 'session_id'
AttributeError: 'ImagingSession' object has no attribute 'session_date'
```

These errors tell you which files need updating.

### 3. Fix Each Error

For each error:
1. Note the file and line number
2. Update to use new attribute name
3. Test again

### 4. Run Full Test Suite

After all errors fixed:
```bash
# Run verification script
python scripts/verify_phase3.py

# Start web server and test manually
python run_web.py

# Test all functionality:
# - Create processing session
# - View imaging sessions
# - Filter files
# - All CRUD operations
```

### 5. Check for Subtle Issues

Look for issues that might not throw errors:
- Queries that filter by old column names (will return wrong results)
- JSON serialization using old names (will have missing fields)
- Comparisons with old attributes (will fail silently)

## Git Workflow for Phase 4

```bash
# Starting from main (with Phase 3 merged)
git checkout main
git pull origin main

# Create Phase 4 branch
git checkout -b claude/schema-migration-phase-four-<session-id>

# Make changes incrementally:

# Step 1: Remove synonyms from models.py
git add models.py
git commit -m "Remove backward compatibility synonyms from models"

# Step 2: Fix all code using old names
git add -A
git commit -m "Update all code to use Phase 3 naming convention"

# Step 3: Update documentation
git add -A
git commit -m "Update comments and docs to use new naming"

# Step 4: Test and verify
python scripts/verify_phase3.py
# Fix any issues, commit fixes

# Step 5: Push and create PR
git push -u origin claude/schema-migration-phase-four-<session-id>
```

## Files Most Likely to Need Updates

Based on Phase 3 work, these files might still use old names:

### Python Files:
- `processing_session_manager.py` - Check file staging/validation code
- `catalog_handler.py` - Check if exists, might use old names
- `main_v2.py` - CLI commands might use old names
- `*.py` in root - Any utility scripts

### Test Files:
- `test_*.py` - Test files might use old attribute names
- `scripts/test_phase3_migration.py` - Update to not use synonyms

## Expected Benefits of Phase 4

After Phase 4 is complete:

1. **Cleaner codebase** - No confusing dual naming
2. **Easier to maintain** - Single source of truth for column names
3. **Prevents bugs** - Can't accidentally use wrong name
4. **Better for new developers** - Less confusion
5. **Smaller models.py** - Remove synonym() declarations

## Rollback Plan

If Phase 4 causes issues:

```bash
# Rollback to Phase 3 (stable)
git checkout main

# Or fix forward by re-adding synonyms temporarily:
# Add back synonym() declarations to models.py while fixing issues
```

## Validation Checklist

Phase 4 is complete when:

- [ ] All synonym() declarations removed from models.py
- [ ] All Python code uses new attribute names
- [ ] `python scripts/verify_phase3.py` runs without errors
- [ ] Web interface works (all CRUD operations)
- [ ] No AttributeError exceptions in logs
- [ ] CLI commands work (if applicable)
- [ ] All tests pass
- [ ] Comments/docs updated
- [ ] Code review complete
- [ ] Merged to main

## Timeline Recommendation

**Phase 3 → Main:** Do this immediately (it's stable)

**Phase 4 Start:** Can be done anytime, no rush
- It's non-urgent cleanup work
- Phase 3 works perfectly with synonyms
- Phase 4 is purely for code cleanliness

**Phase 4 Complete:** Low priority
- Only do when you have time
- Not blocking any other work
- Can wait weeks/months if needed

## Questions Before Starting Phase 4

1. Are there any external tools/scripts using the Python API?
2. Are there any Jupyter notebooks using old attribute names?
3. Are there any cron jobs or automated scripts?
4. Do other developers need to be notified?

If yes to any, coordinate before removing backward compatibility.
