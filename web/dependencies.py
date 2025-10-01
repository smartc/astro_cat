"""
FastAPI dependencies for FITS Cataloger.
"""

import sys


def get_db_session():
    """Dependency to get database session."""
    # Access module via sys.modules to avoid import confusion
    app_module = sys.modules['web.app']
    db_manager = app_module.db_manager
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


def get_config():
    """Dependency to get configuration."""
    app_module = sys.modules['web.app']
    return app_module.config


def get_db_service():
    """Dependency to get database service."""
    app_module = sys.modules['web.app']
    return app_module.db_service


def get_processing_manager():
    """Dependency to get processing session manager."""
    app_module = sys.modules['web.app']
    return app_module.processing_manager


def get_cameras():
    """Dependency to get camera list."""
    app_module = sys.modules['web.app']
    return app_module.cameras


def get_telescopes():
    """Dependency to get telescope list."""
    app_module = sys.modules['web.app']
    return app_module.telescopes


def get_filter_mappings():
    """Dependency to get filter mappings."""
    app_module = sys.modules['web.app']
    return app_module.filter_mappings