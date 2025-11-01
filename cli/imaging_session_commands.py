"""Commands for managing auto-detected imaging sessions."""

import click

from cli.utils import (
    load_app_config,
    setup_logging,
    handle_error,
    get_db_service
)
from models import Session


def register_commands(cli):
    """Register imaging-session commands with main CLI."""

    @cli.group('imaging-session')
    @click.pass_context
    def imaging_session_group(ctx):
        """Manage auto-detected imaging sessions.

        Imaging sessions are automatically detected from FITS file metadata
        during the catalog process. Each session represents a group of files
        captured together (same date, equipment, location).
        """
        pass

    @imaging_session_group.command('info')
    @click.argument('session_id')
    @click.pass_context
    def session_info(ctx, session_id):
        """Show detailed information about an imaging session.

        Examples:
            python main_v2.py imaging-session info 20240815_001
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            db_service = get_db_service(config)
            db_session = db_service.db_manager.get_session()

            session = db_session.query(Session).filter(
                Session.session_id == session_id
            ).first()

            if not session:
                click.echo(f"✗ Imaging session '{session_id}' not found")
                db_session.close()
                return

            # Get session details
            click.echo()
            click.echo("=" * 70)
            click.echo("IMAGING SESSION INFO")
            click.echo("=" * 70)
            click.echo(f"\nSession ID:  {session.session_id}")
            click.echo(f"Date:        {session.session_date or 'Unknown'}")
            click.echo(f"Camera:      {session.camera or 'Unknown'}")
            click.echo(f"Telescope:   {session.telescope or 'Unknown'}")
            click.echo(f"Location:    {session.location or 'Unknown'}")
            click.echo(f"File Count:  {session.file_count or 0}")

            if session.notes:
                click.echo(f"\nNotes:\n{session.notes}")

            click.echo("=" * 70)

            db_session.close()

        except Exception as e:
            handle_error(e, verbose)

    @imaging_session_group.command('notes')
    @click.argument('session_id')
    @click.argument('notes')
    @click.pass_context
    def session_notes(ctx, session_id, notes):
        """Add or update notes for an imaging session.

        Examples:
            python main_v2.py imaging-session notes 20240815_001 "Clear skies, excellent seeing"
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            db_service = get_db_service(config)
            db_session = db_service.db_manager.get_session()

            session = db_session.query(Session).filter(
                Session.session_id == session_id
            ).first()

            if not session:
                click.echo(f"✗ Imaging session '{session_id}' not found")
                db_session.close()
                return

            session.notes = notes
            db_session.commit()
            db_session.close()

            click.echo(f"✓ Updated notes for session {session_id}")

        except Exception as e:
            handle_error(e, verbose)
