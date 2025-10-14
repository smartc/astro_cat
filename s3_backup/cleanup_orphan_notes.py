#!/usr/bin/env python3
"""
One-off script to reconcile S3 backup database with actual S3 objects.

Removes database entries for markdown files that no longer exist in S3.
This is useful after reorganizing S3 paths or cleaning up old backups.
"""

import sys
import logging
from pathlib import Path
from typing import List, Tuple

import click
from tqdm import tqdm
from botocore.exceptions import ClientError

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

from config import load_config
from models import DatabaseManager, DatabaseService
from s3_backup.manager import S3BackupManager, S3BackupConfig
from s3_backup.models import Base as BackupBase, S3BackupSessionNote, S3BackupProcessingSession

logger = logging.getLogger(__name__)


def check_s3_object_exists(s3_client, bucket: str, key: str) -> bool:
    """Check if an object exists in S3."""
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return False
        else:
            logger.warning(f"Error checking {key}: {e}")
            return False


def reconcile_imaging_sessions(
    backup_manager: S3BackupManager,
    db_session,
    dry_run: bool = False
) -> Tuple[int, int, int]:
    """
    Reconcile imaging session markdown backups.
    
    Returns: (total_checked, found_in_s3, removed)
    """
    click.echo("\n" + "=" * 80)
    click.echo("IMAGING SESSION NOTES")
    click.echo("=" * 80)
    
    # Get all backup records
    records = db_session.query(S3BackupSessionNote).all()
    total = len(records)
    
    if total == 0:
        click.echo("No imaging session backup records found in database")
        return 0, 0, 0
    
    click.echo(f"Checking {total} imaging session backup record(s)...")
    
    found = 0
    to_remove = []
    
    with tqdm(total=total, desc="Checking S3", unit="record") as pbar:
        for record in records:
            exists = check_s3_object_exists(
                backup_manager.s3_client,
                record.s3_bucket,
                record.s3_key
            )
            
            if exists:
                found += 1
            else:
                to_remove.append(record)
                tqdm.write(f"  ✗ Missing in S3: {record.session_id} ({record.s3_key})")
            
            pbar.update(1)
    
    # Remove orphaned records
    removed = 0
    if to_remove:
        click.echo(f"\n{len(to_remove)} orphaned record(s) found")
        
        if dry_run:
            click.echo("DRY RUN - Would remove:")
            for record in to_remove[:10]:
                click.echo(f"  - {record.session_id} (uploaded {record.uploaded_at})")
            if len(to_remove) > 10:
                click.echo(f"  ... and {len(to_remove) - 10} more")
        else:
            if click.confirm("Remove these orphaned records?"):
                for record in to_remove:
                    db_session.delete(record)
                db_session.commit()
                removed = len(to_remove)
                click.echo(f"✓ Removed {removed} orphaned record(s)")
            else:
                click.echo("Cancelled - no records removed")
    else:
        click.echo("✓ All records have corresponding S3 objects")
    
    return total, found, removed


def reconcile_processing_sessions(
    backup_manager: S3BackupManager,
    db_session,
    dry_run: bool = False
) -> Tuple[int, int, int]:
    """
    Reconcile processing session markdown backups.
    
    Returns: (total_checked, found_in_s3, removed)
    """
    click.echo("\n" + "=" * 80)
    click.echo("PROCESSING SESSION NOTES")
    click.echo("=" * 80)
    
    # Get all backup records
    records = db_session.query(S3BackupProcessingSession).all()
    total = len(records)
    
    if total == 0:
        click.echo("No processing session backup records found in database")
        return 0, 0, 0
    
    click.echo(f"Checking {total} processing session backup record(s)...")
    
    found = 0
    to_remove = []
    
    with tqdm(total=total, desc="Checking S3", unit="record") as pbar:
        for record in records:
            exists = check_s3_object_exists(
                backup_manager.s3_client,
                record.s3_bucket,
                record.s3_key
            )
            
            if exists:
                found += 1
            else:
                to_remove.append(record)
                tqdm.write(f"  ✗ Missing in S3: {record.processing_session_id} ({record.s3_key})")
            
            pbar.update(1)
    
    # Remove orphaned records
    removed = 0
    if to_remove:
        click.echo(f"\n{len(to_remove)} orphaned record(s) found")
        
        if dry_run:
            click.echo("DRY RUN - Would remove:")
            for record in to_remove[:10]:
                click.echo(f"  - {record.processing_session_id} (uploaded {record.uploaded_at})")
            if len(to_remove) > 10:
                click.echo(f"  ... and {len(to_remove) - 10} more")
        else:
            if click.confirm("Remove these orphaned records?"):
                for record in to_remove:
                    db_session.delete(record)
                db_session.commit()
                removed = len(to_remove)
                click.echo(f"✓ Removed {removed} orphaned record(s)")
            else:
                click.echo("Cancelled - no records removed")
    else:
        click.echo("✓ All records have corresponding S3 objects")
    
    return total, found, removed


