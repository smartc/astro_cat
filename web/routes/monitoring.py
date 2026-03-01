"""
Monitoring routes with database persistence.
"""

import asyncio
import logging
import sys
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

import web.routes.operations as operations

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monitoring")

# Global monitoring state
monitoring_task: Optional[asyncio.Task] = None
monitoring_enabled = False
last_scan = None
files_detected = 0


class MonitoringConfigModel(BaseModel):
    """Monitoring configuration model."""
    enabled: bool
    interval_minutes: int
    ignore_files_newer_than_minutes: int


async def monitoring_callback(filepaths: list):
    """Callback when new files are detected."""
    global files_detected
    
    try:
        files_detected = len(filepaths)
        logger.info(f"Monitoring detected {len(filepaths)} new files, starting auto-chain...")
        
        # Chain: scan → validate → migrate
        scan_task_id = f"auto_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        await operations.run_scan_operation(scan_task_id)
        
        scan_status = operations.bg_tasks.get_task_status(scan_task_id)
        new_files = scan_status.get('results', {}).get('added', 0)
        
        if new_files > 0:
            validate_task_id = f"auto_validate_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            await operations.run_validation_operation(validate_task_id, check_files=True)
            
            migrate_task_id = f"auto_migrate_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            await operations.run_migration_operation(migrate_task_id)
            
            logger.info("Auto-chain complete: scan → validate → migrate")
            
    except Exception as e:
        logger.error(f"Error in monitoring callback: {e}", exc_info=True)


async def periodic_scan_task(interval_minutes: int, initial_delay_minutes: int = 0):
    """
    Periodic scanning task with optional initial delay.

    Each iteration uses FileMonitor.scan_for_new_files() to detect only files
    that arrived since the previous check.  The full scan → validate → migrate
    chain is only triggered when genuinely new files are present, preventing the
    double-scan that occurred when the old code counted all quarantine files
    (including already-catalogued ones) as a trigger condition.

    Upload tokens (.upload_token.<machine>) are respected automatically via
    FileMonitor — if any token is present the check is skipped and the baseline
    set is not updated, so those files are still detected when the upload finishes.

    Args:
        interval_minutes: Minutes between checks
        initial_delay_minutes: Minutes to wait before the first check
    """
    global monitoring_enabled, last_scan

    app_module = sys.modules['web.app']
    config = app_module.config
    db_service = app_module.db_service

    # Wait for initial delay if specified
    if initial_delay_minutes > 0:
        logger.info(f"First scan will run in {initial_delay_minutes} minutes")
        await asyncio.sleep(initial_delay_minutes * 60)

    logger.info(f"Periodic scanning active (interval: {interval_minutes} minutes)")

    # Create a single FileMonitor instance whose last_scan_files set persists
    # across iterations, so only files that are NEW since the previous cycle
    # trigger the catalog chain.
    from file_monitor import FileMonitor
    file_monitor = FileMonitor(config, lambda files: None, db_service)

    # Seed the baseline (skip files modified very recently so they are picked
    # up properly once they stop changing).
    file_monitor.last_scan_files = set(
        file_monitor.find_fits_files(config.paths.quarantine_dir, skip_recent=True)
    )
    logger.info(f"Periodic scan baseline: {len(file_monitor.last_scan_files)} existing file(s)")

    while monitoring_enabled:
        try:
            last_scan = datetime.now().isoformat()
            logger.info("Checking quarantine for new files...")

            # Returns only files added since last check; respects upload tokens.
            new_files = file_monitor.scan_for_new_files()

            if new_files:
                logger.info(
                    f"{len(new_files)} new file(s) detected — "
                    "starting scan → validate → migrate chain"
                )
                await monitoring_callback(new_files)
            else:
                logger.info("No new raw files; cataloging processed outputs...")

            # Catalog processed files on every cycle regardless of raw files.
            try:
                from pathlib import Path
                from processed_catalog.cataloger import ProcessedFileCataloger
                processed_cataloger = ProcessedFileCataloger(config.paths.database_path)
                processing_dir = Path(config.paths.processing_dir)
                sessions_to_catalog = processed_cataloger.get_processing_sessions(processing_dir)
                for session_info in sessions_to_catalog:
                    processed_cataloger.catalog_session(session_info)
                stats = processed_cataloger.stats
                if stats['files_cataloged'] or stats['files_updated']:
                    logger.info(
                        f"Processed files: {stats['files_cataloged']} cataloged, "
                        f"{stats['files_updated']} updated"
                    )
            except Exception as e:
                logger.warning(f"Error cataloging processed files: {e}")

        except Exception as e:
            logger.error(f"Error in periodic scan: {e}", exc_info=True)

        # Wait for next interval
        await asyncio.sleep(interval_minutes * 60)


@router.get("/status")
async def get_monitoring_status():
    """Get current monitoring status from database."""
    global monitoring_enabled, last_scan, files_detected
    
    app_module = sys.modules['web.app']
    db_service = app_module.db_service
    
    # Load settings from database
    enabled_db = db_service.get_setting('monitoring.enabled', False)
    interval = db_service.get_setting('monitoring.interval_minutes', 5)
    ignore_newer = db_service.get_setting('monitoring.ignore_newer_than_minutes', 2)
    
    # Update global state from database
    monitoring_enabled = enabled_db
    
    return {
        "enabled": enabled_db,
        "interval_minutes": interval,
        "ignore_files_newer_than_minutes": ignore_newer,
        "last_scan": last_scan,
        "files_detected": files_detected,
        "next_scan": None  # TODO: Calculate based on last_scan + interval
    }


