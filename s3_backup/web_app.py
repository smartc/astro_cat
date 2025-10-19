"""
Standalone FastAPI web application for S3 backup management.
Runs on port 8083, designed to be embedded in main app via iframe.
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from config import load_config
from models import DatabaseManager, DatabaseService, Session as SessionModel
from s3_backup.manager import S3BackupManager, S3BackupConfig
from s3_backup.models import Base as BackupBase, S3BackupArchive, S3BackupSessionNote, S3BackupProcessingSession, S3BackupProcessedFileRecord, S3BackupProcessingSessionSummary
from processed_catalog.models import ProcessedFile

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


# Global cache
storage_cache = {
    "data": None,
    "last_updated": None
}
CACHE_FILE = Path("storage_categories_cache.json")

def load_cache():
    """Load cache from disk on startup."""
    global storage_cache
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, 'r') as f:
                storage_cache = json.load(f)
                storage_cache["last_updated"] = datetime.fromisoformat(storage_cache["last_updated"])
    except Exception as e:
        logger.error(f"Error loading cache: {e}")

def save_cache():
    """Save cache to disk."""
    try:
        cache_data = {
            "data": storage_cache["data"],
            "last_updated": storage_cache["last_updated"].isoformat() if storage_cache["last_updated"] else None
        }
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache_data, f)
    except Exception as e:
        logger.error(f"Error saving cache: {e}")

async def update_storage_cache():
    """Background task to update cache daily."""
    while True:
        try:
            # Check if update needed
            if storage_cache["last_updated"]:
                next_update = storage_cache["last_updated"] + timedelta(days=1)
                if datetime.now() < next_update:
                    # Sleep until next update time
                    sleep_seconds = (next_update - datetime.now()).total_seconds()
                    await asyncio.sleep(sleep_seconds)
                    continue
            
            # Update cache
            logger.info("Updating storage categories cache...")
            session_db = db_service.db_manager.get_session()
            try:
                result = await _get_storage_categories_internal(session_db)
                storage_cache["data"] = result
                storage_cache["last_updated"] = datetime.now()
                save_cache()
                logger.info("Storage cache updated successfully")
            finally:
                session_db.close()
            
            # Sleep for 24 hours
            await asyncio.sleep(86400)
            
        except Exception as e:
            logger.error(f"Error in cache update task: {e}")
            await asyncio.sleep(3600)  # Retry in 1 hour on error


async def _get_storage_categories_internal(session_db):
    """Internal function with all the logic from get_storage_categories."""
    from sqlalchemy import func
    from s3_backup.models import S3BackupSessionNote, S3BackupProcessingSession, S3BackupProcessedFileRecord
    from processed_catalog.models import ProcessedFile

    if not db_service:
        raise HTTPException(status_code=503, detail="Database not initialized")
        
    try:
        from models import FitsFile
        from s3_backup.models import S3BackupSessionNote, S3BackupProcessingSession
        from pathlib import Path
        
        categories = []
        using_fallback_pricing = False
        
        def get_s3_stats(prefix):
            file_count = 0
            total_size = 0
            paginator = backup_manager.s3_client.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(Bucket=backup_manager.s3_config.bucket, Prefix=prefix):
                if 'Contents' not in page:
                    continue
                for obj in page['Contents']:
                    if not obj['Key'].endswith('/'):
                        file_count += 1
                        total_size += obj['Size']
            return file_count, total_size
        
        # Category 1: Imaging Sessions
        all_fits = session_db.query(FitsFile).all()
        backed_up_sessions = {a.session_id for a in session_db.query(S3BackupArchive).all()}
        
        total_local_size = 0
        backed_up_size = 0
        local_not_backed_count = 0
        
        for f in all_fits:
            file_path = Path(f.folder) / f.file
            if file_path.exists():
                size = file_path.stat().st_size
                total_local_size += size
                if f.session_id in backed_up_sessions:
                    backed_up_size += size
                else:
                    local_not_backed_count += 1
        
        raw_path = backup_manager.s3_config.config['s3_paths']['raw_archives']
        s3_files_raw, s3_size_raw = get_s3_stats(raw_path)
        
        annual_cost, is_fallback = calculate_s3_cost(s3_size_raw, "DEEP_ARCHIVE")
        using_fallback_pricing = using_fallback_pricing or is_fallback
        
        categories.append({
            "name": "Imaging Sessions",
            "local_files": len(all_fits),
            "s3_files": s3_files_raw,
            "local_not_in_s3": local_not_backed_count,
            "local_storage": total_local_size,
            "s3_storage": s3_size_raw,
            "backed_up_size": backed_up_size,
            "storage_class": "Deep Archive",
            "backup_pct": (backed_up_size / total_local_size * 100) if total_local_size > 0 else 0,
            "annual_cost": annual_cost
        })
        
        # Category 2: Imaging Session Notes
        from config import load_config
        main_config, _, _, _ = load_config()
        
        imaging_notes_dir = Path(main_config.paths.notes_dir) / "Imaging_Sessions"
        local_imaging_files = {}
        if imaging_notes_dir.exists():
            for md in imaging_notes_dir.rglob("*.md"):
                session_id = md.stem
                local_imaging_files[session_id] = md.stat().st_size
        
        s3_imaging_notes = {n.session_id for n in session_db.query(S3BackupSessionNote).all()}
        
        imaging_backed_up_size = sum(size for sid, size in local_imaging_files.items() if sid in s3_imaging_notes)
        imaging_not_in_s3 = len([sid for sid in local_imaging_files.keys() if sid not in s3_imaging_notes])
        
        notes_path = backup_manager.s3_config.config['s3_paths']['session_notes']
        s3_notes_count, s3_notes_size = get_s3_stats(notes_path)
        
        annual_cost, is_fallback = calculate_s3_cost(s3_notes_size, "STANDARD_IA")
        using_fallback_pricing = using_fallback_pricing or is_fallback
        
        categories.append({
            "name": "Imaging Session Notes",
            "local_files": len(local_imaging_files),
            "s3_files": s3_notes_count,
            "local_not_in_s3": imaging_not_in_s3,
            "local_storage": sum(local_imaging_files.values()),
            "s3_storage": s3_notes_size,
            "backed_up_size": imaging_backed_up_size,
            "storage_class": "Standard",
            "backup_pct": (imaging_backed_up_size / sum(local_imaging_files.values()) * 100) if local_imaging_files else 0,
            "annual_cost": annual_cost
        })
        
        # Category 3: Processing Session Notes
        proc_notes_dir = Path(main_config.paths.notes_dir) / "Processing_Sessions"
        local_proc_files = {}
        if proc_notes_dir.exists():
            for md in proc_notes_dir.rglob("*.md"):
                session_id = md.stem
                local_proc_files[session_id] = md.stat().st_size
        
        s3_proc_notes = {n.processing_session_id for n in session_db.query(S3BackupProcessingSession).all()}
        
        proc_backed_up_size = sum(size for sid, size in local_proc_files.items() if sid in s3_proc_notes)
        proc_not_in_s3 = len([sid for sid in local_proc_files.keys() if sid not in s3_proc_notes])
        
        proc_path = backup_manager.s3_config.config['s3_paths']['processing_notes']
        s3_proc_count, s3_proc_size = get_s3_stats(proc_path)
        
        annual_cost, is_fallback = calculate_s3_cost(s3_proc_size, "STANDARD_IA")
        using_fallback_pricing = using_fallback_pricing or is_fallback
        
        categories.append({
            "name": "Processing Session Notes",
            "local_files": len(local_proc_files),
            "s3_files": s3_proc_count,
            "local_not_in_s3": proc_not_in_s3,
            "local_storage": sum(local_proc_files.values()),
            "s3_storage": s3_proc_size,
            "backed_up_size": proc_backed_up_size,
            "storage_class": "Standard",
            "backup_pct": (proc_backed_up_size / sum(local_proc_files.values()) * 100) if local_proc_files else 0,
            "annual_cost": annual_cost
        })
        
        # Get backed up sessions (needed for both categories 4 & 5)
        backed_up_processed = session_db.query(S3BackupProcessedFileRecord).all()
        backed_up_ids = {b.processing_session_id for b in backed_up_processed}

        # Set up S3 paginator for both categories
        processed_base = "backups/processed/"
        paginator = backup_manager.s3_client.get_paginator('list_objects_v2')


        # Category 4: Processing Sessions (Intermediates)
        intermediate_file_count = session_db.query(ProcessedFile).filter(
            ProcessedFile.subfolder == 'intermediate',
            ProcessedFile.file_type.in_(['jpg', 'jpeg', 'xisf', 'xosm', 'pxiproject'])
        ).count()

        sessions_with_intermediate_query = session_db.query(ProcessedFile.processing_session_id).filter(
            ProcessedFile.subfolder == 'intermediate',
            ProcessedFile.file_type.in_(['jpg', 'jpeg', 'xisf', 'xosm', 'pxiproject'])
        ).distinct()
        sessions_with_intermediate = {row[0] for row in sessions_with_intermediate_query.all()}

        total_intermediate_size = session_db.query(func.sum(ProcessedFile.file_size)).filter(
            ProcessedFile.subfolder == 'intermediate',
            ProcessedFile.file_type.in_(['jpg', 'jpeg', 'xisf', 'xosm', 'pxiproject'])
        ).scalar() or 0

        backed_up_size_intermediate = session_db.query(func.sum(ProcessedFile.file_size)).join(
            S3BackupProcessedFileRecord,
            ProcessedFile.id == S3BackupProcessedFileRecord.processed_file_id
        ).filter(
            ProcessedFile.subfolder == 'intermediate'
        ).scalar() or 0

        s3_intermediate_file_count = session_db.query(S3BackupProcessedFileRecord).join(
            ProcessedFile,
            ProcessedFile.id == S3BackupProcessedFileRecord.processed_file_id
        ).filter(
            ProcessedFile.subfolder == 'intermediate'
        ).count()

        intermediate_not_backed_up = len([s for s in sessions_with_intermediate if s not in backed_up_ids])

        # Get S3 size by checking for /intermediate/ in paths
        s3_intermediate_size = 0
        s3_intermediate_count = 0
        for page in paginator.paginate(Bucket=backup_manager.s3_config.bucket, Prefix=processed_base):
            if 'Contents' not in page:
                continue
            for obj in page['Contents']:
                if '/intermediate/' in obj['Key'] and not obj['Key'].endswith('/'):
                    s3_intermediate_count += 1
                    s3_intermediate_size += obj['Size']

        annual_cost_intermediate, is_fallback = calculate_s3_cost(s3_intermediate_size, "FLEXIBLE")
        using_fallback_pricing = using_fallback_pricing or is_fallback

        categories.append({
            "name": "Processing Sessions - Intermediate",
            "local_files": intermediate_file_count,
            "s3_files": s3_intermediate_file_count,
            "local_not_in_s3": intermediate_not_backed_up,
            "local_storage": total_intermediate_size,
            "s3_storage": s3_intermediate_size,
            "backed_up_size": backed_up_size_intermediate,
            "storage_class": "Flexible",
            "backup_pct": (backed_up_size_intermediate / total_intermediate_size * 100) if total_intermediate_size > 0 else 0,
            "annual_cost": annual_cost_intermediate
        })


        # Category 5: Processing Sessions (Finals)
        local_file_count = session_db.query(ProcessedFile).filter(
            ProcessedFile.subfolder == 'final',
            ProcessedFile.file_type.in_(['jpg', 'jpeg', 'xisf', 'xosm', 'pxiproject'])
        ).count()

        sessions_with_finals_query = session_db.query(ProcessedFile.processing_session_id).filter(
            ProcessedFile.subfolder == 'final',
            ProcessedFile.file_type.in_(['jpg', 'jpeg', 'xisf', 'xosm', 'pxiproject'])
        ).distinct()
        sessions_with_finals = {row[0] for row in sessions_with_finals_query.all()}

        total_final_size = session_db.query(func.sum(ProcessedFile.file_size)).filter(
            ProcessedFile.subfolder == 'final',
            ProcessedFile.file_type.in_(['jpg', 'jpeg', 'xisf', 'xosm', 'pxiproject'])
        ).scalar() or 0

        backed_up_size_final = session_db.query(func.sum(ProcessedFile.file_size)).join(
            S3BackupProcessedFileRecord,
            ProcessedFile.id == S3BackupProcessedFileRecord.processed_file_id
        ).filter(
            ProcessedFile.subfolder == 'final'
        ).scalar() or 0

        s3_final_file_count = session_db.query(S3BackupProcessedFileRecord).join(
            ProcessedFile,
            ProcessedFile.id == S3BackupProcessedFileRecord.processed_file_id
        ).filter(
            ProcessedFile.subfolder == 'final'
        ).count()

        not_backed_up_count = len(sessions_with_finals - backed_up_ids)

        # Get S3 size by checking for /final/ in paths
        s3_final_size = 0
        s3_final_count = 0
        for page in paginator.paginate(Bucket=backup_manager.s3_config.bucket, Prefix=processed_base):
            if 'Contents' not in page:
                continue
            for obj in page['Contents']:
                if '/final/' in obj['Key'] and not obj['Key'].endswith('/'):
                    s3_final_count += 1
                    s3_final_size += obj['Size']

        annual_cost_final, is_fallback = calculate_s3_cost(s3_final_size, "FLEXIBLE")
        using_fallback_pricing = using_fallback_pricing or is_fallback

        categories.append({
            "name": "Processing Sessions - Final",
            "local_files": local_file_count,
            "s3_files": s3_final_file_count,
            "local_not_in_s3": not_backed_up_count,
            "local_storage": total_final_size,
            "s3_storage": s3_final_size,
            "backed_up_size": backed_up_size_final,
            "storage_class": "Flexible",
            "backup_pct": (backed_up_size_final / total_final_size * 100) if total_final_size > 0 else 0,
            "annual_cost": annual_cost_final
        })

        return {
            "categories": categories,
            "using_fallback_pricing": using_fallback_pricing
        }
        
    except Exception as e:
        logger.error(f"Error getting storage categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    pass

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
        
        # load S3 data cache
        load_cache()
        
        # Start background cache update task
        asyncio.create_task(update_storage_cache())

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


@app.get("/api/status")
async def get_status():
    """Get overall backup status and statistics."""
    if not backup_manager:
        raise HTTPException(status_code=503, detail="Backup manager not initialized")
    
    session_db = db_service.db_manager.get_session()
    
    try:
        total_sessions = session_db.query(SessionModel).count()
        
        # Raw FITS archives
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
        
        # Session notes stats
        session_notes = session_db.query(S3BackupSessionNote).all()
        notes_count = len(session_notes)
        notes_size = sum(n.file_size_bytes or 0 for n in session_notes)
        
        # Processed files stats
        processed_backups = session_db.query(S3BackupProcessedFileRecord).all()
        processed_count = len(processed_backups)
        processed_files = len(processed_backups)  # Count individual file records
        processed_size = sum(p.file_size or 0 for p in processed_backups)        
        
        # Count total processing sessions with final files
        total_with_finals = session_db.query(ProcessedFile.processing_session_id).filter(
            ProcessedFile.subfolder == 'final',
            ProcessedFile.file_type.in_(['jpg', 'jpeg', 'xisf'])
        ).distinct().count()
        
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
            "enabled": backup_manager.s3_config.enabled,
            "raw_images": {
                "count": backed_up,
                "files": total_files,
                "size": total_compressed
            },
            "session_notes": {
                "count": notes_count,
                "size": notes_size
            },
            "processed_output": {
                "backed_up": processed_count,
                "total_with_finals": total_with_finals,
                "remaining": total_with_finals - processed_count,
                "files": processed_files,
                "size": processed_size
            }
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


@app.get("/api/storage-categories")
async def get_storage_categories(force_refresh: bool = False):
    """Get storage summary by category from cache or refresh."""
    # Force refresh if requested or cache empty
    if force_refresh or storage_cache["data"] is None:
        session_db = db_service.db_manager.get_session()
        try:
            result = await _get_storage_categories_internal(session_db)
            storage_cache["data"] = result
            storage_cache["last_updated"] = datetime.now()
            save_cache()
        finally:
            session_db.close()
    
    return {
        **storage_cache["data"],
        "last_updated": storage_cache["last_updated"].isoformat() if storage_cache["last_updated"] else None
    }
                       

def calculate_s3_cost(bytes_size, storage_class):
    """Calculate estimated annual S3 storage cost using config rates.
    
    Returns:
        Tuple of (annual_cost, using_fallback)
    """
    gb = bytes_size / (1024**3)
    
    try:
        config = backup_manager.s3_config.config
        rates = config.get('cost_tracking', {}).get('storage_cost_per_gb_per_month', {})
        
        rate_map = {
            "STANDARD": "STANDARD",
            "STANDARD_IA": "STANDARD_IA", 
            "GLACIER": "GLACIER_FLEXIBLE",
            "DEEP_ARCHIVE": "DEEP_ARCHIVE"
        }
        
        monthly_rate = rates.get(rate_map.get(storage_class, "STANDARD"))
        if monthly_rate is None:
            raise KeyError("Rate not found in config")
        using_fallback = False
    except Exception as e:
        logger.warning(f"Using fallback pricing: {e}")
        monthly_rate = 0.023
        using_fallback = True
    
    monthly_cost = gb * monthly_rate
    return monthly_cost * 12, using_fallback



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8083)