"""
Updated web/routes/stats.py - Complete corrected version with physical file counts
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, distinct
from datetime import datetime, timedelta
from pathlib import Path
import logging

from models import FitsFile, Session as ImagingSession, ProcessingSession, ProcessingSessionFile
from web.dependencies import get_db_service, get_config

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


def count_physical_files_in_folder(folder_path: Path, extensions: list = None) -> int:
    """
    Count physical FITS files in a folder.
    
    Args:
        folder_path: Path to folder to scan
        extensions: List of file extensions to count (default: ['.fits', '.fit', '.fts'])
    
    Returns:
        Number of files found
    """
    if extensions is None:
        extensions = ['.fits', '.fit', '.fts']
    
    if not folder_path.exists():
        return 0
    
    count = 0
    try:
        for ext in extensions:
            # Use glob to find files with this extension (case-insensitive)
            count += len(list(folder_path.glob(f"*{ext}")))
            count += len(list(folder_path.glob(f"*{ext.upper()}")))
    except Exception as e:
        logger.error(f"Error counting files in {folder_path}: {e}")
        return 0
    
    return count


@router.get("/stats")
async def get_stats(db_service = Depends(get_db_service), config = Depends(get_config)):
    """Get comprehensive database and file statistics."""
    try:
        session = db_service.db_manager.get_session()
        
        # Existing database queries
        total_files = session.query(FitsFile).count()
        recent_files = session.query(FitsFile).filter(
            FitsFile.created_at >= (datetime.now() - timedelta(days=7))
        ).count()
        
        # Validation score groups (only for files still in quarantine)
        auto_migrate = session.query(FitsFile).filter(
            FitsFile.validation_score >= 95,
            FitsFile.folder.like(f"%{config.paths.quarantine_dir}%")
        ).count()
        
        needs_review = session.query(FitsFile).filter(
            FitsFile.validation_score.between(80, 95)
        ).count()
        
        manual_only = session.query(FitsFile).filter(
            FitsFile.validation_score < 80,
            FitsFile.validation_score > 0
        ).count()
        
        no_score = session.query(FitsFile).filter(
            FitsFile.validation_score.is_(None)
        ).count()
        
        # Registered files (migrated out of quarantine to library)
        registered_files = session.query(FitsFile).filter(
            ~FitsFile.folder.like(f"%{config.paths.quarantine_dir}%")
        ).count()
        
        # Frame type counts
        frame_type_counts = session.query(
            FitsFile.frame_type, 
            func.count(FitsFile.id)
        ).group_by(FitsFile.frame_type).all()
        
        # Camera counts
        camera_counts = session.query(
            FitsFile.camera, 
            func.count(FitsFile.id)
        ).group_by(FitsFile.camera).limit(10).all()
        
        # Telescope counts
        telescope_counts = session.query(
            FitsFile.telescope, 
            func.count(FitsFile.id)
        ).group_by(FitsFile.telescope).limit(10).all()
        
        # Processing session stats
        total_processing = session.query(ProcessingSession).count()
        in_progress_processing = session.query(ProcessingSession).filter(
            ProcessingSession.status == 'in_progress'
        ).count()
        active_processing = session.query(ProcessingSession).filter(
            ProcessingSession.status.in_(['not_started', 'in_progress'])
        ).count()
        
        # Imaging session stats
        total_imaging_sessions = session.query(ImagingSession).count()
        unique_cameras_in_sessions = session.query(
            func.count(distinct(ImagingSession.camera))
        ).scalar() or 0
        unique_telescopes_in_sessions = session.query(
            func.count(distinct(ImagingSession.telescope))
        ).scalar() or 0
        
        # Staged files (in processing sessions)
        staged_files = session.query(ProcessingSessionFile).count()
        
        # Database-based cleanup stats (for missing files)
        missing_files = session.query(FitsFile).filter(
            FitsFile.file_not_found == True
        ).count()
        
        # Orphaned records
        orphaned = db_service.get_orphaned_records()
        
        # **NEW: Physical file counts for quarantine, duplicates, and bad files**
        quarantine_path = Path(config.paths.quarantine_dir)
        duplicates_path = quarantine_path / "Duplicates"
        bad_files_path = quarantine_path / "Bad"
        
        # Count files in main quarantine (excluding Duplicates and Bad subfolders)
        quarantine_files = 0
        if quarantine_path.exists():
            extensions = ['.fits', '.fit', '.fts']
            for ext in extensions:
                # Get all files with this extension in quarantine
                all_files = list(quarantine_path.glob(f"*{ext}"))
                all_files.extend(list(quarantine_path.glob(f"*{ext.upper()}")))
                
                # Filter out files in Duplicates or Bad subfolders
                quarantine_files += len([
                    f for f in all_files 
                    if 'Duplicates' not in str(f) and 'Bad' not in str(f)
                ])
        
        # Count physical duplicate files
        duplicates_count = count_physical_files_in_folder(duplicates_path)
        
        # Count physical bad files
        bad_files_count = count_physical_files_in_folder(bad_files_path)
        
        # Database duplicate detection (files with same MD5)
        db_duplicates = session.query(FitsFile).filter(
            FitsFile.md5sum.in_(
                session.query(FitsFile.md5sum)
                .group_by(FitsFile.md5sum)
                .having(func.count(FitsFile.id) > 1)
            )
        ).count()
        
        # Close session after all queries complete
        session.close()
        
        return {
            "total_files": total_files,
            "registered_files": registered_files,
            "recent_files": recent_files,
            "validation": {
                "auto_migrate": auto_migrate,
                "needs_review": needs_review,
                "manual_only": manual_only,
                "no_score": no_score,
                "registered": registered_files
            },
            "by_frame_type": {ft: count for ft, count in frame_type_counts},
            "top_cameras": [{"camera": cam, "count": count} for cam, count in camera_counts],
            "top_telescopes": [{"telescope": tel, "count": count} for tel, count in telescope_counts],
            "processing_sessions": {
                "total": total_processing,
                "in_progress": in_progress_processing,
                "active": active_processing
            },
            "imaging_sessions": {
                "total": total_imaging_sessions,
                "unique_cameras": unique_cameras_in_sessions,
                "unique_telescopes": unique_telescopes_in_sessions
            },
            "cleanup": {
                "duplicates": duplicates_count,  # Physical files in Duplicates folder
                "bad_files": bad_files_count,     # Physical files in Bad folder
                "missing_files": missing_files,   # DB records with file_not_found=True
                "db_duplicates": db_duplicates    # DB records that are duplicates (same MD5)
            },
            "orphaned": orphaned,
            "quarantine_files": quarantine_files,  # Physical files in main quarantine
            "staged_files": staged_files,
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))