"""
FastAPI application initialization for FITS Cataloger.
"""

import logging
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from config import load_config
from models import DatabaseManager, DatabaseService
from processing_session_manager import ProcessingSessionManager

# Setup logging
logging.basicConfig(level=logging.INFO)
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

# Initialize FastAPI
app = FastAPI(
    title="FITS Cataloger",
    description="Astrophotography Image Management System",
    version="1.0.0"
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
        logger.info(f"Starting sqlite_web on port {port}...")
        sqlite_web_process = subprocess.Popen(
            [sys.executable, "-m", "sqlite_web", db_path, 
             "--host", "0.0.0.0",
             "--port", str(port), 
             "--no-browser"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        logger.info(f"✓ sqlite_web started - Database browser at http://0.0.0.0:{port}")
    except Exception as e:
        logger.warning(f"Could not start sqlite_web: {e}")
        logger.warning("Install with: pip install sqlite-web")


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup with enhanced error checking."""
    global config, db_manager, db_service, cameras, telescopes, filter_mappings, processing_manager
    
    try:
        logger.info("=" * 60)
        logger.info("FITS Cataloger Web Interface Starting")
        logger.info("=" * 60)
        
        # Load configuration
        logger.info("Loading configuration...")
        config, cameras, telescopes, filter_mappings = load_config()
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
        
        # Initialize processing session manager (needs config AND db_service)
        logger.info("Initializing processing session manager...")
        processing_manager = ProcessingSessionManager(config, db_service)
        logger.info("✓ Processing session manager initialized")
        
        # Start sqlite_web for database management
        db_path = Path(config.paths.database_path)
        if db_path.exists():
            start_sqlite_web(str(db_path), port=8081)
        
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
    global db_manager, sqlite_web_process
    
    logger.info("Shutting down web interface...")
    
    # Stop sqlite_web
    if sqlite_web_process:
        try:
            sqlite_web_process.terminate()
            sqlite_web_process.wait(timeout=5)
            logger.info("✓ Database browser stopped")
        except Exception as e:
            logger.warning(f"Error stopping sqlite_web: {e}")
    
    if db_manager:
        db_manager.close()
        logger.info("✓ Database connection closed")
    
    logger.info("Shutdown complete")


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
    database
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

logger.info("✓ All routes registered")