"""
FastAPI application initialization for FITS Cataloger.
"""

import logging
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


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup with enhanced error checking."""
    global config, db_manager, db_service, cameras, telescopes, filter_mappings, processing_manager
    
    try:
        logger.info("🚀 Starting FITS Cataloger Web Interface...")
        
        # Load configuration
        config, cameras, telescopes, filter_mappings = load_config()
        logger.info(f"✅ Configuration loaded: {len(cameras)} cameras, {len(telescopes)} telescopes")
        
        # Initialize database
        db_manager = DatabaseManager(config.database.connection_string)
        db_service = DatabaseService(db_manager)
        logger.info("✅ Database service initialized")
        
        # Test database connection
        session = db_manager.get_session()
        from models import FitsFile
        from sqlalchemy import func
        test_count = session.query(func.count(FitsFile.id)).scalar()
        session.close()
        logger.info(f"✅ Database connection verified: {test_count} files in database")
        
        # Initialize processing session manager
        processing_manager = ProcessingSessionManager(config, db_service)
        logger.info("✅ Processing session manager initialized")
        
        # Verify critical modules can be imported
        from validation import FitsValidator
        from file_organizer import FileOrganizer
        from fits_processor import OptimizedFitsProcessor
        logger.info("✅ All critical modules imported successfully")
        
        # Test creating instances
        test_validator = FitsValidator(db_service)
        test_organizer = FileOrganizer(config, db_service)
        test_processor = OptimizedFitsProcessor(config, cameras, telescopes, filter_mappings, db_service)
        logger.info("✅ All service instances created successfully")
        
        # Create directories for static files if they don't exist
        Path("static").mkdir(exist_ok=True)
        
        logger.info("🎉 Web interface startup completed successfully!")
        
    except Exception as e:
        logger.error(f"💥 CRITICAL: Web interface startup failed: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global db_manager
    if db_manager:
        db_manager.close()
        logger.info("Database connection closed")


# Import and register route modules
from web.routes import dashboard, files, stats, imaging_sessions, processing_sessions, operations

app.include_router(dashboard.router)
app.include_router(files.router)
app.include_router(stats.router)
app.include_router(imaging_sessions.router)
app.include_router(processing_sessions.router)
app.include_router(operations.router)