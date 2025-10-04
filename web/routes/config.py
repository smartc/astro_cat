"""
Configuration management API routes.
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from web.dependencies import get_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


class PathsConfig(BaseModel):
    quarantine_dir: str
    image_dir: str
    processing_dir: str = ""
    database_path: str
    restore_folder: str


class FileMonitoringConfig(BaseModel):
    extensions: list
    scan_interval_seconds: int
    auto_process: bool


class DatabaseConfig(BaseModel):
    type: str
    connection_string: str
    tables: dict


class LoggingConfig(BaseModel):
    level: str
    file: str
    max_bytes: int
    backup_count: int


class EquipmentConfig(BaseModel):
    cameras_file: str
    telescopes_file: str
    filters_file: str


class FullConfig(BaseModel):
    paths: PathsConfig
    database: DatabaseConfig
    file_monitoring: FileMonitoringConfig
    equipment: EquipmentConfig
    logging: LoggingConfig


@router.get("/config")
async def get_configuration():
    """Get current configuration."""
    try:
        config_path = Path("config.json")
        if not config_path.exists():
            raise HTTPException(status_code=404, detail="Configuration file not found")
        
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        
        return config_data
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON in configuration file")
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config")
async def update_configuration(config: FullConfig):
    """
    Update configuration file.
    Note: Changes require application restart to take effect.
    """
    try:
        config_path = Path("config.json")
        
        # Convert to dict
        config_data = config.dict()
        
        # Save to file with pretty formatting
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        logger.info("Configuration updated successfully")
        
        return {
            "message": "Configuration updated successfully. Restart the application for changes to take effect.",
            "config": config_data
        }
        
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Error saving configuration: {str(e)}")


@router.get("/config/paths")
async def get_paths_config(config=Depends(get_config)):
    """Get paths configuration only."""
    return {
        "quarantine_dir": config.paths.quarantine_dir,
        "image_dir": config.paths.image_dir,
        "processing_dir": getattr(config.paths, 'processing_dir', ''),
        "database_path": config.paths.database_path,
        "restore_folder": config.paths.restore_folder
    }


@router.get("/config/monitoring")
async def get_monitoring_config(config=Depends(get_config)):
    """Get file monitoring configuration only."""
    return {
        "extensions": config.file_monitoring.extensions,
        "scan_interval_seconds": config.file_monitoring.scan_interval_seconds,
        "auto_process": config.file_monitoring.auto_process
    }


@router.get("/config/database")
async def get_database_config(config=Depends(get_config)):
    """Get database configuration only."""
    return {
        "type": config.database.type,
        "connection_string": config.database.connection_string,
        "tables": config.database.tables
    }


@router.get("/config/logging")
async def get_logging_config(config=Depends(get_config)):
    """Get logging configuration only."""
    return {
        "level": config.logging.level,
        "file": config.logging.file,
        "max_bytes": config.logging.max_bytes,
        "backup_count": config.logging.backup_count
    }