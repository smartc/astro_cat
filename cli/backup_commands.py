"""Backup commands for S3 cloud storage."""

import sys

import click

from cli.utils import (
    load_app_config,
    setup_logging,
    handle_error
)
from models import DatabaseService, ProcessingSession
from s3_backup.manager import S3BackupConfig
from s3_backup.processing_file_backup import ProcessingSessionFileBackup


def register_commands(cli):
    """Register backup commands with main CLI."""

    @cli.command('backup')
    @click.argument('target', type=click.Choice(['raw', 'processed', 'database']))
    @click.option('--processing-session', '-s', help='Processing session ID (for processed files)')
    @click.option('--all-sessions', is_flag=True, help='Backup all processing sessions')
    @click.option('--incomplete', is_flag=True, help='Only backup sessions with incomplete backups')
    @click.option('--subfolder', multiple=True,
                  type=click.Choice(['final', 'intermediate']),
                  help='Specific subfolder(s) to backup')
    @click.option('--file-type', '-t', multiple=True,
                  help='Specific file type(s) to backup (e.g., xisf, jpg)')
    @click.option('--force', is_flag=True, help='Force backup even if unchanged')
    @click.option('--not-backed-up', is_flag=True, help='Only backup files not yet in S3 (raw only)')
    @click.option('--year', type=int, help='Backup files from specific year (raw only)')
    @click.option('--imaging-session', help='Backup specific imaging session (raw only)')
    @click.pass_context
    def backup(ctx, target, processing_session, all_sessions, incomplete,
               subfolder, file_type, force, not_backed_up, year, imaging_session):
        """Upload files to S3 cloud storage.

        TARGET: Type of files to backup (raw, processed, database)

        RAW FILES:
            Backup FITS files from library to S3.
            Can filter by year, imaging session, or backup status.
            Uses: python -m s3_backup.cli upload

        PROCESSED FILES:
            Backup processing session outputs to S3.
            Can filter by session, subfolder (final/intermediate), file type.

        DATABASE:
            Backup database file to S3.
            Creates dated snapshot of complete database.

        Examples:
            # Backup all non-backed-up raw files
            python -m main backup raw --not-backed-up

            # Backup raw files from 2024
            python -m main backup raw --year 2024

            # Backup specific imaging session
            python -m main backup raw --imaging-session 20240815_001

            # Backup specific processing session
            python -m main backup processed --processing-session 20250115_ABC123

            # Backup all processing sessions
            python -m main backup processed --all-sessions

            # Backup only final outputs
            python -m main backup processed --processing-session ID --subfolder final

            # Backup specific file types
            python -m main backup processed --processing-session ID --file-type xisf --file-type jpg

            # Backup database
            python -m main backup database
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            if target == 'raw':
                _backup_raw_files(not_backed_up, year, imaging_session, verbose)
            elif target == 'processed':
                _backup_processed_files(
                    config_path, processing_session, all_sessions, incomplete,
                    subfolder, file_type, force, verbose
                )
            elif target == 'database':
                _backup_database(verbose)

        except Exception as e:
            handle_error(e, verbose)


def _backup_raw_files(not_backed_up, year, imaging_session, verbose):
    """Backup raw FITS files to S3.

    Args:
        not_backed_up: Only backup files not yet in S3
        year: Backup files from specific year
        imaging_session: Backup specific imaging session
        verbose: Verbose output flag
    """
    click.echo("Raw file backup delegates to S3 backup CLI.")
    click.echo("\nUse the following command:")

    cmd = "python -m s3_backup.cli upload"

    if not_backed_up:
        cmd += " --not-backed-up"
    if year:
        cmd += f" --year {year}"
    if imaging_session:
        cmd += f" --imaging-session {imaging_session}"

    click.echo(f"  {cmd}")
    click.echo("\nFor more options, see: python -m s3_backup.cli upload --help")


def _backup_processed_files(config_path, session_id, all_sessions, incomplete,
                            subfolder, file_type, force, verbose):
    """Backup processed files to S3.

    Args:
        config_path: Configuration file path
        session_id: Specific processing session ID
        all_sessions: Backup all sessions
        incomplete: Only backup incomplete sessions
        subfolder: Specific subfolders to backup
        file_type: Specific file types to backup
        force: Force backup even if unchanged
        verbose: Verbose output flag
    """
    if not session_id and not all_sessions:
        click.echo("Error: Specify --processing-session or --all-sessions")
        click.echo("\nExamples:")
        click.echo("  python -m main backup processed --processing-session 20250115_ABC123")
        click.echo("  python -m main backup processed --all-sessions")
        sys.exit(1)

    try:
        config, cameras, telescopes, filter_mappings = load_app_config(config_path)
        setup_logging(config, verbose)

        s3_config_path = 's3_config.json'
        s3_config = S3BackupConfig(s3_config_path)

        if not s3_config.enabled:
            click.echo("✗ S3 backup is not enabled in configuration")
            click.echo("  Edit s3_config.json to enable S3 backup")
            sys.exit(1)

        db_service = DatabaseService(config)
        backup_manager = ProcessingSessionFileBackup(config, s3_config, db_service)

        if session_id:
            _backup_single_session(
                backup_manager, db_service, session_id,
                subfolder, file_type, force
            )
        elif all_sessions:
            _backup_all_sessions(
                backup_manager, incomplete, subfolder, file_type, force
            )

    except Exception as e:
        click.echo(f"Error: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _backup_single_session(backup_manager, db_service, session_id,
                           subfolder, file_type, force):
    """Backup a single processing session.

    Args:
        backup_manager: Backup manager instance
        db_service: Database service
        session_id: Session ID to backup
        subfolder: Specific subfolders
        file_type: Specific file types
        force: Force backup
    """
    # Verify session exists
    db_session = db_service.db_manager.get_session()
    ps = db_session.query(ProcessingSession).filter(
        ProcessingSession.id == session_id
    ).first()

    if not ps:
        click.echo(f"✗ Processing session '{session_id}' not found")
        db_session.close()
        sys.exit(1)

    click.echo(f"Backing up: {ps.name}")
    click.echo(f"Session ID: {session_id}")
    if subfolder:
        click.echo(f"Subfolders: {', '.join(subfolder)}")
    if file_type:
        click.echo(f"File types: {', '.join(file_type)}")
    click.echo()

    db_session.close()

    # Perform backup
    subfolders = list(subfolder) if subfolder else None
    file_types = list(file_type) if file_type else None

    stats = backup_manager.backup_session_files(
        session_id=session_id,
        subfolders=subfolders,
        file_types=file_types,
        force=force
    )

    # Display results
    _display_backup_stats(stats, backup_manager)


def _backup_all_sessions(backup_manager, incomplete, subfolder, file_type, force):
    """Backup all processing sessions.

    Args:
        backup_manager: Backup manager instance
        incomplete: Only backup incomplete sessions
        subfolder: Specific subfolders
        file_type: Specific file types
        force: Force backup
    """
    click.echo("Backing up all processing sessions...")
    if incomplete:
        click.echo("(Only sessions with incomplete backups)")
    click.echo()

    # Note: This functionality would need to be implemented in ProcessingSessionFileBackup
    # For now, show a helpful message
    click.echo("Batch backup not yet implemented in new CLI.")
    click.echo("Use the old CLI for now:")
    click.echo("  python main.py processed backup-all")
    if incomplete:
        click.echo("    --incomplete")
    if force:
        click.echo("    --force")


def _display_backup_stats(stats, backup_manager):
    """Display backup statistics.

    Args:
        stats: Backup statistics dict
        backup_manager: Backup manager for formatting
    """
    click.echo()
    click.echo("=" * 70)
    click.echo("BACKUP SUMMARY")
    click.echo("=" * 70)
    click.echo(f"Total files:     {stats['total_files']}")
    click.echo(f"Uploaded:        {stats['uploaded']}")
    click.echo(f"Skipped:         {stats['skipped']} (already backed up)")
    click.echo(f"Failed:          {stats['failed']}")
    click.echo(f"Total size:      {backup_manager._format_bytes(stats['total_size'])}")
    click.echo("=" * 70)

    if stats.get('errors'):
        click.echo()
        click.echo("Errors:")
        for error in stats['errors']:
            click.echo(f"  - {error['file']}: {error['error']}")

    if stats['failed'] > 0:
        sys.exit(1)


def _backup_database(verbose):
    """Backup database file to S3.

    Args:
        verbose: Verbose output flag
    """
    click.echo("Database backup not yet implemented in new CLI.")
    click.echo("\nUse the S3 backup CLI for now:")
    click.echo("  python -m s3_backup.cli backup-database")