@router.post("/start")
async def start_monitoring(config: MonitoringConfigModel = Body(...)):
    """Start automatic monitoring with database persistence."""
    global monitoring_task, monitoring_enabled
    
    if monitoring_task and not monitoring_task.done():
        raise HTTPException(status_code=409, detail="Monitoring already running")
    
    app_module = sys.modules['web.app']
    db_service = app_module.db_service
    
    # Save settings to database
    db_service.set_setting('monitoring.enabled', True)
    db_service.set_setting('monitoring.interval_minutes', config.interval_minutes)
    db_service.set_setting('monitoring.ignore_newer_than_minutes', config.ignore_files_newer_than_minutes)
    
    monitoring_enabled = True
    
    # Start monitoring task
    monitoring_task = asyncio.create_task(periodic_scan_task(config.interval_minutes))
    
    logger.info(f"Monitoring started: {config.interval_minutes}min interval")
    
    return {"message": "Monitoring started", "config": config.dict()}


@router.post("/stop")
async def stop_monitoring():
    """Stop automatic monitoring."""
    global monitoring_task, monitoring_enabled
    
    if not monitoring_task or monitoring_task.done():
        raise HTTPException(status_code=409, detail="Monitoring not running")
    
    app_module = sys.modules['web.app']
    db_service = app_module.db_service
    
    # Save to database
    db_service.set_setting('monitoring.enabled', False)
    
    monitoring_enabled = False
    
    # Cancel task
    monitoring_task.cancel()
    try:
        await monitoring_task
    except asyncio.CancelledError:
        pass
    
    logger.info("Monitoring stopped")
    
    return {"message": "Monitoring stopped"}


@router.put("/config")
async def update_monitoring_config(config: MonitoringConfigModel = Body(...)):
    """Update monitoring configuration in database."""
    app_module = sys.modules['web.app']
    db_service = app_module.db_service
    
    # Save to database
    db_service.set_setting('monitoring.interval_minutes', config.interval_minutes)
    db_service.set_setting('monitoring.ignore_newer_than_minutes', config.ignore_files_newer_than_minutes)
    
    # If monitoring is running and interval changed, restart it
    global monitoring_task, monitoring_enabled
    if monitoring_enabled and monitoring_task and not monitoring_task.done():
        monitoring_task.cancel()
        try:
            await monitoring_task
        except asyncio.CancelledError:
            pass
        monitoring_task = asyncio.create_task(periodic_scan_task(config.interval_minutes))
        logger.info(f"Monitoring restarted with new interval: {config.interval_minutes}min")
    
    return {"message": "Configuration updated", "config": config.dict()}


async def auto_start_monitoring():
    """
    Auto-start monitoring on app startup if enabled in database.
    
    Waits 60 seconds before starting to allow web server to fully initialize,
    then runs first scan immediately.
    """
    try:
        app_module = sys.modules['web.app']
        db_service = app_module.db_service
        
        enabled = db_service.get_setting('monitoring.enabled', False)
        
        if enabled:
            interval = db_service.get_setting('monitoring.interval_minutes', 5)
            ignore_newer = db_service.get_setting('monitoring.ignore_newer_than_minutes', 2)
            
            config = MonitoringConfigModel(
                enabled=True,
                interval_minutes=interval,
                ignore_files_newer_than_minutes=ignore_newer
            )
            
            # Start monitoring with 60 second delay - DON'T await
            # This prevents blocking the web server startup
            asyncio.create_task(start_monitoring_with_delay(config, delay_seconds=60))
            
            logger.info(f"✓ Monitoring will auto-start in 60 seconds (interval: {interval} minutes)")
        else:
            logger.info("Monitoring not auto-started (disabled in database)")
            
    except Exception as e:
        logger.error(f"Error auto-starting monitoring: {e}", exc_info=True)


async def start_monitoring_with_delay(config: MonitoringConfigModel, delay_seconds: int = 60):
    """
    Start monitoring after a delay to prevent blocking server startup.
    First scan runs immediately after the delay period.
    
    Args:
        config: Monitoring configuration
        delay_seconds: Seconds to wait before starting monitoring (default: 60)
    """
    global monitoring_task, monitoring_enabled
    
    try:
        # Wait before starting
        logger.info(f"Monitoring startup in {delay_seconds} seconds...")
        await asyncio.sleep(delay_seconds)
        
        # Check if monitoring was manually started/stopped while waiting
        if monitoring_task and not monitoring_task.done():
            logger.info("Monitoring already started manually, skipping auto-start")
            return
        
        # Save settings to database
        app_module = sys.modules['web.app']
        db_service = app_module.db_service
        
        db_service.set_setting('monitoring.enabled', True)
        db_service.set_setting('monitoring.interval_minutes', config.interval_minutes)
        db_service.set_setting('monitoring.ignore_newer_than_minutes', config.ignore_files_newer_than_minutes)
        
        monitoring_enabled = True

        # Use the full interval as the initial delay so that the first automatic
        # check fires after one complete interval rather than immediately.  This
        # prevents the auto-scan from overlapping with a manual scan the user may
        # run right after restarting the server.
        monitoring_task = asyncio.create_task(
            periodic_scan_task(config.interval_minutes,
                               initial_delay_minutes=config.interval_minutes)
        )

        logger.info(
            f"✓ Monitoring started: {config.interval_minutes}min interval, "
            f"first automatic check in {config.interval_minutes} minute(s)"
        )
        
    except Exception as e:
        logger.error(f"Error starting delayed monitoring: {e}", exc_info=True)