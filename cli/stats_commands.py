"""Statistics commands for database and file analysis."""

import click

from cli.utils import (
    load_app_config,
    setup_logging,
    handle_error,
    get_db_service,
    format_size
)
# Import all models from main models.py
from models import FitsFile, ProcessedFile


def register_commands(cli):
    """Register stats commands with main CLI."""

    @cli.group('stats')
    @click.pass_context
    def stats_group(ctx):
        """Display statistics and analysis.

        Get statistics for raw files, processed files, backups, and storage.
        """
        pass

    @stats_group.command('raw')
    @click.pass_context
    def stats_raw(ctx):
        """Show statistics for raw FITS files.

        Displays:
        - Total file count
        - Breakdown by camera
        - Breakdown by telescope
        - Breakdown by frame type
        - Breakdown by filter
        - Session statistics

        Examples:
            python -m main stats raw
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            db_service = get_db_service(config, cameras, telescopes, filter_mappings)
            stats = db_service.get_database_stats()

            click.echo()
            click.echo("=" * 70)
            click.echo("RAW FITS FILE STATISTICS")
            click.echo("=" * 70)
            click.echo(f"\nTotal Files: {stats.get('total_files', 0)}")

            # By Camera
            click.echo("\nBy Camera:")
            for camera, count in sorted(stats.get('by_camera', {}).items()):
                click.echo(f"  {camera:.<40} {count:>6}")

            # By Telescope
            click.echo("\nBy Telescope:")
            for telescope, count in sorted(stats.get('by_telescope', {}).items()):
                click.echo(f"  {telescope:.<40} {count:>6}")

            # By Frame Type
            click.echo("\nBy Frame Type:")
            for frame_type, count in sorted(stats.get('by_frame_type', {}).items()):
                click.echo(f"  {frame_type:.<40} {count:>6}")

            # By Filter (if available)
            if 'by_filter' in stats and stats['by_filter']:
                click.echo("\nBy Filter:")
                for filter_name, count in sorted(stats.get('by_filter', {}).items()):
                    click.echo(f"  {filter_name:.<40} {count:>6}")

            # Session stats
            click.echo("\nImaging Sessions:")
            sessions = db_service.get_imaging_sessions()
            click.echo(f"  Total sessions: {len(sessions)}")

            # Count sessions by camera
            session_cameras = {}
            for session in sessions:
                cam = session.camera or "Unknown"
                session_cameras[cam] = session_cameras.get(cam, 0) + 1

            click.echo("\n  Sessions by camera:")
            for camera, count in sorted(session_cameras.items()):
                click.echo(f"    {camera:.<38} {count:>6}")

            click.echo("=" * 70)

        except Exception as e:
            handle_error(e, verbose)

    @stats_group.command('processed')
    @click.pass_context
    def stats_processed(ctx):
        """Show statistics for processed files.

        Displays:
        - Total file count
        - Breakdown by file type
        - Breakdown by subfolder
        - Breakdown by processing session

        Examples:
            python -m main stats processed
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            db_service = get_db_service(config, cameras, telescopes, filter_mappings)
            db_session = db_service.db_manager.get_session()

            # Get all processed files
            files = db_session.query(ProcessedFile).all()

            # Calculate statistics
            total = len(files)
            by_type = {}
            by_subfolder = {}
            by_session = {}
            total_size = 0

            for f in files:
                # By type
                file_type = f.file_type or 'Unknown'
                by_type[file_type] = by_type.get(file_type, 0) + 1

                # By subfolder
                subfolder = f.subfolder or 'Unknown'
                by_subfolder[subfolder] = by_subfolder.get(subfolder, 0) + 1

                # By session
                session = f.processing_session_id or 'Unknown'
                by_session[session] = by_session.get(session, 0) + 1

                # Total size
                if f.file_size:
                    total_size += f.file_size

            db_session.close()

            click.echo()
            click.echo("=" * 70)
            click.echo("PROCESSED FILE STATISTICS")
            click.echo("=" * 70)
            click.echo(f"\nTotal Files: {total}")
            click.echo(f"Total Size:  {format_size(total_size)}")

            # By File Type
            click.echo("\nBy File Type:")
            for file_type, count in sorted(by_type.items()):
                click.echo(f"  {file_type:.<40} {count:>6}")

            # By Subfolder
            click.echo("\nBy Subfolder:")
            for subfolder, count in sorted(by_subfolder.items()):
                click.echo(f"  {subfolder:.<40} {count:>6}")

            # By Session (top 10)
            click.echo("\nBy Processing Session (top 10):")
            for session, count in sorted(by_session.items(), key=lambda x: x[1], reverse=True)[:10]:
                session_display = session[:35] if len(session) > 35 else session
                click.echo(f"  {session_display:.<40} {count:>6}")

            click.echo("=" * 70)

        except Exception as e:
            handle_error(e, verbose)

    @stats_group.command('backups')
    @click.pass_context
    def stats_backups(ctx):
        """Show S3 backup statistics.

        Displays:
        - Raw files backed up
        - Processed files backed up
        - Backup status by session

        Examples:
            python -m main stats backups
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            db_service = get_db_service(config, cameras, telescopes, filter_mappings)
            db_session = db_service.db_manager.get_session()

            # Raw files backup status
            raw_total = db_session.query(FitsFile).count()
            raw_backed_up = db_session.query(FitsFile).filter(
                FitsFile.s3_key.isnot(None)
            ).count()

            # Processed files backup status
            processed_total = db_session.query(ProcessedFile).count()
            processed_backed_up = db_session.query(ProcessedFile).filter(
                ProcessedFile.s3_key.isnot(None)
            ).count()

            db_session.close()

            click.echo()
            click.echo("=" * 70)
            click.echo("BACKUP STATISTICS")
            click.echo("=" * 70)

            click.echo("\nRaw FITS Files:")
            click.echo(f"  Total:      {raw_total:>8}")
            click.echo(f"  Backed up:  {raw_backed_up:>8}")
            click.echo(f"  Not backed: {raw_total - raw_backed_up:>8}")
            if raw_total > 0:
                pct = (raw_backed_up / raw_total) * 100
                click.echo(f"  Progress:   {pct:>7.1f}%")

            click.echo("\nProcessed Files:")
            click.echo(f"  Total:      {processed_total:>8}")
            click.echo(f"  Backed up:  {processed_backed_up:>8}")
            click.echo(f"  Not backed: {processed_total - processed_backed_up:>8}")
            if processed_total > 0:
                pct = (processed_backed_up / processed_total) * 100
                click.echo(f"  Progress:   {pct:>7.1f}%")

            click.echo("=" * 70)

        except Exception as e:
            handle_error(e, verbose)

    @stats_group.command('storage')
    @click.pass_context
    def stats_storage(ctx):
        """Show storage usage statistics.

        Displays:
        - Total file sizes by category
        - Disk space usage estimates

        Examples:
            python -m main stats storage
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            db_service = get_db_service(config, cameras, telescopes, filter_mappings)
            db_session = db_service.db_manager.get_session()

            # Raw files by frame type
            click.echo()
            click.echo("=" * 70)
            click.echo("STORAGE STATISTICS")
            click.echo("=" * 70)

            click.echo("\nRaw FITS Files by Frame Type:")
            for frame_type in ['Light', 'Dark', 'Flat', 'Bias']:
                files = db_session.query(FitsFile).filter(
                    FitsFile.frame_type == frame_type
                ).all()

                count = len(files)
                total_size = sum(f.file_size for f in files if f.file_size)

                click.echo(f"  {frame_type:.<20} {count:>6} files  {format_size(total_size):>12}")

            # Processed files
            processed_files = db_session.query(ProcessedFile).all()
            processed_count = len(processed_files)
            processed_size = sum(f.file_size for f in processed_files if f.file_size)

            click.echo(f"\nProcessed Files:")
            click.echo(f"  Total:               {processed_count:>6} files  {format_size(processed_size):>12}")

            db_session.close()

            click.echo("=" * 70)

        except Exception as e:
            handle_error(e, verbose)
