"""
Operations routes for scan, validate, and migrate operations.
"""

import asyncio
import logging
import sys
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks

from validation import FitsValidator
from file_organizer import FileOrganizer
from fits_processor import OptimizedFitsProcessor
from web.dependencies import get_config, get_db_service
import web.background_tasks as bg_tasks
from web import dashboard_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/operations")


def refresh_dashboard_cache():
    """
    Refresh dashboard statistics cache after file operations.

    This should be called after any operation that adds/removes/moves files.
    """
    try:
        app_module = sys.modules['web.app']
        config = app_module.config
        db_service = app_module.db_service

        if not config or not db_service:
            logger.warning("Cannot refresh cache: config or db_service not available")
            return

        session = db_service.db_manager.get_session()
        logger.info("Refreshing dashboard cache after file operation...")
        dashboard_cache.calculate_and_cache_disk_space(session, config)
        session.close()
        logger.info("Dashboard cache refreshed successfully")

    except Exception as e:
        logger.error(f"Error refreshing dashboard cache: {e}", exc_info=True)


# ============================================================================
# BACKGROUND OPERATION FUNCTIONS
# ============================================================================

def _run_scan_sync(task_id: str):
    """Synchronous scan wrapper."""
    try:
        bg_tasks.set_task_status(task_id, "running", "Scanning quarantine directory...", 0)
        
        # Get module globals using sys.modules
        app_module = sys.modules['web.app']
        config = app_module.config
        cameras = app_module.cameras
        telescopes = app_module.telescopes
        filter_mappings = app_module.filter_mappings
        db_service = app_module.db_service
        
        if not config or not db_service:
            raise ValueError("Configuration or database service not initialized")
        
        logger.info(f"Loaded config and services, creating processor...")
        
        # Create processor
        processor = OptimizedFitsProcessor(config, cameras, telescopes, filter_mappings, db_service)
        
        logger.info("Scanning quarantine directory...")
        
        # Scan and process files
        df, sessions = processor.scan_quarantine()
        
        logger.info(f"Scan complete: found {len(df)} files, {len(sessions)} sessions")

        if len(df) > 0:
            # Add sessions to database FIRST (before files that reference them)
            for session_data in sessions:
                db_service.add_imaging_session(session_data)

            logger.info(f"Saved {len(sessions)} sessions")

            # Now add files to database (after sessions exist)
            new_files = 0
            duplicates = 0

            for idx, row in enumerate(df.iter_rows(named=True)):
                success, is_duplicate = db_service.add_fits_file(row)
                if success and not is_duplicate:
                    new_files += 1
                elif is_duplicate:
                    duplicates += 1

                # Update progress
                progress = int((idx + 1) / len(df) * 100)
                bg_tasks.set_task_status(task_id, "running", f"Processing files... ({idx + 1}/{len(df)})", progress)

            logger.info(f"Saved to database: {new_files} new files, {duplicates} duplicates")

            # Clean up any orphaned imaging sessions (sessions with no files)
            orphaned_count = db_service.cleanup_orphaned_imaging_sessions()
            if orphaned_count > 0:
                logger.info(f"Cleaned up {orphaned_count} orphaned imaging sessions")

            results = {
                'added': new_files,
                'duplicates': duplicates,
                'sessions': len(sessions)
            }

            # Refresh dashboard cache with new file counts
            refresh_dashboard_cache()

            bg_tasks.set_task_status(task_id, "completed",
                f"Scan completed: {new_files} new files, {duplicates} duplicates", 100,
                new_files=new_files, duplicates=duplicates, results=results)
        else:
            logger.info("No new files found")
            results = {'added': 0, 'duplicates': 0, 'sessions': 0}
            bg_tasks.set_task_status(task_id, "completed", "No new files found", 100,
                results=results)

    except Exception as e:
        logger.error(f"Scan failed: {e}", exc_info=True)
        bg_tasks.set_task_status(task_id, "failed", f"Scan failed: {str(e)}", 0)
    finally:
        asyncio.run(bg_tasks.clear_operation())


def _run_validation_sync(task_id: str, check_files: bool):
    """Synchronous validation wrapper."""
    try:
        bg_tasks.set_task_status(task_id, "running", "Validating files...", 0)
        
        # Get module globals using sys.modules
        app_module = sys.modules['web.app']
        db_service = app_module.db_service
        validator = FitsValidator(db_service)
        
        # Add progress callback
        def update_progress(progress, stats):
            bg_tasks.set_task_status(task_id, "running",
                f"Validating: {stats['auto_migrate']} auto-migrate ready",
                progress)
        
        stats = validator.validate_all_files(
            check_files=check_files,
            progress_callback=update_progress
        )
        
        bg_tasks.set_task_status(task_id, "completed", 
            f"Validation completed: {stats['auto_migrate']} auto-migrate", 100,
            stats=stats)
        
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        bg_tasks.set_task_status(task_id, "failed", f"Validation failed: {str(e)}", 0)
    finally:
        asyncio.run(bg_tasks.clear_operation())


