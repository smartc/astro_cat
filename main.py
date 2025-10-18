"""Main application for FITS Cataloger with simplified file monitoring."""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import List, Dict

import click
from tqdm import tqdm

from config import load_config, create_default_config, Config
from models import DatabaseManager, DatabaseService, FitsFile, ProcessingSessionFile
from fits_processor import OptimizedFitsProcessor
from file_monitor import FileMonitor
from file_organizer import FileOrganizer
from validation import FitsValidator
from processing_session_manager import ProcessingSessionManager, ProcessingSessionInfo


# Global flag for graceful shutdown
shutdown_flag = False


def setup_logging(config: Config, verbose: bool = False):
    """Set up logging with silent console - only click.echo() messages show."""
    
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


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_flag
    logger = logging.getLogger(__name__)
    logger.info("Received shutdown signal. Stopping gracefully...")
    shutdown_flag = True


class FitsCataloger:
    """Main FITS cataloging application."""
    
    def __init__(self, config: Config, cameras: List, telescopes: List, filter_mappings: Dict[str, str]):
        # Use pre-loaded config and equipment data
        self.config = config
        self.cameras = cameras
        self.telescopes = telescopes
        self.filter_mappings = filter_mappings
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.db_manager = DatabaseManager(self.config.database.connection_string)
        self.db_service = DatabaseService(self.db_manager)
        self.file_monitor = FileMonitor(self.config, self.process_new_files)
        self.file_organizer = FileOrganizer(self.config, self.db_service)
        self.processing_manager = ProcessingSessionManager(self.config, self.db_service)

        
        # Set up database
        self._initialize_database()

        self.fits_processor = OptimizedFitsProcessor(
            self.config, 
            self.cameras, 
            self.telescopes, 
            self.filter_mappings,
            self.db_service
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
        
        click.echo(f"Processing {len(filepaths)} new files...")
        self.logger.info(f"Processing {len(filepaths)} new files")
        
        try:
            # Extract metadata and session data from files
            df, session_data = self.fits_processor.process_files_optimized(filepaths)
            
            if df.is_empty():
                click.echo("No valid metadata extracted from files")
                self.logger.warning("No valid metadata extracted from files")
                return
            
            # Add files to database
            added_count = 0
            duplicate_count = 0
            error_count = 0
            
            with tqdm(total=len(df), desc="Adding to database", disable=False) as pbar:
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
                click.echo(f"Processing {len(session_data)} sessions...")
                self.logger.info(f"Processing {len(session_data)} sessions")
                for session in session_data:
                    try:
                        self.db_service.add_session(session)
                        session_added_count += 1
                    except Exception as e:
                        self.logger.error(f"Failed to add session {session['session_id']}: {e}")
            
            # Report results
            click.echo(f"Scan complete: {added_count} new files, {duplicate_count} duplicates, {error_count} errors")
            if session_added_count > 0:
                click.echo(f"Sessions processed: {session_added_count}")
                
            self.logger.info(
                f"Database update complete: {added_count} new files, "
                f"{duplicate_count} duplicates, {error_count} file errors, "
                f"{session_added_count} sessions processed"
            )
            
        except Exception as e:
            click.echo(f"Error processing files: {e}")
            self.logger.error(f"Error processing files: {e}")

    def scan_quarantine_once(self):
        """Perform a one-time scan of the quarantine directory."""
        click.echo("Scanning quarantine directory...")
        self.logger.info("Performing one-time quarantine scan...")
        
        # Scan for files
        fits_files = self.file_monitor.scan_quarantine()
        
        if not fits_files:
            click.echo("No files found in quarantine directory")
            self.logger.info("No files found in quarantine directory")
            return
        
        # Process files with progress reporting
        self.process_new_files(fits_files) 

    def migrate_files(self, limit: int = None, auto_cleanup: bool = False) -> dict:
        """Migrate files from quarantine to organized structure."""
        return self.file_organizer.migrate_files(limit, auto_cleanup)
    
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
@click.option('--verbose', '-v', is_flag=True, help='Show detailed logging on console')
@click.pass_context
def cli(ctx, config, verbose):
    """FITS Cataloger - Astronomical image management tool."""
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = config
    ctx.obj['verbose'] = verbose


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
    verbose = ctx.obj['verbose']
    
    try:
        config, cameras, telescopes, filter_mappings = load_config(config_path)
        setup_logging(config, verbose)
        
        cataloger = FitsCataloger(config, cameras, telescopes, filter_mappings)
        cataloger.scan_quarantine_once()
        cataloger.cleanup()
        
        click.echo("Quarantine scan completed successfully!")
        
    except Exception as e:
        click.echo(f"Error during scan: {e}")
        sys.exit(1)


@cli.command()
@click.option('--check-files/--no-check-files', default=True, help='Check if physical files exist')
@click.option('--limit', type=int, help='Limit number of files to validate')
@click.pass_context
def validate(ctx, check_files, limit):
    """Validate files and check for missing files."""
    config_path = ctx.obj['config_path']
    verbose = ctx.obj['verbose']
    
    try:
        config, cameras, telescopes, filter_mappings = load_config(config_path)
        setup_logging(config, verbose)
        
        cataloger = FitsCataloger(config, cameras, telescopes, filter_mappings)
        validator = FitsValidator(cataloger.db_service)
        
        click.echo("Starting validation...")
        if check_files:
            click.echo("Checking for missing files on disk...")
        
        stats = validator.validate_all_files(limit=limit, check_files=check_files)
        
        click.echo("\nValidation Results:")
        click.echo(f"  Total files:      {stats['total']:>6}")
        click.echo(f"  Auto-migrate:     {stats['auto_migrate']:>6} (≥95 points)")
        click.echo(f"  Needs review:     {stats['needs_review']:>6} (80-94 points)")
        click.echo(f"  Manual only:      {stats['manual_only']:>6} (<80 points)")
        
        if check_files:
            click.echo(f"  Missing files:    {stats['missing_files']:>6}")
            
            if stats['missing_files'] > 0:
                click.echo(f"\n⚠ Found {stats['missing_files']} files that don't exist on disk")
                click.echo("  Use 'remove-missing' command to clean database")
        
        click.echo(f"  Updated:          {stats['updated']:>6}")
        click.echo(f"  Errors:           {stats['errors']:>6}")
        
        cataloger.cleanup()
        
    except Exception as e:
        click.echo(f"Error during validation: {e}")
        sys.exit(1)


@cli.command()
@click.option('--dry-run/--execute', default=True, help='Dry run mode (default) or execute removal')
@click.pass_context
def remove_missing(ctx, dry_run):
    """Remove database records for files that don't exist on disk."""
    config_path = ctx.obj['config_path']
    verbose = ctx.obj['verbose']
    
    try:
        config, cameras, telescopes, filter_mappings = load_config(config_path)
        setup_logging(config, verbose)
        
        cataloger = FitsCataloger(config, cameras, telescopes, filter_mappings)
        validator = FitsValidator(cataloger.db_service)
        
        if dry_run:
            click.echo("DRY RUN MODE - No files will be removed")
        else:
            if not click.confirm("This will permanently remove missing file records from the database. Continue?"):
                return
        
        stats = validator.remove_missing_files(dry_run=dry_run)
        
        click.echo(f"\nResults:")
        click.echo(f"  Missing files found: {stats['missing']}")
        
        if dry_run:
            click.echo(f"  Would remove: {stats['missing']} records")
            click.echo("\nRun with --execute to actually remove records")
        else:
            click.echo(f"  Removed: {stats['removed']} records")
            click.echo("✓ Database cleaned")
        
        cataloger.cleanup()
        
    except Exception as e:
        click.echo(f"Error removing missing files: {e}")
        sys.exit(1)

@cli.command()
@click.pass_context
def validation_summary(ctx):
    """Show validation summary without running validation."""
    config_path = ctx.obj['config_path']
    verbose = ctx.obj['verbose']
    
    try:
        config, cameras, telescopes, filter_mappings = load_config(config_path)
        setup_logging(config, verbose)
        
        cataloger = FitsCataloger(config, cameras, telescopes, filter_mappings)
        validator = FitsValidator(cataloger.db_service)
        
        summary = validator.get_validation_summary()
        
        click.echo("Validation Summary:")
        click.echo(f"  Total files:        {summary['total_files']:>6}")
        click.echo(f"  Auto-migrate ready: {summary['auto_migrate']:>6} (≥95 points)")
        click.echo(f"  Needs review:       {summary['needs_review']:>6} (80-94 points)")
        click.echo(f"  Manual only:        {summary['manual_only']:>6} (<80 points)")
        
        click.echo("\nAverage scores by frame type:")
        for frame_type, data in summary['frame_type_averages'].items():
            click.echo(f"  {frame_type:>5}: {data['avg_score']:>5.1f} pts ({data['count']:>5} files)")
        
        cataloger.cleanup()
        
    except Exception as e:
        click.echo(f"Error getting validation summary: {e}")
        sys.exit(1)


@cli.command()
@click.option('--limit', '-l', type=int, help='Maximum number of files to migrate')
@click.option('--dry-run', is_flag=True, help='Preview migration without moving files')
@click.option('--auto-cleanup', is_flag=True, help='Automatically delete duplicates and bad files without prompting')
@click.pass_context
def migrate(ctx, limit, dry_run, auto_cleanup):
    """Migrate files from quarantine to organized library structure."""
    config_path = ctx.obj['config_path']
    verbose = ctx.obj['verbose']
    
    try:
        config, cameras, telescopes, filter_mappings = load_config(config_path)
        setup_logging(config, verbose)
        
        cataloger = FitsCataloger(config, cameras, telescopes, filter_mappings)
        
        if dry_run:
            click.echo("Migration preview (showing destination paths):")
            preview_paths = cataloger.preview_migration(limit or 20)
            if preview_paths:
                for path in preview_paths:
                    click.echo(f"  {path}")
                click.echo(f"\nShowing {len(preview_paths)} files. Use --limit to change.")
            else:
                click.echo("No files found to migrate.")
        else:
            if not click.confirm(f"Migrate files from quarantine to organized structure?{' (limit: ' + str(limit) + ')' if limit else ''}"):
                return
                
            stats = cataloger.migrate_files(limit, auto_cleanup=auto_cleanup)
            click.echo("Migration completed!")
            click.echo(f"  Files processed:     {stats['processed']:>6}")
            click.echo(f"  Files moved:         {stats['moved']:>6}")
            click.echo(f"  Left for review:     {stats.get('left_for_review', 0):>6}")
            click.echo(f"  Duplicates handled:  {stats.get('duplicates_moved', 0):>6}")
            click.echo(f"  Bad files handled:   {stats.get('bad_files_moved', 0):>6}")
            click.echo(f"  Errors:              {stats['errors']:>6}")
            click.echo(f"  Skipped:             {stats['skipped']:>6}")
        
        cataloger.cleanup()
        
    except Exception as e:
        click.echo(f"Error during migration: {e}")
        sys.exit(1)


@cli.command()
@click.pass_context
def stats(ctx):
    """Show database statistics."""
    config_path = ctx.obj['config_path']
    verbose = ctx.obj['verbose']
    
    try:
        config, cameras, telescopes, filter_mappings = load_config(config_path)
        setup_logging(config, verbose)
        
        cataloger = FitsCataloger(config, cameras, telescopes, filter_mappings)
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
    verbose = ctx.obj['verbose']
    
    try:
        config, cameras, telescopes, filter_mappings = load_config(config_path)
        setup_logging(config, verbose)
        
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

@cli.group()
@click.pass_context
def processing(ctx):
    """Processing session management commands."""
    pass


@processing.command()
@click.argument('name')
@click.option('--file-ids', '-f', help='Comma-separated list of FITS file IDs (optional - can create empty session)')
@click.option('--notes', '-n', help='Processing notes (markdown format)')
@click.option('--dry-run', is_flag=True, help='Show what would be created without actually creating')
@click.pass_context
def create(ctx, name, file_ids, notes, dry_run):
    """Create a new processing session with selected FITS files.
    
    NAME: Name for the processing session
    
    Examples:
        # Create session with files
        python main.py processing create "NGC7000 LRGB" --file-ids "123,124,125,126" --notes "First attempt"
        
        # Create empty session (for manually adding old images later)
        python main.py processing create "M31 Archive Session" --notes "For importing old data"
    """
    config_path = ctx.obj['config_path']
    verbose = ctx.obj['verbose']
    
    try:
        # Parse comma-separated file IDs if provided
        file_ids_list = []
        if file_ids:
            try:
                file_ids_list = [int(x.strip()) for x in file_ids.split(',')]
            except ValueError as e:
                click.echo(f"Error: Invalid file IDs format. Use comma-separated integers.")
                click.echo(f"Example: --file-ids '123,124,125'")
                sys.exit(1)
        
        config, cameras, telescopes, filter_mappings = load_config(config_path)
        setup_logging(config, verbose)
        
        db_service = DatabaseService(config)
        processing_manager = ProcessingSessionManager(config, db_service)
        
        if dry_run:
            click.echo(f"Would create processing session:")
            click.echo(f"  Name: {name}")
            click.echo(f"  File IDs: {file_ids_list if file_ids_list else 'None (empty session)'}")
            click.echo(f"  Notes: {notes if notes else 'None'}")
            return
        
        session_info = processing_manager.create_processing_session(
            name=name,
            file_ids=file_ids_list,  # Can be empty list
            notes=notes
        )
        
        click.echo(f"✓ Created processing session: {session_info.id}")
        click.echo(f"  Name: {session_info.name}")
        click.echo(f"  Folder: {session_info.folder_path}")
        click.echo(f"  Files: {session_info.total_files}")
        
        if session_info.total_files == 0:
            click.echo(f"\n  Note: Empty session created. Add files using:")
            click.echo(f"    python main.py processing add-files {session_info.id} --file-ids '<ids>'")
        
    except Exception as e:
        click.echo(f"Error creating processing session: {e}")
        import traceback
        if verbose:
            traceback.print_exc()
        sys.exit(1)
        

@processing.command()
@click.option('--status', type=click.Choice(['not_started', 'in_progress', 'complete']), 
              help='Filter by status')
@click.option('--detailed', '-d', is_flag=True, help='Show detailed information')
@click.pass_context
def list(ctx, status, detailed):
    """List processing sessions."""
    config_path = ctx.obj['config_path']
    verbose = ctx.obj['verbose']
    
    try:
        config, cameras, telescopes, filter_mappings = load_config(config_path)
        setup_logging(config, verbose)
        
        cataloger = FitsCataloger(config, cameras, telescopes, filter_mappings)
        processing_manager = ProcessingSessionManager(config, cataloger.db_service)
        
        sessions = processing_manager.list_processing_sessions(status_filter=status)
        
        if not sessions:
            click.echo("No processing sessions found.")
            return
        
        click.echo(f"Found {len(sessions)} processing session(s):")
        click.echo()
        
        for session in sessions:
            click.echo(f"📁 {session.name}")
            click.echo(f"   ID: {session.id}")
            click.echo(f"   Status: {session.status}")
            click.echo(f"   Created: {session.created_at.strftime('%Y-%m-%d %H:%M')}")
            click.echo(f"   Files: {session.total_files} total ({session.lights}L, {session.darks}D, {session.flats}F, {session.bias}B)")
            
            if session.objects:
                click.echo(f"   Objects: {', '.join(session.objects)}")
            
            if detailed:
                click.echo(f"   Folder: {session.folder_path}")
                if session.notes:
                    # Show first line of notes
                    first_line = session.notes.split('\n')[0][:80]
                    click.echo(f"   Notes: {first_line}{'...' if len(session.notes) > 80 else ''}")
            
            click.echo()
        
        cataloger.cleanup()
        
    except Exception as e:
        click.echo(f"Error listing processing sessions: {e}")
        sys.exit(1)


# Updated processing commands for main.py - replace existing processing commands

@processing.command()
@click.argument('session_id')
@click.option('--file-ids', '-f', required=True, help='Comma-separated list of FITS file IDs to add')
@click.option('--dry-run', is_flag=True, help='Show what would be added without actually adding')
@click.pass_context
def add_files(ctx, session_id, file_ids, dry_run):
    """Add additional files to an existing processing session.
    
    SESSION_ID: Processing session ID to add files to
    
    Example:
        python main.py processing add-files "20241201_120000_NGC7000" --file-ids "127,128,129"
    """
    config_path = ctx.obj['config_path']
    verbose = ctx.obj['verbose']
    
    try:
        # Parse file IDs
        try:
            file_ids_list = [int(x.strip()) for x in file_ids.split(',')]
        except ValueError as e:
            click.echo(f"Error: Invalid file IDs format. Use comma-separated integers: {e}")
            return
        
        config, cameras, telescopes, filter_mappings = load_config(config_path)
        setup_logging(config, verbose)
        
        cataloger = FitsCataloger(config, cameras, telescopes, filter_mappings)
        processing_manager = ProcessingSessionManager(config, cataloger.db_service)
        
        # Check if session exists
        session = processing_manager.get_processing_session(session_id)
        if not session:
            click.echo(f"Processing session '{session_id}' not found.")
            return
        
        if dry_run:
            # Validate files and show what would be added
            files, warnings = processing_manager.validate_file_selection(file_ids_list)
            
            if warnings:
                click.echo("Warnings:")
                for warning_type, message in warnings.items():
                    click.echo(f"  - {warning_type}: {message}")
            
            if not files:
                click.echo("Error: No valid files found")
                return
            
            # Analyze what would be added
            frame_counts = {'LIGHT': 0, 'DARK': 0, 'FLAT': 0, 'BIAS': 0, 'OTHER': 0}
            new_objects = []
            
            for file_obj in files:
                frame_type = (file_obj.frame_type or 'OTHER').upper()
                if frame_type in frame_counts:
                    frame_counts[frame_type] += 1
                else:
                    frame_counts['OTHER'] += 1
                
                if file_obj.object and file_obj.object != 'CALIBRATION':
                    if file_obj.object not in session.objects and file_obj.object not in new_objects:
                        new_objects.append(file_obj.object)
            
            click.echo(f"\nWould add to session '{session.name}':")
            click.echo(f"  - Light frames: {frame_counts['LIGHT']}")
            click.echo(f"  - Dark frames: {frame_counts['DARK']}")
            click.echo(f"  - Flat frames: {frame_counts['FLAT']}")
            click.echo(f"  - Bias frames: {frame_counts['BIAS']}")
            if frame_counts['OTHER'] > 0:
                click.echo(f"  - Other frames: {frame_counts['OTHER']}")
            
            if new_objects:
                click.echo(f"  - New objects: {', '.join(new_objects)}")
            
            click.echo("\nDry run completed successfully!")
        else:
            if not click.confirm(f"Add {len(file_ids_list)} files to processing session '{session.name}'?"):
                return
            
            success = processing_manager.add_files_to_session(session_id, file_ids_list)
            
            if success:
                click.echo(f"✓ Added {len(file_ids_list)} files to processing session {session_id}")
            else:
                click.echo(f"Processing session '{session_id}' not found.")
        
        cataloger.cleanup()
        
    except Exception as e:
        click.echo(f"Error adding files to processing session: {e}")
        import traceback
        if verbose:
            traceback.print_exc()
        sys.exit(1)


@processing.command()
@click.argument('session_id')
@click.option('--frame-type', type=click.Choice(['darks', 'flats', 'bias', 'all']), 
              default='all', help='Type of calibration to find')
@click.option('--auto-add', is_flag=True, help='Automatically add all matched calibration without confirmation')
@click.option('--dry-run', is_flag=True, help='Show matches without adding anything')
@click.pass_context
def add_calibration(ctx, session_id, frame_type, auto_add, dry_run):
    """Find and add matching calibration files to a processing session.
    
    SESSION_ID: Processing session ID to add calibration to
    
    Example:
        python main.py processing add-calibration "20241201_120000_NGC7000"
        python main.py processing add-calibration "20241201_120000_NGC7000" --frame-type darks --auto-add
    """
    config_path = ctx.obj['config_path']
    verbose = ctx.obj['verbose']
    
    try:
        config, cameras, telescopes, filter_mappings = load_config(config_path)
        setup_logging(config, verbose)
        
        cataloger = FitsCataloger(config, cameras, telescopes, filter_mappings)
        processing_manager = ProcessingSessionManager(config, cataloger.db_service)
        
        # Check if session exists
        session = processing_manager.get_processing_session(session_id)
        if not session:
            click.echo(f"Processing session '{session_id}' not found.")
            return
        
        click.echo(f"Finding calibration matches for: {session.name}")
        click.echo(f"Objects: {', '.join(session.objects)}")
        click.echo()
        
        # Show light frames summary first
        db_session = cataloger.db_service.db_manager.get_session()
        try:
            from models import ProcessingSessionFile
            light_files = db_session.query(FitsFile).join(ProcessingSessionFile).filter(
                ProcessingSessionFile.processing_session_id == session_id,
                FitsFile.frame_type == 'LIGHT'
            ).all()
            
            if light_files:
                click.echo("** LIGHT FRAMES IN SESSION **")
                
                # Group by camera and capture session
                from collections import defaultdict
                camera_groups = defaultdict(lambda: {'files': [], 'filters': set(), 'exposures': set(), 'sessions': set()})
                
                for f in light_files:
                    camera = f.camera or 'UNKNOWN'
                    telescope = f.telescope or 'UNKNOWN'
                    key = f"{camera}+{telescope}"
                    camera_groups[key]['files'].append(f)
                    if f.filter and f.filter not in ['UNKNOWN', 'NONE']:
                        camera_groups[key]['filters'].add(f.filter)
                    else:
                        camera_groups[key]['filters'].add('None')
                    if f.exposure:
                        camera_groups[key]['exposures'].add(f.exposure)
                    if f.session_id:
                        camera_groups[key]['sessions'].add(f.session_id)
                
                for setup, data in camera_groups.items():
                    camera, telescope = setup.split('+')
                    filters = sorted(data['filters']) if data['filters'] else ['None']
                    exposures = sorted(data['exposures']) if data['exposures'] else []
                    sessions = sorted(data['sessions']) if data['sessions'] else ['UNKNOWN']
                    
                    click.echo(f"  Camera: {camera}, Telescope: {telescope}")
                    click.echo(f"  Files: {len(data['files'])}")
                    click.echo(f"  Filters: {', '.join(filters)}")
                    if exposures:
                        exp_str = ', '.join(f"{e}s" for e in exposures)
                        click.echo(f"  Exposures: {exp_str}")
                    click.echo(f"  Capture Sessions: {', '.join(sessions)}")
                    click.echo()
        finally:
            db_session.close()
        
        # Find matching calibration
        matches = processing_manager.find_matching_calibration(session_id)
        
        # Filter by requested frame type
        if frame_type != 'all':
            if frame_type in matches:
                matches = {frame_type: matches[frame_type]}
            else:
                matches = {}
        
        if not matches or not any(matches.values()):
            click.echo("No matching calibration files found.")
            return
        
        # Display matches
        total_files = 0
        for calib_type, calib_matches in matches.items():
            if not calib_matches:
                continue
                
            click.echo(f"** {calib_type.upper()} MATCHES **")
            
            for match in calib_matches:
                click.echo(f"  Capture Session: {match.capture_session_id}")
                click.echo(f"  Camera: {match.camera}")
                if match.telescope:
                    click.echo(f"  Telescope: {match.telescope}")
                if match.filters:
                    click.echo(f"  Filters: {', '.join(match.filters)}")
                if match.exposure_times:
                    exposures = sorted(set(match.exposure_times))
                    if len(exposures) == 1:
                        click.echo(f"  Exposure: {exposures[0]}s")
                    else:
                        click.echo(f"  Exposures: {exposures}s")
                click.echo(f"  Calibration Date: {match.capture_date}")
                
                # NEW: Show which light frame dates this matches
                if match.matched_light_dates:
                    if len(match.matched_light_dates) == 1:
                        click.echo(f"  → Matches lights from: {match.matched_light_dates[0]}")
                    else:
                        date_range = f"{min(match.matched_light_dates)} to {max(match.matched_light_dates)}"
                        click.echo(f"  → Matches lights from: {date_range}")
                
                # NEW: Show temporal proximity
                if match.days_from_lights is not None:
                    if match.days_from_lights == 0:
                        click.echo(f"  ✓ Same day as lights")
                    elif match.days_from_lights <= 7:
                        click.echo(f"  ✓ Within {match.days_from_lights} days of lights")
                    elif match.days_from_lights <= 30:
                        click.echo(f"  ~ {match.days_from_lights} days from lights")
                    else:
                        click.echo(f"  ⚠ {match.days_from_lights} days from lights")
                
                click.echo(f"  Files: {match.file_count}")
                click.echo()
                
                total_files += match.file_count

        click.echo(f"Total calibration files found: {total_files}")

        # If multiple date clusters were found, inform the user
        if len(set(tuple(m.matched_light_dates) for calib_matches in matches.values() 
                   for m in calib_matches if m.matched_light_dates)) > 1:
            click.echo("\n⚠ Note: Your processing session contains light frames from multiple")
            click.echo("  time periods. Calibration has been matched to each period separately.")
        
        if dry_run:
            click.echo("\nDry run completed - no files added.")
            return
        
        # Get user confirmation unless auto-add
        if not auto_add:
            while True:
                try:
                    choice = input(f"\nAdd calibration files? (A)ll/{total_files} (B)ias (D)arks (F)lats (N)one [N]: ").upper().strip()
                    if not choice:
                        choice = 'N'
                    
                    if choice == 'N':
                        click.echo("No calibration files added.")
                        return
                    elif choice == 'A':
                        # Add all matches
                        break
                    elif choice == 'B':
                        # Add only bias
                        matches = {'bias': matches.get('bias', [])}
                        break
                    elif choice == 'D':
                        # Add only darks  
                        matches = {'darks': matches.get('darks', [])}
                        break
                    elif choice == 'F':
                        # Add only flats
                        matches = {'flats': matches.get('flats', [])}
                        break
                    else:
                        click.echo("Invalid choice. Please enter A, B, D, F, or N.")
                        continue
                except KeyboardInterrupt:
                    click.echo("\nOperation cancelled.")
                    return
        
        # Recalculate total files for selected matches
        total_files = sum(len(calib_matches) for calib_matches in matches.values())
        if total_files == 0:
            click.echo("No files selected for addition.")
            return
        
        # Add calibration files
        success = processing_manager.add_calibration_to_session(session_id, matches)
        
        if success:
            click.echo(f"✓ Added {total_files} calibration files to processing session {session_id}")
        else:
            click.echo("Failed to add calibration files.")
        
        cataloger.cleanup()
        
    except Exception as e:
        click.echo(f"Error adding calibration to processing session: {e}")
        import traceback
        if verbose:
            traceback.print_exc()
        sys.exit(1)


# Update the existing show command to display more object information
@processing.command()
@click.argument('session_id')
@click.option('--detailed', '-d', is_flag=True, help='Show detailed file information')
@click.pass_context
def show(ctx, session_id, detailed):
    """Show detailed information about a processing session."""
    config_path = ctx.obj['config_path']
    verbose = ctx.obj['verbose']
    
    try:
        config, cameras, telescopes, filter_mappings = load_config(config_path)
        setup_logging(config, verbose)
        
        cataloger = FitsCataloger(config, cameras, telescopes, filter_mappings)
        processing_manager = ProcessingSessionManager(config, cataloger.db_service)
        
        session = processing_manager.get_processing_session(session_id)
        
        if not session:
            click.echo(f"Processing session '{session_id}' not found.")
            return
        
        click.echo(f"Processing Session: {session.name}")
        click.echo("=" * 50)
        click.echo(f"ID:           {session.id}")
        click.echo(f"Status:       {session.status}")
        click.echo(f"Created:      {session.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"Folder:       {session.folder_path}")
        click.echo()
        
        click.echo("File Summary:")
        click.echo(f"  Total files:  {session.total_files}")
        click.echo(f"  Light frames: {session.lights}")
        click.echo(f"  Dark frames:  {session.darks}")
        click.echo(f"  Flat frames:  {session.flats}")
        click.echo(f"  Bias frames:  {session.bias}")
        click.echo()
        
        if session.objects:
            click.echo("Objects:")
            for i, obj in enumerate(session.objects, 1):
                click.echo(f"  {i}. {obj}")
            click.echo()
        
        if session.notes:
            click.echo("Notes:")
            click.echo(session.notes)
            click.echo()
        
        # Check if folder exists
        folder_path = Path(session.folder_path)
        if folder_path.exists():
            click.echo("✓ Session folder exists")
        else:
            click.echo("⚠ Session folder not found")
        
        # Show detailed file info if requested
        if detailed:
            db_session = cataloger.db_service.db_manager.get_session()
            try:
                from models import ProcessingSessionFile
                files = db_session.query(ProcessingSessionFile).filter(
                    ProcessingSessionFile.processing_session_id == session_id
                ).all()
                
                if files:
                    click.echo()
                    click.echo("Staged Files:")
                    
                    # Group by frame type
                    frame_groups = defaultdict(list)
                    for f in files:
                        frame_groups[f.frame_type or 'UNKNOWN'].append(f)
                    
                    for frame_type, frame_files in frame_groups.items():
                        click.echo(f"  {frame_type}: {len(frame_files)} files")
                        if verbose:
                            for f in frame_files[:5]:  # Show first 5
                                click.echo(f"    {f.staged_filename}")
                            if len(frame_files) > 5:
                                click.echo(f"    ... and {len(frame_files) - 5} more")
            finally:
                db_session.close()
        
        cataloger.cleanup()
        
    except Exception as e:
        click.echo(f"Error showing processing session: {e}")
        sys.exit(1)


@processing.command()
@click.argument('session_id')
@click.argument('status', type=click.Choice(['not_started', 'in_progress', 'complete']))
@click.option('--notes', '-n', help='Update processing notes')
@click.pass_context
def update_status(ctx, session_id, status, notes):
    """Update processing session status."""
    config_path = ctx.obj['config_path']
    verbose = ctx.obj['verbose']
    
    try:
        config, cameras, telescopes, filter_mappings = load_config(config_path)
        setup_logging(config, verbose)
        
        cataloger = FitsCataloger(config, cameras, telescopes, filter_mappings)
        processing_manager = ProcessingSessionManager(config, cataloger.db_service)
        
        success = processing_manager.update_session_status(session_id, status, notes)
        
        if success:
            click.echo(f"✓ Updated session {session_id} status to: {status}")
            if notes:
                click.echo("✓ Updated processing notes")
        else:
            click.echo(f"Processing session '{session_id}' not found.")
        
        cataloger.cleanup()
        
    except Exception as e:
        click.echo(f"Error updating processing session: {e}")
        sys.exit(1)


@processing.command()
@click.argument('session_id')
@click.option('--keep-files', is_flag=True, help='Keep staged files (remove only database records)')
@click.option('--force', is_flag=True, help='Skip confirmation prompt')
@click.pass_context
def delete(ctx, session_id, keep_files, force):
    """Delete a processing session."""
    config_path = ctx.obj['config_path']
    verbose = ctx.obj['verbose']
    
    try:
        config, cameras, telescopes, filter_mappings = load_config(config_path)
        setup_logging(config, verbose)
        
        cataloger = FitsCataloger(config, cameras, telescopes, filter_mappings)
        processing_manager = ProcessingSessionManager(config, cataloger.db_service)
        
        # Show session info before deletion
        session = processing_manager.get_processing_session(session_id)
        if not session:
            click.echo(f"Processing session '{session_id}' not found.")
            return
        
        click.echo(f"Processing session: {session.name}")
        click.echo(f"Folder: {session.folder_path}")
        click.echo(f"Files: {session.total_files}")
        
        if not force:
            action = "database records only" if keep_files else "session and all staged files"
            if not click.confirm(f"Delete {action}?"):
                return
        
        success = processing_manager.delete_processing_session(session_id, remove_files=not keep_files)
        
        if success:
            click.echo(f"✓ Deleted processing session {session_id}")
            if not keep_files:
                click.echo("✓ Removed staged files and folders")
        else:
            click.echo(f"Processing session '{session_id}' not found.")
        
        cataloger.cleanup()
        
    except Exception as e:
        click.echo(f"Error deleting processing session: {e}")
        sys.exit(1)


@processing.command()
@click.argument('session_id')
@click.pass_context
def open_folder(ctx, session_id):
    """Open the processing session folder in file manager."""
    config_path = ctx.obj['config_path']
    verbose = ctx.obj['verbose']
    
    try:
        config, cameras, telescopes, filter_mappings = load_config(config_path)
        setup_logging(config, verbose)
        
        cataloger = FitsCataloger(config, cameras, telescopes, filter_mappings)
        processing_manager = ProcessingSessionManager(config, cataloger.db_service)
        
        session = processing_manager.get_processing_session(session_id)
        if not session:
            click.echo(f"Processing session '{session_id}' not found.")
            return
        
        folder_path = Path(session.folder_path)
        if not folder_path.exists():
            click.echo(f"Session folder does not exist: {folder_path}")
            return
        
        # Try to open folder in file manager
        import subprocess
        import platform
        
        system = platform.system()
        try:
            if system == "Windows":
                subprocess.run(["explorer", str(folder_path)])
            elif system == "Darwin":  # macOS
                subprocess.run(["open", str(folder_path)])
            else:  # Linux and others
                subprocess.run(["xdg-open", str(folder_path)])
            
            click.echo(f"Opened folder: {folder_path}")
        except Exception as e:
            click.echo(f"Could not open folder automatically: {e}")
            click.echo(f"Manual path: {folder_path}")
        
        cataloger.cleanup()
        
    except Exception as e:
        click.echo(f"Error opening folder: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli()