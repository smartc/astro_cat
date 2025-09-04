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


class Camera(BaseModel):
    """Camera specification."""
    name: str
    x_pixels: int
    y_pixels: int
    pixel_size: float  # in microns


class Telescope(BaseModel):
    """Telescope specification."""
    name: str
    focal_length: float  # in mm
    aperture: Optional[float] = None  # in mm


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
    cameras: List[Camera]
    telescopes: List[Telescope]
    filter_mappings: Dict[str, str]
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


def load_config(config_path: str = "config.json") -> Config:
    """Load configuration from JSON file."""
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_file, 'r') as f:
        config_data = json.load(f)
    
    return Config(**config_data)


def create_default_config(config_path: str = "config.json") -> None:
    """Create a default configuration file."""
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
        "cameras": [
            {
                "name": "ASI1600",
                "x_pixels": 4656,
                "y_pixels": 3520,
                "pixel_size": 3.8
            }
        ],
        "telescopes": [
            {
                "name": "ES127",
                "focal_length": 952,
                "aperture": 127
            }
        ],
        "filter_mappings": {
            "Red": "R",
            "Green": "G",
            "Blue": "B",
            "Lum": "L"
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
    
    print(f"Created default configuration file: {config_path}")


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