def _run_migration_sync(task_id: str):
    """Synchronous migration wrapper with progress tracking."""
    try:
        bg_tasks.set_task_status(task_id, "running", "Starting migration...", 0)

        # Get module globals using sys.modules
        app_module = sys.modules['web.app']
        config = app_module.config
        db_service = app_module.db_service

        logger.info(f"Starting migration operation {task_id}")

        # Check if files have been validated
        session = db_service.db_manager.get_session()
        try:
            from models import FitsFile
            quarantine_files = session.query(FitsFile).filter(
                FitsFile.folder.like(f"%{config.paths.quarantine_dir}%")
            ).count()

            validated_files = session.query(FitsFile).filter(
                FitsFile.folder.like(f"%{config.paths.quarantine_dir}%"),
                FitsFile.validation_score != None,
                FitsFile.validation_score > 0
            ).count()

            if quarantine_files > 0 and validated_files == 0:
                error_msg = f"No files have been validated. Please run 'Validate' before migrating. Found {quarantine_files} files in quarantine with no validation scores."
                logger.warning(error_msg)
                bg_tasks.set_task_status(task_id, "failed", error_msg, 0)
                return
        finally:
            session.close()

        # Create progress callback
        def update_progress(progress, stats):
            # Update message based on what's happening
            if stats['moved'] > 0:
                message = f"Migrated {stats['moved']} files"
            elif stats['processed'] > 0:
                message = f"Processing: {stats['processed']} files..."
            else:
                message = "Preparing migration..."

            bg_tasks.set_task_status(task_id, "running", message, progress)

        # Create organizer and run migration with web_mode=True
        organizer = FileOrganizer(config, db_service)
        stats = organizer.migrate_files(
            limit=None,
            auto_cleanup=False,  # Don't auto-delete in web mode
            progress_callback=update_progress,
            web_mode=True  # Skip interactive prompts
        )
        
        # Build completion message
        message_parts = [f"{stats['moved']} files migrated"]
        
        if stats.get('duplicates_found', 0) > 0:
            message_parts.append(f"{stats['duplicates_found']} duplicates in quarantine/Duplicates")
        
        if stats.get('bad_files_found', 0) > 0:
            message_parts.append(f"{stats['bad_files_found']} bad files in quarantine/Bad")
        
        if stats.get('left_for_review', 0) > 0:
            message_parts.append(f"{stats['left_for_review']} files left for review")
        
        completion_message = "Migration completed: " + ", ".join(message_parts)

        # Refresh dashboard cache after moving files
        refresh_dashboard_cache()

        bg_tasks.set_task_status(task_id, "completed", completion_message, 100, results=stats)

        logger.info(f"Migration operation {task_id} completed: {stats}")

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        bg_tasks.set_task_status(task_id, "failed", f"Migration failed: {str(e)}", 0)
    finally:
        asyncio.run(bg_tasks.clear_operation())

# ============================================================================
# ASYNC OPERATION WRAPPERS
# ============================================================================

async def run_scan_operation(task_id: str):
    """Async wrapper to run scan in executor."""
    await bg_tasks.set_operation("scan")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(bg_tasks.executor, _run_scan_sync, task_id)


async def run_validation_operation(task_id: str, check_files: bool):
    """Async wrapper to run validation in executor."""
    await bg_tasks.set_operation("validation")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(bg_tasks.executor, _run_validation_sync, task_id, check_files)


async def run_migration_operation(task_id: str):
    """Async wrapper to run migration in executor."""
    await bg_tasks.set_operation("migration")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(bg_tasks.executor, _run_migration_sync, task_id)


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.post("/scan")
async def start_scan(background_tasks: BackgroundTasks):
    """Start a quarantine scan operation."""
    logger.info("🔍 Scan request received")
    
    if bg_tasks.is_operation_in_progress():
        logger.warning(f"❌ Cannot start scan: operation already in progress")
        raise HTTPException(
            status_code=409, 
            detail="Cannot start scan: operation already in progress"
        )

    task_id = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"🆔 Created scan task: {task_id}")
    
    # Initialize status first
    bg_tasks.set_task_status(task_id, "pending", "Scan queued...", 0)
    
    try:
        background_tasks.add_task(run_scan_operation, task_id)
        logger.info(f"✅ Scan task {task_id} queued successfully")
        return {"task_id": task_id, "message": "Scan started"}
    except Exception as e:
        logger.error(f"❌ Failed to queue scan task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start scan: {e}")


@router.post("/validate")
async def start_validation(
    background_tasks: BackgroundTasks,
    check_files: bool = Query(True, description="Check if physical files exist")
):
    """Start a validation operation."""
    logger.info(f"🔍 Validation request received: check_files={check_files}")
    
    if bg_tasks.is_operation_in_progress():
        logger.warning(f"❌ Cannot start validation: operation already in progress")
        raise HTTPException(
            status_code=409, 
            detail="Cannot start validation: operation already in progress"
        )
    
    task_id = f"validate_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"🆔 Created validation task: {task_id}")
    
    # Initialize status
    bg_tasks.set_task_status(task_id, "pending", "Validation queued...", 0, check_files=check_files)
    
    try:
        background_tasks.add_task(run_validation_operation, task_id, check_files)
        logger.info(f"✅ Validation task {task_id} queued successfully")
        return {"task_id": task_id, "message": "Validation started"}
    except Exception as e:
        logger.error(f"❌ Failed to queue validation task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start validation: {e}")


