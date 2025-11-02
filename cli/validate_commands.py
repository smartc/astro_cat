"""Validation commands for checking file integrity and database consistency."""

import sys

import click

from cli.utils import (
    load_app_config,
    setup_logging,
    handle_error,
    get_db_service,
    confirm_action
)
from validation import FitsValidator


def register_commands(cli):
    """Register validate commands with main CLI."""

    @cli.command('validate')
    @click.argument('target', type=click.Choice(['raw', 'database']))
    @click.option('--check-files/--no-check-files', default=True,
                  help='Check if physical files exist (raw only)')
    @click.option('--limit', type=int, help='Limit number of files to validate (raw only)')
    @click.option('--remove-missing', is_flag=True,
                  help='Remove missing file records from database (raw only)')
    @click.option('--dry-run', is_flag=True,
                  help='Dry run mode for remove-missing (raw only)')
    @click.pass_context
    def validate(ctx, target, check_files, limit, remove_missing, dry_run):
        """Validate files and check database integrity.

        TARGET: What to validate (raw, database)

        RAW FILES:
            - Scores files for migration readiness (0-100 points)
            - Categories: auto-migrate (≥95), needs-review (80-94), manual (<80)
            - Optionally checks if physical files exist
            - Can remove missing file records

        DATABASE:
            - Shows validation summary without re-scoring
            - Displays statistics by frame type and quality score

        Examples:
            # Validate raw files and score for migration
            python main_v2.py validate raw

            # Validate and check physical files exist
            python main_v2.py validate raw --check-files

            # Validate limited set
            python main_v2.py validate raw --limit 100

            # Remove missing file records (dry run)
            python main_v2.py validate raw --check-files --remove-missing --dry-run

            # Actually remove missing records
            python main_v2.py validate raw --check-files --remove-missing

            # Show database validation summary
            python main_v2.py validate database
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            db_service = get_db_service(config, cameras, telescopes, filter_mappings)
            validator = FitsValidator(db_service)

            if target == 'raw':
                _validate_raw_files(validator, check_files, limit, remove_missing, dry_run, verbose)
            elif target == 'database':
                _show_validation_summary(validator)

        except Exception as e:
            handle_error(e, verbose)


def _validate_raw_files(validator, check_files, limit, remove_missing, dry_run, verbose):
    """Validate raw FITS files and optionally remove missing records.

    Args:
        validator: FitsValidator instance
        check_files: Whether to check physical file existence
        limit: Maximum files to validate
        remove_missing: Whether to remove missing file records
        dry_run: Dry run mode for removal
        verbose: Verbose output flag
    """
    if remove_missing:
        _remove_missing_files(validator, dry_run)
        return

    click.echo("Validating raw files...")
    if check_files:
        click.echo("Checking for missing files on disk...")

    stats = validator.validate_all_files(limit=limit, check_files=check_files)

    click.echo("\n" + "=" * 60)
    click.echo("VALIDATION RESULTS")
    click.echo("=" * 60)
    click.echo(f"Total files:      {stats['total']:>6}")
    click.echo(f"Auto-migrate:     {stats['auto_migrate']:>6}  (≥95 points)")
    click.echo(f"Needs review:     {stats['needs_review']:>6}  (80-94 points)")
    click.echo(f"Manual only:      {stats['manual_only']:>6}  (<80 points)")

    if check_files:
        click.echo(f"Missing files:    {stats['missing_files']:>6}")

        if stats['missing_files'] > 0:
            click.echo("\n" + "!" * 60)
            click.echo(f"⚠  Found {stats['missing_files']} files that don't exist on disk")
            click.echo("   Use --remove-missing flag to clean database:")
            click.echo("     python main_v2.py validate raw --check-files --remove-missing")
            click.echo("!" * 60)

    click.echo(f"Updated:          {stats['updated']:>6}")
    click.echo(f"Errors:           {stats['errors']:>6}")
    click.echo("=" * 60)

    if stats['auto_migrate'] > 0:
        click.echo(f"\n✓ {stats['auto_migrate']} files ready for automatic migration")
        click.echo("  Run: python main_v2.py migrate raw --dry-run")


def _remove_missing_files(validator, dry_run):
    """Remove database records for files that don't exist on disk.

    Args:
        validator: FitsValidator instance
        dry_run: Whether to run in dry-run mode
    """
    if dry_run:
        click.echo("DRY RUN MODE - No files will be removed\n")
    else:
        if not confirm_action("This will permanently remove missing file records from the database. Continue?"):
            return

    stats = validator.remove_missing_files(dry_run=dry_run)

    click.echo(f"\nResults:")
    click.echo(f"  Missing files found: {stats['missing']}")

    if dry_run:
        click.echo(f"  Would remove: {stats['missing']} records")
        click.echo("\nRun without --dry-run to actually remove records:")
        click.echo("  python main_v2.py validate raw --check-files --remove-missing")
    else:
        click.echo(f"  Removed: {stats['removed']} records")
        click.echo("✓ Database cleaned")


def _show_validation_summary(validator):
    """Show validation summary from database.

    Args:
        validator: FitsValidator instance
    """
    summary = validator.get_validation_summary()

    click.echo("=" * 60)
    click.echo("DATABASE VALIDATION SUMMARY")
    click.echo("=" * 60)
    click.echo(f"Total files:        {summary['total_files']:>6}")
    click.echo(f"Auto-migrate ready: {summary['auto_migrate']:>6}  (≥95 points)")
    click.echo(f"Needs review:       {summary['needs_review']:>6}  (80-94 points)")
    click.echo(f"Manual only:        {summary['manual_only']:>6}  (<80 points)")

    click.echo("\nAverage scores by frame type:")
    click.echo("-" * 60)
    for frame_type, data in summary['frame_type_averages'].items():
        click.echo(f"  {frame_type:>8}: {data['avg_score']:>5.1f} pts  ({data['count']:>5} files)")
    click.echo("=" * 60)
