"""
Standalone FastAPI web application for S3 backup management.
Runs on port 8083, designed to be embedded in main app via iframe.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from config import load_config
from models import DatabaseManager, DatabaseService, Session as SessionModel
from s3_backup.manager import S3BackupManager, S3BackupConfig
from s3_backup.models import Base as BackupBase, S3BackupArchive

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize app
app = FastAPI(title="S3 Backup Manager", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global services
backup_manager: Optional[S3BackupManager] = None
db_manager: Optional[DatabaseManager] = None
db_service: Optional[DatabaseService] = None


@app.post("/api/toggle-enabled")
async def toggle_enabled():
    """Toggle S3 backup enabled status and update config."""
    import json
    
    # Toggle in s3_config.json
    config_path = Path('s3_config.json')
    config = json.loads(config_path.read_text())
    config['enabled'] = not config.get('enabled', False)
    config_path.write_text(json.dumps(config, indent=2))
    
    return {"enabled": config['enabled']}
    

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global backup_manager, db_manager, db_service
    
    try:
        config, cameras, telescopes, filter_mappings = load_config()
        db_manager = DatabaseManager(config.database.connection_string)
        db_service = DatabaseService(db_manager)
        
        BackupBase.metadata.create_all(bind=db_manager.engine)
        
        s3_config = S3BackupConfig('s3_config.json')
        
        if not s3_config.enabled:
            logger.warning("S3 backup is disabled in s3_config.json")
        
        base_dir = Path(config.paths.image_dir).parent if hasattr(config.paths, 'image_dir') else None
        backup_manager = S3BackupManager(db_service, s3_config, base_dir)
        
        logger.info("S3 Backup web app initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize S3 backup web app: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    if db_manager:
        db_manager.close()


# Request/Response Models
class UploadRequest(BaseModel):
    session_ids: Optional[list[str]] = None
    year: Optional[int] = None
    limit: Optional[int] = None


class BackupStats(BaseModel):
    total_sessions: int
    backed_up_sessions: int
    remaining_sessions: int
    total_files: int
    total_original_size: int
    total_compressed_size: int
    raw_images: dict
    session_notes: dict
    processed_output: dict


# API Endpoints
@app.get("/api/status")
async def get_status():
    """Get overall backup status and statistics."""
    if not backup_manager:
        raise HTTPException(status_code=503, detail="Backup manager not initialized")
    
    session_db = db_service.db_manager.get_session()
    
    try:
        total_sessions = session_db.query(SessionModel).count()
        
        archives = session_db.query(S3BackupArchive).all()
        backed_up = len(archives)
        
        total_files = sum(a.file_count or 0 for a in archives)
        total_original = sum(a.original_size_bytes or 0 for a in archives)
        total_compressed = sum(a.compressed_size_bytes or 0 for a in archives)
        
        # Storage class breakdown
        storage_classes = {}
        for archive in archives:
            storage_class = archive.current_storage_class or 'STANDARD'
            storage_classes[storage_class] = storage_classes.get(storage_class, 0) + 1
        
        return {
            "total_sessions": total_sessions,
            "backed_up": backed_up,
            "remaining": total_sessions - backed_up,
            "progress_percentage": (backed_up / total_sessions * 100) if total_sessions > 0 else 0,
            "total_files": total_files,
            "total_original_size": total_original,
            "total_compressed_size": total_compressed,
            "space_saved": total_original - total_compressed,
            "avg_compression": (total_compressed / total_original) if total_original > 0 else 0,
            "storage_classes": storage_classes,
            "bucket": backup_manager.s3_config.bucket,
            "region": backup_manager.s3_config.region,
            "enabled": backup_manager.s3_config.enabled
        }
        
    finally:
        session_db.close()


@app.get("/api/temp-info")
async def get_temp_info():
    """Get temp directory information."""
    if not backup_manager:
        raise HTTPException(status_code=503, detail="Backup manager not initialized")
    
    import shutil
    
    temp_dir = backup_manager.temp_dir
    
    if not temp_dir.exists():
        return {
            "exists": False,
            "path": str(temp_dir),
            "total": 0,
            "used": 0,
            "free": 0,
            "usage_percent": 0,
            "largest_session_id": None,
            "largest_session_size": 0,
            "required_with_buffer": 0,
            "has_space": True,
            "orphaned_archives": 0,
            "orphaned_size": 0
        }
    
    try:
        stat = shutil.disk_usage(temp_dir)
    except Exception as e:
        logger.error(f"Error getting disk usage: {e}")
        stat = type('obj', (object,), {'total': 0, 'used': 0, 'free': 0})()
    
    # Get largest session with error handling
    try:
        largest_session_id, largest_size = backup_manager.get_largest_session_size()
    except Exception as e:
        logger.error(f"Error getting largest session: {e}")
        largest_session_id, largest_size = None, 0
    
    # Check for orphaned archives
    try:
        archives = list(temp_dir.glob("*.tar*"))
        archive_size = sum(f.stat().st_size for f in archives)
    except Exception as e:
        logger.error(f"Error checking orphaned archives: {e}")
        archives = []
        archive_size = 0
    
    return {
        "exists": True,
        "path": str(temp_dir),
        "total": stat.total,
        "used": stat.used,
        "free": stat.free,
        "usage_percent": (stat.used / stat.total * 100) if stat.total > 0 else 0,
        "largest_session_id": largest_session_id,
        "largest_session_size": largest_size,
        "required_with_buffer": int(largest_size * 1.1) if largest_size else 0,
        "has_space": stat.free >= int(largest_size * 1.1) if largest_size else True,
        "orphaned_archives": len(archives),
        "orphaned_size": archive_size
    }


@app.get("/api/sessions")
async def get_sessions(
    not_backed_up: bool = False,
    year: Optional[int] = None,
    limit: int = 50
):
    """Get list of sessions with backup status."""
    if not backup_manager:
        raise HTTPException(status_code=503, detail="Backup manager not initialized")
    
    session_db = db_service.db_manager.get_session()
    
    try:
        query = session_db.query(SessionModel)
        
        if year:
            query = query.filter(SessionModel.session_date.like(f"{year}%"))
        
        query = query.order_by(SessionModel.session_date.desc()).limit(limit)
        sessions = query.all()
        
        result = []
        for session_model in sessions:
            archive = session_db.query(S3BackupArchive).filter(
                S3BackupArchive.session_id == session_model.session_id
            ).first()
            
            backed_up = archive is not None
            
            if not_backed_up and backed_up:
                continue
            
            result.append({
                "session_id": session_model.session_id,
                "session_date": session_model.session_date,
                "camera": session_model.camera,
                "telescope": session_model.telescope,
                "backed_up": backed_up,
                "archive_size": archive.compressed_size_bytes if archive else None,
                "file_count": archive.file_count if archive else None,
                "uploaded_at": archive.uploaded_at.isoformat() if archive and archive.uploaded_at else None
            })
        
        return result
        
    finally:
        session_db.close()


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main backup interface."""
    html_file = Path(__file__).parent / "templates" / "backup.html"
    
    if not html_file.exists():
        return HTMLResponse("""
        <html>
            <body>
                <h1>S3 Backup Manager</h1>
                <p>Template file not found. Creating basic interface...</p>
            </body>
        </html>
        """)
    
    return HTMLResponse(html_file.read_text())


def format_bytes(size: int) -> str:
    """Format bytes to human readable."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8083)