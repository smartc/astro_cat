"""Cataloging commands for adding file metadata to database."""

import sys

import click
from tqdm import tqdm

from cli.utils import (
    load_app_config,
    setup_logging,
    handle_error,
    get_db_service
)
from file_monitor import FileMonitor
from processing import OptimizedFitsProcessor


def register_commands(cli):
    """Register catalog commands with main CLI."""

    @cli.command('catalog')
    @click.argument('target', type=click.Choice(['raw', 'processed']))
    @click.option('--processing-session', '-s', help='Catalog files for specific processing session (processed only)')
    @click.option('--all-sessions', is_flag=True, help='Catalog all processing sessions (processed only)')
    @click.pass_context
    def catalog(ctx, target, processing_session, all_sessions):
        """Extract metadata and add files to database catalog.

        TARGET: Type of files to catalog (raw, processed)

        RAW FILES:
            Extracts FITS metadata from quarantine files and adds to database.
            Auto-detects imaging sessions from metadata.
            Run 'scan raw' first to find files.

        PROCESSED FILES:
            Catalogs processed output files (JPG, XISF, XOSM, etc).
            Note: 'scan processed' already catalogs files automatically.

        Examples:
            # Catalog raw FITS files from quarantine
            python main_v2.py catalog raw

            # Catalog processed files for specific session
            python main_v2.py catalog processed --processing-session 20251010_022B0AE9

            # Catalog all processed files
            python main_v2.py catalog processed --all-sessions
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            if target == 'raw':
                _catalog_raw_files(config, cameras, telescopes, filter_mappings, verbose)
            elif target == 'processed':
                # Note: Processed file scanning and cataloging happen together
                # We maintain this for consistency but inform the user
                click.echo("Note: For processed files, 'scan processed' already catalogs files.")
                click.echo("Use 'scan processed' instead:")
                if processing_session:
                    click.echo(f"  python main_v2.py scan processed --processing-session {processing_session}")
                elif all_sessions:
                    click.echo("  python main_v2.py scan processed --all-sessions")
                else:
                    click.echo("  python main_v2.py scan processed --processing-session <ID>")
                    click.echo("  python main_v2.py scan processed --all-sessions")

        except Exception as e:
            handle_error(e, verbose)


def _catalog_raw_files(config, cameras, telescopes, filter_mappings, verbose):
    """Catalog raw FITS files from quarantine.

    Args:
        config: Application configuration
        cameras: Camera equipment list
        telescopes: Telescope equipment list
        filter_mappings: Filter name mappings
        verbose: Verbose output flag
    """
    click.echo("Cataloging raw FITS files from quarantine...")

    db_service = get_db_service(config, cameras, telescopes, filter_mappings)

    # Scan for files
    file_monitor = FileMonitor(config, lambda x: None)
    fits_files = file_monitor.scan_quarantine()

    if not fits_files:
        click.echo("✓ No files found in quarantine directory")
        return

    click.echo(f"Found {len(fits_files)} files to process...")

    # Initialize FITS processor
    fits_processor = OptimizedFitsProcessor(
        config,
        cameras,
        telescopes,
        filter_mappings,
        db_service
    )

    # Extract metadata
    click.echo("Extracting metadata from FITS files...")
    df, session_data = fits_processor.process_files_optimized(fits_files)

    if df.is_empty():
        click.echo("✗ No valid metadata extracted from files")
        return

    # Add sessions to database FIRST (before files that reference them)
    session_added_count = 0
    if session_data:
        click.echo(f"Processing {len(session_data)} imaging sessions...")
        for session in session_data:
            try:
                db_service.add_imaging_session(session)
                session_added_count += 1
            except Exception as e:
                if verbose:
                    click.echo(f"Error adding session {session['id']}: {e}")

    # Add files to database (after sessions exist)
    added_count = 0
    duplicate_count = 0
    error_count = 0
    errors = []  # Collect error details

    with tqdm(total=len(df), desc="Adding to database", disable=False) as pbar:
        for row in df.iter_rows(named=True):
            try:
                success, is_duplicate = db_service.add_fits_file(row)
                if success:
                    if is_duplicate:
                        duplicate_count += 1
                    else:
                        added_count += 1
                else:
                    error_count += 1
                    filename = row.get('file', 'unknown')
                    errors.append((filename, "Failed to add to database"))
                pbar.update(1)

            except Exception as e:
                error_count += 1
                filename = row.get('file', 'unknown')
                errors.append((filename, str(e)))
                if verbose:
                    click.echo(f"\nError adding file: {e}")
                pbar.update(1)

    # Clean up any orphaned imaging sessions (sessions with no files)
    orphaned_count = db_service.cleanup_orphaned_imaging_sessions()
    if verbose and orphaned_count > 0:
        click.echo(f"\n✓ Cleaned up {orphaned_count} orphaned imaging sessions")

    # Report results
    click.echo(f"\n✓ Catalog complete:")
    click.echo(f"  New files:         {added_count:>6}")
    click.echo(f"  Duplicates:        {duplicate_count:>6}")
    click.echo(f"  Errors:            {error_count:>6}")
    if session_added_count > 0:
        click.echo(f"  Imaging sessions:  {session_added_count:>6}")

    # Display error details if any occurred
    if errors:
        click.echo("\nErrors encountered:")
        for filename, error_msg in errors:
            click.echo(f"  • {filename}")
            click.echo(f"    {error_msg}")

    click.echo("\nNext steps:")
    click.echo("  1. Validate files:  python -m main validate raw")
    click.echo("  2. Migrate files:   python -m main migrate raw --dry-run")
