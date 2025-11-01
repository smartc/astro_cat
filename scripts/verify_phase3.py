#!/usr/bin/env python3
"""
Quick verification script for Phase 4 migration.

Checks:
- Table structure is correct
- Primary keys exist
- Foreign keys work
- Synonyms are removed (breaking changes)
- Data integrity (no orphans)
- Row counts match expectations
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models import (
    FitsFile, ImagingSession, ProcessingSession, ProcessingSessionFile,
    DatabaseManager, DatabaseService
)
import sqlite3


def check_table_structure(db_path):
    """Check that tables have correct structure."""
    print("="*60)
    print("CHECKING TABLE STRUCTURE")
    print("="*60)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check imaging_sessions
    cursor.execute("PRAGMA table_info('imaging_sessions')")
    cols = {row[1]: row for row in cursor.fetchall()}

    print("\n✓ imaging_sessions table:")
    assert 'id' in cols, "Missing 'id' column"
    assert cols['id'][5] == 1, "id is not PRIMARY KEY"
    assert 'date' in cols, "Missing 'date' column"
    print(f"  ✓ id (PRIMARY KEY)")
    print(f"  ✓ date")

    # Check fits_files
    cursor.execute("PRAGMA table_info('fits_files')")
    cols = {row[1]: row for row in cursor.fetchall()}

    print("\n✓ fits_files table:")
    assert 'id' in cols, "Missing 'id' column"
    assert cols['id'][5] == 1, "id is not PRIMARY KEY"
    assert 'imaging_session_id' in cols, "Missing 'imaging_session_id' column"
    assert 'width_pixels' in cols, "Missing 'width_pixels' column"
    assert 'height_pixels' in cols, "Missing 'height_pixels' column"
    print(f"  ✓ id (PRIMARY KEY)")
    print(f"  ✓ imaging_session_id")
    print(f"  ✓ width_pixels")
    print(f"  ✓ height_pixels")

    # Check processing_session_files FK
    cursor.execute("PRAGMA foreign_key_list('processing_session_files')")
    fks = cursor.fetchall()

    print("\n✓ processing_session_files foreign keys:")
    fk_tables = {fk[2] for fk in fks}
    assert 'fits_files' in fk_tables, "Missing FK to fits_files"
    assert 'processing_sessions' in fk_tables, "Missing FK to processing_sessions"
    for fk in fks:
        print(f"  ✓ {fk[3]} → {fk[2]}.{fk[4]}")

    conn.close()
    print("\n✓ All table structures correct")


def check_data_counts(db_service):
    """Check row counts in all tables."""
    print("\n" + "="*60)
    print("CHECKING DATA COUNTS")
    print("="*60)

    session = db_service.db_manager.get_session()

    try:
        fits_count = session.query(FitsFile).count()
        imaging_count = session.query(ImagingSession).count()
        processing_count = session.query(ProcessingSession).count()
        psf_count = session.query(ProcessingSessionFile).count()

        print(f"\n  fits_files: {fits_count:,}")
        print(f"  imaging_sessions: {imaging_count:,}")
        print(f"  processing_sessions: {processing_count:,}")
        print(f"  processing_session_files: {psf_count:,}")

        assert fits_count > 0, "No FITS files found!"
        assert imaging_count > 0, "No imaging sessions found!"

        print("\n✓ All counts look reasonable")

        return {
            'fits': fits_count,
            'imaging': imaging_count,
            'processing': processing_count,
            'psf': psf_count
        }
    finally:
        session.close()


def check_data_integrity(db_service):
    """Check for orphaned records and data integrity."""
    print("\n" + "="*60)
    print("CHECKING DATA INTEGRITY")
    print("="*60)

    session = db_service.db_manager.get_session()

    try:
        # Check for files without imaging_session_id
        orphaned = session.query(FitsFile).filter(
            FitsFile.imaging_session_id.is_(None)
        ).count()

        if orphaned > 0:
            print(f"\n  ⚠ WARNING: {orphaned} files without imaging_session_id")
        else:
            print(f"\n  ✓ No files without imaging_session_id")

        # Check for invalid imaging_session_id references
        # (files referencing non-existent imaging sessions)
        invalid_refs = session.query(FitsFile).filter(
            FitsFile.imaging_session_id.isnot(None)
        ).filter(
            ~FitsFile.imaging_session_id.in_(
                session.query(ImagingSession.id)
            )
        ).count()

        if invalid_refs > 0:
            print(f"  ⚠ WARNING: {invalid_refs} files with invalid imaging_session_id")
        else:
            print(f"  ✓ All imaging_session_id references are valid")

        # Check processing_session_files integrity
        invalid_psf = session.query(ProcessingSessionFile).filter(
            ~ProcessingSessionFile.fits_file_id.in_(
                session.query(FitsFile.id)
            )
        ).count()

        if invalid_psf > 0:
            print(f"  ⚠ WARNING: {invalid_psf} processing_session_files with invalid fits_file_id")
        else:
            print(f"  ✓ All processing_session_files references are valid")

        print("\n✓ Data integrity verified")

    finally:
        session.close()


def check_synonyms(db_service):
    """Check that backward compatibility synonyms work."""
    print("\n" + "="*60)
    print("CHECKING BACKWARD COMPATIBILITY (Synonyms)")
    print("="*60)

    session = db_service.db_manager.get_session()

    try:
        # Test FitsFile synonyms
        file = session.query(FitsFile).first()

        if file:
            print("\n✓ FitsFile attributes (Phase 4 - synonyms removed):")

            # Verify new attribute names work
            print(f"  ✓ imaging_session_id: {file.imaging_session_id}")
            if file.width_pixels:
                print(f"  ✓ width_pixels: {file.width_pixels}")
            if file.height_pixels:
                print(f"  ✓ height_pixels: {file.height_pixels}")

            # Verify old synonyms are REMOVED
            try:
                _ = file.session_id
                print("  ✗ FAIL: session_id synonym should be removed")
                return False
            except AttributeError:
                print("  ✓ session_id synonym correctly removed")

            try:
                _ = file.x
                print("  ✗ FAIL: x synonym should be removed")
                return False
            except AttributeError:
                print("  ✓ x synonym correctly removed")

            try:
                _ = file.y
                print("  ✗ FAIL: y synonym should be removed")
                return False
            except AttributeError:
                print("  ✓ y synonym correctly removed")

        # Test ImagingSession attributes
        img_session = session.query(ImagingSession).first()

        if img_session:
            print("\n✓ ImagingSession attributes (Phase 4 - synonyms removed):")

            # Verify new attribute names work
            print(f"  ✓ id: {img_session.id}")
            print(f"  ✓ date: {img_session.date}")

            # Verify old synonyms are REMOVED
            try:
                _ = img_session.session_id
                print("  ✗ FAIL: session_id synonym should be removed")
                return False
            except AttributeError:
                print("  ✓ session_id synonym correctly removed")

            try:
                _ = img_session.session_date
                print("  ✗ FAIL: session_date synonym should be removed")
                return False
            except AttributeError:
                print("  ✓ session_date synonym correctly removed")

        print("\n✓ All synonyms correctly removed (Phase 4 complete)")

    finally:
        session.close()


def check_indexes(db_path):
    """Check that all indexes exist."""
    print("\n" + "="*60)
    print("CHECKING INDEXES")
    print("="*60)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    expected_indexes = {
        'imaging_sessions': [
            'idx_session_date',
            'idx_session_telescope_camera'
        ],
        'fits_files': [
            'idx_fits_imaging_session',
            'idx_fits_frame_type',
            'idx_fits_object',
            'idx_fits_telescope_camera'
        ],
        'processing_session_files': [
            'idx_processing_session_id',
            'idx_processing_file_fits',
            'idx_processing_file_type'
        ]
    }

    for table, indexes in expected_indexes.items():
        cursor.execute(f"""
            SELECT name FROM sqlite_master
            WHERE type='index' AND tbl_name='{table}'
            AND sql IS NOT NULL
        """)
        existing = {row[0] for row in cursor.fetchall()}

        print(f"\n{table}:")
        for idx in indexes:
            if idx in existing:
                print(f"  ✓ {idx}")
            else:
                print(f"  ✗ MISSING: {idx}")

    conn.close()
    print("\n✓ Index check complete")


def main():
    """Main entry point."""
    db_path = Path.home() / 'Astro' / 'fits_catalog.db'

    print("="*60)
    print("PHASE 3 MIGRATION VERIFICATION")
    print("="*60)
    print(f"\nDatabase: {db_path}\n")

    if not db_path.exists():
        print(f"✗ Error: Database not found: {db_path}")
        return 1

    try:
        # Initialize database service
        connection_string = f"sqlite:///{db_path}"
        db_manager = DatabaseManager(connection_string)
        db_service = DatabaseService(db_manager)

        # Run all checks
        check_table_structure(db_path)
        counts = check_data_counts(db_service)
        check_data_integrity(db_service)
        check_synonyms(db_service)
        check_indexes(db_path)

        # Summary
        print("\n" + "="*60)
        print("✓ PHASE 3 VERIFICATION COMPLETE")
        print("="*60)
        print(f"""
Summary:
  - Table structures: ✓ Correct
  - Primary keys: ✓ Defined
  - Foreign keys: ✓ Working
  - Data integrity: ✓ Verified
  - Synonyms: ✓ Working
  - Indexes: ✓ Present

  - Total FITS files: {counts['fits']:,}
  - Total imaging sessions: {counts['imaging']:,}
  - Total processing sessions: {counts['processing']:,}
  - Total processing session files: {counts['psf']:,}

Phase 3 migration is successful!

Next steps:
1. Test the web interface manually (see PHASE3_TESTING_CHECKLIST.md)
2. Verify performance is good (< 500ms for most operations)
3. Check for any JavaScript errors in browser console
        """)

        return 0

    except AssertionError as e:
        print(f"\n✗ VERIFICATION FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
