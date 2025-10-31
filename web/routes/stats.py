"""
Updated web/routes/stats.py - Complete corrected version with physical file counts
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, distinct, extract
from datetime import datetime, timedelta
from pathlib import Path
import logging
import shutil

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


def format_integration_time(seconds: float) -> dict:
    """Format integration time in seconds to hours, minutes, seconds."""
    if seconds is None or seconds == 0:
        return {"hours": 0, "minutes": 0, "seconds": 0, "total_seconds": 0, "formatted": "0h 0m 0s"}

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    return {
        "hours": hours,
        "minutes": minutes,
        "seconds": secs,
        "total_seconds": round(seconds, 1),
        "formatted": f"{hours}h {minutes}m {secs}s"
    }


def calculate_integration_time_stats(session):
    """Calculate integration time statistics for LIGHT frames."""
    # Total integration time
    total_time = session.query(func.sum(FitsFile.exposure)).filter(
        FitsFile.frame_type == 'LIGHT'
    ).scalar() or 0

    # By year
    by_year_raw = session.query(
        func.substr(FitsFile.obs_date, 1, 4).label('year'),
        func.sum(FitsFile.exposure).label('total_time')
    ).filter(
        FitsFile.frame_type == 'LIGHT',
        FitsFile.obs_date.isnot(None)
    ).group_by('year').order_by('year').all()

    by_year = {year: format_integration_time(time) for year, time in by_year_raw if year}

    # By telescope
    by_telescope_raw = session.query(
        FitsFile.telescope,
        func.sum(FitsFile.exposure).label('total_time')
    ).filter(
        FitsFile.frame_type == 'LIGHT',
        FitsFile.telescope.isnot(None)
    ).group_by(FitsFile.telescope).order_by(func.sum(FitsFile.exposure).desc()).all()

    by_telescope = {tel: format_integration_time(time) for tel, time in by_telescope_raw if tel}

    # By camera
    by_camera_raw = session.query(
        FitsFile.camera,
        func.sum(FitsFile.exposure).label('total_time')
    ).filter(
        FitsFile.frame_type == 'LIGHT',
        FitsFile.camera.isnot(None)
    ).group_by(FitsFile.camera).order_by(func.sum(FitsFile.exposure).desc()).all()

    by_camera = {cam: format_integration_time(time) for cam, time in by_camera_raw if cam}

    return {
        "total": format_integration_time(total_time),
        "by_year": by_year,
        "by_telescope": by_telescope,
        "by_camera": by_camera
    }


def calculate_object_count_stats(session):
    """Calculate object count statistics for LIGHT frames."""
    # Total unique objects
    total_objects = session.query(func.count(distinct(FitsFile.object))).filter(
        FitsFile.frame_type == 'LIGHT',
        FitsFile.object.isnot(None),
        FitsFile.object != ''
    ).scalar() or 0

    # By year
    by_year_raw = session.query(
        func.substr(FitsFile.obs_date, 1, 4).label('year'),
        func.count(distinct(FitsFile.object)).label('count')
    ).filter(
        FitsFile.frame_type == 'LIGHT',
        FitsFile.object.isnot(None),
        FitsFile.object != '',
        FitsFile.obs_date.isnot(None)
    ).group_by('year').order_by('year').all()

    by_year = {year: count for year, count in by_year_raw if year}

    # By telescope
    by_telescope_raw = session.query(
        FitsFile.telescope,
        func.count(distinct(FitsFile.object)).label('count')
    ).filter(
        FitsFile.frame_type == 'LIGHT',
        FitsFile.object.isnot(None),
        FitsFile.object != '',
        FitsFile.telescope.isnot(None)
    ).group_by(FitsFile.telescope).order_by(func.count(distinct(FitsFile.object)).desc()).all()

    by_telescope = {tel: count for tel, count in by_telescope_raw if tel}

    # By camera
    by_camera_raw = session.query(
        FitsFile.camera,
        func.count(distinct(FitsFile.object)).label('count')
    ).filter(
        FitsFile.frame_type == 'LIGHT',
        FitsFile.object.isnot(None),
        FitsFile.object != '',
        FitsFile.camera.isnot(None)
    ).group_by(FitsFile.camera).order_by(func.count(distinct(FitsFile.object)).desc()).all()

    by_camera = {cam: count for cam, count in by_camera_raw if cam}

    return {
        "total": total_objects,
        "by_year": by_year,
        "by_telescope": by_telescope,
        "by_camera": by_camera
    }


def calculate_new_sessions_stats(session, config):
    """Calculate statistics for newly added imaging sessions."""
    now = datetime.now()

    def get_stats_for_period(start_date):
        """Get stats for a specific time period."""
        # Count imaging sessions created in this period
        session_count = session.query(ImagingSession).filter(
            ImagingSession.created_at >= start_date
        ).count()

        # Count frames by type added in this period
        frame_counts = session.query(
            FitsFile.frame_type,
            func.count(FitsFile.id).label('count')
        ).filter(
            FitsFile.created_at >= start_date
        ).group_by(FitsFile.frame_type).all()

        frame_dict = {ft: count for ft, count in frame_counts}

        # Total integration time for LIGHT frames
        integration_time = session.query(func.sum(FitsFile.exposure)).filter(
            FitsFile.frame_type == 'LIGHT',
            FitsFile.created_at >= start_date
        ).scalar() or 0

        # Calculate total file size
        # Sum up file sizes from filesystem
        files = session.query(FitsFile.folder, FitsFile.file).filter(
            FitsFile.created_at >= start_date
        ).all()

        total_size = 0
        for folder, filename in files:
            try:
                file_path = Path(folder) / filename
                if file_path.exists():
                    total_size += file_path.stat().st_size
            except Exception as e:
                logger.debug(f"Could not get size for {folder}/{filename}: {e}")

        return {
            "session_count": session_count,
            "frame_counts": {
                "light": frame_dict.get('LIGHT', 0),
                "dark": frame_dict.get('DARK', 0),
                "flat": frame_dict.get('FLAT', 0),
                "bias": frame_dict.get('BIAS', 0),
                "total": sum(frame_dict.values())
            },
            "integration_time": format_integration_time(integration_time),
            "total_file_size": total_size,
            "total_file_size_gb": round(total_size / (1024**3), 2)
        }

    # Year to date
    year_start = datetime(now.year, 1, 1)
    ytd = get_stats_for_period(year_start)

    # Past 30 days
    past_30d = get_stats_for_period(now - timedelta(days=30))

    # Past 7 days
    past_7d = get_stats_for_period(now - timedelta(days=7))

    # Past 24 hours
    past_24h = get_stats_for_period(now - timedelta(hours=24))

    return {
        "year_to_date": ytd,
        "past_30_days": past_30d,
        "past_7_days": past_7d,
        "past_24_hours": past_24h
    }


def calculate_disk_space_stats(session, config):
    """Calculate disk space utilization statistics."""
    # Get the catalog root directory (where the database is located)
    db_path = Path(config.database.connection_string.replace('sqlite:///', ''))
    catalog_root = db_path.parent

    # Get disk usage stats for the catalog drive
    try:
        disk_usage = shutil.disk_usage(catalog_root)
        total_space = disk_usage.total
        used_space = disk_usage.used
        free_space = disk_usage.free
        used_percent = (used_space / total_space * 100) if total_space > 0 else 0
    except Exception as e:
        logger.error(f"Error getting disk usage: {e}")
        total_space = 0
        used_space = 0
        free_space = 0
        used_percent = 0

    # Calculate space used by cataloged files
    files = session.query(FitsFile.folder, FitsFile.file).all()

    cataloged_size = 0
    for folder, filename in files:
        try:
            file_path = Path(folder) / filename
            if file_path.exists():
                cataloged_size += file_path.stat().st_size
        except Exception as e:
            logger.debug(f"Could not get size for {folder}/{filename}: {e}")

    # Calculate space by frame type
    by_frame_type = {}
    for frame_type in ['LIGHT', 'DARK', 'FLAT', 'BIAS']:
        files = session.query(FitsFile.folder, FitsFile.file).filter(
            FitsFile.frame_type == frame_type
        ).all()

        frame_size = 0
        for folder, filename in files:
            try:
                file_path = Path(folder) / filename
                if file_path.exists():
                    frame_size += file_path.stat().st_size
            except Exception as e:
                logger.debug(f"Could not get size for {folder}/{filename}: {e}")

        by_frame_type[frame_type] = {
            "bytes": frame_size,
            "gb": round(frame_size / (1024**3), 2)
        }

    # Calculate space used by session notes
    imaging_notes_size = 0
    processing_notes_size = 0

    try:
        # Imaging session notes
        imaging_notes_dir = catalog_root / "Imaging_Sessions"
        if imaging_notes_dir.exists():
            for md_file in imaging_notes_dir.rglob("*.md"):
                try:
                    imaging_notes_size += md_file.stat().st_size
                except Exception as e:
                    logger.debug(f"Could not get size for {md_file}: {e}")

        # Processing session notes
        processing_notes_dir = catalog_root / "Processing_Sessions"
        if processing_notes_dir.exists():
            for md_file in processing_notes_dir.rglob("*.md"):
                try:
                    processing_notes_size += md_file.stat().st_size
                except Exception as e:
                    logger.debug(f"Could not get size for {md_file}: {e}")
    except Exception as e:
        logger.error(f"Error calculating session notes size: {e}")

    # Calculate database size
    db_size = 0
    try:
        if db_path.exists():
            db_size = db_path.stat().st_size
    except Exception as e:
        logger.error(f"Error getting database size: {e}")

    return {
        "disk_usage": {
            "total_bytes": total_space,
            "total_gb": round(total_space / (1024**3), 2),
            "used_bytes": used_space,
            "used_gb": round(used_space / (1024**3), 2),
            "free_bytes": free_space,
            "free_gb": round(free_space / (1024**3), 2),
            "used_percent": round(used_percent, 1)
        },
        "cataloged_files": {
            "total_bytes": cataloged_size,
            "total_gb": round(cataloged_size / (1024**3), 2),
            "by_frame_type": by_frame_type
        },
        "session_notes": {
            "imaging_bytes": imaging_notes_size,
            "imaging_kb": round(imaging_notes_size / 1024, 2),
            "processing_bytes": processing_notes_size,
            "processing_kb": round(processing_notes_size / 1024, 2),
            "total_bytes": imaging_notes_size + processing_notes_size,
            "total_kb": round((imaging_notes_size + processing_notes_size) / 1024, 2)
        },
        "database": {
            "bytes": db_size,
            "mb": round(db_size / (1024**2), 2)
        }
    }


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
        
        # Calculate new statistics
        integration_time_stats = calculate_integration_time_stats(session)
        object_count_stats = calculate_object_count_stats(session)
        new_sessions_stats = calculate_new_sessions_stats(session, config)
        disk_space_stats = calculate_disk_space_stats(session, config)

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
            "integration_time": integration_time_stats,
            "object_counts": object_count_stats,
            "new_sessions": new_sessions_stats,
            "disk_space": disk_space_stats,
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))