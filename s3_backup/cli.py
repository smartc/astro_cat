"""CLI interface for S3 backup operations."""

import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional

import click
from tqdm import tqdm
from tabulate import tabulate

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from config import load_config
from models import DatabaseManager, DatabaseService, Session as SessionModel
from s3_backup.manager import S3BackupManager, S3BackupConfig
from s3_backup.models import Base as BackupBase, S3BackupArchive

logger = logging.getLogger(__name__)


def get_backup_manager(config_path: str = 'config.json', s3_config_path: str = 's3_config.json'):
    """Initialize backup manager with configuration."""
    config, cameras, telescopes, filter_mappings = load_config(config_path)
    db_manager = DatabaseManager(config.database.connection_string)
    db_service = DatabaseService(db_manager)
    
    # Create backup tables if needed
    BackupBase.metadata.create_all(bind=db_manager.engine)
    
    s3_config = S3BackupConfig(s3_config_path)
    
    if not s3_config.enabled:
        click.echo("⚠️  S3 backup is disabled in s3_config.json")
        click.echo("    Set 'enabled': true to use backup features")
        sys.exit(1)
    
    # Extract base directory from main config for resolving relative paths
    # Use image_dir as the base (typically /mnt/phoebe/Astro)
    base_dir = Path(config.paths.image_dir).parent if hasattr(config.paths, 'image_dir') else None
    
    backup_manager = S3BackupManager(db_service, s3_config, base_dir)
    
    return backup_manager, db_manager, db_service


@click.group()
@click.option('--config', '-c', default='config.json', help='Main configuration file')
@click.option('--s3-config', default='s3_config.json', help='S3 configuration file')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.pass_context
def cli(ctx, config, s3_config, verbose):
    """S3 Backup Manager for FITS Cataloger."""
    ctx.ensure_object(dict)
    ctx.obj['config'] = config
    ctx.obj['s3_config'] = s3_config
    
    # Setup logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


@cli.command()
@click.pass_context
def cleanup(ctx):
    """Clean up temporary archive files."""
    backup_manager, db_manager, db_service = get_backup_manager(
        ctx.obj['config'], ctx.obj['s3_config']
    )
    
    try:
        temp_dir = backup_manager.temp_dir
        
        if not temp_dir.exists():
            click.echo(f"✓ Temp directory does not exist: {temp_dir}")
            return
        
        # Find all archive files
        archives = list(temp_dir.glob("*.tar*"))
        
        if not archives:
            click.echo(f"✓ No orphaned archives found in: {temp_dir}")
            return
        
        # Calculate total size
        total_size = sum(f.stat().st_size for f in archives)
        
        click.echo(f"\nFound {len(archives)} orphaned archive(s) in: {temp_dir}")
        click.echo(f"Total size: {format_bytes(total_size)}")
        click.echo("\nFiles:")
        for archive in archives:
            size = archive.stat().st_size
            click.echo(f"  {archive.name}: {format_bytes(size)}")
        
        if not click.confirm("\nDelete these files?"):
            click.echo("Cancelled.")
            return
        
        # Delete
        deleted = 0
        for archive in archives:
            try:
                archive.unlink()
                deleted += 1
            except Exception as e:
                click.echo(f"❌ Failed to delete {archive.name}: {e}")
        
        click.echo(f"\n✓ Deleted {deleted} file(s), freed {format_bytes(total_size)}")
        
    finally:
        db_manager.close()


