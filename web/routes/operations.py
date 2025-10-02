"""
Operations routes for scan, validate, and migrate operations.
"""

import asyncio
import logging
import sys
import time
import threading
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks

from validation import FitsValidator
from file_organizer import FileOrganizer
from fits_processor import OptimizedFitsProcessor
from web.dependencies import get_db_service
import web.background_tasks as bg_tasks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/operations")


# ============================================================================
# BACKGROUND OPERATION FUNCTIONS
# ============================================================================

def _run_scan_sync(task_id: str):
    """Synchronous scan wrapper."""
    if task_id in bg_tasks._processing_tasks:
        return

    bg_tasks._processing_tasks.add(task_id)
    bg_tasks.current_operation = "scan"
    
    try:
        bg_tasks.background_tasks_status[task_id]["status"] = "running"
        bg_tasks.background_tasks_status[task_id]["message"] = "Scanning quarantine..."
        
        logger.info(f"Starting scan operation {task_id}")
        
        # Get module globals
        app_module = sys.modules['web.app']
        config = app_module.config
        cameras = app_module.cameras
        telescopes = app_module.telescopes
        filter_mappings = app_module.filter_mappings
        db_service = app_module.db_service
        
        fits_processor = OptimizedFitsProcessor(
            config, cameras, telescopes, filter_mappings, db_service
        )
        
        df, session_data = fits_processor.scan_quarantine()
        
        # Process results
        added_count = 0
        duplicate_count = 0
        error_count = 0
        
        for row in df.iter_rows(named=True):
            try:
                success, is_duplicate = db_service.add_fits_file(row)
                if success:
                    if is_duplicate:
                        duplicate_count += 1
                    else:
                        added_count += 1
                else:
                    error_count += 1
            except Exception as e:
                error_count += 1
                logger.error(f"Error adding file to database: {e}")
        
        # Add sessions
        session_count = 0
        for session in session_data:
            try:
                db_service.add_session(session)
                session_count += 1
            except Exception as e:
                logger.error(f"Error adding session: {e}")
        
        bg_tasks.background_tasks_status[task_id] = {
            "status": "completed",
            "message": f"Scan completed: {added_count} new files, {duplicate_count} duplicates",
            "progress": 100,
            "started_at": bg_tasks.background_tasks_status[task_id]["started_at"],
            "completed_at": datetime.now(),
            "results": {
                "added": added_count,
                "duplicates": duplicate_count,
                "errors": error_count,
                "sessions": session_count
            }
        }
        
        logger.info(f"Scan operation {task_id} completed: {added_count} added, {duplicate_count} duplicates")
        
    except Exception as e:
        bg_tasks.background_tasks_status[task_id] = {
            "status": "error",
            "message": f"Scan failed: {str(e)}",
            "completed_at": datetime.now()
        }
        logger.error(f"Background scan failed: {e}")

    finally:
        # Delay clearing to allow final status poll
        def cleanup():
            time.sleep(5)
            bg_tasks._processing_tasks.discard(task_id)
            bg_tasks.current_operation = None
        
        threading.Thread(target=cleanup, daemon=True).start()


