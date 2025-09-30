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
from web.dependencies import get_config, get_db_service, get_cameras, get_telescopes, get_filter_mappings
from web.background_tasks import (
    set_operation, clear_operation, is_operation_in_progress, 
    set_task_status, get_task_status, executor, background_tasks_status
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/operations")


# ============================================================================
# BACKGROUND OPERATION FUNCTIONS
# ============================================================================

def _run_scan_sync(task_id: str):
    """Synchronous scan wrapper."""
    try:
        logger.info(f"Starting scan operation: task_id={task_id}")
        set_task_status(task_id, "running", "Scanning quarantine directory...", 0)
        
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
            # Save to database
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
                set_task_status(task_id, "running", f"Processing files... ({idx + 1}/{len(df)})", progress)
            
            logger.info(f"Saved to database: {new_files} new files, {duplicates} duplicates")
            
            # Save sessions
            for session_data in sessions:
                db_service.add_or_update_session(session_data)
            
            logger.info(f"Saved {len(sessions)} sessions")
            
            set_task_status(task_id, "completed", 
                f"Scan completed: {new_files} new files, {duplicates} duplicates", 100,
                new_files=new_files, duplicates=duplicates)
        else:
            logger.info("No new files found")
            set_task_status(task_id, "completed", "No new files found", 100,
                new_files=0, duplicates=0)
        
    except Exception as e:
        logger.error(f"Scan failed: {e}", exc_info=True)
        set_task_status(task_id, "failed", f"Scan failed: {str(e)}", 0)
    finally:
        asyncio.run(clear_operation())


def _run_validation_sync(task_id: str, check_files: bool):
    """Synchronous validation wrapper."""
    try:
        set_task_status(task_id, "running", "Validating files...", 0)
        
        # Get module globals using sys.modules
        app_module = sys.modules['web.app']
        db_service = app_module.db_service
        validator = FitsValidator(db_service)
        
        stats = validator.validate_all_files(check_files=check_files)
        
        set_task_status(task_id, "completed", 
            f"Validation completed: {stats['validated']} files validated", 100,
            stats=stats)
        
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        set_task_status(task_id, "failed", f"Validation failed: {str(e)}", 0)
    finally:
        asyncio.run(clear_operation())


def _run_migration_sync(task_id: str):
    """Synchronous migration wrapper."""
    try:
        set_task_status(task_id, "running", "Migrating files...", 0)
        
        # Get module globals using sys.modules
        app_module = sys.modules['web.app']
        config = app_module.config
        db_service = app_module.db_service
        organizer = FileOrganizer(config, db_service)
        
        stats = organizer.migrate_files()
        
        set_task_status(task_id, "completed",
            f"Migration completed: {stats['migrated']} files migrated", 100,
            stats=stats)
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        set_task_status(task_id, "failed", f"Migration failed: {str(e)}", 0)
    finally:
        asyncio.run(clear_operation())


# ============================================================================
# ASYNC OPERATION WRAPPERS
# ============================================================================

async def run_scan_operation(task_id: str):
    """Async wrapper to run scan in executor."""
    await set_operation("scan")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, _run_scan_sync, task_id)


async def run_validation_operation(task_id: str, check_files: bool):
    """Async wrapper to run validation in executor."""
    await set_operation("validation")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, _run_validation_sync, task_id, check_files)


async def run_migration_operation(task_id: str):
    """Async wrapper to run migration in executor."""
    await set_operation("migration")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, _run_migration_sync, task_id)


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.post("/scan")
async def start_scan(background_tasks: BackgroundTasks):
    """Start a quarantine scan operation."""
    logger.info("🔍 Scan request received")
    
    if is_operation_in_progress():
        logger.warning(f"❌ Cannot start scan: operation already in progress")
        raise HTTPException(
            status_code=409, 
            detail="Cannot start scan: operation already in progress"
        )

    task_id = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"🆔 Created scan task: {task_id}")
    
    # Initialize status first
    set_task_status(task_id, "pending", "Scan queued...", 0)
    
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
    
    if is_operation_in_progress():
        logger.warning(f"❌ Cannot start validation: operation already in progress")
        raise HTTPException(
            status_code=409, 
            detail="Cannot start validation: operation already in progress"
        )
    
    task_id = f"validate_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"🆔 Created validation task: {task_id}")
    
    # Initialize status
    set_task_status(task_id, "pending", "Validation queued...", 0, check_files=check_files)
    
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
    
    if is_operation_in_progress():
        logger.warning(f"❌ Cannot start migration: operation already in progress")
        raise HTTPException(
            status_code=409, 
            detail="Cannot start migration: operation already in progress"
        )
    
    task_id = f"migrate_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"🆔 Created migration task: {task_id}")
    
    # Initialize status
    set_task_status(task_id, "pending", "Migration queued...", 0)
    
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
    status = get_task_status(task_id)
    if not status or status.get("status") == "unknown":
        raise HTTPException(status_code=404, detail="Task not found")
    return status


@router.get("/current")
async def get_current_operations():
    """Get information about current operations."""
    from web.background_tasks import get_all_tasks_summary
    return get_all_tasks_summary()


@router.delete("/remove-missing")
async def remove_missing_files(
    dry_run: bool = Query(True),
    db_service = Depends(get_db_service)
):
    """Remove database records for missing files."""
    if is_operation_in_progress():
        raise HTTPException(
            status_code=409, 
            detail="Cannot remove files: operation already in progress"
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