@cli.command()
@click.pass_context
def temp_info(ctx):
    """Show temporary directory info and disk usage."""
    backup_manager, db_manager, db_service = get_backup_manager(
        ctx.obj['config'], ctx.obj['s3_config']
    )
    
    try:
        import shutil
        
        temp_dir = backup_manager.temp_dir
        
        click.echo("=" * 80)
        click.echo("TEMPORARY DIRECTORY INFO")
        click.echo("=" * 80)
        click.echo(f"\nTemp directory: {temp_dir}")
        click.echo(f"Exists: {'Yes' if temp_dir.exists() else 'No'}")
        
        # Get disk usage
        if temp_dir.exists():
            stat = shutil.disk_usage(temp_dir)
            click.echo(f"\nDisk usage:")
            click.echo(f"  Total: {format_bytes(stat.total)}")
            click.echo(f"  Used: {format_bytes(stat.used)}")
            click.echo(f"  Free: {format_bytes(stat.free)}")
            click.echo(f"  Usage: {stat.used / stat.total * 100:.1f}%")
            
            # DYNAMIC LARGEST SESSION CHECK
            click.echo("\nCalculating largest session size...")
            largest_session_id, largest_size = backup_manager.get_largest_session_size()
            
            if largest_session_id:
                required_space = int(largest_size * 1.1)  # 10% buffer
                click.echo(f"\nLargest session: {largest_session_id}")
                click.echo(f"  Size: {format_bytes(largest_size)}")
                click.echo(f"  With buffer: {format_bytes(required_space)}")
                
                if stat.free >= required_space:
                    click.echo(f"\n✓ Sufficient space for largest session")
                else:
                    shortage = required_space - stat.free
                    click.echo(f"\n⚠️  WARNING: Insufficient space!")
                    click.echo(f"  Short by: {format_bytes(shortage)}")
                    click.echo(f"\n  Consider using a different temp directory")
                    click.echo(f"  Edit s3_config.json:")
                    click.echo(f'    "archive_settings": {{')
                    click.echo(f'      "temp_dir": "/path/to/larger/storage"')
                    click.echo(f'    }}')
            else:
                click.echo("\nNo sessions found in database")
            
            # Check for archives
            archives = list(temp_dir.glob("*.tar*"))
            if archives:
                total_archive_size = sum(f.stat().st_size for f in archives)
                click.echo(f"\nOrphaned archives:")
                click.echo(f"  Count: {len(archives)}")
                click.echo(f"  Size: {format_bytes(total_archive_size)}")
                click.echo(f"\n  Run 'python -m s3_backup.cli cleanup' to remove them")
            else:
                click.echo(f"\n✓ No orphaned archives")
        
        click.echo("\n" + "=" * 80)
        
    finally:
        db_manager.close()

@cli.command()
@click.pass_context
def status(ctx):
    """Show backup status and statistics."""
    backup_manager, db_manager, db_service = get_backup_manager(
        ctx.obj['config'], ctx.obj['s3_config']
    )
    
    session_db = db_manager.get_session()
    
    try:
        # Get all sessions
        total_sessions = session_db.query(SessionModel).count()
        
        # Get backed up sessions
        backed_up = session_db.query(S3BackupArchive).count()
        
        # Get backup stats
        backed_up_archives = session_db.query(S3BackupArchive).all()
        
        total_original_size = sum(a.original_size_bytes or 0 for a in backed_up_archives)
        total_compressed_size = sum(a.compressed_size_bytes or 0 for a in backed_up_archives)
        total_files = sum(a.file_count or 0 for a in backed_up_archives)
        
        avg_compression = (
            total_compressed_size / total_original_size 
            if total_original_size > 0 else 0
        )
        
        # Storage class breakdown
        storage_classes = {}
        for archive in backed_up_archives:
            storage_class = archive.current_storage_class or 'STANDARD'
            storage_classes[storage_class] = storage_classes.get(storage_class, 0) + 1
        
        # Display status
        click.echo("=" * 80)
        click.echo("S3 BACKUP STATUS")
        click.echo("=" * 80)
        
        click.echo(f"\nBucket: s3://{backup_manager.s3_config.bucket}")
        click.echo(f"Region: {backup_manager.s3_config.region}")
        
        click.echo(f"\nSessions:")
        click.echo(f"  Total in database: {total_sessions}")
        click.echo(f"  Backed up: {backed_up}")
        click.echo(f"  Not backed up: {total_sessions - backed_up}")
        click.echo(f"  Backup percentage: {(backed_up / total_sessions * 100) if total_sessions > 0 else 0:.1f}%")
        
        click.echo(f"\nArchive Statistics:")
        click.echo(f"  Total files backed up: {total_files:,}")
        click.echo(f"  Original size: {format_bytes(total_original_size)}")
        click.echo(f"  Compressed size: {format_bytes(total_compressed_size)}")
        click.echo(f"  Space saved: {format_bytes(total_original_size - total_compressed_size)}")
        click.echo(f"  Average compression: {avg_compression:.1%}")
        
        if storage_classes:
            click.echo(f"\nStorage Classes:")
            for storage_class, count in sorted(storage_classes.items()):
                click.echo(f"  {storage_class}: {count} archives")
        
        click.echo("\n" + "=" * 80 + "\n")
        
    finally:
        session_db.close()
        db_manager.close()