def _run_validation_sync(task_id: str, check_files: bool = True):
    """Synchronous validation wrapper."""
    if task_id in bg_tasks._processing_tasks:
        return
    
    bg_tasks._processing_tasks.add(task_id)
    bg_tasks.current_operation = "validation"
    
    try:
        # Update from pending to running
        bg_tasks.background_tasks_status[task_id]["status"] = "running"
        bg_tasks.background_tasks_status[task_id]["message"] = "Running validation..."
        
        def update_progress(progress, stats):
            bg_tasks.background_tasks_status[task_id]["progress"] = progress
            bg_tasks.background_tasks_status[task_id]["message"] = f"Validating: {stats['auto_migrate']} auto"
        
        logger.info(f"Starting validation operation {task_id} with check_files={check_files}")
        
        # Get module globals
        app_module = sys.modules['web.app']
        db_service = app_module.db_service
        
        validator = FitsValidator(db_service)
        stats = validator.validate_all_files(
            check_files=check_files,
            progress_callback=update_progress
        )
        
        bg_tasks.background_tasks_status[task_id].update({
            "status": "completed",
            "message": f"Completed: {stats['auto_migrate']} auto-migrate",
            "progress": 100,
            "completed_at": datetime.now(),
            "results": stats
        })
        
        logger.info(f"DEBUG: Set status to completed: {bg_tasks.background_tasks_status[task_id]}")
        logger.info(f"Validation operation {task_id} completed: {stats}")
        
    except Exception as e:
        bg_tasks.background_tasks_status[task_id] = {
            "status": "error",
            "message": str(e),
            "completed_at": datetime.now()
        }
        logger.error(f"Background validation failed: {e}")
    finally:
        # Delay clearing to allow final status poll
        def cleanup():
            time.sleep(5)
            bg_tasks._processing_tasks.discard(task_id)
            bg_tasks.current_operation = None
        
        threading.Thread(target=cleanup, daemon=True).start()


def _run_migration_sync(task_id: str):
    """Synchronous migration wrapper."""
    if task_id in bg_tasks._processing_tasks:
        return
    
    bg_tasks._processing_tasks.add(task_id)
    bg_tasks.current_operation = "migration"
    
    try:
        bg_tasks.background_tasks_status[task_id]["status"] = "running"
        bg_tasks.background_tasks_status[task_id]["message"] = "Migrating files..."
        
        logger.info(f"Starting migration operation {task_id}")
        
        # Get module globals
        app_module = sys.modules['web.app']
        config = app_module.config
        db_service = app_module.db_service
        
        # Use FileOrganizer to migrate files
        file_organizer = FileOrganizer(config, db_service)
        stats = file_organizer.migrate_files(limit=None, auto_cleanup=True)
        
        bg_tasks.background_tasks_status[task_id] = {
            "status": "completed",
            "message": f"Migration completed: {stats['moved']} files moved",
            "progress": 100,
            "started_at": bg_tasks.background_tasks_status[task_id]["started_at"],
            "completed_at": datetime.now(),
            "results": {
                "moved": stats['moved'],
                "processed": stats['processed'],
                "errors": stats['errors'],
                "skipped": stats['skipped'],
                "duplicates_moved": stats.get('duplicates_moved', 0),
                "bad_files_moved": stats.get('bad_files_moved', 0),
                "left_for_review": stats.get('left_for_review', 0)
            }
        }
        
        logger.info(f"Migration operation {task_id} completed: {stats['moved']} files moved")
        
    except Exception as e:
        bg_tasks.background_tasks_status[task_id] = {
            "status": "error",
            "message": f"Migration failed: {str(e)}",
            "completed_at": datetime.now()
        }
        logger.error(f"Background migration failed: {e}")
    finally:
        # Delay clearing to allow final status poll
        def cleanup():
            time.sleep(5)
            bg_tasks._processing_tasks.discard(task_id)
            bg_tasks.current_operation = None
        
        threading.Thread(target=cleanup, daemon=True).start()


# ============================================================================
# ASYNC OPERATION WRAPPERS
# ============================================================================

async def run_scan_operation(task_id: str):
    """Async wrapper that runs sync scan in executor."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(bg_tasks.executor, _run_scan_sync, task_id)


async def run_validation_operation(task_id: str, check_files: bool = True):
    """Async wrapper that runs sync validation in executor."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(bg_tasks.executor, _run_validation_sync, task_id, check_files)


