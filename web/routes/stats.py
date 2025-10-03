"""
Statistics and dashboard data routes.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from models import FitsFile, ProcessingSession, ProcessingSessionFile
from web.dependencies import get_db_session, get_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/stats")
async def get_stats(session: Session = Depends(get_db_session), config = Depends(get_config)):
    """Get dashboard statistics."""
    try:
        # Total files
        total_files = session.query(FitsFile).count()
        
        # Validation scores
        auto_migrate = session.query(FitsFile).filter(
            FitsFile.validation_score >= 95
        ).count()
        
        needs_review = session.query(FitsFile).filter(
            FitsFile.validation_score >= 80,
            FitsFile.validation_score < 95
        ).count()
        
        manual_only = session.query(FitsFile).filter(
            FitsFile.validation_score < 80
        ).count()
        
        no_score = session.query(FitsFile).filter(
            FitsFile.validation_score.is_(None)
        ).count()
        
        # Recent files (last 7 days)
        recent_cutoff = datetime.now() - timedelta(days=7)
        recent_files = session.query(FitsFile).filter(
            FitsFile.created_at >= recent_cutoff
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
        ).group_by(FitsFile.camera).all()
        
        # Telescope counts
        telescope_counts = session.query(
            FitsFile.telescope, 
            func.count(FitsFile.id)
        ).group_by(FitsFile.telescope).all()
        
        # Missing files (database records where physical file doesn't exist)
        missing_files = session.query(FitsFile).filter(
            FitsFile.file_not_found == True
        ).count()

        # Quarantine files
        quarantine_files = session.query(FitsFile).filter(
            FitsFile.folder.like(f"%{config.paths.quarantine_dir}%")
        ).count()

        # Staged files (in processing sessions)
        staged_files = session.query(ProcessingSessionFile).count()

        # Processing sessions
        total_sessions = session.query(ProcessingSession).count()
        active_sessions = session.query(ProcessingSession).filter(
            ProcessingSession.status.in_(['not_started', 'in_progress'])
        ).count()
        
        # Cleanup counts - physical files in special folders
        quarantine_path = Path(config.paths.quarantine_dir)
        duplicates_folder = quarantine_path / "Duplicates"
        bad_files_folder = quarantine_path / "Bad"
        
        # Count duplicate files
        duplicates_count = 0
        if duplicates_folder.exists():
            for ext in ['.fits', '.fit', '.fts']:
                duplicates_count += len(list(duplicates_folder.glob(f"*{ext}")))
        
        # Count bad files
        bad_files_count = 0
        if bad_files_folder.exists():
            for ext in ['.fits', '.fit', '.fts']:
                bad_files_count += len(list(bad_files_folder.glob(f"*{ext}")))

        stats = {
            "total_files": total_files,
            "quarantine_files": quarantine_files,
            "staged_files": staged_files,
            "missing_files": missing_files,
            "cleanup": {
                "duplicates": duplicates_count,
                "bad_files": bad_files_count,
                "missing_files": missing_files,
                "total": duplicates_count + bad_files_count + missing_files
            },
            "validation": {
                "total_files": total_files,
                "auto_migrate": auto_migrate,
                "needs_review": needs_review,
                "manual_only": manual_only,
                "no_score": no_score
            },
            "processing_sessions": {
                "total": total_sessions,
                "active": active_sessions
            },
            "recent_files": recent_files,
            "by_frame_type": {ft: count for ft, count in frame_type_counts if ft},
            "by_camera": {cam: count for cam, count in camera_counts if cam},
            "by_telescope": {tel: count for tel, count in telescope_counts if tel},
            "last_updated": datetime.now().isoformat()
        }
        
        logger.debug(f"Stats compiled: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))