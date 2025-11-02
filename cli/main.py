"""Main CLI entry point - Root command group with global options."""

import click

from version import __version__


@click.group()
@click.option('--config', '-c', default='config.json', help='Configuration file path')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed logging on console')
@click.version_option(version=__version__, prog_name='FITS Cataloger')
@click.pass_context
def cli(ctx, config, verbose):
    """FITS Cataloger v2.0 - Astronomical image management tool.

    A comprehensive tool for managing FITS astronomical images with:
    - Automated file scanning and metadata extraction
    - Intelligent file organization by session and equipment
    - Processing session management for image workflows
    - Cloud backup with S3 integration
    - Web interface for browsing and analysis

    Commands use a consistent verb-first syntax:
        scan, catalog, validate, migrate, backup, verify, list, stats

    Examples:
        # Scan for new raw FITS files in quarantine
        python -m main scan raw

        # Catalog scanned files to database
        python -m main catalog raw

        # Create a processing session
        python -m main processing-session create "M31 LRGB" --file-ids "1,2,3"

        # Backup processed files
        python -m main backup processed --processing-session <ID>
    """
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = config
    ctx.obj['verbose'] = verbose


def register_all_commands():
    """Register all command modules with the main CLI."""
    # Import all command modules
    from cli import (
        config_commands,
        scan_commands,
        catalog_commands,
        validate_commands,
        migrate_commands,
        backup_commands,
        verify_commands,
        list_commands,
        stats_commands,
        imaging_session_commands,
        processing_session_commands,
    )

    # Register commands from each module
    config_commands.register_commands(cli)
    scan_commands.register_commands(cli)
    catalog_commands.register_commands(cli)
    validate_commands.register_commands(cli)
    migrate_commands.register_commands(cli)
    backup_commands.register_commands(cli)
    verify_commands.register_commands(cli)
    list_commands.register_commands(cli)
    stats_commands.register_commands(cli)
    imaging_session_commands.register_commands(cli)
    processing_session_commands.register_commands(cli)


# Register all commands when module is imported
register_all_commands()