async def run_migration_operation(task_id: str):
    """Async wrapper that runs sync migration in executor."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(bg_tasks.executor, _run_migration_sync, task_id)


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.post("/scan")
async def start_scan(background_tasks: BackgroundTasks):
    """Start a quarantine scan operation."""
    logger.info("🔍 Scan request received")
    
    if bg_tasks.current_operation:
        logger.warning(f"❌ Cannot start scan: {bg_tasks.current_operation} operation already in progress")
        raise HTTPException(
            status_code=409, 
            detail=f"Cannot start scan: {bg_tasks.current_operation} operation already in progress"
        )

    task_id = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"🆔 Created scan task: {task_id}")
    
    # Initialize status first
    bg_tasks.background_tasks_status[task_id] = {
        "status": "pending",
        "message": "Scan queued...",
        "progress": 0,
        "started_at": datetime.now()
    }
    
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
    
    if bg_tasks.current_operation:
        logger.warning(f"❌ Cannot start validation: {bg_tasks.current_operation} operation already in progress")
        raise HTTPException(
            status_code=409, 
            detail=f"Cannot start validation: {bg_tasks.current_operation} operation already in progress"
        )
    
    task_id = f"validate_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"🆔 Created validation task: {task_id}")
    
    # Initialize status BEFORE background task starts
    bg_tasks.background_tasks_status[task_id] = {
        "status": "pending",
        "message": "Validation queued...",
        "progress": 0,
        "started_at": datetime.now(),
        "check_files": check_files
    }
    
    try:
        background_tasks.add_task(run_validation_operation, task_id, check_files)
        logger.info(f"✅ Validation task {task_id} queued successfully with check_files={check_files}")
        return {"task_id": task_id, "message": "Validation started"}
    except Exception as e:
        logger.error(f"❌ Failed to queue validation task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start validation: {e}")


@router.post("/migrate")
async def start_migration(background_tasks: BackgroundTasks):
    """Start a file migration operation."""
    logger.info("🔍 Migration request received")
    
    if bg_tasks.current_operation:
        logger.warning(f"❌ Cannot start migration: {bg_tasks.current_operation} operation already in progress")
        raise HTTPException(
            status_code=409, 
            detail=f"Cannot start migration: {bg_tasks.current_operation} operation already in progress"
        )
    
    task_id = f"migrate_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"🆔 Created migration task: {task_id}")
    
    # Initialize status BEFORE background task starts
    bg_tasks.background_tasks_status[task_id] = {
        "status": "pending",
        "message": "Migration queued...",
        "progress": 0,
        "started_at": datetime.now()
    }
    
    try:
        background_tasks.add_task(run_migration_operation, task_id)
        logger.info(f"✅ Migration task {task_id} queued successfully")
        return {"task_id": task_id, "message": "Migration started"}
    except Exception as e:
        logger.error(f"❌ Failed to queue migration task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start migration: {e}")


@router.get("/status/{task_id}")
async def get_operation_status(task_id: str):
    """Get status of a background operation."""
    if task_id not in bg_tasks.background_tasks_status:
        logger.warning(f"Task {task_id} not found in background_tasks_status")
        raise HTTPException(status_code=404, detail="Task not found")
    
    return bg_tasks.background_tasks_status[task_id]


@router.get("/current")
async def get_current_operation():
    """Get current operation status."""
    result = {
        "current_operation": bg_tasks.current_operation,
        "processing_tasks": list(bg_tasks._processing_tasks),
        "total_tracked_tasks": len(bg_tasks.background_tasks_status)
    }
    logger.info(f"DEBUG /current: {result}")
    return result


@router.delete("/remove-missing")
async def remove_missing_files(
    dry_run: bool = Query(True),
    db_service = Depends(get_db_service)
):
    """Remove database records for missing files."""
    if bg_tasks.current_operation:
        raise HTTPException(
            status_code=409, 
            detail=f"Cannot remove files: {bg_tasks.current_operation} operation already in progress"
        )
    
    try:
        validator = FitsValidator(db_service)
        stats = validator.remove_missing_files(dry_run=dry_run)
        
        return {
            "message": "Dry run completed" if dry_run else "Missing files removed",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Error removing missing files: {e}")
        raise HTTPException(status_code=500, detail=str(e))