"""
FastAPI dependencies for FITS Cataloger.
"""


def get_db_session():
    """Dependency to get database session."""
    # Import at call time to avoid circular imports
    import web.app
    globals_dict = web.app.get_globals()
    db_manager = globals_dict['db_manager']
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


def get_config():
    """Dependency to get configuration."""
    # Import at call time to avoid circular imports
    import web.app
    globals_dict = web.app.get_globals()
    return globals_dict['config']


def get_db_service():
    """Dependency to get database service."""
    # Import at call time to avoid circular imports
    import web.app
    globals_dict = web.app.get_globals()
    return globals_dict['db_service']


def get_processing_manager():
    """Dependency to get processing session manager."""
    # Import at call time to avoid circular imports
    import web.app
    globals_dict = web.app.get_globals()
    return globals_dict['processing_manager']


def get_cameras():
    """Dependency to get camera list."""
    # Import at call time to avoid circular imports
    import web.app
    globals_dict = web.app.get_globals()
    return globals_dict['cameras']


def get_telescopes():
    """Dependency to get telescope list."""
    # Import at call time to avoid circular imports
    import web.app
    globals_dict = web.app.get_globals()
    return globals_dict['telescopes']


def get_filter_mappings():
    """Dependency to get filter mappings."""
    # Import at call time to avoid circular imports
    import web.app
    globals_dict = web.app.get_globals()
    return globals_dict['filter_mappings']