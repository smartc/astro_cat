#!/usr/bin/env python3
"""Basic test script for FITS Cataloger Phase 1."""

import os
import sys
import tempfile
from pathlib import Path

def test_config_loading():
    """Test configuration loading."""
    print("Testing configuration loading...")
    
    try:
        from config import load_config, create_default_config
        
        # Create temp config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_path = f.name
        
        # Create default config
        create_default_config(config_path)
        
        # Load and validate
        config = load_config(config_path)
        
        print(f"✓ Config loaded successfully")
        print(f"  - Found {len(config.cameras)} cameras")
        print(f"  - Found {len(config.telescopes)} telescopes")
        print(f"  - Quarantine dir: {config.paths.quarantine_dir}")
        
        # Cleanup
        os.unlink(config_path)
        
    except Exception as e:
        print(f"✗ Config test failed: {e}")
        return False
    
    return True


def test_database_setup():
    """Test database setup."""
    print("\nTesting database setup...")
    
    try:
        from models import DatabaseManager, DatabaseService
        from config import load_config, create_default_config
        
        # Create temp config
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_path = f.name
        
        create_default_config(config_path)
        config = load_config(config_path)
        
        # Use in-memory SQLite for testing
        config.database.connection_string = "sqlite:///:memory:"
        
        # Test database operations
        db_manager = DatabaseManager(config.database.connection_string)
        db_manager.create_tables()
        
        db_service = DatabaseService(db_manager)
        
        # Test equipment initialization
        db_service.initialize_equipment(
            cameras=[cam.dict() for cam in config.cameras],
            telescopes=[tel.dict() for tel in config.telescopes],
            filter_mappings=config.filter_mappings
        )
        
        # Test queries
        cameras = db_service.get_cameras()
        telescopes = db_service.get_telescopes()
        
        print(f"✓ Database setup successful")
        print(f"  - Created tables")
        print(f"  - Loaded {len(cameras)} cameras")
        print(f"  - Loaded {len(telescopes)} telescopes")
        
        # Cleanup
        db_manager.close()
        os.unlink(config_path)
        
    except Exception as e:
        print(f"✗ Database test failed: {e}")
        return False
    
    return True


def test_fits_processor():
    """Test FITS processor (without actual FITS files)."""
    print("\nTesting FITS processor...")
    
    try:
        from fits_processor import FitsProcessor
        from config import load_config, create_default_config
        
        # Create temp config
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config_path = f.name
        
        create_default_config(config_path)
        config = load_config(config_path)
        
        processor = FitsProcessor(config)
        
        # Test camera identification
        camera = processor._identify_camera(4656, 3520, 1)
        print(f"✓ Camera identification: {camera}")
        
        # Test telescope identification  
        telescope = processor._identify_telescope(952.0)
        print(f"✓ Telescope identification: {telescope}")
        
        # Test filter normalization
        normalized = processor._normalize_filter("Red")
        print(f"✓ Filter normalization: Red -> {normalized}")
        
        # Cleanup
        os.unlink(config_path)
        
    except Exception as e:
        print(f"✗ FITS processor test failed: {e}")
        return False
    
    return True


def run_all_tests():
    """Run all basic tests."""
    print("FITS Cataloger - Basic Tests")
    print("=" * 40)
    
    tests = [
        test_config_loading,
        test_database_setup,
        test_fits_processor,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\nTest Results: {passed}/{total} passed")
    
    if passed == total:
        print("✓ All tests passed! Ready for deployment.")
        return True
    else:
        print("✗ Some tests failed. Please check the errors above.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)