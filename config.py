"""Configuration management for FITS Cataloger."""

import json
import os
from pathlib import Path
from typing import Dict, List
from pydantic import BaseModel, validator

from equipment_manager import EquipmentManager, EquipmentPaths


class PathConfig(BaseModel):
    """File and directory paths configuration."""
    quarantine_dir: str
    image_dir: str
    database_path: str
    restore_folder: str
    processing_dir: str
    notes_dir: str

    @validator('*', pre=True)
    def expand_paths(cls, v):
        """Expand environment variables and user home directory."""
        return os.path.expanduser(os.path.expandvars(v))


class DatabaseConfig(BaseModel):
    """Database configuration."""
    type: str = "sqlite"
    connection_string: str
    tables: Dict[str, str]


class FileMonitoringConfig(BaseModel):
    """File monitoring configuration."""
    extensions: List[str] = [".fits", ".fit", ".fts"]
    scan_interval_seconds: int = 30
    auto_process: bool = False


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    file: str = "fits_cataloger.log"
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5


class Config(BaseModel):
    """Main configuration model."""
    paths: PathConfig
    database: DatabaseConfig
    file_monitoring: FileMonitoringConfig
    equipment: EquipmentPaths
    logging: LoggingConfig

    @validator('database', pre=True)
    def format_database_connection(cls, v, values):
        """Format the database connection string with actual paths."""
        if 'paths' in values and 'database_path' in values['paths']:
            v['connection_string'] = v['connection_string'].replace(
                '{{database_path}}', 
                os.path.expanduser(os.path.expandvars(values['paths']['database_path']))
            )
        return v


def create_directories_if_needed(config: Config) -> None:
    """Create missing directories without prompting."""
    paths_to_check = [
        config.paths.quarantine_dir,
        config.paths.image_dir,
        config.paths.restore_folder,
        config.paths.processing_dir,
        config.paths.notes_dir,
        str(Path(config.paths.database_path).parent)
    ]
    
    for path_str in paths_to_check:
        path = Path(path_str)
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
                print(f"Created directory: {path}")
            except Exception as e:
                print(f"Warning: Could not create directory {path}: {e}")


def load_config(config_path: str = "config.json"):
    """Load configuration from JSON file and equipment data."""
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_file, 'r') as f:
        config_data = json.load(f)
    
    config = Config(**config_data)
    
    # Fix the database connection string after config creation
    if '{{database_path}}' in config.database.connection_string:
        config.database.connection_string = config.database.connection_string.replace(
            '{{database_path}}', 
            config.paths.database_path
        )
    
    # Create directories as needed
    create_directories_if_needed(config)
    
    # Load equipment data using EquipmentManager
    equipment_manager = EquipmentManager(config.equipment)
    cameras, telescopes, filter_mappings = equipment_manager.load_equipment()
    
    return config, cameras, telescopes, filter_mappings


def create_default_config(config_path: str = "config.json") -> None:
    """Create a default configuration file and equipment files."""
    default_config = {
        "paths": {
            "quarantine_dir": "~/astro/quarantine",
            "image_dir": "~/astro/images",
            "database_path": "~/astro/fits_catalog.db",
            "restore_folder": "~/astro/restore",
            "processing_dir": "~/astro/processing",
            "notes_dir": "~/astro/Session_Notes"  # NEW: Default notes directory
        },
        "database": {
            "type": "sqlite",
            "connection_string": "sqlite:///{{database_path}}",
            "tables": {
                "fits_files": "fits_files",
                "process_log": "process_log",
                "cameras": "cameras",
                "telescopes": "telescopes"
            }
        },
        "file_monitoring": {
            "extensions": [".fits", ".fit", ".fts"],
            "scan_interval_seconds": 30,
            "auto_process": False
        },
        "equipment": {
            "cameras_file": "cameras.json",
            "telescopes_file": "telescopes.json", 
            "filters_file": "filters.json"
        },
        "logging": {
            "level": "INFO",
            "file": "fits_cataloger.log",
            "max_bytes": 10485760,
            "backup_count": 5
        }
    }
    
    # Save config file
    with open(config_path, 'w') as f:
        json.dump(default_config, f, indent=2)
    
    # Create default equipment files using EquipmentManager
    equipment_paths = EquipmentPaths(**default_config["equipment"])
    equipment_manager = EquipmentManager(equipment_paths)
    equipment_manager.create_default_equipment_files()
    
    print(f"Created default configuration file: {config_path}")
    print("Created default equipment files: cameras.json, telescopes.json, filters.json")
    

def setup_logging(config: Config, verbose: bool = False):
    """Setup logging based on configuration."""
    import logging
    
    log_level = logging.DEBUG if verbose else getattr(logging, config.logging.level)
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(config.logging.file),
            logging.StreamHandler()
        ]
    )


if __name__ == "__main__":
    # Example usage
    try:
        config, cameras, telescopes, filter_mappings = load_config()
        print("Configuration loaded successfully!")
        print(f"Quarantine dir: {config.paths.quarantine_dir}")
        print(f"Found {len(cameras)} cameras and {len(telescopes)} telescopes")
        print(f"Filter mappings: {len(filter_mappings)} entries")
            
    except FileNotFoundError:
        print("Creating default configuration...")
        create_default_config()