"""
Updated web/routes/stats.py - Complete corrected version with physical file counts
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, distinct, extract
from datetime import datetime, timedelta
from pathlib import Path
import logging
import shutil
from typing import Optional
import pygal
from pygal.style import Style

from models import FitsFile, Session as ImagingSession, ProcessingSession, ProcessingSessionFile
from web.dependencies import get_db_service, get_config
from web import dashboard_cache

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)

# Custom Pygal style
custom_style = Style(
    background='transparent',
    plot_background='transparent',
    foreground='#333',
    foreground_strong='#333',
    foreground_subtle='#999',
    colors=('#2563eb', '#9333ea', '#ea580c', '#16a34a', '#0891b2'),
    font_family='system-ui, -apple-system, sans-serif',
    label_font_size=12,
    major_label_font_size=12,
    value_font_size=12,
    tooltip_font_size=14,
)


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


def format_number(value: float, max_digits: int = 3) -> float:
    """
    Format number to specified significant digits.
    Examples: 22.7, 8.54, 0.12, 101, 2041
    """
    if value is None or value == 0:
        return 0

    # For integers >= 100, don't use decimals
    if value >= 100:
        return round(value)

    # For smaller numbers, use up to 3 significant digits
    if value >= 10:
        return round(value, 1)  # 22.7
    elif value >= 1:
        return round(value, 2)  # 8.54
    else:
        return round(value, 2)  # 0.12


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
        "total_seconds": format_number(seconds),
        "formatted": f"{hours}h {minutes}m {secs}s"
    }


def format_time_for_display(seconds: float) -> str:
    """Format time in seconds to compact display string."""
    if seconds is None or seconds == 0:
        return "0h"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def add_svg_tooltips(svg_string: str, tooltips: list) -> str:
    """
    Add native SVG <title> elements for tooltips since Vue v-html doesn't execute JavaScript.

    Pygal embeds JavaScript for tooltips, but when we use v-html in Vue, scripts don't execute.
    Instead, we add SVG <title> elements which provide native browser tooltips.
    """
    import re

    # Find all rect elements that represent bars (they have class 'reactive')
    # Add a <title> child element to each
    for i, tooltip_text in enumerate(tooltips):
        # Pattern to find the i-th bar rect element
        # Pygal bars have class="reactive" and are in order
        pattern = r'(<rect[^>]*class="[^"]*reactive[^"]*"[^>]*>)'

        matches = list(re.finditer(pattern, svg_string))
        if i < len(matches):
            match = matches[i]
            # Insert <title> right after the opening <rect> tag
            insert_pos = match.end()
            title_element = f'<title>{tooltip_text}</title>'
            svg_string = svg_string[:insert_pos] + title_element + svg_string[insert_pos:]

    return svg_string


def generate_integration_time_chart(data_dict: dict, title: str) -> str:
    """Generate a vertical bar chart for integration time using Pygal."""
    if not data_dict:
        return None

    # Sort by label for years, by value for equipment
    is_year_data = all(key.isdigit() and len(key) == 4 for key in data_dict.keys())
    if is_year_data:
        sorted_items = sorted(data_dict.items(), key=lambda x: x[0])
    else:
        sorted_items = sorted(data_dict.items(), key=lambda x: x[1]['total_seconds'], reverse=True)

    # Create chart with custom configuration
    # Use consistent dimensions and margins to align chart areas across all three charts
    chart = pygal.Bar(
        style=custom_style,
        height=350,
        show_legend=False,
        truncate_label=-1,
        x_label_rotation=45 if not is_year_data else 0,
        print_values=False,
        print_zeroes=False,
        show_y_guides=False,  # Remove horizontal gridlines
        show_x_guides=False,  # Remove vertical gridlines
        margin_bottom=80,  # Fixed bottom margin to align chart areas
        margin_top=40,
        margin_left=60,
        margin_right=20,
    )
    chart.title = title

    # Prepare all data points and tooltip texts
    chart.x_labels = [item[0] for item in sorted_items]
    values = []
    tooltip_texts = []
    for label, time_data in sorted_items:
        seconds = time_data['total_seconds']
        formatted = format_time_for_display(seconds)
        tooltip_text = f"{label}: {formatted}"
        values.append(seconds / 3600)  # Convert to hours for chart
        tooltip_texts.append(tooltip_text)

    # Add all bars as a single series
    chart.add('Integration Time', values)

    # Render and add SVG tooltips
    svg_string = chart.render(is_unicode=True)
    svg_string = add_svg_tooltips(svg_string, tooltip_texts)

    return svg_string


def generate_object_count_chart(data_dict: dict, title: str) -> str:
    """Generate a vertical bar chart for object counts using Pygal."""
    if not data_dict:
        return None

    # Sort by label for years, by value for equipment
    is_year_data = all(key.isdigit() and len(key) == 4 for key in data_dict.keys())
    if is_year_data:
        sorted_items = sorted(data_dict.items(), key=lambda x: x[0])
    else:
        sorted_items = sorted(data_dict.items(), key=lambda x: x[1], reverse=True)

    # Create chart with custom configuration
    # Use consistent dimensions and margins to align chart areas across all three charts
    chart = pygal.Bar(
        style=custom_style,
        height=350,
        show_legend=False,
        truncate_label=-1,
        x_label_rotation=45 if not is_year_data else 0,
        print_values=False,
        print_zeroes=False,
        show_y_guides=False,  # Remove horizontal gridlines
        show_x_guides=False,  # Remove vertical gridlines
        margin_bottom=80,  # Fixed bottom margin to align chart areas
        margin_top=40,
        margin_left=60,
        margin_right=20,
    )
    chart.title = title

    # Prepare all data points and tooltip texts
    chart.x_labels = [item[0] for item in sorted_items]
    values = []
    tooltip_texts = []
    for label, count in sorted_items:
        plural = "objects" if count != 1 else "object"
        tooltip_text = f"{label}: {count} {plural}"
        values.append(count)
        tooltip_texts.append(tooltip_text)

    # Add all bars as a single series
    chart.add('Object Count', values)

    # Render and add SVG tooltips
    svg_string = chart.render(is_unicode=True)
    svg_string = add_svg_tooltips(svg_string, tooltip_texts)

    return svg_string


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

    # Generate charts with consistent physical dimensions for visual alignment
    chart_by_year = generate_integration_time_chart(by_year, "Integration Time by Year")
    chart_by_telescope = generate_integration_time_chart(by_telescope, "Integration Time by Telescope")
    chart_by_camera = generate_integration_time_chart(by_camera, "Integration Time by Camera")

    return {
        "total": format_integration_time(total_time),
        "by_year": by_year,
        "by_telescope": by_telescope,
        "by_camera": by_camera,
        "charts": {
            "by_year": chart_by_year,
            "by_telescope": chart_by_telescope,
            "by_camera": chart_by_camera
        }
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

    # Generate charts with consistent physical dimensions for visual alignment
    chart_by_year = generate_object_count_chart(by_year, "Object Count by Year")
    chart_by_telescope = generate_object_count_chart(by_telescope, "Object Count by Telescope")
    chart_by_camera = generate_object_count_chart(by_camera, "Object Count by Camera")

    return {
        "total": total_objects,
        "by_year": by_year,
        "by_telescope": by_telescope,
        "by_camera": by_camera,
        "charts": {
            "by_year": chart_by_year,
            "by_telescope": chart_by_telescope,
            "by_camera": chart_by_camera
        }
    }


def calculate_new_sessions_stats(session, config):
    """Calculate statistics for imaging sessions based on observation date."""
    now = datetime.now()

    def get_stats_for_period(start_date):
        """Get stats for a specific time period based on observation date."""
        # Count imaging sessions by session_date (observation date)
        session_count = session.query(ImagingSession).filter(
            ImagingSession.session_date >= start_date.strftime('%Y-%m-%d')
        ).count()

        # Count frames by type based on observation date
        frame_counts = session.query(
            FitsFile.frame_type,
            func.count(FitsFile.id).label('count')
        ).filter(
            FitsFile.obs_date >= start_date.strftime('%Y-%m-%d'),
            FitsFile.obs_date.isnot(None)
        ).group_by(FitsFile.frame_type).all()

        frame_dict = {ft: count for ft, count in frame_counts}

        # Total integration time for LIGHT frames based on observation date
        integration_time = session.query(func.sum(FitsFile.exposure)).filter(
            FitsFile.frame_type == 'LIGHT',
            FitsFile.obs_date >= start_date.strftime('%Y-%m-%d'),
            FitsFile.obs_date.isnot(None)
        ).scalar() or 0

        # Calculate actual file sizes for files from this observation period
        # This is reasonable since we're only looking at recent observations
        files = session.query(FitsFile.folder, FitsFile.file).filter(
            FitsFile.obs_date >= start_date.strftime('%Y-%m-%d'),
            FitsFile.obs_date.isnot(None)
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
            "total_file_size_gb": format_number(total_size / (1024**3))
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
    """
    Get disk space statistics from persistent cache.

    The cache is updated by catalog operations, not on every API call.
    We only calculate real-time disk usage (fast operation).
    """
    # Get cached file size data
    cached_data = dashboard_cache.get_cached_disk_space()

    # If no cache, calculate it now (first run or after invalidation)
    if cached_data is None:
        logger.info("No cached disk space data, calculating now...")
        cached_data = dashboard_cache.calculate_and_cache_disk_space(session, config)

    # Get real-time disk usage (fast operation)
    db_path = Path(config.database.connection_string.replace('sqlite:///', ''))
    catalog_root = db_path.parent

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

    # Combine real-time disk usage with cached file sizes
    result = {
        "disk_usage": {
            "total_bytes": total_space,
            "total_gb": format_number(total_space / (1024**3)),
            "used_bytes": used_space,
            "used_gb": format_number(used_space / (1024**3)),
            "free_bytes": free_space,
            "free_gb": format_number(free_space / (1024**3)),
            "used_percent": format_number(used_percent)
        },
        **cached_data  # Include all cached data (cataloged_files, processed_files, session_notes, database)
    }

    # Apply format_number to cached values
    if "cataloged_files" in result:
        result["cataloged_files"]["total_gb"] = format_number(result["cataloged_files"]["total_gb"])
        for frame_type in result["cataloged_files"].get("by_frame_type", {}).values():
            frame_type["gb"] = format_number(frame_type["gb"])

    if "processed_files" in result:
        result["processed_files"]["intermediate_gb"] = format_number(result["processed_files"]["intermediate_gb"])
        result["processed_files"]["final_gb"] = format_number(result["processed_files"]["final_gb"])
        result["processed_files"]["total_gb"] = format_number(result["processed_files"]["total_gb"])

    if "session_notes" in result:
        result["session_notes"]["imaging_kb"] = format_number(result["session_notes"]["imaging_kb"])
        result["session_notes"]["processing_kb"] = format_number(result["session_notes"]["processing_kb"])
        result["session_notes"]["total_kb"] = format_number(result["session_notes"]["total_kb"])

    if "database" in result:
        result["database"]["mb"] = format_number(result["database"]["mb"])

    return result


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


@router.post("/stats/refresh-disk-cache")
async def refresh_disk_cache(db_service = Depends(get_db_service), config = Depends(get_config)):
    """
    Manually refresh the disk space cache.

    This endpoint should be called after catalog operations that add/remove files.
    """
    try:
        session = db_service.db_manager.get_session()
        logger.info("Manual disk cache refresh requested")

        # Recalculate and cache disk space stats
        disk_stats = dashboard_cache.calculate_and_cache_disk_space(session, config)

        session.close()

        cache_age = dashboard_cache.get_cache_age()

        return {
            "success": True,
            "message": "Disk space cache refreshed successfully",
            "cache_age_seconds": cache_age,
            "summary": {
                "cataloged_files_gb": disk_stats["cataloged_files"]["total_gb"],
                "processed_files_gb": disk_stats.get("processed_files", {}).get("total_gb", 0),
                "session_notes_kb": disk_stats["session_notes"]["total_kb"],
                "database_mb": disk_stats["database"]["mb"]
            }
        }

    except Exception as e:
        logger.error(f"Error refreshing disk cache: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))