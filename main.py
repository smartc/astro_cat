"""Main application for FITS Cataloger - Phase 1."""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import List

import click
from tqdm import tqdm

from config import load_config, create_default_config, Config
from models import DatabaseManager, DatabaseService
from fits_processor import FitsProcessor
from file_monitor import FileMonitorService


# Global flag for graceful shutdown
shutdown_flag = False


def setup_logging(config: Config):
    """Set up logging configuration."""
    log_level = getattr(logging, config.logging.level.upper())
    
    # Create logs directory if it doesn't exist
    log_file = Path(config.logging.file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(config.logging.file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set astropy logging to WARNING to reduce noise
    logging.getLogger('astropy').setLevel(logging.WARNING)


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_flag
    logger = logging.getLogger(__name__)
    logger.info("Received shutdown signal. Stopping gracefully...")
    shutdown_flag = True


class FitsCataloger:
    """Main FITS cataloging application."""
    
    def __init__(self, config_path: str = "config.json"):
        # Load config and equipment data
        self.config, self.cameras, self.telescopes, self.filter_mappings = load_config(config_path)
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.db_manager = DatabaseManager(self.config.database.connection_string)
        self.db_service = DatabaseService(self.db_manager)
        self.fits_processor = FitsProcessor(self.config, self.cameras, self.telescopes, self.filter_mappings)
        self.file_monitor = None
        
        # Set up database
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize database and tables."""
        try:
            self.logger.info("Initializing database...")
            self.db_manager.create_tables()
            
            # Convert equipment data to database format (matching original field names)
            camera_data = []
            for cam in self.cameras:
                camera_data.append({
                    'name': cam.camera,  # Map 'camera' to 'name'
                    'x_pixels': cam.x,   # Map 'x' to 'x_pixels'
                    'y_pixels': cam.y,   # Map 'y' to 'y_pixels'
                    'pixel_size': cam.pixel  # Map 'pixel' to 'pixel_size'
                })
            
            telescope_data = []
            for tel in self.telescopes:
                telescope_data.append({
                    'name': tel.scope,    # Map 'scope' to 'name'
                    'focal_length': tel.focal  # Map 'focal' to 'focal_length'
                })
            
            # Initialize equipment from config
            self.db_service.initialize_equipment(
                cameras=camera_data,
                telescopes=telescope_data,
                filter_mappings=self.filter_mappings
            )
            
            self.logger.info("Database initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise
    
    def process_new_files(self, filepaths: List[str]):
        """Process new files found in quarantine."""
        if not filepaths:
            return
        
        self.logger.info(f"Processing {len(filepaths)} new files")
        
        try:
            # Extract metadata from files
            df = self.fits_processor.process_files(filepaths)
            
            if df.is_empty():
                self.logger.warning("No valid metadata extracted from files")
                return
            
            # Add files to database
            added_count = 0
            duplicate_count = 0
            
            with tqdm(total=len(df), desc="Adding to database") as pbar:
                for row in df.iter_rows(named=True):
                    try:
                        fits_file = self.db_service.add_fits_file(row)
                        if fits_file.duplicate:
                            duplicate_count += 1
                        else:
                            added_count += 1
                        pbar.update(1)
                        
                    except Exception as e:
                        self.logger.error(f"Failed to add file to database: {e}")
                        pbar.update(1)
            
            self.logger.info(
                f"Database update complete: {added_count} new files, "
                f"{duplicate_count} duplicates"
            )
            
        except Exception as e:
            self.logger.error(f"Error processing files: {e}")
    
    def scan_quarantine_once(self):
        """Perform a one-time scan of the quarantine directory."""
        self.logger.info("Performing one-time quarantine scan...")
        
        df = self.fits_processor.scan_quarantine()
        
        if df.is_empty():
            self.logger.info("No files found in quarantine directory")
            return
        
        # Convert DataFrame to list of file paths for processing
        filepaths = [
            str(Path(row['folder']) / row['file']) 
            for row in df.iter_rows(named=True)
        ]
        
        self.process_new_files(filepaths)
    
    async def start_monitoring(self):
        """Start continuous monitoring of quarantine directory."""
        global shutdown_flag
        
        self.logger.info("Starting quarantine monitoring...")
        
        # Set up file monitor
        self.file_monitor = FileMonitorService(self.config, self.process_new_files)
        
        try:
            # Start monitoring
            self.file_monitor.start()
            
            # Perform initial scan
            self.logger.info("Performing initial scan...")
            existing_files = self.file_monitor.scan_existing()
            if existing_files:
                self.process_new_files(existing_files)
            
            # Keep running until shutdown signal
            self.logger.info("Monitoring active. Press Ctrl+C to stop.")
            
            while not shutdown_flag:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        except Exception as e:
            self.logger.error(f"Error during monitoring: {e}")
        finally:
            if self.file_monitor:
                self.file_monitor.stop()
    
    def get_stats(self) -> dict:
        """Get database statistics."""
        # This would query the database for summary stats
        # Implementation depends on specific queries needed
        return {
            "total_files": 0,  # Placeholder
            "by_camera": {},
            "by_telescope": {},
            "by_frame_type": {}
        }
    
    def cleanup(self):
        """Clean up resources."""
        if self.db_manager:
            self.db_manager.close()


@click.group()
@click.option('--config', '-c', default='config.json', help='Configuration file path')
@click.pass_context
def cli(ctx, config):
    """FITS Cataloger - Astronomical image management tool."""
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = config


@cli.command()
@click.pass_context
def init_config(ctx):
    """Create a default configuration file."""
    config_path = ctx.obj['config_path']
    
    if Path(config_path).exists():
        click.echo(f"Configuration file already exists: {config_path}")
        if not click.confirm("Overwrite existing configuration?"):
            return
    
    create_default_config(config_path)
    click.echo(f"Created configuration file: {config_path}")
    click.echo("Please edit the configuration file with your specific paths and equipment.")


@cli.command()
@click.pass_context
def scan(ctx):
    """Perform a one-time scan of the quarantine directory."""
    config_path = ctx.obj['config_path']
    
    try:
        config, cameras, telescopes, filter_mappings = load_config(config_path)
        setup_logging(config)
        
        cataloger = FitsCataloger(config_path)
        cataloger.scan_quarantine_once()
        cataloger.cleanup()
        
        click.echo("Quarantine scan completed successfully!")
        
    except Exception as e:
        click.echo(f"Error during scan: {e}")
        sys.exit(1)


@cli.command()
@click.pass_context
def monitor(ctx):
    """Start continuous monitoring of quarantine directory."""
    config_path = ctx.obj['config_path']
    
    try:
        config, cameras, telescopes, filter_mappings = load_config(config_path)
        setup_logging(config)
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        cataloger = FitsCataloger(config_path)
        
        # Run the async monitoring
        asyncio.run(cataloger.start_monitoring())
        cataloger.cleanup()
        
        click.echo("Monitoring stopped successfully!")
        
    except Exception as e:
        click.echo(f"Error during monitoring: {e}")
        sys.exit(1)


@cli.command()
@click.pass_context
def stats(ctx):
    """Show database statistics."""
    config_path = ctx.obj['config_path']
    
    try:
        config, cameras, telescopes, filter_mappings = load_config(config_path)
        setup_logging(config)
        
        cataloger = FitsCataloger(config_path)
        stats = cataloger.get_stats()
        cataloger.cleanup()
        
        click.echo("Database Statistics:")
        click.echo(f"  Total files: {stats['total_files']}")
        # Add more stats display as needed
        
    except Exception as e:
        click.echo(f"Error getting stats: {e}")
        sys.exit(1)


@cli.command()
@click.pass_context
def test_db(ctx):
    """Test database connection and setup."""
    config_path = ctx.obj['config_path']
    
    try:
        config, cameras, telescopes, filter_mappings = load_config(config_path)
        setup_logging(config)
        
        click.echo("Testing database connection...")
        
        db_manager = DatabaseManager(config.database.connection_string)
        db_manager.create_tables()
        
        with db_manager.get_session() as session:
            # Simple query to test connection
            from sqlalchemy import text
            result = session.execute(text("SELECT 1")).scalar()
            
        db_manager.close()
        
        click.echo("✓ Database connection successful!")
        click.echo("✓ Tables created/verified!")
        
    except Exception as e:
        click.echo(f"✗ Database test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli()