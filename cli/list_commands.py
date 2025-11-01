"""List commands for querying database records."""

import sys

import click

from cli.utils import (
    load_app_config,
    setup_logging,
    handle_error,
    get_db_service,
    format_table_row
)
# Import all models from main models.py
from models import FitsFile, ImagingSession, ProcessingSession, Camera, Telescope, FilterMapping, ProcessedFile


def register_commands(cli):
    """Register list commands with main CLI."""

    @cli.group('list')
    @click.pass_context
    def list_group(ctx):
        """Query and list database records.

        List raw files, processed files, sessions, equipment, and more.
        """
        pass

    @list_group.command('raw')
    @click.option('--object', '-o', help='Filter by object name')
    @click.option('--camera', '-c', help='Filter by camera name')
    @click.option('--telescope', '-t', help='Filter by telescope name')
    @click.option('--filter', '-f', 'filter_name', help='Filter by filter name')
    @click.option('--frame-type', type=click.Choice(['Light', 'Dark', 'Flat', 'Bias']),
                  help='Filter by frame type')
    @click.option('--limit', '-l', type=int, default=50, help='Limit results (default: 50)')
    @click.pass_context
    def list_raw(ctx, object, camera, telescope, filter_name, frame_type, limit):
        """List raw FITS files from catalog.

        Examples:
            # List recent files
            python main_v2.py list raw

            # Find files for specific object
            python main_v2.py list raw --object "M31"

            # Filter by equipment
            python main_v2.py list raw --camera "ASI2600MM" --telescope "EF200"

            # Find light frames with specific filter
            python main_v2.py list raw --frame-type Light --filter Ha

            # Show more results
            python main_v2.py list raw --limit 100
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            db_service = get_db_service(config)
            db_session = db_service.db_manager.get_session()

            # Build query
            query = db_session.query(FitsFile)

            if object:
                query = query.filter(FitsFile.object_name.ilike(f'%{object}%'))
            if camera:
                query = query.filter(FitsFile.camera_name.ilike(f'%{camera}%'))
            if telescope:
                query = query.filter(FitsFile.telescope_name.ilike(f'%{telescope}%'))
            if filter_name:
                query = query.filter(FitsFile.filter_name.ilike(f'%{filter_name}%'))
            if frame_type:
                query = query.filter(FitsFile.frame_type == frame_type)

            # Order by date descending
            query = query.order_by(FitsFile.date_obs.desc())

            # Apply limit
            files = query.limit(limit).all()

            db_session.close()

            if not files:
                click.echo("No files found matching criteria")
                return

            # Display results
            click.echo(f"\nFound {len(files)} files (showing up to {limit}):\n")
            click.echo(format_table_row(
                ['ID', 'Object', 'Frame', 'Filter', 'Exp(s)', 'Camera', 'Date'],
                [6, 20, 8, 10, 8, 15, 20]
            ))
            click.echo("-" * 100)

            for f in files:
                click.echo(format_table_row(
                    [
                        str(f.id),
                        (f.object_name or 'Unknown')[:20],
                        (f.frame_type or 'N/A')[:8],
                        (f.filter_name or 'N/A')[:10],
                        f"{f.exposure_time:.1f}" if f.exposure_time else 'N/A',
                        (f.camera_name or 'Unknown')[:15],
                        str(f.date_obs)[:19] if f.date_obs else 'N/A'
                    ],
                    [6, 20, 8, 10, 8, 15, 20]
                ))

        except Exception as e:
            handle_error(e, verbose)

    @list_group.command('processed')
    @click.option('--processing-session', '-s', help='Filter by processing session ID')
    @click.option('--file-type', '-t',
                  type=click.Choice(['jpg', 'jpeg', 'xisf', 'xosm', 'pxiproject', 'all']),
                  default='all', help='Filter by file type')
    @click.option('--subfolder', type=click.Choice(['final', 'intermediate', 'all']),
                  default='all', help='Filter by subfolder')
    @click.option('--limit', '-l', type=int, default=50, help='Limit results')
    @click.pass_context
    def list_processed(ctx, processing_session, file_type, subfolder, limit):
        """List processed output files.

        Examples:
            # List all processed files
            python main_v2.py list processed

            # List files for specific session
            python main_v2.py list processed --processing-session 20250115_ABC123

            # List only final JPG files
            python main_v2.py list processed --file-type jpg --subfolder final
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            db_service = get_db_service(config)
            db_session = db_service.db_manager.get_session()

            # Build query
            query = db_session.query(ProcessedFile)

            if processing_session:
                query = query.filter(ProcessedFile.processing_session_id == processing_session)

            if file_type != 'all':
                if file_type == 'jpeg':
                    query = query.filter(ProcessedFile.file_type.in_(['jpg', 'jpeg']))
                else:
                    query = query.filter(ProcessedFile.file_type == file_type)

            if subfolder != 'all':
                query = query.filter(ProcessedFile.subfolder == subfolder)

            # Order by created date
            query = query.order_by(ProcessedFile.created_at.desc())

            # Apply limit
            files = query.limit(limit).all()

            db_session.close()

            if not files:
                click.echo("No processed files found")
                return

            # Display results
            click.echo(f"\nFound {len(files)} files:\n")
            click.echo(format_table_row(
                ['ID', 'Session', 'Type', 'Subfolder', 'Filename'],
                [6, 20, 10, 12, 40]
            ))
            click.echo("-" * 100)

            for f in files:
                click.echo(format_table_row(
                    [
                        str(f.id),
                        (f.processing_session_id or 'N/A')[:20],
                        (f.file_type or 'N/A')[:10],
                        (f.subfolder or 'N/A')[:12],
                        (f.filename or 'N/A')[:40]
                    ],
                    [6, 20, 10, 12, 40]
                ))

        except Exception as e:
            handle_error(e, verbose)

    @list_group.command('imaging-sessions')
    @click.option('--recent', '-r', type=int, default=20, help='Show recent N sessions')
    @click.option('--camera', '-c', help='Filter by camera')
    @click.option('--telescope', '-t', help='Filter by telescope')
    @click.pass_context
    def list_imaging_sessions(ctx, recent, camera, telescope):
        """List auto-detected imaging sessions.

        Examples:
            # List 20 most recent sessions
            python main_v2.py list imaging-sessions

            # List 50 recent sessions
            python main_v2.py list imaging-sessions --recent 50

            # Filter by equipment
            python main_v2.py list imaging-sessions --camera ASI2600MM
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            db_service = get_db_service(config)
            sessions = db_service.get_sessions()

            if camera:
                sessions = [s for s in sessions if s.camera and camera.lower() in s.camera.lower()]
            if telescope:
                sessions = [s for s in sessions if s.telescope and telescope.lower() in s.telescope.lower()]

            # Limit to recent N
            sessions = sessions[:recent]

            if not sessions:
                click.echo("No imaging sessions found")
                return

            click.echo(f"\nFound {len(sessions)} imaging sessions:\n")
            click.echo(format_table_row(
                ['Session ID', 'Date', 'Camera', 'Telescope', 'Files'],
                [25, 12, 20, 20, 8]
            ))
            click.echo("-" * 100)

            for s in sessions:
                click.echo(format_table_row(
                    [
                        (s.id or 'N/A')[:25],
                        (str(s.date) if s.date else 'N/A')[:12],
                        (s.camera or 'Unknown')[:20],
                        (s.telescope or 'Unknown')[:20],
                        str(s.file_count or 0)
                    ],
                    [25, 12, 20, 20, 8]
                ))

        except Exception as e:
            handle_error(e, verbose)

    @list_group.command('processing-sessions')
    @click.option('--status', type=click.Choice(['not_started', 'in_progress', 'complete']),
                  help='Filter by status')
    @click.option('--limit', '-l', type=int, default=50, help='Limit results')
    @click.pass_context
    def list_processing_sessions(ctx, status, limit):
        """List user-created processing sessions.

        Examples:
            # List all processing sessions
            python main_v2.py list processing-sessions

            # Filter by status
            python main_v2.py list processing-sessions --status in_progress
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            db_service = get_db_service(config)
            db_session = db_service.db_manager.get_session()

            # Build query
            query = db_session.query(ProcessingSession)

            if status:
                query = query.filter(ProcessingSession.status == status)

            # Order by created date
            query = query.order_by(ProcessingSession.created_at.desc())

            sessions = query.limit(limit).all()
            db_session.close()

            if not sessions:
                click.echo("No processing sessions found")
                return

            click.echo(f"\nFound {len(sessions)} processing sessions:\n")
            click.echo(format_table_row(
                ['ID', 'Name', 'Status', 'Files', 'Created'],
                [25, 30, 15, 8, 20]
            ))
            click.echo("-" * 110)

            for s in sessions:
                # Count files
                db_session = db_service.db_manager.get_session()
                file_count = db_session.query(FitsFile).join(
                    FitsFile.processing_sessions
                ).filter(ProcessingSession.id == s.id).count()
                db_session.close()

                click.echo(format_table_row(
                    [
                        (s.id or 'N/A')[:25],
                        (s.name or 'N/A')[:30],
                        (s.status or 'N/A')[:15],
                        str(file_count),
                        str(s.created_at)[:19] if s.created_at else 'N/A'
                    ],
                    [25, 30, 15, 8, 20]
                ))

        except Exception as e:
            handle_error(e, verbose)

    @list_group.command('cameras')
    @click.pass_context
    def list_cameras(ctx):
        """List configured cameras."""
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, cameras, _, _ = load_app_config(config_path)

            click.echo(f"\nConfigured cameras ({len(cameras)}):\n")
            for cam in cameras:
                click.echo(f"  {cam.camera}: {cam.x}x{cam.y} pixels, {cam.pixel}μm pixel size")

        except Exception as e:
            handle_error(e, verbose)

    @list_group.command('telescopes')
    @click.pass_context
    def list_telescopes(ctx):
        """List configured telescopes."""
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, _, telescopes, _ = load_app_config(config_path)

            click.echo(f"\nConfigured telescopes ({len(telescopes)}):\n")
            for tel in telescopes:
                click.echo(f"  {tel.scope}: {tel.focal}mm focal length")

        except Exception as e:
            handle_error(e, verbose)

    @list_group.command('filters')
    @click.pass_context
    def list_filters(ctx):
        """List configured filters."""
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, _, _, filter_mappings = load_app_config(config_path)

            click.echo(f"\nConfigured filters ({len(filter_mappings)}):\n")
            for original, mapped in sorted(filter_mappings.items()):
                click.echo(f"  {original} → {mapped}")

        except Exception as e:
            handle_error(e, verbose)
