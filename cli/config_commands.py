"""Configuration management commands."""

import sys
from pathlib import Path

import click
from sqlalchemy import text

from config import create_default_config
from cli.utils import (
    load_app_config,
    setup_logging,
    handle_error
)
from models import DatabaseManager


def register_commands(cli):
    """Register config commands with main CLI."""

    @cli.group('config')
    @click.pass_context
    def config_group(ctx):
        """Configuration management commands.

        Initialize, test, and manage application configuration.
        """
        pass

    @config_group.command('init')
    @click.pass_context
    def init_config(ctx):
        """Create a default configuration file.

        Creates config.json with default settings for:
        - Database connection
        - File paths (quarantine, library, processed)
        - Logging configuration
        - S3 backup settings

        Examples:
            # Create default config.json
            python main_v2.py config init

            # Create config at custom location
            python main_v2.py --config my_config.json config init
        """
        config_path = ctx.obj['config_path']

        if Path(config_path).exists():
            click.echo(f"Configuration file already exists: {config_path}")
            if not click.confirm("Overwrite existing configuration?"):
                return

        create_default_config(config_path)
        click.echo(f"✓ Created configuration file: {config_path}")
        click.echo("\nNext steps:")
        click.echo("  1. Edit the configuration file with your specific paths")
        click.echo("  2. Configure database connection string")
        click.echo("  3. Set up equipment files (cameras.json, telescopes.json, filters.json)")
        click.echo("  4. Test the configuration with: python main_v2.py config test-db")

    @config_group.command('test-db')
    @click.pass_context
    def test_db(ctx):
        """Test database connection and setup.

        Verifies that:
        - Database connection string is valid
        - Tables can be created/accessed
        - Database is ready for operations

        Examples:
            python main_v2.py config test-db
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, cameras, telescopes, filter_mappings = load_app_config(config_path)
            setup_logging(config, verbose)

            click.echo("Testing database connection...")

            db_manager = DatabaseManager(config.database.connection_string)
            db_manager.create_tables()

            session = db_manager.get_session()
            try:
                # Simple query to test connection
                result = session.execute(text("SELECT 1")).scalar()
            finally:
                session.close()

            db_manager.close()

            click.echo("✓ Database connection successful!")
            click.echo("✓ Tables created/verified!")
            click.echo("\nDatabase is ready for use.")

        except Exception as e:
            click.echo(f"✗ Database test failed: {e}", err=True)
            if verbose:
                import traceback
                click.echo(traceback.format_exc(), err=True)
            sys.exit(1)

    @config_group.command('show')
    @click.pass_context
    def show_config(ctx):
        """Display current configuration settings.

        Shows:
        - Configuration file path
        - Database connection
        - Directory paths
        - Logging settings
        - S3 backup configuration

        Examples:
            python main_v2.py config show
        """
        config_path = ctx.obj['config_path']
        verbose = ctx.obj['verbose']

        try:
            config, cameras, telescopes, filter_mappings = load_app_config(config_path)

            click.echo(f"Configuration file: {config_path}")
            click.echo("\nDatabase:")
            click.echo(f"  Connection: {config.database.connection_string}")

            click.echo("\nDirectories:")
            click.echo(f"  Quarantine: {config.directories.quarantine}")
            click.echo(f"  Library:    {config.directories.library}")
            click.echo(f"  Processed:  {config.directories.processed}")

            click.echo("\nLogging:")
            click.echo(f"  File: {config.logging.file}")

            click.echo("\nEquipment:")
            click.echo(f"  Cameras:    {len(cameras)}")
            click.echo(f"  Telescopes: {len(telescopes)}")
            click.echo(f"  Filters:    {len(filter_mappings)}")

            if hasattr(config, 's3_backup') and config.s3_backup:
                click.echo("\nS3 Backup:")
                click.echo(f"  Bucket: {config.s3_backup.bucket_name}")
                click.echo(f"  Region: {config.s3_backup.region}")

        except Exception as e:
            handle_error(e, verbose)