@router.post("/migrate")
async def start_migration(background_tasks: BackgroundTasks):
    """Start a file migration operation."""
    logger.info("🔍 Migration request received")
    
    if bg_tasks.is_operation_in_progress():
        logger.warning(f"❌ Cannot start migration: operation already in progress")
        raise HTTPException(
            status_code=409, 
            detail="Cannot start migration: operation already in progress"
        )
    
    task_id = f"migrate_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"🆔 Created migration task: {task_id}")
    
    # Initialize status
    bg_tasks.set_task_status(task_id, "pending", "Migration queued...", 0)
    
    try:
        background_tasks.add_task(run_migration_operation, task_id)
        logger.info(f"✅ Migration task {task_id} queued successfully")
        return {"task_id": task_id, "message": "Migration started"}
    except Exception as e:
        logger.error(f"❌ Failed to queue migration task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start migration: {e}")


@router.get("/status/{task_id}")
async def get_operation_status(task_id: str):
    """Get the status of an operation."""
    if task_id not in bg_tasks.background_tasks_status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # FIXED: Match old behavior - add task_id and debug_info
    status_data = bg_tasks.background_tasks_status[task_id].copy()
    status_data["task_id"] = task_id
    status_data["debug_info"] = {
        "current_operation": bg_tasks.current_operation,
        "processing_tasks": list(bg_tasks._processing_tasks),
        "total_tracked_tasks": len(bg_tasks.background_tasks_status)
    }
    
    return status_data


@router.get("/current")
async def get_current_operations():
    """Get information about current operations."""
    return bg_tasks.get_all_tasks_summary()


@router.delete("/remove-missing")
async def remove_missing_files(
    dry_run: bool = Query(True),
    db_service = Depends(get_db_service)
):
    """Remove database records for missing files."""
    if bg_tasks.is_operation_in_progress():
        raise HTTPException(
            status_code=409, 
            detail="Cannot remove files: operation already in progress"
        )
    
    try:
        validator = FitsValidator(db_service)
        stats = validator.remove_missing_files(dry_run=dry_run)

        # Refresh cache if actually removed files (not dry run)
        if not dry_run and stats.get('removed', 0) > 0:
            refresh_dashboard_cache()

        return {
            "message": "Dry run completed" if dry_run else "Missing files removed",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Error removing missing files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cleanup-duplicates")
async def cleanup_duplicates(config = Depends(get_config)):
    """Delete duplicate files from quarantine/Duplicates folder."""
    if bg_tasks.is_operation_in_progress():
        raise HTTPException(
            status_code=409, 
            detail="Cannot cleanup: operation already in progress"
        )
    
    try:
        from pathlib import Path
        import shutil
        
        duplicates_folder = Path(config.paths.quarantine_dir) / "Duplicates"
        
        if not duplicates_folder.exists():
            return {
                "message": "Duplicates folder does not exist",
                "deleted": 0
            }
        
        # Count files before deletion
        file_count = 0
        for ext in ['.fits', '.fit', '.fts']:
            file_count += len(list(duplicates_folder.glob(f"*{ext}")))
        
        # Delete the folder and all contents
        shutil.rmtree(duplicates_folder)
        logger.info(f"Deleted duplicates folder with {file_count} files")

        # Refresh cache after deleting files
        if file_count > 0:
            refresh_dashboard_cache()

        return {
            "message": f"Deleted {file_count} duplicate files",
            "deleted": file_count
        }

    except Exception as e:
        logger.error(f"Error cleaning up duplicates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cleanup-bad-files")
async def cleanup_bad_files(config = Depends(get_config)):
    """Delete bad files from quarantine/Bad folder."""
    if bg_tasks.is_operation_in_progress():
        raise HTTPException(
            status_code=409, 
            detail="Cannot cleanup: operation already in progress"
        )
    
    try:
        from pathlib import Path
        import shutil
        
        bad_files_folder = Path(config.paths.quarantine_dir) / "Bad"
        
        if not bad_files_folder.exists():
            return {
                "message": "Bad files folder does not exist",
                "deleted": 0
            }
        
        # Count files before deletion
        file_count = 0
        for ext in ['.fits', '.fit', '.fts']:
            file_count += len(list(bad_files_folder.glob(f"*{ext}")))
        
        # Delete the folder and all contents
        shutil.rmtree(bad_files_folder)
        logger.info(f"Deleted bad files folder with {file_count} files")

        # Refresh cache after deleting files
        if file_count > 0:
            refresh_dashboard_cache()

        return {
            "message": f"Deleted {file_count} bad files",
            "deleted": file_count
        }

    except Exception as e:
        logger.error(f"Error cleaning up bad files: {e}")
        raise HTTPException(status_code=500, detail=str(e))