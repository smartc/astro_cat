"""File scanning commands for raw and processed files."""

import sys
from pathlib import Path

import click

from cli.utils import (
    load_app_config,
    setup_logging,
    handle_error
)
from file_monitor import FileMonitor
from processed_catalog import ProcessedFileCataloger


def register_commands(cli):
    """Register scan commands with main CLI."""

    @cli.command('scan')
    @click.argument('target', type=click.Choice(['raw', 'processed', 'all']))
    @click.option('--processing-session', '-s', help='Scan specific processing session (for processed files)')
    @click.option('--all-sessions', is_flag=True, help='Scan all processing sessions (for processed files)')
    @click.pass_context
    def scan(ctx, target, processing_session, all_sessions):
        """Scan for new files in quarantine or processing directories.

        TARGET: Type of files to scan (raw, processed, all)

        RAW FILES:
            Scans quarantine directory for new FITS files.
            Files are found but NOT added to database until 'catalog' is run.

        PROCESSED FILES:
            Scans processing session folders for output files (JPG, XISF, XOSM, etc).
            Requires --processing-session or --all-sessions option.

        Examples:
            # Scan for new raw FITS files in quarantine
            python -m main scan raw

            # Scan specific processing session for outputs
            python -m main scan processed --processing-session 20251010_022B0AE9

            # Scan all processing sessions
            python -m main scan processed --all-sessions

            # Scan both raw and processed files
            python -m main scan all
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            if target in ['raw', 'all']:
                _scan_raw_files(config, verbose)

            if target in ['processed', 'all']:
                if not processing_session and not all_sessions:
                    click.echo("Error: For processed files, specify --processing-session or --all-sessions")
                    click.echo("\nExamples:")
                    click.echo("  python -m main scan processed --processing-session 20251010_022B0AE9")
                    click.echo("  python -m main scan processed --all-sessions")
                    sys.exit(1)

                _scan_processed_files(config, processing_session, all_sessions, verbose)

        except Exception as e:
            handle_error(e, verbose)


def _scan_raw_files(config, verbose):
    """Scan quarantine directory for raw FITS files.

    Args:
        config: Application configuration
        verbose: Verbose output flag
    """
    click.echo("Scanning quarantine directory for raw FITS files...")

    file_monitor = FileMonitor(config, lambda x: None)  # Dummy callback
    fits_files = file_monitor.scan_quarantine()

    if not fits_files:
        click.echo("✓ No new files found in quarantine directory")
        return

    click.echo(f"✓ Found {len(fits_files)} FITS files in quarantine")
    click.echo("\nNext step: Run 'catalog raw' to extract metadata and add to database")
    click.echo("  python -m main catalog raw")


def _scan_processed_files(config, session_id, scan_all, verbose):
    """Scan processing session folders for processed output files.

    Args:
        config: Application configuration
        session_id: Specific session ID to scan (optional)
        scan_all: Whether to scan all sessions
        verbose: Verbose output flag
    """
    click.echo("Scanning processing sessions for output files...")

    try:
        # Note: ProcessedFileCataloger both scans and catalogs in one operation
        # This is a design decision in the original code that we're preserving
        cataloger = ProcessedFileCataloger(config.paths.database_path)

        if scan_all:
            processing_dir = Path(config.paths.processing_dir)
            if not processing_dir.exists():
                click.echo(f"✗ Processing directory not found: {processing_dir}")
                sys.exit(1)

            click.echo(f"Scanning all sessions in: {processing_dir}")
            cataloger.run(processing_dir)

        elif session_id:
            click.echo(f"Scanning session: {session_id}")
            cataloger.run(Path('.'), session_id)

        click.echo("✓ Scan complete")
        click.echo("\nNote: Processed files are automatically cataloged during scan")

    except Exception as e:
        click.echo(f"Error scanning processed files: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
