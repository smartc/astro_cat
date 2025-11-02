"""Commands for managing auto-detected imaging sessions."""

import click

from cli.utils import (
    load_app_config,
    setup_logging,
    handle_error,
    get_db_service
)
from models import ImagingSession, FitsFile


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
            python -m main imaging-session info 20240815_001
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            db_service = get_db_service(config, cameras, telescopes, filter_mappings)
            db_session = db_service.db_manager.get_session()

            session = db_session.query(ImagingSession).filter(
                ImagingSession.id == session_id
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
            click.echo(f"\nSession ID:  {session.id}")
            click.echo(f"Date:        {session.date or 'Unknown'}")
            click.echo(f"Camera:      {session.camera or 'Unknown'}")
            click.echo(f"Telescope:   {session.telescope or '-'}")
            click.echo(f"Location:    {session.location or 'Unknown'}")

            # Get files in this session
            files = db_session.query(FitsFile).filter(
                FitsFile.imaging_session_id == session_id
            ).all()

            click.echo(f"File Count:  {len(files)}")

            # Show file breakdown by frame type
            if files:
                frame_types = {}
                for f in files:
                    ft = f.frame_type or 'UNKNOWN'
                    frame_types[ft] = frame_types.get(ft, 0) + 1

                click.echo("\nFrame Types:")
                for ft, count in sorted(frame_types.items()):
                    click.echo(f"  {ft}: {count}")

                # Show file list
                click.echo("\nFiles:")
                for f in files:
                    telescope_display = f.telescope or '-'
                    click.echo(f"  {f.file:40s}  {f.frame_type:10s}  Telescope: {telescope_display:15s}  Score: {f.validation_score or 0}")

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
            python -m main imaging-session notes 20240815_001 "Clear skies, excellent seeing"
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            db_service = get_db_service(config, cameras, telescopes, filter_mappings)
            db_session = db_service.db_manager.get_session()

            session = db_session.query(ImagingSession).filter(
                ImagingSession.id == session_id
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
