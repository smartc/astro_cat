"""Verification commands for checking S3 backup integrity."""

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
    """Register verify commands with main CLI."""

    @cli.command('verify')
    @click.argument('target', type=click.Choice(['raw', 'processed']))
    @click.option('--processing-session', '-s', help='Processing session ID (for processed files)')
    @click.option('--all', 'verify_all', is_flag=True, help='Verify all files/sessions')
    @click.pass_context
    def verify(ctx, target, processing_session, verify_all):
        """Verify S3 backup integrity by checking file hashes.

        TARGET: Type of files to verify (raw, processed)

        RAW FILES:
            Verifies FITS file backups in S3 match local files.
            Compares file sizes and checksums.

        PROCESSED FILES:
            Verifies processing session file backups in S3.
            Checks all files in session against S3 records.

        Examples:
            # Verify all raw files
            python -m main verify raw --all

            # Verify specific processing session
            python -m main verify processed --processing-session 20250115_ABC123

            # Verify all processing sessions
            python -m main verify processed --all
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            if target == 'raw':
                _verify_raw_files(verify_all, verbose)
            elif target == 'processed':
                _verify_processed_files(config_path, processing_session, verify_all, verbose)

        except Exception as e:
            handle_error(e, verbose)


def _verify_raw_files(verify_all, verbose):
    """Verify raw FITS file backups in S3.

    Args:
        verify_all: Verify all files
        verbose: Verbose output flag
    """
    click.echo("Raw file verification delegates to S3 backup CLI.")
    click.echo("\nUse the following command:")

    cmd = "python -m s3_backup.cli verify"

    if verify_all:
        cmd += " --all"

    click.echo(f"  {cmd}")
    click.echo("\nFor more options, see: python -m s3_backup.cli verify --help")


def _verify_processed_files(config_path, session_id, verify_all, verbose):
    """Verify processed file backups in S3.

    Args:
        config_path: Configuration file path
        session_id: Specific processing session ID
        verify_all: Verify all sessions
        verbose: Verbose output flag
    """
    if not session_id and not verify_all:
        click.echo("Error: Specify --processing-session or --all")
        click.echo("\nExamples:")
        click.echo("  python -m main verify processed --processing-session 20250115_ABC123")
        click.echo("  python -m main verify processed --all")
        sys.exit(1)

    try:
        config, cameras, telescopes, filter_mappings = load_app_config(config_path)
        setup_logging(config, verbose)

        s3_config_path = 's3_config.json'
        s3_config = S3BackupConfig(s3_config_path)

        if not s3_config.enabled:
            click.echo("✗ S3 backup is not enabled in configuration")
            sys.exit(1)

        db_service = DatabaseService(config)
        backup_manager = ProcessingSessionFileBackup(config, s3_config, db_service)

        if session_id:
            _verify_single_session(backup_manager, db_service, session_id, verbose)
        else:
            click.echo("Verify all sessions not yet implemented.")
            click.echo("Verify individual sessions:")
            click.echo("  python -m main verify processed --processing-session <ID>")

    except Exception as e:
        click.echo(f"Error: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _verify_single_session(backup_manager, db_service, session_id, verbose):
    """Verify a single processing session backup.

    Args:
        backup_manager: Backup manager instance
        db_service: Database service
        session_id: Session ID to verify
        verbose: Verbose output flag
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

    click.echo(f"Verifying: {ps.name}")
    click.echo(f"Session ID: {session_id}")
    click.echo()

    db_session.close()

    # Perform verification
    try:
        results = backup_manager.verify_session_backup(session_id)

        click.echo()
        click.echo("=" * 70)
        click.echo("VERIFICATION RESULTS")
        click.echo("=" * 70)
        click.echo(f"Total files:     {results.get('total', 0)}")
        click.echo(f"Verified OK:     {results.get('verified', 0)}")
        click.echo(f"Missing in S3:   {results.get('missing', 0)}")
        click.echo(f"Hash mismatch:   {results.get('mismatch', 0)}")
        click.echo(f"Errors:          {results.get('errors', 0)}")
        click.echo("=" * 70)

        if results.get('missing', 0) > 0:
            click.echo("\n⚠  Some files are missing from S3 backup")
            click.echo("   Run backup again to upload missing files")

        if results.get('mismatch', 0) > 0:
            click.echo("\n⚠  Some files have hash mismatches")
            click.echo("   Run backup with --force to re-upload")

        if results.get('verified', 0) == results.get('total', 0):
            click.echo("\n✓ All files verified successfully")

    except AttributeError:
        # verify_session_backup may not exist in ProcessingSessionFileBackup
        click.echo("Verification not yet fully implemented.")
        click.echo("Use the old CLI for now:")
        click.echo(f"  python main.py processed backup-verify {session_id}")