@cli.command()
@click.option('--session-id', '-s', help='Specific session ID to upload')
@click.option('--year', '-y', type=int, help='Upload all sessions from specific year')
@click.option('--limit', '-l', type=int, help='Limit number of NEW sessions to upload (skips existing)')
@click.option('--skip-existing', is_flag=True, default=True, help='Skip already backed up sessions')
@click.option('--no-cleanup', is_flag=True, help='Keep local archives after upload')
@click.pass_context
def upload(ctx, session_id, year, limit, skip_existing, no_cleanup):
    """Upload imaging session(s) to S3."""
    backup_manager, db_manager, db_service = get_backup_manager(
        ctx.obj['config'], ctx.obj['s3_config']
    )
    
    session_db = db_manager.get_session()
    
    try:
        # Build session list
        query = session_db.query(SessionModel)
        
        if session_id:
            query = query.filter(SessionModel.session_id == session_id)
            sessions = query.all()
            if not sessions:
                click.echo(f"❌ Session not found: {session_id}")
                return
        elif year:
            query = query.filter(SessionModel.session_date.like(f"{year}%"))
            sessions = query.order_by(SessionModel.session_date).all()
        else:
            # Upload all sessions, oldest first
            sessions = query.order_by(SessionModel.session_date).all()
        
        if not sessions:
            click.echo("No sessions found to upload.")
            return
        
        # Track how many we checked for limit mode
        checked_count = 0
        
        # If limit specified and skip_existing, filter to get enough non-backed-up sessions
        if limit and skip_existing:
            click.echo(f"Finding {limit} session(s) not yet backed up...")
            
            sessions_to_upload = []
            
            for session_model in sessions:
                checked_count += 1
                
                # Get year for S3 check
                try:
                    year_val = datetime.strptime(session_model.session_date, '%Y-%m-%d').year
                except:
                    click.echo(f"⚠️  Skipping {session_model.session_id}: invalid date format")
                    continue
                
                # Check if exists in S3 (not just database)
                if backup_manager.check_archive_exists(session_model.session_id, year_val):
                    click.echo(f"⏭️  Skipping (already in S3): {session_model.session_id}")
                    continue
                
                # Add to upload list
                sessions_to_upload.append(session_model)
                
                # Stop when we have enough
                if len(sessions_to_upload) >= limit:
                    break
                
                # Safety check - don't scan forever
                if checked_count > limit * 10:
                    click.echo(f"⚠️  Checked {checked_count} sessions, stopping search.")
                    break
            
            sessions = sessions_to_upload
            
            if not sessions:
                click.echo(f"✓ No new sessions to upload (checked {checked_count} sessions)")
                return
            
            click.echo(f"✓ Found {len(sessions)} session(s) to upload (checked {checked_count} total)")
        elif limit:
            # Limit without skip_existing - just take first N
            sessions = sessions[:limit]
        
        click.echo(f"\nFound {len(sessions)} session(s) to process")
        
        # if not click.confirm("Continue with upload?"):
        #     click.echo("Cancelled.")
        #     return
        
        # Track results
        results = {
            'success': 0,
            'skipped': 0,
            'failed': 0,
            'total_uploaded_bytes': 0,
            'checked_count': checked_count
        }
        
        # Upload each session
        with tqdm(total=len(sessions), desc="Uploading sessions", unit="session") as pbar:
            for session_model in sessions:
                pbar.set_description(f"Processing {session_model.session_id[:20]}")
                
                result = backup_manager.backup_session(
                    session_model.session_id,
                    skip_existing=skip_existing,
                    cleanup_archive=not no_cleanup
                )
                
                if result.success:
                    if result.error and "skipped" in result.error.lower():
                        results['skipped'] += 1
                        tqdm.write(f"⏭️  Skipped (exists): {session_model.session_id}")
                    else:
                        results['success'] += 1
                        results['total_uploaded_bytes'] += result.compressed_size
                        
                        # Save to database
                        backup_archive = S3BackupArchive(
                            session_id=session_model.session_id,
                            session_date=session_model.session_date,
                            session_year=datetime.strptime(session_model.session_date, '%Y-%m-%d').year,
                            s3_bucket=backup_manager.s3_config.bucket,
                            s3_key=result.s3_key,
                            s3_region=backup_manager.s3_config.region,
                            s3_etag=result.s3_etag,
                            file_count=result.file_count,
                            original_size_bytes=result.original_size,
                            compressed_size_bytes=result.compressed_size,
                            compression_ratio=result.compression_ratio,
                            uploaded_at=datetime.now(),
                            verified=True,
                            verification_method='etag',
                            camera_name=session_model.camera,
                            telescope_name=session_model.telescope
                        )
                        
                        session_db.add(backup_archive)
                        session_db.commit()
                        
                        tqdm.write(
                            f"✅ {session_model.session_id}: "
                            f"{result.file_count} files, "
                            f"{format_bytes(result.compressed_size)}"
                        )
                else:
                    results['failed'] += 1
                    tqdm.write(f"❌ Failed: {session_model.session_id} - {result.error}")
                
                pbar.update(1)
        
        # Summary
        click.echo("\n" + "=" * 80)
        click.echo("UPLOAD SUMMARY")
        click.echo("=" * 80)
        click.echo(f"  Successful: {results['success']}")
        click.echo(f"  Skipped: {results['skipped']}")
        click.echo(f"  Failed: {results['failed']}")
        click.echo(f"  Total uploaded: {format_bytes(results['total_uploaded_bytes'])}")
        
        # Show how many we checked if limit was used
        if results['checked_count'] > 0:
            click.echo(f"  Sessions checked: {results['checked_count']}")
        
        click.echo("=" * 80 + "\n")
        
    finally:
        session_db.close()
        db_manager.close()


