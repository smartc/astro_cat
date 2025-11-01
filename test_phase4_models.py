#!/usr/bin/env python3
"""
Test script for Phase 4 - Final Cleanup.
Verifies that old attribute names are removed and only new names work.
"""

import sys
import tempfile
from pathlib import Path

print("=" * 70)
print("PHASE 4 FINAL CLEANUP - TEST SCRIPT")
print("=" * 70)

try:
    # Test 1: Import all models
    print("\n1. Testing model imports...")
    from models import (
        ImagingSession,
        ProcessingSession,
        ProcessedFile,
        FitsFile,
        Camera,
        Telescope,
        SchemaVersion,
        DatabaseManager
    )
    print("   ✓ All model imports successful")

    # Test 2: Verify Session alias is REMOVED
    print("\n2. Testing Session alias removed...")
    try:
        from models import Session
        print("   ✗ FAIL: Session alias should be removed")
        sys.exit(1)
    except ImportError:
        print("   ✓ Session alias correctly removed")

    # Test 3: Verify old synonym attributes are REMOVED
    print("\n3. Testing synonyms removed...")

    # FitsFile should NOT have old synonym names
    assert hasattr(FitsFile, 'width_pixels'), "FitsFile should have width_pixels"
    assert hasattr(FitsFile, 'height_pixels'), "FitsFile should have height_pixels"
    assert hasattr(FitsFile, 'imaging_session_id'), "FitsFile should have imaging_session_id"

    assert not hasattr(FitsFile, 'x'), "FitsFile should NOT have x (synonym removed)"
    assert not hasattr(FitsFile, 'y'), "FitsFile should NOT have y (synonym removed)"
    assert not hasattr(FitsFile, 'session_id'), "FitsFile should NOT have session_id (synonym removed)"
    print("   ✓ FitsFile synonyms correctly removed")

    # ImagingSession should NOT have old synonym names
    assert hasattr(ImagingSession, 'id'), "ImagingSession should have id"
    assert hasattr(ImagingSession, 'date'), "ImagingSession should have date"

    assert not hasattr(ImagingSession, 'session_id'), "ImagingSession should NOT have session_id (synonym removed)"
    assert not hasattr(ImagingSession, 'session_date'), "ImagingSession should NOT have session_date (synonym removed)"
    print("   ✓ ImagingSession synonyms correctly removed")

    # Test 4: Create in-memory database and test new names work
    print("\n4. Testing with in-memory database...")

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        db_manager = DatabaseManager(f'sqlite:///{db_path}')
        db_manager.create_tables()
        print("   ✓ Database tables created successfully")

        # Test creating an ImagingSession
        session = db_manager.get_session()

        # Create using ONLY new attribute names
        imaging_session = ImagingSession(
            id='20250101_TEST',
            date='2025-01-01',
            telescope='Test Scope',
            camera='Test Camera'
        )
        session.add(imaging_session)
        session.commit()
        print("   ✓ Created ImagingSession using new attribute names")

        # Query it back and test ONLY new attribute access
        result = session.query(ImagingSession).filter(ImagingSession.id == '20250101_TEST').first()
        assert result is not None
        assert result.id == '20250101_TEST'
        assert result.date == '2025-01-01'
        print("   ✓ New attribute names work")

        # Test that old attribute names DON'T work
        try:
            _ = result.session_id
            print("   ✗ FAIL: session_id synonym should not exist")
            sys.exit(1)
        except AttributeError:
            print("   ✓ Old attribute 'session_id' correctly raises AttributeError")

        try:
            _ = result.session_date
            print("   ✗ FAIL: session_date synonym should not exist")
            sys.exit(1)
        except AttributeError:
            print("   ✓ Old attribute 'session_date' correctly raises AttributeError")

        # Test that querying with old names DOESN'T work
        try:
            result2 = session.query(ImagingSession).filter(
                ImagingSession.session_id == '20250101_TEST'
            ).first()
            print("   ✗ FAIL: Querying with session_id should not work")
            sys.exit(1)
        except AttributeError:
            print("   ✓ Querying with old attribute names correctly fails")

        # Create FitsFile and test new names
        fits_file = FitsFile(
            file='test.fits',
            folder='/test',
            imaging_session_id='20250101_TEST',
            width_pixels=1920,
            height_pixels=1080
        )
        session.add(fits_file)
        session.commit()
        print("   ✓ Created FitsFile using new attribute names")

        # Verify new names work
        fits_result = session.query(FitsFile).first()
        assert fits_result.imaging_session_id == '20250101_TEST'
        assert fits_result.width_pixels == 1920
        assert fits_result.height_pixels == 1080
        print("   ✓ FitsFile new attribute names work")

        # Test old names DON'T work
        try:
            _ = fits_result.session_id
            print("   ✗ FAIL: FitsFile.session_id synonym should not exist")
            sys.exit(1)
        except AttributeError:
            print("   ✓ FitsFile.session_id correctly raises AttributeError")

        try:
            _ = fits_result.x
            print("   ✗ FAIL: FitsFile.x synonym should not exist")
            sys.exit(1)
        except AttributeError:
            print("   ✓ FitsFile.x correctly raises AttributeError")

        session.close()

    finally:
        # Cleanup
        Path(db_path).unlink(missing_ok=True)

    # Test 5: Verify consolidated ProcessingSession has all fields
    print("\n5. Testing consolidated ProcessingSession...")
    expected_fields = [
        'id', 'name', 'folder_path', 'objects', 'notes', 'status',
        'primary_target', 'target_type', 'image_type',
        'ra', 'dec', 'total_integration_seconds',
        'date_range_start', 'date_range_end'
    ]
    for field in expected_fields:
        assert hasattr(ProcessingSession, field), f"ProcessingSession should have {field}"
    print("   ✓ ProcessingSession has all consolidated fields")

    # Test 6: Verify ProcessedFile
    print("\n6. Testing ProcessedFile...")
    assert hasattr(ProcessedFile, 'id'), "ProcessedFile should have id"
    assert hasattr(ProcessedFile, 'file_path'), "ProcessedFile should have file_path"
    assert hasattr(ProcessedFile, 'processing_session_id'), "ProcessedFile should have processing_session_id"
    print("   ✓ ProcessedFile available in models.py")

    # Test 7: Verify SchemaVersion table exists
    print("\n7. Testing SchemaVersion table...")
    assert hasattr(SchemaVersion, 'version'), "SchemaVersion should have version"
    assert hasattr(SchemaVersion, 'applied_at'), "SchemaVersion should have applied_at"
    assert hasattr(SchemaVersion, 'description'), "SchemaVersion should have description"
    print("   ✓ SchemaVersion table ready")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED! ✓")
    print("=" * 70)
    print("\nPhase 4 final cleanup is working correctly:")
    print("  • Old synonym attributes are removed")
    print("  • Old Session alias is removed")
    print("  • Only new attribute names work")
    print("  • Database operations use new names only")
    print("  • All models consolidated in models.py")
    print("\nPhase 4 complete! Breaking changes in effect.")

    sys.exit(0)

except Exception as e:
    print(f"\n✗ TEST FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
