"""Migration commands for moving files from quarantine to library."""

import click

from cli.utils import (
    load_app_config,
    setup_logging,
    handle_error,
    get_db_service,
    confirm_action
)
from file_organizer import FileOrganizer


def register_commands(cli):
    """Register migrate commands with main CLI."""

    @cli.command('migrate')
    @click.argument('target', type=click.Choice(['raw']))
    @click.option('--limit', '-l', type=int, help='Maximum number of files to migrate')
    @click.option('--dry-run', is_flag=True, help='Preview migration without moving files')
    @click.option('--auto-cleanup', is_flag=True,
                  help='Automatically delete duplicates and bad files without prompting')
    @click.pass_context
    def migrate(ctx, target, limit, dry_run, auto_cleanup):
        """Migrate files from quarantine to organized library structure.

        TARGET: Type of files to migrate (currently only 'raw' supported)

        RAW FILES:
            Moves validated files from quarantine to library organized by:
            - Date (YYYY/YYYYMMDD/)
            - Equipment (telescope/camera/)
            - Object name
            - Frame type (Light, Dark, Flat, Bias)

            Only migrates files with validation score ≥95 (auto-migrate category).
            Files with lower scores require manual review.

        Migration handles:
            - Duplicate detection and cleanup
            - Bad file quarantine
            - Database path updates
            - Folder structure creation

        Examples:
            # Preview migration (dry run)
            python main_v2.py migrate raw --dry-run

            # Preview first 20 files
            python main_v2.py migrate raw --dry-run --limit 20

            # Migrate all auto-migrate files
            python main_v2.py migrate raw

            # Migrate with auto cleanup (no prompts)
            python main_v2.py migrate raw --auto-cleanup

            # Migrate limited batch
            python main_v2.py migrate raw --limit 100
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            db_service = get_db_service(config)
            file_organizer = FileOrganizer(config, db_service)

            if dry_run:
                _preview_migration(file_organizer, limit)
            else:
                _execute_migration(file_organizer, limit, auto_cleanup)

        except Exception as e:
            handle_error(e, verbose)


def _preview_migration(file_organizer, limit):
    """Preview migration without moving files.

    Args:
        file_organizer: FileOrganizer instance
        limit: Maximum number of files to preview
    """
    click.echo("=" * 80)
    click.echo("MIGRATION PREVIEW")
    click.echo("=" * 80)
    click.echo("Showing destination paths for files ready to migrate...")
    click.echo()

    preview_paths = file_organizer.create_folder_structure_preview(limit or 20)

    if preview_paths:
        for i, path in enumerate(preview_paths, 1):
            click.echo(f"{i:>4}. {path}")

        click.echo()
        click.echo("=" * 80)
        click.echo(f"Showing {len(preview_paths)} files")
        if limit:
            click.echo(f"(Limited to {limit} files - use --limit to change)")
        click.echo()
        click.echo("To execute migration:")
        click.echo("  python main_v2.py migrate raw")
    else:
        click.echo("No files found ready for migration.")
        click.echo()
        click.echo("Files must have validation score ≥95 to auto-migrate.")
        click.echo("Run validation to score files:")
        click.echo("  python main_v2.py validate raw")

    click.echo("=" * 80)


def _execute_migration(file_organizer, limit, auto_cleanup):
    """Execute file migration from quarantine to library.

    Args:
        file_organizer: FileOrganizer instance
        limit: Maximum number of files to migrate
        auto_cleanup: Whether to auto-cleanup without prompting
    """
    # Confirm migration
    message = "Migrate files from quarantine to organized library structure?"
    if limit:
        message = f"Migrate up to {limit} files from quarantine to library?"

    if not confirm_action(message):
        return

    click.echo()
    click.echo("=" * 80)
    click.echo("MIGRATION IN PROGRESS")
    click.echo("=" * 80)

    stats = file_organizer.migrate_files(limit, auto_cleanup=auto_cleanup)

    click.echo()
    click.echo("=" * 80)
    click.echo("MIGRATION COMPLETE")
    click.echo("=" * 80)
    click.echo(f"Files processed:      {stats['processed']:>6}")
    click.echo(f"Files moved:          {stats['moved']:>6}")
    click.echo(f"Left for review:      {stats.get('left_for_review', 0):>6}")
    click.echo(f"Duplicates handled:   {stats.get('duplicates_moved', 0):>6}")
    click.echo(f"Bad files handled:    {stats.get('bad_files_moved', 0):>6}")
    click.echo(f"Errors:               {stats['errors']:>6}")
    click.echo(f"Skipped:              {stats['skipped']:>6}")
    click.echo("=" * 80)

    if stats['moved'] > 0:
        click.echo()
        click.echo("Next steps:")
        click.echo("  1. Backup files:  python main_v2.py backup raw --not-backed-up")
        click.echo("  2. View stats:    python main_v2.py stats raw")
