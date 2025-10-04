"""
Statistics and dashboard data routes.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct

from models import FitsFile, ProcessingSession, ProcessingSessionFile, Session as ImagingSession
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
            FitsFile.validation_score >= 95,
            FitsFile.folder.like(f"%{config.paths.quarantine_dir}%")
        ).count()

        needs_review = session.query(FitsFile).filter(
            FitsFile.validation_score >= 80,
            FitsFile.validation_score < 95,
            FitsFile.folder.like(f"%{config.paths.quarantine_dir}%")
        ).count()

        manual_only = session.query(FitsFile).filter(
            FitsFile.validation_score < 80,
            FitsFile.folder.like(f"%{config.paths.quarantine_dir}%")
        ).count()

        no_score = session.query(FitsFile).filter(
            FitsFile.validation_score.is_(None),
            FitsFile.folder.like(f"%{config.paths.quarantine_dir}%")
        ).count()

        # Registered files (migrated to library)
        registered_files = session.query(FitsFile).filter(
            ~FitsFile.folder.like(f"%{config.paths.quarantine_dir}%")
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
        ).group_by(FitsFile.camera).limit(10).all()
        
        # Telescope counts
        telescope_counts = session.query(
            FitsFile.telescope, 
            func.count(FitsFile.id)
        ).group_by(FitsFile.telescope).limit(10).all()
        
        # Quarantine and staged files
        quarantine_files = session.query(FitsFile).filter(
            FitsFile.folder.like(f"%{config.paths.quarantine_dir}%")
        ).count()
        
        staged_files = session.query(ProcessingSessionFile).count()
        
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
        
        # Cleanup info
        duplicates = session.query(FitsFile).filter(
            FitsFile.md5sum.in_(
                session.query(FitsFile.md5sum)
                .group_by(FitsFile.md5sum)
                .having(func.count(FitsFile.id) > 1)
            )
        ).count()
        
        bad_files = session.query(FitsFile).filter(FitsFile.bad == True).count()
        missing_files = session.query(FitsFile).filter(FitsFile.file_not_found == True).count()
        
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
                "duplicates": duplicates,
                "bad_files": bad_files,
                "missing_files": missing_files
            },
            "quarantine_files": quarantine_files,
            "staged_files": staged_files,
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))