@click.command()
@click.option('--config', '-c', default='config.json', help='Main configuration file')
@click.option('--s3-config', default='s3_config.json', help='S3 configuration file')
@click.option('--dry-run', is_flag=True, help='Show what would be removed without deleting')
@click.option('--imaging/--no-imaging', default=True, help='Check imaging sessions')
@click.option('--processing/--no-processing', default=True, help='Check processing sessions')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def main(config, s3_config, dry_run, imaging, processing, verbose):
    """
    Reconcile S3 backup database with actual S3 objects.
    
    Removes database entries for markdown files that no longer exist in S3.
    """
    # Setup logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    click.echo("=" * 80)
    click.echo("S3 BACKUP DATABASE RECONCILIATION")
    click.echo("=" * 80)
    
    if dry_run:
        click.echo("🔍 DRY RUN MODE - No changes will be made")
    
    click.echo()
    
    try:
        # Load configuration
        main_config, cameras, telescopes, filter_mappings = load_config(config)
        db_manager = DatabaseManager(main_config.database.connection_string)
        db_service = DatabaseService(db_manager)
        
        # Create backup tables if needed
        BackupBase.metadata.create_all(bind=db_manager.engine)
        
        s3_config_obj = S3BackupConfig(s3_config)
        
        if not s3_config_obj.enabled:
            click.echo("⚠️  S3 backup is disabled in s3_config.json")
            sys.exit(1)
        
        # Extract base directory from main config
        base_dir = Path(main_config.paths.image_dir).parent if hasattr(main_config.paths, 'image_dir') else None
        
        backup_manager = S3BackupManager(db_service, s3_config_obj, base_dir, dry_run=True, auto_cleanup=False)
        
        db_session = db_manager.get_session()
        
        total_stats = {
            'total_checked': 0,
            'found_in_s3': 0,
            'removed': 0
        }
        
        # Check imaging sessions
        if imaging:
            total, found, removed = reconcile_imaging_sessions(backup_manager, db_session, dry_run)
            total_stats['total_checked'] += total
            total_stats['found_in_s3'] += found
            total_stats['removed'] += removed
        
        # Check processing sessions
        if processing:
            total, found, removed = reconcile_processing_sessions(backup_manager, db_session, dry_run)
            total_stats['total_checked'] += total
            total_stats['found_in_s3'] += found
            total_stats['removed'] += removed
        
        # Print summary
        click.echo("\n" + "=" * 80)
        click.echo("SUMMARY")
        click.echo("=" * 80)
        click.echo(f"Total records checked:     {total_stats['total_checked']}")
        click.echo(f"Found in S3:               {total_stats['found_in_s3']}")
        click.echo(f"Orphaned (missing in S3):  {total_stats['total_checked'] - total_stats['found_in_s3']}")
        
        if dry_run:
            click.echo(f"Would remove:              {total_stats['total_checked'] - total_stats['found_in_s3']}")
            click.echo("\n💡 Run without --dry-run to remove orphaned records")
        else:
            click.echo(f"Removed:                   {total_stats['removed']}")
            if total_stats['removed'] > 0:
                click.echo("\n✅ Database reconciliation complete!")
            else:
                click.echo("\n✅ Database is clean - no orphaned records found")
        
        click.echo("=" * 80)
        
        db_session.close()
        db_manager.close()
        
    except Exception as e:
        click.echo(f"\n❌ Error: {e}")
        logger.error(f"Reconciliation failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()