"""Configuration management for FITS Cataloger."""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, validator


class PathConfig(BaseModel):
    """File and directory paths configuration."""
    quarantine_dir: str
    image_dir: str
    database_path: str
    restore_folder: str

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


class EquipmentPaths(BaseModel):
    """Equipment data file paths."""
    cameras_file: str = "cameras.json"
    telescopes_file: str = "telescopes.json"
    filters_file: str = "filters.json"


class Camera(BaseModel):
    """Camera specification - matches cameras.json field names."""
    camera: str  # matches JSON field name
    bin: int = 1
    x: int       # matches JSON field name  
    y: int       # matches JSON field name
    type: str
    brand: str
    pixel: float  # matches JSON field name
    comments: Optional[str] = None


class Telescope(BaseModel):
    """Telescope specification - matches telescopes.json field names."""
    scope: str   # matches JSON field name
    focal: int   # matches JSON field name
    make: str
    type: str
    comments: Optional[str] = None


class FilterMapping(BaseModel):
    """Filter name mapping."""
    raw_name: str
    proper_name: str


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = "INFO"
    file: str = "fits_cataloger.log"
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5


class Config(BaseModel):
    """Main configuration model - only references equipment files."""
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
                values['paths']['database_path']
            )
        return v


def validate_and_create_paths(config: Config) -> None:
    """Validate and optionally create missing directories."""
    paths_to_check = [
        ("quarantine_dir", config.paths.quarantine_dir),
        ("image_dir", config.paths.image_dir),
        ("restore_folder", config.paths.restore_folder)
    ]
    
    # Check database directory
    db_dir = Path(config.paths.database_path).parent
    paths_to_check.append(("database directory", str(db_dir)))
    
    for name, path_str in paths_to_check:
        path = Path(path_str)
        if not path.exists():
            print(f"Warning: {name} does not exist: {path}")
            response = input(f"Create {name}? (y/n): ").lower().strip()
            if response == 'y':
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    print(f"Created: {path}")
                except Exception as e:
                    print(f"Error creating {path}: {e}")
                    raise
            else:
                print(f"Skipping creation of {path}")


def load_equipment(equipment_paths: EquipmentPaths):
    """Load equipment data from JSON files."""
    # Load cameras
    cameras = []
    if Path(equipment_paths.cameras_file).exists():
        with open(equipment_paths.cameras_file, 'r') as f:
            cameras_data = json.load(f)
            cameras = [Camera(**cam) for cam in cameras_data]
    
    # Load telescopes
    telescopes = []
    if Path(equipment_paths.telescopes_file).exists():
        with open(equipment_paths.telescopes_file, 'r') as f:
            telescopes_data = json.load(f)
            telescopes = [Telescope(**tel) for tel in telescopes_data]
    
    # Load filter mappings
    filter_mappings = {}
    if Path(equipment_paths.filters_file).exists():
        with open(equipment_paths.filters_file, 'r') as f:
            filters_data = json.load(f)
            filter_mappings = {f['raw_name']: f['proper_name'] for f in filters_data}
    
    return cameras, telescopes, filter_mappings


def load_config(config_path: str = "config.json"):
    """Load configuration from JSON file and equipment data."""
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_file, 'r') as f:
        config_data = json.load(f)
    
    config = Config(**config_data)
    
    # Validate and create paths
    validate_and_create_paths(config)
    
    # Load equipment data
    cameras, telescopes, filter_mappings = load_equipment(config.equipment)
    
    return config, cameras, telescopes, filter_mappings


def create_default_config(config_path: str = "config.json") -> None:
    """Create a default configuration file and equipment files."""
    default_config = {
        "paths": {
            "quarantine_dir": "~/astro/quarantine",
            "image_dir": "~/astro/images",
            "database_path": "~/astro/fits_catalog.db",
            "restore_folder": "~/astro/restore"
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
    
    with open(config_path, 'w') as f:
        json.dump(default_config, f, indent=2)
    
    # Create default equipment files if they don't exist
    if not Path("cameras.json").exists():
        default_cameras = [
            {
                "camera": "ASI1600",
                "bin": 1,
                "x": 4656,
                "y": 3520,
                "type": "CMOS",
                "brand": "ZWO",
                "pixel": 3.8,
                "comments": "Example camera"
            }
        ]
        with open("cameras.json", 'w') as f:
            json.dump(default_cameras, f, indent=2)
    
    if not Path("telescopes.json").exists():
        default_telescopes = [
            {
                "scope": "ES127",
                "focal": 952,
                "make": "Explore Scientific",
                "type": "Refractor",
                "comments": "Example telescope"
            }
        ]
        with open("telescopes.json", 'w') as f:
            json.dump(default_telescopes, f, indent=2)
    
    if not Path("filters.json").exists():
        default_filters = [
            {
                "raw_name": "Red",
                "proper_name": "R"
            },
            {
                "raw_name": "Green", 
                "proper_name": "G"
            },
            {
                "raw_name": "Blue",
                "proper_name": "B"
            },
            {
                "raw_name": "Lum",
                "proper_name": "L"
            }
        ]
        with open("filters.json", 'w') as f:
            json.dump(default_filters, f, indent=2)
    
    print(f"Created default configuration file: {config_path}")
    print("Created default equipment files: cameras.json, telescopes.json, filters.json")


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