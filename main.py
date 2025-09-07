"""Main application for FITS Cataloger - Phase 1 with File Migration."""

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
from file_organizer import FileOrganizer


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
        self.file_monitor = None
        self.file_organizer = FileOrganizer(self.config, self.db_service)
        
        # Set up database
        self._initialize_database()

        self.fits_processor = FitsProcessor(
            self.config, 
            self.cameras, 
            self.telescopes, 
            self.filter_mappings,
            self.db_service  # Add this parameter
        )
    
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
            # Extract metadata and session data from files
            df, session_data = self.fits_processor.process_files(filepaths)
            
            if df.is_empty():
                self.logger.warning("No valid metadata extracted from files")
                return
            
            # Add files to database
            added_count = 0
            duplicate_count = 0
            error_count = 0
            
            with tqdm(total=len(df), desc="Adding files to database") as pbar:
                for row in df.iter_rows(named=True):
                    try:
                        success, is_duplicate = self.db_service.add_fits_file(row)
                        if success:
                            if is_duplicate:
                                duplicate_count += 1
                            else:
                                added_count += 1
                        else:
                            error_count += 1
                        pbar.update(1)
                        
                    except Exception as e:
                        self.logger.error(f"Failed to add file to database: {e}")
                        error_count += 1
                        pbar.update(1)
            
            # Add sessions to database
            session_added_count = 0
            if session_data:
                self.logger.info(f"Processing {len(session_data)} sessions")
                for session in session_data:
                    try:
                        self.db_service.add_session(session)
                        session_added_count += 1
                    except Exception as e:
                        self.logger.error(f"Failed to add session {session['session_id']}: {e}")
            
            self.logger.info(
                f"Database update complete: {added_count} new files, "
                f"{duplicate_count} duplicates, {error_count} file errors, "
                f"{session_added_count} sessions processed"
            )
            
        except Exception as e:
            self.logger.error(f"Error processing files: {e}")

    def scan_quarantine_once(self):
        """Perform a one-time scan of the quarantine directory."""
        self.logger.info("Performing one-time quarantine scan...")
        
        # Find FITS files and extract session data
        df, session_data = self.fits_processor.scan_quarantine()
        
        if df.is_empty():
            self.logger.info("No files found in quarantine directory")
            return
        
        # Process files directly
        filepaths = [str(Path(row['folder']) / row['file']) for row in df.iter_rows(named=True)]
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
    
    def migrate_files(self, limit: int = None) -> dict:
        """Migrate files from quarantine to organized structure."""
        return self.file_organizer.migrate_files(limit)
    
    def preview_migration(self, limit: int = 10) -> List[str]:
        """Preview migration without moving files."""
        return self.file_organizer.create_folder_structure_preview(limit)
    
    def get_stats(self) -> dict:
        """Get database statistics."""
        try:
            return self.db_service.get_database_stats()
        except Exception as e:
            self.logger.error(f"Error getting database stats: {e}")
            return {
                "total_files": 0,
                "by_camera": {},
                "by_telescope": {},
                "by_frame_type": {}
            }
    
    def get_session_stats(self) -> dict:
        """Get session statistics."""
        try:
            sessions = self.db_service.get_sessions()
            stats = {
                "total_sessions": len(sessions),
                "sessions_by_camera": {},
                "sessions_by_telescope": {},
                "sessions_by_date": {}
            }
            
            for session in sessions:
                # Count by camera
                camera = session.camera or "Unknown"
                stats["sessions_by_camera"][camera] = stats["sessions_by_camera"].get(camera, 0) + 1
                
                # Count by telescope
                telescope = session.telescope or "Unknown"
                stats["sessions_by_telescope"][telescope] = stats["sessions_by_telescope"].get(telescope, 0) + 1
                
                # Count by date
                date = session.session_date or "Unknown"
                stats["sessions_by_date"][date] = stats["sessions_by_date"].get(date, 0) + 1
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting session stats: {e}")
            return {"total_sessions": 0, "sessions_by_camera": {}, "sessions_by_telescope": {}, "sessions_by_date": {}}
    
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
@click.option('--limit', '-l', type=int, help='Maximum number of files to migrate')
@click.option('--dry-run', is_flag=True, help='Preview migration without moving files')
@click.pass_context
def migrate(ctx, limit, dry_run):
    """Migrate files from quarantine to organized library structure."""
    config_path = ctx.obj['config_path']
    
    try:
        config, cameras, telescopes, filter_mappings = load_config(config_path)
        setup_logging(config)
        
        cataloger = FitsCataloger(config_path)
        
        if dry_run:
            preview_paths = cataloger.preview_migration(limit or 20)
            if preview_paths:
                click.echo("Migration preview (showing destination paths):")
                for path in preview_paths:
                    click.echo(f"  {path}")
                click.echo(f"\nShowing {len(preview_paths)} files. Use --limit to change.")
            else:
                click.echo("No files found to migrate.")
        else:
            if not click.confirm(f"Migrate files from quarantine to organized structure?{' (limit: ' + str(limit) + ')' if limit else ''}"):
                return
                
            stats = cataloger.migrate_files(limit)
            click.echo("Migration completed!")
            click.echo(f"  Files processed: {stats['processed']}")
            click.echo(f"  Files moved: {stats['moved']}")
            click.echo(f"  Duplicates handled: {stats.get('duplicates_moved', 0)}")
            click.echo(f"  Errors: {stats['errors']}")
            click.echo(f"  Skipped: {stats['skipped']}")
        
        cataloger.cleanup()
        
    except Exception as e:
        click.echo(f"Error during migration: {e}")
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
        file_stats = cataloger.get_stats()
        session_stats = cataloger.get_session_stats()
        cataloger.cleanup()
        
        click.echo("Database Statistics:")
        click.echo(f"  Total files: {file_stats['total_files']}")
        click.echo(f"  Total sessions: {session_stats['total_sessions']}")
        
        if file_stats['by_frame_type']:
            click.echo("  By frame type:")
            for frame_type, count in file_stats['by_frame_type'].items():
                click.echo(f"    {frame_type}: {count}")
        
        if session_stats['sessions_by_camera']:
            click.echo("  Sessions by camera:")
            for camera, count in session_stats['sessions_by_camera'].items():
                click.echo(f"    {camera}: {count}")
        
        if session_stats['sessions_by_telescope']:
            click.echo("  Sessions by telescope:")
            for telescope, count in session_stats['sessions_by_telescope'].items():
                click.echo(f"    {telescope}: {count}")
        
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
        
        session = db_manager.get_session()
        try:
            # Simple query to test connection
            from sqlalchemy import text
            result = session.execute(text("SELECT 1")).scalar()
        finally:
            session.close()
        
        db_manager.close()
        
        click.echo("✓ Database connection successful!")
        click.echo("✓ Tables created/verified!")
        
    except Exception as e:
        click.echo(f"✗ Database test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli()