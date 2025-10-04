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


async def periodic_scan_task(interval_minutes: int):
    """Periodic scanning task."""
    global monitoring_enabled, last_scan
    
    app_module = sys.modules['web.app']
    config = app_module.config
    db_service = app_module.db_service
    
    from fits_processor import OptimizedFitsProcessor
    
    logger.info(f"Periodic scanning started (interval: {interval_minutes} minutes)")
    
    while monitoring_enabled:
        try:
            last_scan = datetime.now().isoformat()
            
            # Scan quarantine
            processor = OptimizedFitsProcessor(
                config, 
                app_module.cameras, 
                app_module.telescopes, 
                app_module.filter_mappings, 
                db_service
            )
            
            df, sessions = processor.scan_quarantine()
            
            if len(df) > 0:
                await monitoring_callback([])
                
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
    """Auto-start monitoring on app startup if enabled in database."""
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
            
            await start_monitoring(config)
            logger.info("✓ Auto-started monitoring from database settings")
        else:
            logger.info("Monitoring not auto-started (disabled in database)")
            
    except Exception as e:
        logger.error(f"Error auto-starting monitoring: {e}", exc_info=True)