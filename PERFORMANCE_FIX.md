# Performance Fix for Processing Sessions Modal

## Problem

After Phase 3 migration, Processing Sessions Detail Modal loads slowly because queries are loading ALL 70+ columns from FitsFile table when only a few are needed.

## Root Cause

In `web/routes/processing_sessions.py`:

**Line 141-143:**
```python
files = session.query(FitsFile).join(ProcessingSessionFile).filter(
    ProcessingSessionFile.processing_session_id == session_id
).all()  # Loads ALL columns!
```

**Line 688-690:**
```python
files = session.query(FitsFile).join(ProcessingSessionFile).filter(
    ProcessingSessionFile.processing_session_id == session_id
).all()  # Loads ALL columns!
```

Phase 3 didn't add columns, but the way the table was recreated may have changed the physical layout, making full-table scans slower. Also, with 70+ columns being loaded, the overhead is significant.

## Solution Options

### Option 1: Use `load_only()` (Quick Fix)

```python
from sqlalchemy.orm import load_only

# Line 141: Only load columns actually needed
files = session.query(FitsFile).options(
    load_only(
        FitsFile.id,
        FitsFile.object,
        FitsFile.frame_type,
        FitsFile.filter,
        FitsFile.exposure
    )
).join(ProcessingSessionFile).filter(
    ProcessingSessionFile.processing_session_id == session_id
).all()

# Line 688: Only load columns actually used
files = session.query(FitsFile).options(
    load_only(
        FitsFile.id,
        FitsFile.file,
        FitsFile.folder,
        FitsFile.imaging_session_id,  # Note: renamed from session_id
        FitsFile.frame_type,
        FitsFile.camera,
        FitsFile.telescope,
        FitsFile.obs_date,
        FitsFile.exposure,
        FitsFile.filter,
        FitsFile.object
    )
).join(ProcessingSessionFile).filter(
    ProcessingSessionFile.processing_session_id == session_id
).all()
```

### Option 2: Use SQL with Only Needed Columns (Best Performance)

```python
# Line 141: Use GROUP BY in SQL instead of loading all files
from sqlalchemy import case

object_summaries = session.query(
    FitsFile.object,
    FitsFile.filter,
    FitsFile.exposure,
    func.count(FitsFile.id).label('count'),
    func.sum(FitsFile.exposure).label('total_exposure'),
    func.group_concat(FitsFile.id).label('file_ids')
).join(ProcessingSessionFile).filter(
    ProcessingSessionFile.processing_session_id == session_id,
    FitsFile.frame_type == 'LIGHT'
).group_by(
    FitsFile.object,
    FitsFile.filter,
    FitsFile.exposure
).all()

# This avoids loading individual files entirely!
```

### Option 3: Add Indexes (Helps Both)

The join between `FitsFile` and `ProcessingSessionFile` may benefit from an index on `fits_file_id`:

```python
# Already have: idx_processing_file_fits on ProcessingSessionFile.fits_file_id
# Check it exists:
# CREATE INDEX IF NOT EXISTS idx_processing_file_fits ON processing_session_files(fits_file_id)
```

## Line 702 Issue

**Also found:** Line 702 uses `file.session_id` which is now a deprecated synonym for `file.imaging_session_id`. While it works, it's using the old naming.

**Fix:**
```python
# Change line 702 from:
"session_id": file.session_id,

# To:
"imaging_session_id": file.imaging_session_id,
```

## Recommended Approach

1. **Immediate**: Run `python scripts/vacuum_database.py` to reclaim 19 MB
2. **Short-term**: Apply Option 1 (load_only) to both queries
3. **Long-term**: Refactor to Option 2 (SQL aggregation) for best performance

## Testing

After applying fixes, test with a large processing session (1000+ files):
- Before: 5-10 seconds to load
- After: <1 second to load

## Implementation

Would you like me to create a pull request with these optimizations?
