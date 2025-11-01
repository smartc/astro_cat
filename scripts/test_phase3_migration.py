#!/usr/bin/env python3
"""
Test script for Phase 3 migration verification.

This script verifies that:
1. The migration script successfully renamed tables and columns
2. The updated models.py works correctly with the new schema
3. All queries and relationships function as expected
4. Foreign keys are properly configured

Run this AFTER:
1. Running scripts/migrate_schema_phase3.py
2. Replacing models.py with models_phase3.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import sqlite3
from datetime import datetime


def test_database_schema():
    """Test database schema has been migrated correctly."""
    print("="*60)
    print("Testing Database Schema")
    print("="*60)

    db_path = Path.home() / 'Astro' / 'fits_catalog.db'

    if not db_path.exists():
        print(f"✗ Error: Database not found: {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    errors = []

    # Test 1: Check tables exist with new names
    print("\n[1/7] Checking table names...")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]

    if 'imaging_sessions' in tables:
        print("  ✓ imaging_sessions table exists")
    else:
        errors.append("imaging_sessions table not found")
        print("  ✗ imaging_sessions table not found")

    if 'sessions' in tables:
        errors.append("Old sessions table still exists")
        print("  ✗ Old sessions table still exists")
    else:
        print("  ✓ Old sessions table removed")

    # Test 2: Check ImagingSession columns
    print("\n[2/7] Checking imaging_sessions columns...")
    cursor.execute("PRAGMA table_info(imaging_sessions)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    if 'id' in columns:
        print("  ✓ Column 'id' exists")
    else:
        errors.append("Column 'id' not found in imaging_sessions")
        print("  ✗ Column 'id' not found")

    if 'date' in columns:
        print("  ✓ Column 'date' exists")
    else:
        errors.append("Column 'date' not found in imaging_sessions")
        print("  ✗ Column 'date' not found")

    if 'session_id' in columns:
        errors.append("Old column 'session_id' still exists in imaging_sessions")
        print("  ✗ Old column 'session_id' still exists")

    if 'session_date' in columns:
        errors.append("Old column 'session_date' still exists in imaging_sessions")
        print("  ✗ Old column 'session_date' still exists")

    # Test 3: Check FitsFile columns
    print("\n[3/7] Checking fits_files columns...")
    cursor.execute("PRAGMA table_info(fits_files)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    required_columns = ['width_pixels', 'height_pixels', 'imaging_session_id']
    old_columns = ['x', 'y', 'session_id']

    for col in required_columns:
        if col in columns:
            print(f"  ✓ Column '{col}' exists")
        else:
            errors.append(f"Column '{col}' not found in fits_files")
            print(f"  ✗ Column '{col}' not found")

    for col in old_columns:
        if col in columns:
            errors.append(f"Old column '{col}' still exists in fits_files")
            print(f"  ✗ Old column '{col}' still exists")

    # Test 4: Check data integrity
    print("\n[4/7] Checking data integrity...")
    cursor.execute("SELECT COUNT(*) FROM imaging_sessions")
    session_count = cursor.fetchone()[0]
    print(f"  ✓ Found {session_count} imaging sessions")

    cursor.execute("SELECT COUNT(*) FROM fits_files")
    fits_count = cursor.fetchone()[0]
    print(f"  ✓ Found {fits_count} FITS files")

    # Test 5: Check schema version
    print("\n[5/7] Checking schema version...")
    cursor.execute("SELECT version, description, applied_at FROM schema_version ORDER BY version DESC LIMIT 1")
    row = cursor.fetchone()
    if row:
        version, description, applied_at = row
        if version == 2:
            print(f"  ✓ Schema version: {version}")
            print(f"    Description: {description}")
            print(f"    Applied: {applied_at}")
        else:
            errors.append(f"Schema version is {version}, expected 2")
            print(f"  ✗ Schema version is {version}, expected 2")
    else:
        errors.append("No schema version found")
        print("  ✗ No schema version found")

    # Test 6: Check indexes
    print("\n[6/7] Checking indexes...")
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND tbl_name='imaging_sessions'
    """)
    imaging_indexes = [row[0] for row in cursor.fetchall()]

    expected_indexes = ['idx_session_date', 'idx_session_telescope_camera']
    for idx in expected_indexes:
        if idx in imaging_indexes:
            print(f"  ✓ Index '{idx}' exists")
        else:
            errors.append(f"Index '{idx}' missing from imaging_sessions")
            print(f"  ✗ Index '{idx}' missing")

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND tbl_name='fits_files'
    """)
    fits_indexes = [row[0] for row in cursor.fetchall()]

    if 'idx_fits_imaging_session' in fits_indexes:
        print("  ✓ Index 'idx_fits_imaging_session' exists")
    else:
        errors.append("Index 'idx_fits_imaging_session' missing")
        print("  ✗ Index 'idx_fits_imaging_session' missing")

    # Test 7: Check foreign keys
    print("\n[7/7] Checking foreign key constraints...")
    cursor.execute("PRAGMA foreign_key_list(fits_files)")
    fks = cursor.fetchall()

    has_imaging_session_fk = False
    for fk in fks:
        table = fk[2]
        from_col = fk[3]
        to_col = fk[4]

        if table == 'imaging_sessions' and from_col == 'imaging_session_id':
            has_imaging_session_fk = True
            print(f"  ✓ Foreign key: fits_files.{from_col} -> {table}.{to_col}")

    if not has_imaging_session_fk:
        errors.append("Foreign key from fits_files to imaging_sessions not found")
        print("  ✗ Foreign key from fits_files to imaging_sessions not found")

    conn.close()

    # Summary
    print("\n" + "="*60)
    if errors:
        print("SCHEMA VERIFICATION FAILED")
        print("="*60)
        for error in errors:
            print(f"  ✗ {error}")
        return False
    else:
        print("✓ All schema checks passed!")
        print("="*60)
        return True


def test_models_import():
    """Test that models.py can be imported and used."""
    print("\n" + "="*60)
    print("Testing Models Import and Usage")
    print("="*60)

    try:
        from models import (
            DatabaseManager, ImagingSession, FitsFile,
            ProcessingSession, DatabaseService
        )
        print("  ✓ All models imported successfully")

        # Check that ImagingSession uses correct table
        if ImagingSession.__tablename__ == 'imaging_sessions':
            print("  ✓ ImagingSession uses 'imaging_sessions' table")
        else:
            print(f"  ✗ ImagingSession uses '{ImagingSession.__tablename__}' table (expected 'imaging_sessions')")
            return False

        # Check that Session alias exists for backward compatibility
        try:
            from models import Session
            print("  ✓ Deprecated 'Session' alias exists (backward compatibility)")
            # Verify it's an alias to ImagingSession
            if Session is ImagingSession:
                print("  ✓ Session is an alias to ImagingSession")
            else:
                print("  ✗ Session is not an alias to ImagingSession")
                return False
        except ImportError:
            print("  ✗ Session alias missing (needed for backward compatibility)")
            return False

        return True

    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_queries():
    """Test that database queries work with new schema."""
    print("\n" + "="*60)
    print("Testing Database Queries")
    print("="*60)

    try:
        from models import DatabaseManager, ImagingSession, FitsFile

        db_path = Path.home() / 'Astro' / 'fits_catalog.db'
        db = DatabaseManager(f'sqlite:///{db_path}')
        session = db.get_session()

        # Test 1: Query imaging sessions
        print("\n[1/5] Querying imaging sessions...")
        imaging_sessions = session.query(ImagingSession).limit(5).all()
        print(f"  ✓ Found {len(imaging_sessions)} imaging sessions")

        for img_session in imaging_sessions[:3]:
            print(f"    - {img_session.id}: {img_session.date} ({img_session.telescope}/{img_session.camera})")

        # Test 2: Query FITS files
        print("\n[2/5] Querying FITS files...")
        files = session.query(FitsFile).limit(5).all()
        print(f"  ✓ Found {len(files)} FITS files")

        for f in files[:3]:
            print(f"    - {f.id}: {f.width_pixels}x{f.height_pixels} ({f.object})")

        # Test 3: Test foreign key relationship
        print("\n[3/5] Testing foreign key relationships...")
        if imaging_sessions:
            img_session = imaging_sessions[0]
            file_count = session.query(FitsFile).filter(
                FitsFile.imaging_session_id == img_session.id
            ).count()
            print(f"  ✓ Session '{img_session.id}' has {file_count} files")

        # Test 4: Test joins
        print("\n[4/5] Testing joins...")
        result = session.query(FitsFile, ImagingSession).join(
            ImagingSession,
            FitsFile.imaging_session_id == ImagingSession.id
        ).limit(5).all()
        print(f"  ✓ Join query returned {len(result)} results")

        # Test 5: Test filters and aggregations
        print("\n[5/5] Testing filters and aggregations...")
        from sqlalchemy import func

        # Count files by session
        session_counts = session.query(
            ImagingSession.id,
            func.count(FitsFile.id).label('file_count')
        ).join(
            FitsFile,
            FitsFile.imaging_session_id == ImagingSession.id
        ).group_by(
            ImagingSession.id
        ).limit(5).all()

        print(f"  ✓ Aggregation query returned {len(session_counts)} results")
        for sess_id, count in session_counts[:3]:
            print(f"    - Session {sess_id}: {count} files")

        session.close()
        print("\n✓ All query tests passed!")
        return True

    except Exception as e:
        print(f"  ✗ Query test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_service():
    """Test DatabaseService methods with new schema."""
    print("\n" + "="*60)
    print("Testing DatabaseService")
    print("="*60)

    try:
        from models import DatabaseManager, DatabaseService

        db_path = Path.home() / 'Astro' / 'fits_catalog.db'
        db = DatabaseManager(f'sqlite:///{db_path}')
        service = DatabaseService(db)

        # Test 1: Get imaging sessions
        print("\n[1/3] Testing get_imaging_sessions()...")
        sessions = service.get_imaging_sessions()
        print(f"  ✓ Found {len(sessions)} imaging sessions")

        # Test 2: Get specific imaging session
        print("\n[2/3] Testing get_imaging_session()...")
        if sessions:
            session_id = sessions[0].id
            img_session = service.get_imaging_session(session_id)
            if img_session:
                print(f"  ✓ Retrieved session: {img_session.id} ({img_session.date})")
            else:
                print("  ✗ Failed to retrieve session")
                return False

        # Test 3: Get database stats
        print("\n[3/3] Testing get_database_stats()...")
        stats = service.get_database_stats()
        print(f"  ✓ Total files: {stats.get('total_files', 0)}")
        print(f"  ✓ Frame types: {list(stats.get('by_frame_type', {}).keys())}")

        print("\n✓ All DatabaseService tests passed!")
        return True

    except Exception as e:
        print(f"  ✗ DatabaseService test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all verification tests."""
    print("="*60)
    print("Phase 3 Migration Verification Tests")
    print("="*60)
    print()

    results = {
        'schema': test_database_schema(),
        'import': test_models_import(),
        'queries': test_database_queries(),
        'service': test_database_service(),
    }

    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)

    all_passed = all(results.values())

    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {test_name}")

    print("="*60)

    if all_passed:
        print("\n🎉 All verification tests passed!")
        print("\nYour Phase 3 migration is complete and working correctly.")
        print("\nNext steps:")
        print("  1. Test CLI commands")
        print("  2. Test web interface")
        print("  3. Run the application normally for a few days")
        print("  4. Keep backup for at least 30 days")
        return 0
    else:
        print("\n⚠️  Some tests failed!")
        print("\nPlease review the errors above and:")
        print("  1. Check that migration script completed successfully")
        print("  2. Verify models.py was updated to models_phase3.py")
        print("  3. Check database schema manually with sqlite3")
        print("\nIf problems persist, restore from backup:")
        db_path = Path.home() / 'Astro' / 'fits_catalog.db'
        backup_dir = db_path.parent / 'backups'
        print(f"  cp {backup_dir}/fits_catalog_pre_phase3_*.db {db_path}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
