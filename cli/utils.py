"""Shared utilities for CLI commands."""

import logging
import sys
from pathlib import Path
from typing import Tuple, Dict, List

import click

from config import load_config, Config
from models import DatabaseService, DatabaseManager


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


def get_db_service(config: Config) -> DatabaseService:
    """Get database service instance.

    Args:
        config: Application configuration

    Returns:
        DatabaseService instance
    """
    db_manager = DatabaseManager(config.database.connection_string)
    return DatabaseService(db_manager)


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
