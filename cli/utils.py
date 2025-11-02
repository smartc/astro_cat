"""Shared utilities for CLI commands."""

import logging
import sys
from pathlib import Path
from typing import Tuple, Dict, List

import click

from config import load_config, Config
from models import DatabaseService, DatabaseManager
from equipment_manager import Camera as EquipCamera, Telescope as EquipTelescope


def load_app_config(config_path: str) -> Tuple[Config, List, List, Dict[str, str]]:
    """Load application configuration and equipment data.

    Args:
        config_path: Path to configuration file

    Returns:
        Tuple of (config, cameras, telescopes, filter_mappings)

    Raises:
        Exception: If configuration cannot be loaded
    """
    return load_config(config_path)


def convert_equipment_for_db(cameras: List[EquipCamera], telescopes: List[EquipTelescope],
                             filter_mappings: Dict[str, str]) -> Tuple[List[dict], List[dict], Dict[str, str]]:
    """Convert equipment data from EquipmentManager format to database format.

    Args:
        cameras: List of Camera objects from EquipmentManager
        telescopes: List of Telescope objects from EquipmentManager
        filter_mappings: Dict of raw_name -> proper_name

    Returns:
        Tuple of (cameras_dict, telescopes_dict, filter_mappings) ready for database
    """
    # Convert cameras
    cameras_dict = []
    for cam in cameras:
        cam_dict = {
            'name': cam.camera,
            'x_pixels': cam.x,
            'y_pixels': cam.y,
            'pixel_size': cam.pixel,
            'notes': cam.comments
        }
        cameras_dict.append(cam_dict)

    # Convert telescopes
    telescopes_dict = []
    for tel in telescopes:
        tel_dict = {
            'name': tel.scope,
            'focal_length': float(tel.focal),
            'aperture': tel.aperture,
            'telescope_type': tel.type,
            'notes': tel.comments
        }
        telescopes_dict.append(tel_dict)

    # Filter mappings just need proper_name -> standard_name (same thing)
    filter_mappings_dict = {raw: proper for raw, proper in filter_mappings.items()}

    return cameras_dict, telescopes_dict, filter_mappings_dict


def get_db_service(config: Config, cameras: List = None, telescopes: List = None,
                   filter_mappings: Dict[str, str] = None) -> DatabaseService:
    """Get database service instance.

    Args:
        config: Application configuration
        cameras: Optional list of cameras to initialize
        telescopes: Optional list of telescopes to initialize
        filter_mappings: Optional filter mappings to initialize

    Returns:
        DatabaseService instance
    """
    db_manager = DatabaseManager(config.database.connection_string)
    db_manager.create_tables()  # Ensure tables exist (no-op if already created)
    db_service = DatabaseService(db_manager)

    # Initialize equipment if provided
    if cameras is not None and telescopes is not None and filter_mappings is not None:
        cameras_dict, telescopes_dict, filter_mappings_dict = convert_equipment_for_db(
            cameras, telescopes, filter_mappings
        )
        db_service.initialize_equipment(cameras_dict, telescopes_dict, filter_mappings_dict)

    return db_service


def setup_logging_from_context(ctx: click.Context):
    """Configure logging from Click context.

    Args:
        ctx: Click context containing config and verbose flag
    """
    try:
        config_path = ctx.obj.get('config_path', 'config.json')
        verbose = ctx.obj.get('verbose', False)

        config, _, _, _ = load_config(config_path)
        setup_logging(config, verbose)

    except Exception as e:
        # Fallback to basic logging if config fails
        logging.basicConfig(
            level=logging.WARNING if not ctx.obj.get('verbose') else logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )


def setup_logging(config: Config, verbose: bool = False):
    """Set up logging with silent console - only click.echo() messages show.

    Args:
        config: Application configuration
        verbose: Whether to show console logging
    """
    # Create logs directory if it doesn't exist
    log_file = Path(config.logging.file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Clear any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers = []

    # File handler only - WARNING level
    file_handler = logging.FileHandler(config.logging.file)
    file_handler.setLevel(logging.WARNING)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)

    # Console handler only if verbose flag is used
    if verbose:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)
        console_formatter = logging.Formatter('LOG: %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # Root logger setup
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)

    # Quiet all libraries
    logging.getLogger('astropy').setLevel(logging.ERROR)
    logging.getLogger('urllib3').setLevel(logging.ERROR)
    logging.getLogger('requests').setLevel(logging.ERROR)


def handle_error(error: Exception, verbose: bool = False):
    """Handle and display errors consistently.

    Args:
        error: Exception to handle
        verbose: Whether to show full traceback
    """
    if verbose:
        import traceback
        click.echo(f"Error: {error}", err=True)
        click.echo(traceback.format_exc(), err=True)
    else:
        click.echo(f"Error: {error}", err=True)
    sys.exit(1)


def confirm_action(message: str, default: bool = False) -> bool:
    """Prompt user for confirmation.

    Args:
        message: Confirmation message
        default: Default response if user just presses enter

    Returns:
        True if user confirms, False otherwise
    """
    return click.confirm(message, default=default)


def format_size(bytes_size: int) -> str:
    """Format bytes as human-readable size.

    Args:
        bytes_size: Size in bytes

    Returns:
        Formatted string (e.g., "1.5 GB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"


def format_time(seconds: float) -> str:
    """Format seconds as human-readable duration.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "2h 30m 45s")
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours}h {minutes}m {secs}s"


def format_table_row(columns: List[str], widths: List[int]) -> str:
    """Format a table row with aligned columns.

    Args:
        columns: Column values
        widths: Column widths

    Returns:
        Formatted row string
    """
    formatted = []
    for col, width in zip(columns, widths):
        formatted.append(str(col).ljust(width))
    return "  ".join(formatted)
