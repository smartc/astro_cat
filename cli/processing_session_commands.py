"""Commands for managing user-created processing sessions."""

import sys
from pathlib import Path

import click

from cli.utils import (
    load_app_config,
    setup_logging,
    handle_error,
    get_db_service,
    confirm_action
)
from processing_session_manager import ProcessingSessionManager


def register_commands(cli):
    """Register processing-session commands with main CLI."""

    @cli.group('processing-session')
    @click.pass_context
    def processing_session_group(ctx):
        """Manage user-created processing sessions.

        Processing sessions are user-created projects for organizing files
        for processing workflows (stacking, calibration, integration, etc.).
        """
        pass

    @processing_session_group.command('create')
    @click.argument('name')
    @click.option('--file-ids', '-f',
                  help='Comma-separated list of FITS file IDs (optional - can create empty session)')
    @click.option('--notes', '-n', help='Processing notes (markdown format)')
    @click.option('--dry-run', is_flag=True, help='Show what would be created without actually creating')
    @click.pass_context
    def create(ctx, name, file_ids, notes, dry_run):
        """Create a new processing session with selected FITS files.

        NAME: Name for the processing session

        Examples:
            # Create session with files
            python main_v2.py processing-session create "NGC7000 LRGB" --file-ids "123,124,125,126"

            # Create with notes
            python main_v2.py processing-session create "M31 LRGB" --file-ids "123,124" --notes "First attempt"

            # Create empty session (for manually adding files later)
            python main_v2.py processing-session create "M31 Archive Session" --notes "For importing old data"
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            # Parse comma-separated file IDs if provided
            file_ids_list = []
            if file_ids:
                try:
                    file_ids_list = [int(x.strip()) for x in file_ids.split(',')]
                except ValueError:
                    click.echo("✗ Invalid file IDs format. Use comma-separated integers.")
                    click.echo("  Example: --file-ids '123,124,125'")
                    sys.exit(1)

            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            db_service = get_db_service(config)
            processing_manager = ProcessingSessionManager(config, db_service)

            if dry_run:
                click.echo("Would create processing session:")
                click.echo(f"  Name:     {name}")
                click.echo(f"  File IDs: {file_ids_list if file_ids_list else 'None (empty session)'}")
                click.echo(f"  Notes:    {notes if notes else 'None'}")
                return

            session_info = processing_manager.create_processing_session(
                name=name,
                file_ids=file_ids_list,  # Can be empty list
                notes=notes
            )

            click.echo(f"✓ Created processing session: {session_info.id}")
            click.echo(f"  Name:   {session_info.name}")
            click.echo(f"  Folder: {session_info.folder_path}")
            click.echo(f"  Files:  {session_info.total_files}")

            if session_info.total_files == 0:
                click.echo(f"\n  Note: Empty session created. Add files using:")
                click.echo(f"    python main_v2.py processing-session add-files {session_info.id} --file-ids '<ids>'")

        except Exception as e:
            handle_error(e, verbose)

    @processing_session_group.command('add-files')
    @click.argument('session_id')
    @click.option('--file-ids', '-f', required=True, help='Comma-separated list of FITS file IDs to add')
    @click.option('--dry-run', is_flag=True, help='Show what would be added without actually adding')
    @click.pass_context
    def add_files(ctx, session_id, file_ids, dry_run):
        """Add additional files to an existing processing session.

        Examples:
            python main_v2.py processing-session add-files 20241201_120000_NGC7000 --file-ids "127,128,129"
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            # Parse file IDs
            try:
                file_ids_list = [int(x.strip()) for x in file_ids.split(',')]
            except ValueError:
                click.echo("✗ Invalid file IDs format. Use comma-separated integers.")
                sys.exit(1)

            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            db_service = get_db_service(config)
            processing_manager = ProcessingSessionManager(config, db_service)

            if dry_run:
                click.echo(f"Would add {len(file_ids_list)} files to session {session_id}")
                return

            result = processing_manager.add_files_to_session(session_id, file_ids_list)

            click.echo(f"✓ Added {result['added']} files to session {session_id}")
            if result.get('skipped', 0) > 0:
                click.echo(f"  Skipped: {result['skipped']} (already in session)")

        except Exception as e:
            handle_error(e, verbose)

    @processing_session_group.command('info')
    @click.argument('session_id')
    @click.option('--detailed', '-d', is_flag=True, help='Show detailed file information')
    @click.pass_context
    def info(ctx, session_id, detailed):
        """Show detailed information about a processing session.

        Examples:
            python main_v2.py processing-session info 20241201_120000_NGC7000
            python main_v2.py processing-session info 20241201_120000_NGC7000 --detailed
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            db_service = get_db_service(config)
            processing_manager = ProcessingSessionManager(config, db_service)

            session_info = processing_manager.get_processing_session_info(session_id)

            if not session_info:
                click.echo(f"✗ Processing session '{session_id}' not found")
                sys.exit(1)

            # Display session info
            click.echo()
            click.echo("=" * 70)
            click.echo("PROCESSING SESSION INFO")
            click.echo("=" * 70)
            click.echo(f"\nID:       {session_info.id}")
            click.echo(f"Name:     {session_info.name}")
            click.echo(f"Status:   {session_info.status}")
            click.echo(f"Created:  {session_info.created_at.strftime('%Y-%m-%d %H:%M')}")
            click.echo(f"Folder:   {session_info.folder_path}")

            click.echo(f"\nFiles:    {session_info.total_files} total")
            click.echo(f"  Lights: {session_info.lights}")
            click.echo(f"  Darks:  {session_info.darks}")
            click.echo(f"  Flats:  {session_info.flats}")
            click.echo(f"  Bias:   {session_info.bias}")

            if session_info.objects:
                click.echo(f"\nObjects:  {', '.join(session_info.objects)}")

            if session_info.notes:
                click.echo(f"\nNotes:\n{session_info.notes}")

            if detailed:
                click.echo("\n" + "-" * 70)
                click.echo("FILES:")
                # Note: Detailed file listing would require additional implementation
                click.echo("(Detailed file listing not yet implemented)")

            click.echo("=" * 70)

        except Exception as e:
            handle_error(e, verbose)

    @processing_session_group.command('update-status')
    @click.argument('session_id')
    @click.argument('status', type=click.Choice(['not_started', 'in_progress', 'complete']))
    @click.option('--notes', '-n', help='Optional notes about the status change')
    @click.pass_context
    def update_status(ctx, session_id, status, notes):
        """Update the status of a processing session.

        Examples:
            python main_v2.py processing-session update-status 20241201_120000_NGC7000 in_progress
            python main_v2.py processing-session update-status 20241201_120000_NGC7000 complete --notes "Final stack complete"
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            db_service = get_db_service(config)
            processing_manager = ProcessingSessionManager(config, db_service)

            processing_manager.update_session_status(session_id, status, notes)

            click.echo(f"✓ Updated session {session_id} status to: {status}")
            if notes:
                click.echo(f"  Notes: {notes}")

        except Exception as e:
            handle_error(e, verbose)

    @processing_session_group.command('notes')
    @click.argument('session_id')
    @click.argument('notes')
    @click.pass_context
    def update_notes(ctx, session_id, notes):
        """Update notes for a processing session.

        Examples:
            python main_v2.py processing-session notes 20241201_120000_NGC7000 "Updated processing notes"
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            db_service = get_db_service(config)
            processing_manager = ProcessingSessionManager(config, db_service)

            processing_manager.update_session_notes(session_id, notes)

            click.echo(f"✓ Updated notes for session {session_id}")

        except Exception as e:
            handle_error(e, verbose)

    @processing_session_group.command('open')
    @click.argument('session_id')
    @click.pass_context
    def open_folder(ctx, session_id):
        """Open the processing session folder in file manager.

        Examples:
            python main_v2.py processing-session open 20241201_120000_NGC7000
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            db_service = get_db_service(config)
            processing_manager = ProcessingSessionManager(config, db_service)

            session_info = processing_manager.get_processing_session_info(session_id)

            if not session_info:
                click.echo(f"✗ Processing session '{session_id}' not found")
                sys.exit(1)

            folder_path = Path(session_info.folder_path)

            if not folder_path.exists():
                click.echo(f"✗ Folder does not exist: {folder_path}")
                sys.exit(1)

            # Open folder based on platform
            import platform
            import subprocess

            system = platform.system()
            if system == 'Darwin':  # macOS
                subprocess.run(['open', str(folder_path)])
            elif system == 'Windows':
                subprocess.run(['explorer', str(folder_path)])
            else:  # Linux
                subprocess.run(['xdg-open', str(folder_path)])

            click.echo(f"✓ Opened folder: {folder_path}")

        except Exception as e:
            handle_error(e, verbose)

    @processing_session_group.command('delete')
    @click.argument('session_id')
    @click.option('--keep-files', is_flag=True, help='Keep staged files (remove only database records)')
    @click.option('--force', is_flag=True, help='Skip confirmation prompt')
    @click.pass_context
    def delete(ctx, session_id, keep_files, force):
        """Delete a processing session.

        By default, removes both database records and staged files.
        Use --keep-files to only remove database records.

        Examples:
            # Delete session and all files
            python main_v2.py processing-session delete 20241201_120000_NGC7000

            # Delete only database records
            python main_v2.py processing-session delete 20241201_120000_NGC7000 --keep-files

            # Skip confirmation
            python main_v2.py processing-session delete 20241201_120000_NGC7000 --force
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            db_service = get_db_service(config)
            processing_manager = ProcessingSessionManager(config, db_service)

            if not force:
                action = "database records" if keep_files else "session and all files"
                if not confirm_action(f"Delete {action} for session {session_id}?"):
                    return

            result = processing_manager.delete_processing_session(session_id, keep_files=keep_files)

            if keep_files:
                click.echo(f"✓ Removed database records for session {session_id}")
                click.echo(f"  Files kept in: {result.get('folder_path', 'N/A')}")
            else:
                click.echo(f"✓ Deleted session {session_id}")
                click.echo(f"  Removed {result.get('files_deleted', 0)} files")

        except Exception as e:
            handle_error(e, verbose)

    @processing_session_group.command('archive')
    @click.argument('session_id')
    @click.pass_context
    def archive(ctx, session_id):
        """Archive a processing session (mark as complete and read-only).

        Examples:
            python main_v2.py processing-session archive 20241201_120000_NGC7000
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            # Same as updating status to complete
            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            db_service = get_db_service(config)
            processing_manager = ProcessingSessionManager(config, db_service)

            processing_manager.update_session_status(session_id, 'complete', 'Archived')

            click.echo(f"✓ Archived session {session_id}")

        except Exception as e:
            handle_error(e, verbose)
