#!/usr/bin/env python3
"""
Test script for Phase 2 model consolidation.
Verifies column mappings and backward compatibility.
"""

import sys
import tempfile
from pathlib import Path

print("=" * 70)
print("PHASE 2 MODEL CONSOLIDATION - TEST SCRIPT")
print("=" * 70)

try:
    # Test 1: Import all models
    print("\n1. Testing model imports...")
    from models import (
        ImagingSession,
        Session,
        ProcessingSession,
        ProcessedFile,
        FitsFile,
        Camera,
        Telescope,
        SchemaVersion,
        DatabaseManager
    )
    print("   ✓ All model imports successful")

    # Test 2: Verify Session is an alias
    print("\n2. Testing Session alias...")
    assert Session is ImagingSession, "Session should be alias for ImagingSession"
    print("   ✓ Session correctly aliased to ImagingSession")

    # Test 3: Verify column mappings exist
    print("\n3. Testing column mappings...")

    # FitsFile should have both new and old names
    assert hasattr(FitsFile, 'width_pixels'), "FitsFile should have width_pixels"
    assert hasattr(FitsFile, 'height_pixels'), "FitsFile should have height_pixels"
    assert hasattr(FitsFile, 'imaging_session_id'), "FitsFile should have imaging_session_id"

    # And backward compatible names via synonyms
    assert hasattr(FitsFile, 'x'), "FitsFile should have x (synonym)"
    assert hasattr(FitsFile, 'y'), "FitsFile should have y (synonym)"
    assert hasattr(FitsFile, 'session_id'), "FitsFile should have session_id (synonym)"
    print("   ✓ FitsFile column mappings and synonyms present")

    # ImagingSession should have new names
    assert hasattr(ImagingSession, 'id'), "ImagingSession should have id"
    assert hasattr(ImagingSession, 'date'), "ImagingSession should have date"

    # And backward compatible names via synonyms
    assert hasattr(ImagingSession, 'session_id'), "ImagingSession should have session_id (synonym)"
    assert hasattr(ImagingSession, 'session_date'), "ImagingSession should have session_date (synonym)"
    print("   ✓ ImagingSession column mappings and synonyms present")

    # Test 4: Test processed_catalog compatibility shim
    print("\n4. Testing processed_catalog compatibility shim...")
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        from processed_catalog.models import ProcessingSession as PS2, ProcessedFile as PF2
        # Should get a deprecation warning
        assert len(w) == 1, "Should get exactly one deprecation warning"
        assert issubclass(w[0].category, DeprecationWarning), "Should be DeprecationWarning"
        assert "processed_catalog.models is deprecated" in str(w[0].message)
    print("   ✓ Compatibility shim issues deprecation warning")
    print(f"   ✓ Warning: {w[0].message}")

    # Test 5: Create in-memory database and test actual usage
    print("\n5. Testing with in-memory database...")

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    try:
        db_manager = DatabaseManager(f'sqlite:///{db_path}')
        db_manager.create_tables()
        print("   ✓ Database tables created successfully")

        # Test creating an ImagingSession
        session = db_manager.get_session()

        # Create using new attribute names
        imaging_session = ImagingSession(
            id='20250101_TEST',
            date='2025-01-01',
            telescope='Test Scope',
            camera='Test Camera'
        )
        session.add(imaging_session)
        session.commit()
        print("   ✓ Created ImagingSession using new attribute names")

        # Query it back and test both new and old attribute access
        result = session.query(ImagingSession).filter(ImagingSession.id == '20250101_TEST').first()
        assert result is not None
        assert result.id == '20250101_TEST'
        assert result.date == '2025-01-01'

        # Test old attribute names via synonyms
        assert result.session_id == '20250101_TEST', "Should access via session_id synonym"
        assert result.session_date == '2025-01-01', "Should access via session_date synonym"
        print("   ✓ Both new and old attribute names work")

        # Test querying with old names
        result2 = session.query(ImagingSession).filter(
            ImagingSession.session_id == '20250101_TEST'
        ).first()
        assert result2 is not None, "Should be able to query using session_id synonym"
        print("   ✓ Querying with old attribute names works")

        session.close()

    finally:
        # Cleanup
        Path(db_path).unlink(missing_ok=True)

    # Test 6: Verify consolidated ProcessingSession has all fields
    print("\n6. Testing consolidated ProcessingSession...")
    expected_fields = [
        'id', 'name', 'folder_path', 'objects', 'notes', 'status',
        'primary_target', 'target_type', 'image_type',
        'ra', 'dec', 'total_integration_seconds',
        'date_range_start', 'date_range_end'
    ]
    for field in expected_fields:
        assert hasattr(ProcessingSession, field), f"ProcessingSession should have {field}"
    print("   ✓ ProcessingSession has all consolidated fields")

    # Test 7: Verify ProcessedFile moved to models.py
    print("\n7. Testing ProcessedFile consolidation...")
    assert hasattr(ProcessedFile, 'id'), "ProcessedFile should have id"
    assert hasattr(ProcessedFile, 'file_path'), "ProcessedFile should have file_path"
    assert hasattr(ProcessedFile, 'processing_session_id'), "ProcessedFile should have processing_session_id"
    print("   ✓ ProcessedFile successfully consolidated in models.py")

    # Test 8: Verify SchemaVersion table exists
    print("\n8. Testing SchemaVersion table...")
    assert hasattr(SchemaVersion, 'version'), "SchemaVersion should have version"
    assert hasattr(SchemaVersion, 'applied_at'), "SchemaVersion should have applied_at"
    assert hasattr(SchemaVersion, 'description'), "SchemaVersion should have description"
    print("   ✓ SchemaVersion table ready for migration tracking")

    print("\n" + "=" * 70)
    print("ALL TESTS PASSED! ✓")
    print("=" * 70)
    print("\nPhase 2 model consolidation is working correctly:")
    print("  • Column mappings work (Python names → DB columns)")
    print("  • Backward compatibility via synonyms")
    print("  • Compatibility shim issues warnings")
    print("  • Database operations successful")
    print("  • All models consolidated in models.py")
    print("\nReady for deployment!")

    sys.exit(0)

except Exception as e:
    print(f"\n✗ TEST FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
