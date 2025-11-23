"""
FastAPI application initialization for FITS Cataloger.
"""

import logging
import os
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware


def get_service_bind_host():
    """Get the bind host for secondary services.

    Uses ASTROCAT_BIND_HOST env var if set, otherwise defaults to '127.0.0.1'.
    Examples:
        127.0.0.1 - localhost only (default, secure for reverse proxy)
        0.0.0.0   - all interfaces (for direct network access)
        192.168.1.100 - specific interface
    """
    return os.environ.get('ASTROCAT_BIND_HOST', '127.0.0.1')

from version import __version__
from config import load_config
from models import DatabaseManager, DatabaseService
from processing_session_manager import ProcessingSessionManager
from webdav_server import start_webdav_server, stop_webdav_server
from web.routes import processed_files

# Setup logging (will be reconfigured after loading config)
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Global configuration and services (initialized on startup)
config = None
db_manager = None
db_service = None
cameras = []
telescopes = []
filter_mappings = {}
processing_manager = None
sqlite_web_process = None
webdav_server = None
s3_backup_process = None

app = FastAPI(
    title="FITS Cataloger",
    description="Astrophotography Image Management System",
    version=__version__
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")


def get_globals():
    """Return a dictionary of global application state."""
    return {
        'config': config,
        'db_manager': db_manager,
        'db_service': db_service,
        'cameras': cameras,
        'telescopes': telescopes,
        'filter_mappings': filter_mappings,
        'processing_manager': processing_manager
    }


def start_sqlite_web(db_path: str, port: int = 8081):
    """Start sqlite_web in a separate process."""
    global sqlite_web_process
    try:
        bind_host = get_service_bind_host()
        logger.info(f"Starting sqlite_web on {bind_host}:{port}...")
        sqlite_web_process = subprocess.Popen(
            [sys.executable, "-m", "sqlite_web", db_path,
             "--host", bind_host,
             "--port", str(port),
             "--no-browser"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        logger.info(f"✓ sqlite_web started - Database browser at http://{bind_host}:{port}")
    except Exception as e:
        logger.warning(f"Could not start sqlite_web: {e}")
        logger.warning("Install with: pip install sqlite-web")


def start_s3_backup_web(port: int = 8083):
    """Start S3 backup web interface."""
    global s3_backup_process
    try:
        bind_host = get_service_bind_host()
        logger.info(f"Starting S3 backup web interface on {bind_host}:{port}...")
        s3_backup_process = subprocess.Popen(
            [sys.executable, "-m", "s3_backup.run_web"],
            stdout=None,  # Changed from subprocess.PIPE
            stderr=None   # Changed from subprocess.PIPE
        )
        logger.info(f"✓ S3 backup interface at http://{bind_host}:{port}")
    except Exception as e:
        logger.warning(f"Could not start S3 backup interface: {e}")
        

def restart_s3_backup_web():
    """Restart S3 backup web interface."""
    global s3_backup_process
    
    # Stop existing
    if s3_backup_process:
        try:
            s3_backup_process.terminate()
            s3_backup_process.wait(timeout=3)
        except:
            pass
    
    # Restart
    start_s3_backup_web(port=8083)


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup with enhanced error checking."""
    global config, db_manager, db_service, cameras, telescopes, filter_mappings, processing_manager, webdav_server
    
    try:
        logger.info("=" * 60)
        logger.info("FITS Cataloger Web Interface Starting")
        logger.info("=" * 60)
        
        # Load configuration
        logger.info("Loading configuration...")
        config, cameras, telescopes, filter_mappings = load_config()

        # Reconfigure logging based on config
        log_level = getattr(logging, config.logging.level.upper(), logging.INFO)
        logging.getLogger().setLevel(log_level)

        logger.info(f"✓ Configuration loaded")
        logger.info(f"  - Cameras: {len(cameras)}")
        logger.info(f"  - Telescopes: {len(telescopes)}")
        logger.info(f"  - Filter mappings: {len(filter_mappings)}")
        
        # Initialize database
        logger.info("Initializing database connection...")
        db_manager = DatabaseManager(config.database.connection_string)
        db_manager.create_tables()
        logger.info(f"✓ Database connected: {config.database.connection_string}")
        
        # Create database service
        db_service = DatabaseService(db_manager)
        logger.info("✓ Database service initialized")

        # Initialize equipment tables in database
        from cli.utils import convert_equipment_for_db
        cameras_dict, telescopes_dict, filter_mappings_dict = convert_equipment_for_db(
            cameras, telescopes, filter_mappings
        )
        db_service.initialize_equipment(cameras_dict, telescopes_dict, filter_mappings_dict)
        logger.info("✓ Equipment tables initialized")
        
        # Initialize processing session manager (needs config AND db_service)
        logger.info("Initializing processing session manager...")
        processing_manager = ProcessingSessionManager(config, db_service)
        logger.info("✓ Processing session manager initialized")

        # Load dashboard cache
        logger.info("Loading dashboard statistics cache...")
        from web import dashboard_cache
        dashboard_cache.load_cache()
        cache_age = dashboard_cache.get_cache_age()
        if cache_age is not None:
            logger.info(f"✓ Dashboard cache loaded (age: {cache_age/3600:.1f} hours)")
        else:
            logger.info("✓ Dashboard cache initialized (empty)")
        
        # Start WebDAV server (add this near the end, before the final success message)
        if config and config.paths.processing_dir:
            try:
                from pathlib import Path
                from webdav_server import start_webdav_server
                
                processing_dir = Path(config.paths.processing_dir)
                webdav_server = start_webdav_server(processing_dir, port=8082)
                if webdav_server:
                    logger.info("✓ WebDAV server ready for file access")
                else:
                    logger.warning("! WebDAV server failed to start - file access unavailable")
            except Exception as e:
                logger.error(f"Failed to start WebDAV server: {e}")
                logger.warning("Continuing without WebDAV file access")


        # Start sqlite_web for database management
        db_path = Path(config.paths.database_path)
        if db_path.exists():
            start_sqlite_web(str(db_path), port=8081)


        # Start S3 backup interface
        start_s3_backup_web(port=8083)

        
        logger.info("=" * 60)
        logger.info("Web interface ready!")
        logger.info("Open your browser to: http://localhost:8000")
        logger.info("=" * 60)

        # Auto-start monitoring if enabled
        from web.routes import monitoring
        await monitoring.auto_start_monitoring()
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}", exc_info=True)
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global db_manager, sqlite_web_process, webdav_server
    
    logger.info("Shutting down web interface...")
    
    # Stop sqlite_web
    if sqlite_web_process:
        try:
            sqlite_web_process.terminate()
            sqlite_web_process.wait(timeout=5)
            logger.info("✓ Database browser stopped")
        except Exception as e:
            logger.warning(f"Error stopping sqlite_web: {e}")

    # Stop S3 backup interface
    if s3_backup_process:
        try:
            s3_backup_process.terminate()
            s3_backup_process.wait(timeout=5)
            logger.info("✓ S3 backup interface stopped")
        except Exception as e:
            logger.warning(f"Error stopping S3 backup interface: {e}")
    
    if db_manager:
        db_manager.close()
        logger.info("✓ Database connection closed")

    # Stop WebDAV server
    if webdav_server:
        from webdav_server import stop_webdav_server
        stop_webdav_server()
    
    logger.info("Shutdown complete")

@app.get("/api/version")
async def get_version():
    return {"version": __version__}


# ============================================================================
# IMPORT AND REGISTER ROUTES
# ============================================================================

# Import all route modules
from web.routes import (
    dashboard,
    files,
    stats,
    operations,
    monitoring,
    imaging_sessions,
    processing_sessions,
    equipment,
    config as config_routes,
    database,
    webdav,
    proxy
)

# Register all routers
app.include_router(dashboard.router)
app.include_router(files.router)
app.include_router(stats.router)
app.include_router(operations.router)
app.include_router(monitoring.router)
app.include_router(imaging_sessions.router)
app.include_router(processing_sessions.router)
app.include_router(equipment.router)
app.include_router(config_routes.router)
app.include_router(database.router)
app.include_router(webdav.router)
app.include_router(processed_files.router)
app.include_router(proxy.router)

logger.info("✓ All routes registered")