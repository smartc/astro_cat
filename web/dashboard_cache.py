"""
Dashboard statistics cache manager.

This module manages a persistent cache of expensive-to-calculate statistics
(particularly disk space usage). The cache is updated when catalog operations
run, not on every API request.

Approach similar to S3 Backup's storage_categories_cache.json
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_FILE = Path("dashboard_stats_cache.json")

# In-memory cache
_cache = {
    "disk_space": None,
    "last_updated": None
}


def load_cache() -> None:
    """Load cache from disk on startup."""
    global _cache
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
                _cache["disk_space"] = data.get("disk_space")
                if data.get("last_updated"):
                    _cache["last_updated"] = datetime.fromisoformat(data["last_updated"])
                logger.info(f"Loaded dashboard cache from {CACHE_FILE}")
    except Exception as e:
        logger.error(f"Error loading dashboard cache: {e}")


def save_cache() -> None:
    """Save cache to disk."""
    try:
        cache_data = {
            "disk_space": _cache["disk_space"],
            "last_updated": _cache["last_updated"].isoformat() if _cache["last_updated"] else None
        }
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache_data, f, indent=2)
        logger.info(f"Saved dashboard cache to {CACHE_FILE}")
    except Exception as e:
        logger.error(f"Error saving dashboard cache: {e}")


def get_cached_disk_space() -> Optional[dict]:
    """Get cached disk space statistics."""
    return _cache.get("disk_space")


def get_cache_age() -> Optional[float]:
    """Get age of cache in seconds, or None if no cache."""
    if _cache["last_updated"]:
        return (datetime.now() - _cache["last_updated"]).total_seconds()
    return None


def calculate_and_cache_disk_space(db_session, config) -> dict:
    """
    Calculate disk space statistics and update cache.

    This should be called after catalog operations that add/remove files.
    """
    from models import FitsFile

    logger.info("Calculating disk space statistics for cache...")

    # Calculate cataloged file sizes by frame type
    cataloged_size = 0
    by_frame_type = {}

    for frame_type in ['LIGHT', 'DARK', 'FLAT', 'BIAS']:
        files = db_session.query(FitsFile.folder, FitsFile.file).filter(
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

        cataloged_size += frame_size
        by_frame_type[frame_type] = {
            "bytes": frame_size,
            "gb": round(frame_size / (1024**3), 2)
        }

    logger.info(f"Cataloged FITS files: {cataloged_size / (1024**3):.2f} GB")

    # Calculate processed file sizes (intermediate and final)
    try:
        # Import here to avoid circular dependency
        from models import ProcessedFile

        # Get intermediate files
        intermediate_files = db_session.query(ProcessedFile.file_size).filter(
            ProcessedFile.subfolder == 'intermediate'
        ).all()

        intermediate_size = sum(f[0] for f in intermediate_files if f[0])

        # Get final files
        final_files = db_session.query(ProcessedFile.file_size).filter(
            ProcessedFile.subfolder == 'final'
        ).all()

        final_size = sum(f[0] for f in final_files if f[0])

        logger.info(f"Processed files - Intermediate: {intermediate_size / (1024**3):.2f} GB, Final: {final_size / (1024**3):.2f} GB")

    except ImportError:
        logger.warning("ProcessedFile model not available, skipping processed files")
        intermediate_size = 0
        final_size = 0
    except Exception as e:
        logger.error(f"Error calculating processed file sizes: {e}")
        intermediate_size = 0
        final_size = 0

    # Calculate session notes sizes
    imaging_notes_size = 0
    processing_notes_size = 0

    try:
        notes_dir = Path(config.paths.notes_dir)

        # Imaging session notes
        imaging_notes_dir = notes_dir / "Imaging_Sessions"
        if imaging_notes_dir.exists():
            for md_file in imaging_notes_dir.rglob("*.md"):
                try:
                    imaging_notes_size += md_file.stat().st_size
                except Exception as e:
                    logger.debug(f"Could not get size for {md_file}: {e}")

        # Processing session notes
        processing_notes_dir = notes_dir / "Processing_Sessions"
        if processing_notes_dir.exists():
            for md_file in processing_notes_dir.rglob("*.md"):
                try:
                    processing_notes_size += md_file.stat().st_size
                except Exception as e:
                    logger.debug(f"Could not get size for {md_file}: {e}")
    except Exception as e:
        logger.error(f"Error calculating session notes size: {e}")

    # Calculate database size
    db_path = Path(config.database.connection_string.replace('sqlite:///', ''))
    db_size = 0
    try:
        if db_path.exists():
            db_size = db_path.stat().st_size
    except Exception as e:
        logger.error(f"Error getting database size: {e}")

    # Build cache data
    disk_space_data = {
        "cataloged_files": {
            "total_bytes": cataloged_size,
            "total_gb": round(cataloged_size / (1024**3), 2),
            "by_frame_type": by_frame_type
        },
        "processed_files": {
            "intermediate_bytes": intermediate_size,
            "intermediate_gb": round(intermediate_size / (1024**3), 2),
            "final_bytes": final_size,
            "final_gb": round(final_size / (1024**3), 2),
            "total_bytes": intermediate_size + final_size,
            "total_gb": round((intermediate_size + final_size) / (1024**3), 2)
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

    # Update cache
    _cache["disk_space"] = disk_space_data
    _cache["last_updated"] = datetime.now()

    # Save to disk
    save_cache()

    logger.info("Dashboard cache updated successfully")

    return disk_space_data


def invalidate_cache() -> None:
    """Mark cache as needing refresh (without recalculating now)."""
    global _cache
    _cache["disk_space"] = None
    _cache["last_updated"] = None
    save_cache()
    logger.info("Dashboard cache invalidated")
