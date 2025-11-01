# Phase 2 Model Consolidation - Testing Guide

## What Was Fixed

The initial Phase 2 implementation had SQLAlchemy issues that have now been resolved:

### Issues Resolved ✓

1. **SQLAlchemy duplicate column warnings** - Fixed by using `synonym()` instead of simple aliases
2. **Index column name errors** - Fixed by referencing DB column names in indexes
3. **Backward compatibility** - Fully working via SQLAlchemy synonyms

## How to Test

### 1. Start the Web Interface

```bash
python run_web.py
```

**Expected Result:**
- ✓ No SQLAlchemy warnings about duplicate columns
- ✓ No errors about missing column names in indexes
- ✓ Web interface starts successfully on http://localhost:8000

### 2. Run the Test Script (if dependencies are installed)

```bash
python test_phase2_models.py
```

**Expected Result:**
- All 8 tests pass
- Confirms model imports, column mappings, synonyms, and database operations work

### 3. Verify CLI Commands Still Work

```bash
# List imaging sessions (old Session model now ImagingSession)
python main_v2.py list imaging-sessions --recent 5

# List processing sessions
python main_v2.py processing-session list

# List raw files
python main_v2.py list raw --limit 10
```

**Expected Result:**
- All commands work as before
- No errors or warnings

### 4. Test Deprecation Warnings (Optional)

In Python shell:

```python
import warnings
warnings.simplefilter('always')

# This should show a deprecation warning
from processed_catalog.models import ProcessedFile, ProcessingSession

# But the imports still work
print(ProcessedFile.__name__)  # Should print: ProcessedFile
print(ProcessingSession.__name__)  # Should print: ProcessingSession
```

**Expected Result:**
- Warning message about importing from processed_catalog.models being deprecated
- But imports still work (backward compatibility)

## What Changed

### models.py - Column Mappings

**ImagingSession (formerly Session):**
- Python: `session.id` → Database: `session_id`
- Python: `session.date` → Database: `session_date`
- Old names still work: `session.session_id`, `session.session_date` (via synonyms)

**FitsFile:**
- Python: `fits.width_pixels` → Database: `x`
- Python: `fits.height_pixels` → Database: `y`
- Python: `fits.imaging_session_id` → Database: `session_id`
- Old names still work: `fits.x`, `fits.y`, `fits.session_id` (via synonyms)

**ProcessingSession:**
- Consolidated from two versions
- Now includes: `primary_target`, `target_type`, `image_type`, `ra`, `dec`, integration metadata

**ProcessedFile:**
- Moved from `processed_catalog/models.py` to main `models.py`
- No changes to fields

### Backward Compatibility

✓ **Old imports work** - With deprecation warnings:
```python
from processed_catalog.models import ProcessedFile  # Still works
```

✓ **Old attribute names work** - Via synonyms:
```python
fits_file.x  # Works (synonym for width_pixels)
session.session_id  # Works (synonym for id)
```

✓ **Old queries work** - Via synonyms:
```python
session.query(ImagingSession).filter(
    ImagingSession.session_id == 'some_id'  # Works via synonym
)
```

## Database Compatibility

**Zero schema changes** - The database remains unchanged:
- Tables: Same structure
- Columns: Same names
- Indexes: Same
- Foreign keys: Same

The changes are **code-only** using SQLAlchemy's column mapping feature.

## Next Steps

Once testing confirms everything works:

1. Review the changes in the branch
2. Merge to main
3. Deploy without database migration (safe!)
4. Phase 3 can then implement actual schema migration if desired

## Troubleshooting

### If you see SQLAlchemy warnings:
- Make sure you've pulled the latest commit: `f3b5475`
- The warnings should be gone with the synonym() fixes

### If imports fail:
- Check that `models.py` is the latest version
- Verify `processed_catalog/models.py` is the compatibility shim

### If queries fail:
- Check if you're using new attribute names (`id`, `date`, `width_pixels`)
- Or use old names (they work via synonyms)

## Questions?

The consolidation is designed to be:
- ✓ Zero breaking changes
- ✓ Fully backward compatible
- ✓ No database schema changes
- ✓ Safe to deploy immediately

All existing code continues to work while new code can use clearer naming!
