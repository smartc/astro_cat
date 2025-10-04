"""
Monitoring routes for automatic quarantine scanning.
"""

import asyncio
import logging
import sys
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel

from file_monitor import FileMonitor
from web.dependencies import get_config, get_db_service
import web.routes.operations as operations

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monitoring")

# Global monitoring state
monitoring_task: Optional[asyncio.Task] = None
file_monitor: Optional[FileMonitor] = None


class MonitoringConfig(BaseModel):
    """Monitoring configuration model."""
    enabled: bool
    interval_minutes: int
    ignore_files_newer_than_minutes: int


async def monitoring_callback(filepaths: list):
    """
    Callback when new files are detected by monitoring.
    Chains scan → validate → migrate operations.
    """
    try:
        logger.info(f"Monitoring detected {len(filepaths)} new files, starting auto-chain...")
        
        # 1. Start scan operation
        scan_task_id = f"auto_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"Starting auto-scan: {scan_task_id}")
        
        await operations.run_scan_operation(scan_task_id)
        
        # Check scan results
        scan_status = operations.bg_tasks.get_task_status(scan_task_id)
        new_files = scan_status.get('results', {}).get('added', 0)
        
        logger.info(f"Auto-scan complete: {new_files} new files added")
        
        if new_files > 0:
            # 2. Start validation
            validate_task_id = f"auto_validate_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            logger.info(f"Starting auto-validate: {validate_task_id}")
            
            await operations.run_validation_operation(validate_task_id, check_files=True)
            
            # 3. Start migration
            migrate_task_id = f"auto_migrate_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            logger.info(f"Starting auto-migrate: {migrate_task_id}")
            
            await operations.run_migration_operation(migrate_task_id)
            
            logger.info("Auto-chain complete: scan → validate → migrate")
        else:
            logger.info("No new files added, skipping validate/migrate")
            
    except Exception as e:
        logger.error(f"Error in monitoring callback: {e}", exc_info=True)


@router.get("/status")
async def get_monitoring_status(db_service=Depends(get_db_service)):
    """Get current monitoring status."""
    global file_monitor, monitoring_task
    
    is_active = monitoring_task is not None and not monitoring_task.done()
    
    # Get settings from database
    enabled = db_service.get_setting('monitoring.enabled', False)
    interval = db_service.get_setting('monitoring.interval_minutes', 30)
    ignore_recent = db_service.get_setting('monitoring.ignore_files_newer_than_minutes', 30)
    
    status = {
        'is_active': is_active,
        'enabled': enabled,
        'interval_minutes': interval,
        'ignore_files_newer_than_minutes': ignore_recent,
        'last_scan_time': None,
        'last_scan_file_count': 0
    }
    
    if file_monitor:
        stats = file_monitor.get_monitoring_stats()
        status['last_scan_time'] = stats.get('last_scan_time')
        status['last_scan_file_count'] = stats.get('last_scan_file_count', 0)
    
    return status


@router.get("/config")
async def get_monitoring_config(db_service=Depends(get_db_service)):
    """Get monitoring configuration."""
    return {
        'enabled': db_service.get_setting('monitoring.enabled', False),
        'interval_minutes': db_service.get_setting('monitoring.interval_minutes', 30),
        'ignore_files_newer_than_minutes': db_service.get_setting(
            'monitoring.ignore_files_newer_than_minutes', 30
        )
    }


@router.post("/config")
async def update_monitoring_config(
    config: MonitoringConfig,
    db_service=Depends(get_db_service)
):
    """Update monitoring configuration."""
    global monitoring_task, file_monitor
    
    # Validate values
    if config.interval_minutes < 5 or config.interval_minutes > 1440:
        raise HTTPException(status_code=400, detail="Interval must be between 5 and 1440 minutes")
    
    if config.ignore_files_newer_than_minutes < 1 or config.ignore_files_newer_than_minutes > 1440:
        raise HTTPException(status_code=400, detail="Ignore time must be between 1 and 1440 minutes")
    
    # Save to database
    db_service.set_setting('monitoring.enabled', config.enabled)
    db_service.set_setting('monitoring.interval_minutes', config.interval_minutes)
    db_service.set_setting('monitoring.ignore_files_newer_than_minutes', 
                          config.ignore_files_newer_than_minutes)
    
    logger.info(f"Monitoring config updated: {config.dict()}")
    
    # Restart monitoring if enabled and settings changed
    was_active = monitoring_task is not None and not monitoring_task.done()
    
    if was_active:
        # Stop current monitoring
        if file_monitor:
            file_monitor.stop_monitoring()
        if monitoring_task:
            monitoring_task.cancel()
            try:
                await monitoring_task
            except asyncio.CancelledError:
                pass
    
    if config.enabled:
        # Start new monitoring with updated settings
        await start_monitoring_internal()
        return {"message": "Monitoring restarted with new settings"}
    else:
        return {"message": "Monitoring disabled"}


@router.post("/start")
async def start_monitoring():
    """Start automatic monitoring."""
    global monitoring_task, file_monitor
    
    if monitoring_task and not monitoring_task.done():
        raise HTTPException(status_code=409, detail="Monitoring already running")
    
    await start_monitoring_internal()
    
    return {"message": "Monitoring started"}


@router.post("/stop")
async def stop_monitoring():
    """Stop automatic monitoring."""
    global monitoring_task, file_monitor
    
    if not monitoring_task or monitoring_task.done():
        raise HTTPException(status_code=409, detail="Monitoring not running")
    
    # Stop the file monitor
    if file_monitor:
        file_monitor.stop_monitoring()
    
    # Cancel the async task
    monitoring_task.cancel()
    try:
        await monitoring_task
    except asyncio.CancelledError:
        pass
    
    logger.info("Monitoring stopped")
    
    return {"message": "Monitoring stopped"}


async def start_monitoring_internal():
    """Internal function to start monitoring."""
    global monitoring_task, file_monitor
    
    # Get config and services from app module
    app_module = sys.modules['web.app']
    config = app_module.config
    db_service = app_module.db_service
    
    # Create file monitor
    file_monitor = FileMonitor(config, monitoring_callback, db_service)
    
    # Get interval from database
    interval_minutes = db_service.get_setting('monitoring.interval_minutes', 30)
    
    # Start monitoring task
    monitoring_task = asyncio.create_task(
        file_monitor.start_periodic_monitoring(interval_minutes)
    )
    
    # Update enabled setting
    db_service.set_setting('monitoring.enabled', True)
    
    logger.info(f"Monitoring started with {interval_minutes} minute interval")


# Startup function to auto-start monitoring if enabled
async def auto_start_monitoring():
    """Auto-start monitoring on app startup if enabled in settings."""
    try:
        app_module = sys.modules['web.app']
        db_service = app_module.db_service
        
        enabled = db_service.get_setting('monitoring.enabled', False)
        
        if enabled:
            logger.info("Auto-starting monitoring (enabled in settings)")
            await start_monitoring_internal()
        else:
            logger.info("Monitoring not auto-started (disabled in settings)")
            
    except Exception as e:
        logger.error(f"Error auto-starting monitoring: {e}", exc_info=True)