@cli.command()
@click.option('--session-id', '-s', help='Verify specific session')
@click.option('--all', 'verify_all', is_flag=True, help='Verify all backed up sessions')
@click.pass_context
def verify(ctx, session_id, verify_all):
    """Verify backed up archives in S3."""
    backup_manager, db_manager, db_service = get_backup_manager(
        ctx.obj['config'], ctx.obj['s3_config']
    )
    
    session_db = db_manager.get_session()
    
    try:
        # Get archives to verify
        query = session_db.query(S3BackupArchive)
        
        if session_id:
            query = query.filter(S3BackupArchive.session_id == session_id)
        elif not verify_all:
            click.echo("Specify --session-id or --all")
            return
        
        archives = query.all()
        
        if not archives:
            click.echo("No archives found to verify.")
            return
        
        click.echo(f"\nVerifying {len(archives)} archive(s)...")
        
        verified_count = 0
        failed_count = 0
        
        with tqdm(total=len(archives), desc="Verifying", unit="archive") as pbar:
            for archive in archives:
                result = backup_manager.verify_archive(
                    archive.session_id,
                    archive.session_year
                )
                
                if result.verified:
                    verified_count += 1
                    archive.last_verified_at = datetime.now()
                    archive.verified = True
                    session_db.commit()
                    tqdm.write(f"✅ {archive.session_id}: Verified")
                else:
                    failed_count += 1
                    tqdm.write(f"❌ {archive.session_id}: {result.error}")
                
                pbar.update(1)
        
        click.echo(f"\nVerification complete: {verified_count} OK, {failed_count} failed\n")
        
    finally:
        session_db.close()
        db_manager.close()


@cli.command()
@click.option('--year', '-y', type=int, help='List sessions from specific year')
@click.option('--not-backed-up', is_flag=True, help='Show only sessions not backed up')
@click.pass_context
def list_sessions(ctx, year, not_backed_up):
    """List imaging sessions and their backup status."""
    backup_manager, db_manager, db_service = get_backup_manager(
        ctx.obj['config'], ctx.obj['s3_config']
    )
    
    session_db = db_manager.get_session()
    
    try:
        query = session_db.query(SessionModel)
        
        if year:
            query = query.filter(SessionModel.session_date.like(f"{year}%"))
        
        sessions = query.order_by(SessionModel.session_date).all()
        
        # Check backup status
        table_data = []
        
        for session_model in sessions:
            # Check if backed up
            backup_archive = session_db.query(S3BackupArchive).filter(
                S3BackupArchive.session_id == session_model.session_id
            ).first()
            
            backed_up = backup_archive is not None
            
            if not_backed_up and backed_up:
                continue
            
            table_data.append([
                session_model.session_id[:25],
                session_model.session_date,
                (session_model.camera or 'Unknown')[:15],
                (session_model.telescope or 'Unknown')[:15],
                "✅" if backed_up else "❌",
                format_bytes(backup_archive.compressed_size_bytes) if backed_up else "-"
            ])
        
        if not table_data:
            click.echo("No sessions found.")
            return
        
        headers = ['Session ID', 'Date', 'Camera', 'Telescope', 'Backed Up', 'Size']
        click.echo(f"\n{len(table_data)} session(s) found:\n")
        click.echo(tabulate(table_data, headers=headers, tablefmt='grid'))
        click.echo()
        
    finally:
        session_db.close()
        db_manager.close()


@cli.command()
@click.pass_context
def init_config(ctx):
    """Initialize s3_config.json from template."""
    template_path = Path('s3_config.json.template')
    config_path = Path('s3_config.json')
    
    if config_path.exists():
        click.echo(f"⚠️  {config_path} already exists")
        if not click.confirm("Overwrite?"):
            return
    
    if not template_path.exists():
        click.echo(f"❌ Template not found: {template_path}")
        return
    
    # Copy template
    import shutil
    shutil.copy(template_path, config_path)
    
    click.echo(f"✅ Created {config_path}")
    click.echo(f"\nNext steps:")
    click.echo(f"  1. Edit {config_path} with your settings")
    click.echo(f"  2. Set 'enabled': true")
    click.echo(f"  3. Configure your bucket name and region")
    click.echo(f"  4. Run: python -m s3_backup.cli status")


def format_bytes(bytes_size: int) -> str:
    """Format bytes to human readable string."""
    if bytes_size == 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"


if __name__ == '__main__':
    cli()