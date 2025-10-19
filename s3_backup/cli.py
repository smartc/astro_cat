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
from s3_backup.models import S3BackupSessionNote, S3BackupProcessingSession

logger = logging.getLogger(__name__)


def get_backup_manager(config_path: str = 'config.json', s3_config_path: str = 's3_config.json', dry_run: bool  = False, auto_cleanup: bool = True):
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
    
    backup_manager = S3BackupManager(db_service, s3_config, base_dir, dry_run, auto_cleanup)
    
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
@click.option("--dry-run", is_flag=True, help="Show what would be deleted without actually removing files.")
@click.pass_context
def cleanup(ctx, dry_run):
    """Clean up temporary archive files."""
    backup_manager, db_manager, db_service = get_backup_manager(
        ctx.obj['config'], ctx.obj['s3_config'], dry_run=dry_run, auto_cleanup=False
    )


    try:
        temp_dir = backup_manager.temp_dir

        if not temp_dir.exists():
            click.echo(f"✓ Temp directory does not exist: {temp_dir}")
            return

        archives = list(temp_dir.glob("*.tar*"))
        if not archives:
            click.echo(f"✓ No orphaned archives found in: {temp_dir}")
            return

        total_size = sum(f.stat().st_size for f in archives)
        click.echo(f"\nFound {len(archives)} orphaned archive(s) in: {temp_dir}")
        click.echo(f"Total size: {format_bytes(total_size)}\n")

        for archive in archives:
            click.echo(f"  {archive.name}: {format_bytes(archive.stat().st_size)}")

        if not click.confirm("\nDelete these files?"):
            click.echo("Cancelled.")
            return

        deleted = 0
        for archive in archives:
            if dry_run:
                click.echo(f"🧩 Would delete: {archive}")
                continue
            if backup_manager.safe_unlink(archive):
                deleted += 1
            else:
                click.echo(f"⚠️ Skipped or missing: {archive.name}")

        if dry_run:
            click.echo(f"\n✅ Dry run complete — {len(archives)} files would be deleted.")
        else:
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


def _backup_imaging_markdown(backup_manager, config, session_db, dry_run, limit, force):
    """Backup imaging session markdown files with database tracking."""
    stats = {'uploaded': 0, 'skipped': 0, 'failed': 0, 'total': 0}
    
    # NEW: Use centralized Session_notes directory
    notes_dir = Path(config.paths.notes_dir) / "Imaging_Sessions"
    
    if not notes_dir.exists():
        click.echo("   No Imaging_Sessions directory found")
        return stats
    
    # Find all markdown files - no longer has _session_notes suffix
    markdown_files = sorted(notes_dir.rglob("*.md"))
    stats['total'] = len(markdown_files)
    
    if stats['total'] == 0:
        click.echo("   No imaging session notes found")
        return stats
    
    for md_file in markdown_files:
        # Check upload limit
        if limit and stats['uploaded'] >= limit:
            break
        
        try:
            # Extract session info - filename is just {session_id}.md
            session_id = md_file.stem  # No more _session_notes suffix
            year = int(md_file.parent.name)
            
            # Build S3 key - update to match new naming
            s3_key = backup_manager._get_session_note_key(session_id, year)
            
            # Check if upload needed (unless forced)
            if not force:
                needs_upload, reason = backup_manager.needs_markdown_backup(md_file, s3_key)
                
                if not needs_upload:
                    stats['skipped'] += 1
                    if dry_run:
                        click.echo(f"   ⊘ {md_file.name}: {reason}")
                    continue
                else:
                    if dry_run or force:
                        click.echo(f"   → {md_file.name}: {reason}")
            
            # In dry-run mode, don't actually upload
            if dry_run:
                stats['uploaded'] += 1
                continue
            
            # Get session metadata from database
            imaging_session = session_db.query(SessionModel).filter(
                SessionModel.session_id == session_id
            ).first()
            
            metadata = {
                'session_id': session_id,
                'session_date': imaging_session.session_date if imaging_session else '',
                'type': 'imaging_session'
            }
            
            # Upload to S3
            result = backup_manager.upload_markdown(
                md_file, s3_key, 'imaging_sessions', metadata, force=force
            )
            
            if result.success and result.needs_backup:
                stats['uploaded'] += 1
                click.echo(f"   ✓ {md_file.name}")
                
                # Save to database
                try:
                    # Check if record exists
                    existing = session_db.query(S3BackupSessionNote).filter(
                        S3BackupSessionNote.session_id == session_id
                    ).first()
                    
                    if existing:
                        # Update existing record
                        existing.s3_etag = result.s3_etag
                        existing.uploaded_at = datetime.now()
                        existing.file_size_bytes = result.file_size
                        existing.verified = True
                    else:
                        # Create new record
                        backup_note = S3BackupSessionNote(
                            session_id=session_id,
                            session_year=year,
                            s3_bucket=backup_manager.s3_config.bucket,
                            s3_key=s3_key,
                            s3_region=backup_manager.s3_config.region,
                            s3_etag=result.s3_etag,
                            uploaded_at=datetime.now(),
                            file_size_bytes=result.file_size,
                            archive_policy='never',
                            backup_policy='never',
                            current_storage_class='STANDARD',
                            verified=True
                        )
                        session_db.add(backup_note)
                    
                    session_db.commit()
                    
                except Exception as db_error:
                    logger.warning(f"Failed to save database record for {session_id}: {db_error}")
                    session_db.rollback()
                    # Don't fail the whole operation if database save fails
                
            elif result.success and not result.needs_backup:
                stats['skipped'] += 1
            else:
                stats['failed'] += 1
                click.echo(f"   ✗ {md_file.name}: {result.error}")
            
        except Exception as e:
            stats['failed'] += 1
            click.echo(f"   ✗ {md_file.name}: {e}")
            logger.error(f"Failed to backup {md_file}: {e}")
    
    return stats


def _backup_processing_markdown(backup_manager, config, session_db, dry_run, limit, force):
    """Backup processing session markdown files with database tracking."""
    stats = {'uploaded': 0, 'skipped': 0, 'failed': 0, 'total': 0}
    
    # NEW: Use centralized Session_notes directory
    notes_dir = Path(config.paths.notes_dir) / "Processing_Sessions"
    
    if not notes_dir.exists():
        click.echo("   No Processing_Sessions directory found")
        return stats
    
    # Find all markdown files - now named {session_id}.md
    markdown_files = sorted(notes_dir.rglob("*.md"))
    stats['total'] = len(markdown_files)
    
    if stats['total'] == 0:
        click.echo("   No processing session notes found")
        return stats
    
    for md_file in markdown_files:
        # Check upload limit
        if limit and stats['uploaded'] >= limit:
            break
        
        try:
            # Session ID is the filename without extension
            session_id = md_file.stem
            
            # Build S3 key
            s3_key = backup_manager._get_processing_note_key(session_id)
            
            # Check if upload needed (unless forced)
            if not force:
                needs_upload, reason = backup_manager.needs_markdown_backup(md_file, s3_key)
                
                if not needs_upload:
                    stats['skipped'] += 1
                    if dry_run:
                        click.echo(f"   ⊘ {md_file.name}: {reason}")
                    continue
                else:
                    if dry_run or force:
                        click.echo(f"   → {md_file.name}: {reason}")
            
            # In dry-run mode, don't actually upload
            if dry_run:
                stats['uploaded'] += 1
                continue
            
            metadata = {
                'session_id': session_id,
                'type': 'processing_session'
            }
            
            # Upload to S3
            result = backup_manager.upload_markdown(
                md_file, s3_key, 'processing_sessions', metadata, force=force
            )
            
            if result.success and result.needs_backup:
                stats['uploaded'] += 1
                click.echo(f"   ✓ {md_file.name}")
                
                # Save to database
                try:
                    # Check if record exists
                    existing = session_db.query(S3BackupProcessingSession).filter(
                        S3BackupProcessingSession.processing_session_id == session_id
                    ).first()
                    
                    if existing:
                        # Update existing record
                        existing.s3_etag = result.s3_etag
                        existing.uploaded_at = datetime.now()
                        existing.file_size_bytes = result.file_size
                    else:
                        # Create new record
                        backup_proc = S3BackupProcessingSession(
                            processing_session_id=session_id,
                            s3_bucket=backup_manager.s3_config.bucket,
                            s3_key=s3_key,
                            s3_region=backup_manager.s3_config.region,
                            s3_etag=result.s3_etag,
                            uploaded_at=datetime.now(),
                            file_size_bytes=result.file_size,
                            archive_policy='never',
                            backup_policy='never',
                            current_storage_class='STANDARD'
                        )
                        session_db.add(backup_proc)
                    
                    session_db.commit()
                    
                except Exception as db_error:
                    logger.warning(f"Failed to save database record for {session_id}: {db_error}")
                    session_db.rollback()
                    # Don't fail the whole operation if database save fails
                
            elif result.success and not result.needs_backup:
                stats['skipped'] += 1
            else:
                stats['failed'] += 1
                click.echo(f"   ✗ {md_file.name}: {result.error}")
            
        except Exception as e:
            stats['failed'] += 1
            click.echo(f"   ✗ {md_file.name}: {e}")
            logger.error(f"Failed to backup {md_file}: {e}")
    
    return stats


@cli.command('backup-markdown')
@click.option('--dry-run', is_flag=True, help='Show what would be backed up without uploading')
@click.option('--limit', type=int, default=None, help='Maximum number of files to upload')
@click.option('--imaging/--no-imaging', default=True, help='Backup imaging session notes')
@click.option('--processing/--no-processing', default=True, help='Backup processing session notes')
@click.option('--force', is_flag=True, help='Upload all files regardless of modification time')
@click.pass_context
def backup_markdown(ctx, dry_run, limit, imaging, processing, force):
    """
    Upload session markdown files to S3 with smart-skip.
    
    Only uploads files that are new or have been modified since last backup.
    Tracks uploads in the database.
    """
    backup_manager, db_manager, db_service = get_backup_manager(
        ctx.obj['config'], ctx.obj['s3_config'], dry_run=dry_run
    )
    
    session_db = db_manager.get_session()
    
    try:
        click.echo("\n" + "=" * 80)
        click.echo("SESSION MARKDOWN BACKUP TO S3")
        click.echo("=" * 80)
        
        if dry_run:
            click.echo("🔍 DRY RUN MODE - No files will be uploaded")
        
        if limit:
            click.echo(f"📊 Upload limit: {limit} files")
        
        if force:
            click.echo("⚠️  FORCE MODE - All files will be uploaded")
        
        click.echo()
        
        total_stats = {
            'uploaded': 0,
            'skipped': 0,
            'failed': 0,
            'total_checked': 0
        }
        
        # Get main config for paths
        from config import load_config
        main_config, _, _, _ = load_config(ctx.obj['config'])
        
        # Backup imaging sessions
        if imaging:
            click.echo("📸 Checking imaging session notes...")
            imaging_stats = _backup_imaging_markdown(
                backup_manager, main_config, session_db, dry_run, limit, force
            )
            total_stats['uploaded'] += imaging_stats['uploaded']
            total_stats['skipped'] += imaging_stats['skipped']
            total_stats['failed'] += imaging_stats['failed']
            total_stats['total_checked'] += imaging_stats['total']
            
            # Update limit
            if limit:
                limit -= imaging_stats['uploaded']
                if limit <= 0:
                    click.echo(f"\n✓ Upload limit reached")
                    _print_markdown_summary(total_stats, dry_run)
                    return
        
        # Backup processing sessions (NOW PASSES session_db)
        if processing:
            click.echo("\n🔧 Checking processing session notes...")
            processing_stats = _backup_processing_markdown(
                backup_manager, main_config, session_db, dry_run, limit, force
            )
            total_stats['uploaded'] += processing_stats['uploaded']
            total_stats['skipped'] += processing_stats['skipped']
            total_stats['failed'] += processing_stats['failed']
            total_stats['total_checked'] += processing_stats['total']
        
        # Print summary
        _print_markdown_summary(total_stats, dry_run)
        
    finally:
        session_db.close()
        db_manager.close()


@cli.command('markdown-status')
@click.option('--imaging/--no-imaging', default=True, help='Show imaging sessions')
@click.option('--processing/--no-processing', default=True, help='Show processing sessions')
@click.pass_context
def markdown_status(ctx, imaging, processing):
    """
    Check backup status of session markdown files.
    
    Shows which files are backed up and which need backup.
    """
    backup_manager, db_manager, db_service = get_backup_manager(
        ctx.obj['config'], ctx.obj['s3_config']
    )
    
    session_db = db_manager.get_session()
    
    try:
        click.echo("\n" + "=" * 80)
        click.echo("SESSION MARKDOWN BACKUP STATUS")
        click.echo("=" * 80)
        
        # Get main config for paths
        from config import load_config
        main_config, _, _, _ = load_config(ctx.obj['config'])
        
        if imaging:
            click.echo("\n📸 Imaging Sessions:")
            _check_imaging_markdown_status(backup_manager, main_config, session_db)
        
        if processing:
            click.echo("\n🔧 Processing Sessions:")
            _check_processing_markdown_status(backup_manager, main_config)
        
        click.echo()
        
    finally:
        session_db.close()
        db_manager.close()

# ============================================================================
# HELPER FUNCTIONS FOR MARKDOWN BACKUP
# ============================================================================

def _check_imaging_markdown_status(backup_manager, config, session_db):
    """Check status of imaging session backups (checks both S3 and database)."""
    # NEW: Use centralized Session_notes directory
    notes_dir = Path(config.paths.notes_dir) / "Imaging_Sessions"
    
    if not notes_dir.exists():
        click.echo("   No Imaging_Sessions directory found")
        return
    
    # Find all markdown files - no longer has _session_notes suffix
    markdown_files = sorted(notes_dir.rglob("*.md"))
    
    if not markdown_files:
        click.echo("   No imaging session notes found")
        return
    
    needs_backup = []
    backed_up = []
    
    for md_file in markdown_files:
        try:
            session_id = md_file.stem  # No more _session_notes suffix
            year = int(md_file.parent.name)
            
            # Check database first
            db_record = session_db.query(S3BackupSessionNote).filter(
                S3BackupSessionNote.session_id == session_id
            ).first()
            
            if db_record:
                # In database, show when backed up
                backed_up.append(f"{md_file.name} (backed up {db_record.uploaded_at.strftime('%Y-%m-%d')})")
            else:
                # Not in database, check S3 directly
                s3_key = backup_manager._get_session_note_key(session_id, year)
                needs, reason = backup_manager.needs_markdown_backup(md_file, s3_key)
                
                if needs:
                    needs_backup.append((md_file.name, reason))
                else:
                    # In S3 but not database - show as backed up
                    backed_up.append(f"{md_file.name} (in S3, not tracked)")
        
        except Exception as e:
            click.echo(f"   ✗ Error checking {md_file.name}: {e}")
    
    # Display results
    if backed_up:
        click.echo(f"\n   ✓ Backed up ({len(backed_up)}):")
        for name in backed_up[:5]:  # Show first 5
            click.echo(f"      • {name}")
        if len(backed_up) > 5:
            click.echo(f"      ... and {len(backed_up) - 5} more")
    
    if needs_backup:
        click.echo(f"\n   ⚠ Needs backup ({len(needs_backup)}):")
        for name, reason in needs_backup[:10]:  # Show first 10
            click.echo(f"      • {name}: {reason}")
        if len(needs_backup) > 10:
            click.echo(f"      ... and {len(needs_backup) - 10} more")


def _check_processing_markdown_status(backup_manager, config, session_db):
    """Check status of processing session backups (checks both S3 and database)."""
    # NEW: Use centralized Session_notes directory
    notes_dir = Path(config.paths.notes_dir) / "Processing_Sessions"
    
    if not notes_dir.exists():
        click.echo("   No Processing_Sessions directory found")
        return
    
    # Find all markdown files
    markdown_files = sorted(notes_dir.rglob("*.md"))
    
    if not markdown_files:
        click.echo("   No processing session notes found")
        return
    
    needs_backup = []
    backed_up = []
    
    for md_file in markdown_files:
        try:
            session_id = md_file.stem
            
            # Check database first
            db_record = session_db.query(S3BackupProcessingSession).filter(
                S3BackupProcessingSession.processing_session_id == session_id
            ).first()
            
            if db_record:
                # In database, show when backed up
                backed_up.append(f"{md_file.name} (backed up {db_record.uploaded_at.strftime('%Y-%m-%d')})")
            else:
                # Not in database, check S3 directly
                s3_key = backup_manager._get_processing_note_key(session_id)
                needs, reason = backup_manager.needs_markdown_backup(md_file, s3_key)
                
                if needs:
                    needs_backup.append((md_file.name, reason))
                else:
                    # In S3 but not database - show as backed up
                    backed_up.append(f"{md_file.name} (in S3, not tracked)")
        
        except Exception as e:
            click.echo(f"   ✗ Error checking {md_file.name}: {e}")
    
    # Display results
    if backed_up:
        click.echo(f"\n   ✓ Backed up ({len(backed_up)}):")
        for name in backed_up[:5]:  # Show first 5
            click.echo(f"      • {name}")
        if len(backed_up) > 5:
            click.echo(f"      ... and {len(backed_up) - 5} more")
    
    if needs_backup:
        click.echo(f"\n   ⚠ Needs backup ({len(needs_backup)}):")
        for name, reason in needs_backup[:10]:  # Show first 10
            click.echo(f"      • {name}: {reason}")
        if len(needs_backup) > 10:
            click.echo(f"      ... and {len(needs_backup) - 10} more")


def _print_markdown_summary(stats, dry_run):
    """Print backup summary."""
    click.echo("\n" + "=" * 80)
    click.echo("SUMMARY")
    click.echo("=" * 80)
    click.echo(f"Total files checked: {stats['total_checked']}")
    
    if dry_run:
        click.echo(f"Would upload:        {stats['uploaded']}")
    else:
        click.echo(f"Uploaded:            {stats['uploaded']}")
    
    click.echo(f"Skipped (current):   {stats['skipped']}")
    
    if stats['failed'] > 0:
        click.echo(f"Failed:              {stats['failed']}")
    
    click.echo()
    
    if dry_run:
        click.echo("💡 Run without --dry-run to perform actual upload")
    elif stats['uploaded'] > 0:
        click.echo("✓ Backup complete!")
    elif stats['skipped'] > 0:
        click.echo("✓ All files already backed up")
    else:
        click.echo("ℹ️  No markdown files found")


"""
S3 Database Sync Command - Add to s3_backup/cli.py

Polls S3 for all backup files and syncs database records.
Detects drift between S3 and local database.
"""

@cli.command('sync-database')
@click.option('--dry-run', is_flag=True, help='Show what would be synced without making changes')
@click.option('--archives/--no-archives', default=True, help='Sync FITS archive records')
@click.option('--markdown/--no-markdown', default=True, help='Sync markdown file records')
@click.pass_context
def sync_database(ctx, dry_run, archives, markdown):
    """
    Sync database with S3 - detect and fix drift.
    
    Polls S3 for all backup files and creates missing database records.
    Useful for detecting drift after database issues.
    
    Examples:
        # Dry-run to see what's missing
        python -m s3_backup.cli sync-database --dry-run
        
        # Sync only markdown files
        python -m s3_backup.cli sync-database --no-archives
        
        # Sync everything
        python -m s3_backup.cli sync-database
    """
    backup_manager, db_manager, db_service = get_backup_manager(
        ctx.obj['config'], ctx.obj['s3_config']
    )
    
    session_db = db_manager.get_session()
    
    try:
        click.echo("\n" + "=" * 80)
        click.echo("S3 DATABASE SYNC")
        click.echo("=" * 80)
        
        if dry_run:
            click.echo("🔍 DRY RUN MODE - No database changes will be made")
        
        click.echo(f"\nScanning S3 bucket: {backup_manager.s3_config.bucket}")
        click.echo()
        
        total_stats = {
            'archives_in_s3': 0,
            'archives_in_db': 0,
            'archives_added': 0,
            'markdown_in_s3': 0,
            'markdown_in_db': 0,
            'markdown_added': 0,
            'errors': 0
        }
        
        # Sync FITS archives
        if archives:
            click.echo("📦 Syncing FITS archive records...")
            archive_stats = _sync_fits_archives(
                backup_manager, session_db, dry_run
            )
            total_stats['archives_in_s3'] = archive_stats['in_s3']
            total_stats['archives_in_db'] = archive_stats['in_db']
            total_stats['archives_added'] = archive_stats['added']
            total_stats['errors'] += archive_stats['errors']
        
        # Sync markdown files
        if markdown:
            click.echo("\n📝 Syncing markdown file records...")
            markdown_stats = _sync_markdown_files(
                backup_manager, session_db, dry_run
            )
            total_stats['markdown_in_s3'] = markdown_stats['in_s3']
            total_stats['markdown_in_db'] = markdown_stats['in_db']
            total_stats['markdown_added'] = markdown_stats['added']
            total_stats['errors'] += markdown_stats['errors']
        
        # Print summary
        _print_sync_summary(total_stats, dry_run)
        
    finally:
        session_db.close()
        db_manager.close()


def _sync_fits_archives(backup_manager, session_db, dry_run):
    """Sync FITS archive records from S3."""
    stats = {'in_s3': 0, 'in_db': 0, 'added': 0, 'errors': 0}
    
    try:
        # Get all archives from S3
        click.echo("   Listing archives in S3...")
        
        s3_archives = {}
        paginator = backup_manager.s3_client.get_paginator('list_objects_v2')
        
        # Scan the raw_archives path
        raw_path = backup_manager.s3_config.config['s3_paths']['raw_archives']
        
        for page in paginator.paginate(
            Bucket=backup_manager.s3_config.bucket,
            Prefix=raw_path
        ):
            if 'Contents' not in page:
                continue
            
            for obj in page['Contents']:
                key = obj['Key']
                
                # Parse session_id from key (e.g., "backups/raw/2024/SESSION_ID.tar.gz")
                if key.endswith('.tar') or key.endswith('.tar.gz'):
                    filename = Path(key).stem
                    if filename.endswith('.tar'):
                        filename = filename[:-4]  # Remove .tar from .tar.gz
                    
                    session_id = filename
                    
                    # Extract year from path
                    parts = key.split('/')
                    try:
                        year_idx = parts.index('raw') + 1
                        year = int(parts[year_idx])
                    except:
                        year = None
                    
                    s3_archives[session_id] = {
                        's3_key': key,
                        'year': year,
                        'size': obj['Size'],
                        'etag': obj['ETag'].strip('"'),
                        'last_modified': obj['LastModified']
                    }
        
        stats['in_s3'] = len(s3_archives)
        click.echo(f"   Found {stats['in_s3']} archives in S3")
        
        # Get all archives from database
        db_archives = {}
        for record in session_db.query(S3BackupArchive).all():
            db_archives[record.session_id] = record
        
        stats['in_db'] = len(db_archives)
        click.echo(f"   Found {stats['in_db']} archives in database")
        
        # Find missing records
        missing = set(s3_archives.keys()) - set(db_archives.keys())
        
        if not missing:
            click.echo("   ✓ All S3 archives are tracked in database")
            return stats
        
        click.echo(f"\n   ⚠ Found {len(missing)} archives in S3 not tracked in database:")
        
        # Add missing records
        for session_id in sorted(missing):
            s3_info = s3_archives[session_id]
            
            try:
                click.echo(f"      • {session_id} ({format_bytes(s3_info['size'])})")
                
                if dry_run:
                    stats['added'] += 1
                    continue
                
                # Get session info from main database if available
                from models import Session as SessionModel
                imaging_session = session_db.query(SessionModel).filter(
                    SessionModel.session_id == session_id
                ).first()
                
                # Create database record
                archive_record = S3BackupArchive(
                    session_id=session_id,
                    session_date=imaging_session.session_date if imaging_session else None,
                    session_year=s3_info['year'],
                    s3_bucket=backup_manager.s3_config.bucket,
                    s3_key=s3_info['s3_key'],
                    s3_region=backup_manager.s3_config.region,
                    s3_etag=s3_info['etag'],
                    compressed_size_bytes=s3_info['size'],
                    uploaded_at=s3_info['last_modified'],
                    verified=True,
                    verification_method='sync_from_s3',
                    current_storage_class='STANDARD',
                    camera_name=imaging_session.camera if imaging_session else None,
                    telescope_name=imaging_session.telescope if imaging_session else None
                )
                
                session_db.add(archive_record)
                session_db.commit()
                stats['added'] += 1
                
            except Exception as e:
                stats['errors'] += 1
                click.echo(f"         ✗ Error: {e}")
                session_db.rollback()
        
        return stats
        
    except Exception as e:
        click.echo(f"   ✗ Error syncing archives: {e}")
        stats['errors'] += 1
        return stats


def _sync_markdown_files(backup_manager, session_db, dry_run):
    """Sync markdown file records from S3."""
    stats = {'in_s3': 0, 'in_db': 0, 'added': 0, 'errors': 0}
    
    try:
        # Get all markdown files from S3
        click.echo("   Listing markdown files in S3...")
        
        s3_imaging = {}
        s3_processing = {}
        paginator = backup_manager.s3_client.get_paginator('list_objects_v2')
        
        # Scan imaging session notes
        session_path = backup_manager.s3_config.config['s3_paths']['session_notes']
        
        for page in paginator.paginate(
            Bucket=backup_manager.s3_config.bucket,
            Prefix=session_path
        ):
            if 'Contents' not in page:
                continue
            
            for obj in page['Contents']:
                key = obj['Key']
                
                # FIXED: Look for .md files (no suffix)
                if key.endswith('.md'):
                    # Extract session_id from filename
                    filename = Path(key).stem  # Just the session_id
                    session_id = filename
                    
                    # Extract year from path
                    parts = key.split('/')
                    try:
                        year = int(parts[-2])  # Year is parent directory
                    except:
                        year = None
                    
                    s3_imaging[session_id] = {
                        's3_key': key,
                        'year': year,
                        'size': obj['Size'],
                        'etag': obj['ETag'].strip('"'),
                        'last_modified': obj['LastModified']
                    }

        # Scan processing session notes
        processing_path = backup_manager.s3_config.config['s3_paths']['processing_notes']
        
        for page in paginator.paginate(
            Bucket=backup_manager.s3_config.bucket,
            Prefix=processing_path
        ):
            if 'Contents' not in page:
                continue
            
            for obj in page['Contents']:
                key = obj['Key']
                
                # FIXED: Look for .md files (no suffix, not in subfolders)
                if key.endswith('.md'):
                    # Extract session_id from filename
                    filename = Path(key).stem
                    session_id = filename
                    
                    s3_processing[session_id] = {
                        's3_key': key,
                        'size': obj['Size'],
                        'etag': obj['ETag'].strip('"'),
                        'last_modified': obj['LastModified']
                    }
                    
        stats['in_s3'] = len(s3_imaging) + len(s3_processing)
        click.echo(f"   Found {len(s3_imaging)} imaging + {len(s3_processing)} processing = {stats['in_s3']} markdown files in S3")
        
        # Get database records
        db_imaging = {}
        for record in session_db.query(S3BackupSessionNote).all():
            db_imaging[record.session_id] = record
        
        db_processing = {}
        for record in session_db.query(S3BackupProcessingSession).all():
            db_processing[record.processing_session_id] = record
        
        stats['in_db'] = len(db_imaging) + len(db_processing)
        click.echo(f"   Found {len(db_imaging)} imaging + {len(db_processing)} processing = {stats['in_db']} markdown files in database")
        
        # Find missing imaging sessions
        missing_imaging = set(s3_imaging.keys()) - set(db_imaging.keys())
        
        if missing_imaging:
            click.echo(f"\n   ⚠ Found {len(missing_imaging)} imaging session notes in S3 not tracked:")
            
            for session_id in sorted(missing_imaging):
                s3_info = s3_imaging[session_id]
                
                try:
                    click.echo(f"      • {session_id}")
                    
                    if dry_run:
                        stats['added'] += 1
                        continue
                    
                    # Create database record
                    note_record = S3BackupSessionNote(
                        session_id=session_id,
                        session_year=s3_info['year'],
                        s3_bucket=backup_manager.s3_config.bucket,
                        s3_key=s3_info['s3_key'],
                        s3_region=backup_manager.s3_config.region,
                        s3_etag=s3_info['etag'],
                        uploaded_at=s3_info['last_modified'],
                        file_size_bytes=s3_info['size'],
                        archive_policy='never',
                        backup_policy='never',
                        current_storage_class='STANDARD',
                        verified=True
                    )
                    
                    session_db.add(note_record)
                    session_db.commit()
                    stats['added'] += 1
                    
                except Exception as e:
                    stats['errors'] += 1
                    click.echo(f"         ✗ Error: {e}")
                    session_db.rollback()
        
        # Find missing processing sessions
        missing_processing = set(s3_processing.keys()) - set(db_processing.keys())
        
        if missing_processing:
            click.echo(f"\n   ⚠ Found {len(missing_processing)} processing session notes in S3 not tracked:")
            
            for session_name in sorted(missing_processing):
                s3_info = s3_processing[session_name]
                
                try:
                    click.echo(f"      • {session_name}")
                    
                    if dry_run:
                        stats['added'] += 1
                        continue
                    
                    # Create database record
                    proc_record = S3BackupProcessingSession(
                        processing_session_id=session_name,
                        s3_bucket=backup_manager.s3_config.bucket,
                        s3_key=s3_info['s3_key'],
                        s3_region=backup_manager.s3_config.region,
                        s3_etag=s3_info['etag'],
                        uploaded_at=s3_info['last_modified'],
                        file_size_bytes=s3_info['size'],
                        archive_policy='never',
                        backup_policy='never',
                        current_storage_class='STANDARD'
                    )
                    
                    session_db.add(proc_record)
                    session_db.commit()
                    stats['added'] += 1
                    
                except Exception as e:
                    stats['errors'] += 1
                    click.echo(f"         ✗ Error: {e}")
                    session_db.rollback()
        
        if not missing_imaging and not missing_processing:
            click.echo("   ✓ All S3 markdown files are tracked in database")
        
        return stats
        
    except Exception as e:
        click.echo(f"   ✗ Error syncing markdown: {e}")
        stats['errors'] += 1
        return stats


def _print_sync_summary(stats, dry_run):
    """Print sync summary."""
    click.echo("\n" + "=" * 80)
    click.echo("SYNC SUMMARY")
    click.echo("=" * 80)
    
    if stats['archives_in_s3'] > 0:
        click.echo(f"\nFITS Archives:")
        click.echo(f"  In S3:            {stats['archives_in_s3']}")
        click.echo(f"  In database:      {stats['archives_in_db']}")
        if dry_run:
            click.echo(f"  Would add:        {stats['archives_added']}")
        else:
            click.echo(f"  Added:            {stats['archives_added']}")
    
    if stats['markdown_in_s3'] > 0:
        click.echo(f"\nMarkdown Files:")
        click.echo(f"  In S3:            {stats['markdown_in_s3']}")
        click.echo(f"  In database:      {stats['markdown_in_db']}")
        if dry_run:
            click.echo(f"  Would add:        {stats['markdown_added']}")
        else:
            click.echo(f"  Added:            {stats['markdown_added']}")
    
    if stats['errors'] > 0:
        click.echo(f"\nErrors:             {stats['errors']}")
    
    click.echo()
    
    if dry_run:
        click.echo("💡 Run without --dry-run to add missing records to database")
    elif stats['archives_added'] + stats['markdown_added'] > 0:
        click.echo("✓ Database sync complete!")
    else:
        click.echo("✓ Database already in sync with S3")


@cli.command('backup-database')
@click.option('--db-path', type=click.Path(exists=True), help='Path to SQLite database file (default: from config)')
@click.option('--description', help='Optional description for this backup version')
@click.pass_context
def backup_database(ctx, db_path, description):
    """
    Backup the database file to S3 with versioning.
    
    Creates a timestamped backup of the SQLite database in S3.
    S3 bucket versioning keeps all previous versions automatically.
    """
    backup_manager, db_manager, db_service = get_backup_manager(
        ctx.obj['config'], ctx.obj['s3_config']
    )
    
    try:
        # Get database path from config if not specified
        if not db_path:
            from config import load_config
            main_config, _, _, _ = load_config(ctx.obj['config'])
            db_path = Path(main_config.paths.database_path)
        else:
            db_path = Path(db_path)
        
        if not db_path.exists():
            click.echo(f"❌ Database file not found: {db_path}")
            return
        
        click.echo(f"\n💾 Backing up database: {db_path.name}")
        
        result = backup_manager.backup_database(db_path, description)
        
        if result['success']:
            click.echo(f"✅ Database backup successful!")
            click.echo(f"   S3 Key: {result['s3_key']}")
            click.echo(f"   Size: {format_bytes(result['size'])}")
            if result.get('version_id'):
                click.echo(f"   Version ID: {result['version_id']}")
            if description:
                click.echo(f"   Description: {description}")
        else:
            click.echo(f"❌ Backup failed: {result.get('error')}")
            
    finally:
        db_manager.close()


@cli.command('list-database-backups')
@click.pass_context
def list_database_backups(ctx):
    """List all database backup versions in S3."""
    backup_manager, db_manager, db_service = get_backup_manager(
        ctx.obj['config'], ctx.obj['s3_config']
    )
    
    try:
        click.echo("\n📋 Database Backup Versions:\n")
        
        versions = backup_manager.list_database_versions()
        
        if not versions:
            click.echo("No database backups found in S3.")
            return
        
        # Prepare table data
        table_data = []
        for v in versions:
            table_data.append([
                v['timestamp'],
                format_bytes(v['size']),
                v.get('description', '-')[:40],
                v.get('version_id', '-')[:20]
            ])
        
        headers = ['Timestamp', 'Size', 'Description', 'Version ID']
        click.echo(tabulate(table_data, headers=headers, tablefmt='grid'))
        click.echo(f"\nTotal: {len(versions)} backup(s)\n")
        
    finally:
        db_manager.close()


@cli.command('restore-database')
@click.option('--version-id', required=True, help='S3 version ID to restore')
@click.option('--output', type=click.Path(), required=True, help='Output path for restored database')
@click.pass_context
def restore_database(ctx, version_id, output):
    """Restore a specific database version from S3."""
    backup_manager, db_manager, db_service = get_backup_manager(
        ctx.obj['config'], ctx.obj['s3_config']
    )
    
    try:
        output_path = Path(output)
        
        if output_path.exists():
            if not click.confirm(f"⚠️  File {output} already exists. Overwrite?"):
                click.echo("Restore cancelled.")
                return
        
        click.echo(f"\n📥 Restoring database version: {version_id}")
        
        result = backup_manager.restore_database(version_id, output_path)
        
        if result['success']:
            click.echo(f"✅ Database restored successfully!")
            click.echo(f"   Output: {output_path}")
            click.echo(f"   Size: {format_bytes(result['size'])}")
        else:
            click.echo(f"❌ Restore failed: {result.get('error')}")
            
    finally:
        db_manager.close()


@cli.group('processed')
@click.pass_context
def processed(ctx):
    """Backup processed final output files (JPG, XISF)."""
    pass


@processed.command('status')
@click.pass_context
def processed_status(ctx):
    """Show backup status of processed files."""
    from processed_catalog.models import ProcessedFile
    from models import ProcessingSession
    from s3_backup.models import S3BackupProcessedFiles
    
    config, cameras, telescopes, filter_mappings = load_config(ctx.obj['config'])
    db_manager = DatabaseManager(config.database.connection_string)
    db_session = db_manager.get_session()
    
    try:
        # Load S3 config
        s3_config = S3BackupConfig(ctx.obj['s3_config'])
        
        # Get sessions with final files (JPG/XISF only)
        sessions_with_finals = db_session.query(ProcessedFile.processing_session_id).filter(
            ProcessedFile.subfolder == 'final',
            ProcessedFile.file_type.in_(['jpg', 'jpeg', 'xisf'])
        ).distinct().all()
        
        session_ids = [s[0] for s in sessions_with_finals]
        
        # Get backed up sessions
        backed_up = db_session.query(S3BackupProcessedFiles).all()
        backed_up_ids = {b.processing_session_id for b in backed_up}
        
        # Calculate statistics
        total_sessions = len(session_ids)
        backed_up_count = len(backed_up_ids)
        not_backed_up = total_sessions - backed_up_count
        
        total_files = sum(b.file_count or 0 for b in backed_up)
        total_original = sum(b.original_size_bytes or 0 for b in backed_up)
        total_archive = sum(b.archive_size_bytes or 0 for b in backed_up)
        
        # Display status
        click.echo("=" * 80)
        click.echo("PROCESSED FILES BACKUP STATUS")
        click.echo("=" * 80)
        
        click.echo(f"\nBucket: s3://{s3_config.bucket}")
        click.echo(f"Prefix: backups/processed/")
        
        click.echo(f"\nProcessing Sessions with Final Files:")
        click.echo(f"  Total sessions: {total_sessions}")
        click.echo(f"  Backed up: {backed_up_count}")
        click.echo(f"  Not backed up: {not_backed_up}")
        if total_sessions > 0:
            click.echo(f"  Backup percentage: {(backed_up_count / total_sessions * 100):.1f}%")
        
        click.echo(f"\nBackup Statistics:")
        click.echo(f"  Total files backed up: {total_files:,}")
        click.echo(f"  Original size: {total_original / 1024 / 1024 / 1024:.2f} GB")
        click.echo(f"  Archive size: {total_archive / 1024 / 1024 / 1024:.2f} GB")
        
        if not_backed_up > 0:
            click.echo(f"\n⚠️  {not_backed_up} session(s) with final files need backup")
        else:
            click.echo(f"\n✓ All sessions with final files are backed up")
        
        click.echo("\n" + "=" * 80 + "\n")
        
    finally:
        db_session.close()
        db_manager.close()


@processed.command('upload')
@click.option('--session-id', '-s', help='Backup specific processing session')
@click.option('--all', 'backup_all', is_flag=True, help='Backup all sessions with final files')
@click.option('--limit', '-l', type=int, help='Limit number of sessions to backup')
@click.option('--skip-existing', is_flag=True, default=True, help='Skip already backed up sessions')
@click.option('--no-cleanup', is_flag=True, help='Keep local archives after upload')
@click.pass_context
def processed_upload(ctx, session_id, backup_all, limit, skip_existing, no_cleanup):
    """Upload processed final files to S3."""
    import tarfile
    import tempfile
    from pathlib import Path
    from processed_catalog.models import ProcessedFile
    from s3_backup.models import S3BackupProcessedFiles
    
    config, cameras, telescopes, filter_mappings = load_config(ctx.obj['config'])
    db_manager = DatabaseManager(config.database.connection_string)
    db_session = db_manager.get_session()
    
    try:
        # Load S3 config and create S3 client
        s3_config = S3BackupConfig(ctx.obj['s3_config'])
        import boto3
        s3_client = boto3.client('s3', region_name=s3_config.region)
        
        # Temp directory for archives
        temp_dir = Path(tempfile.gettempdir()) / "astrocat_processed_archives"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Build session list
        if session_id:
            sessions = [session_id]
        elif backup_all:
            # Get all sessions with final files
            sessions_query = db_session.query(ProcessedFile.processing_session_id).filter(
                ProcessedFile.subfolder == 'final',
                ProcessedFile.file_type.in_(['jpg', 'jpeg', 'xisf'])
            ).distinct().all()
            
            sessions = [s[0] for s in sessions_query]
            
            # Filter out already backed up if skip_existing
            if skip_existing:
                backed_up = db_session.query(S3BackupProcessedFiles.processing_session_id).all()
                backed_up_ids = {b[0] for b in backed_up}
                sessions = [s for s in sessions if s not in backed_up_ids]
            
            # Apply limit
            if limit and len(sessions) > limit:
                sessions = sessions[:limit]
        else:
            click.echo("Error: Specify either --session-id or --all")
            return
        
        if not sessions:
            click.echo("No sessions to backup.")
            return
        
        click.echo(f"\nFound {len(sessions)} session(s) to backup")
        
        # Track results
        results = {
            'success': 0,
            'skipped': 0,
            'failed': 0,
            'total_files': 0,
            'total_bytes': 0
        }
        
        # Upload each session
        with tqdm(total=len(sessions), desc="Backing up sessions", unit="session") as pbar:
            for ps_id in sessions:
                pbar.set_description(f"Processing {ps_id[:20]}")
                
                try:
                    # Get files to backup (final JPG/XISF only)
                    files = db_session.query(ProcessedFile).filter(
                        ProcessedFile.processing_session_id == ps_id,
                        ProcessedFile.subfolder == 'final',
                        ProcessedFile.file_type.in_(['jpg', 'jpeg', 'xisf'])
                    ).all()
                    
                    if not files:
                        tqdm.write(f"⏭️  {ps_id}: No final files to backup")
                        results['skipped'] += 1
                        pbar.update(1)
                        continue
                    
                    # Check if already exists in S3
                    if skip_existing:
                        try:
                            year = int(ps_id[:4])
                        except (ValueError, IndexError):
                            year = datetime.now().year
                        
                        archive_filename = f"{ps_id}_final.tar"
                        s3_key = f"backups/processed/{year}/{archive_filename}"
                        
                        try:
                            s3_client.head_object(Bucket=s3_config.bucket, Key=s3_key)
                            tqdm.write(f"⏭️  {ps_id}: Already in S3 (skipped)")
                            results['skipped'] += 1
                            pbar.update(1)
                            continue
                        except:
                            pass  # Doesn't exist, continue with backup
                    
                    # Create archive
                    archive_path = temp_dir / f"{ps_id}_final.tar"
                    
                    total_size = 0
                    files_added = 0
                    
                    with tarfile.open(archive_path, 'w') as tar:
                        for file_record in files:
                            file_path = Path(file_record.file_path)
                            
                            if file_path.exists():
                                arcname = file_path.name
                                tar.add(file_path, arcname=arcname)
                                files_added += 1
                                total_size += file_record.file_size or 0
                            else:
                                logger.warning(f"File not found: {file_path}")
                    
                    if files_added == 0:
                        tqdm.write(f"❌ {ps_id}: No files found on disk")
                        results['failed'] += 1
                        archive_path.unlink(missing_ok=True)
                        pbar.update(1)
                        continue
                    
                    # Upload to S3
                    archive_size = archive_path.stat().st_size
                    
                    try:
                        year = int(ps_id[:4])
                    except (ValueError, IndexError):
                        year = datetime.now().year
                    
                    s3_key = f"backups/processed/{year}/{archive_path.name}"
                    
                    # Load archive policies from config
                    archive_policy = s3_config.config.get('backup_rules', {}).get('final_outputs', {}).get('archive_policy', 'standard')
                    backup_policy = s3_config.config.get('backup_rules', {}).get('final_outputs', {}).get('backup_policy', 'flexible')

                    # Create tags matching the pattern used for other backups
                    tags = f"archive_policy={archive_policy}&backup_policy={backup_policy}"

                    with open(archive_path, 'rb') as f:
                        response = s3_client.put_object(
                            Bucket=s3_config.bucket,
                            Key=s3_key,
                            Body=f,
                            StorageClass='STANDARD',
                            Tagging=tags
                        )
                    
                    etag = response['ETag'].strip('"')
                    
                    # Save to database
                    backup_record = S3BackupProcessedFiles(
                        processing_session_id=ps_id,
                        s3_bucket=s3_config.bucket,
                        s3_key=s3_key,
                        s3_region=s3_config.region,
                        s3_etag=etag,
                        uploaded_at=datetime.utcnow(),
                        file_count=files_added,
                        original_size_bytes=total_size,
                        archive_size_bytes=archive_size,
                        archive_format='tar',
                        storage_class='STANDARD'
                    )
                    
                    # Merge (insert or update)
                    existing = db_session.query(S3BackupProcessedFiles).filter(
                        S3BackupProcessedFiles.processing_session_id == ps_id
                    ).first()
                    
                    if existing:
                        for key, value in backup_record.__dict__.items():
                            if not key.startswith('_'):
                                setattr(existing, key, value)
                    else:
                        db_session.add(backup_record)
                    
                    db_session.commit()
                    
                    # Cleanup
                    if not no_cleanup:
                        archive_path.unlink()
                    
                    results['success'] += 1
                    results['total_files'] += files_added
                    results['total_bytes'] += archive_size
                    
                    tqdm.write(f"✓ {ps_id}: {files_added} files, "
                             f"{archive_size / 1024 / 1024:.2f} MB")
                    
                except Exception as e:
                    tqdm.write(f"❌ {ps_id}: {str(e)}")
                    results['failed'] += 1
                
                pbar.update(1)
        
        # Print summary
        click.echo("\n" + "=" * 80)
        click.echo("BACKUP SUMMARY")
        click.echo("=" * 80)
        click.echo(f"Successful: {results['success']}")
        click.echo(f"Skipped: {results['skipped']}")
        click.echo(f"Failed: {results['failed']}")
        click.echo(f"Total files backed up: {results['total_files']:,}")
        click.echo(f"Total data uploaded: {results['total_bytes'] / 1024 / 1024 / 1024:.2f} GB")
        click.echo("=" * 80 + "\n")
        
    finally:
        db_session.close()
        db_manager.close()


@processed.command('verify')
@click.option('--session-id', '-s', help='Verify specific processing session')
@click.option('--all', 'verify_all', is_flag=True, help='Verify all backed up sessions')
@click.pass_context
def processed_verify(ctx, session_id, verify_all):
    """Verify backed up archives exist in S3."""
    from s3_backup.models import S3BackupProcessedFiles
    import boto3
    
    config, cameras, telescopes, filter_mappings = load_config(ctx.obj['config'])
    db_manager = DatabaseManager(config.database.connection_string)
    db_session = db_manager.get_session()
    
    try:
        # Load S3 config
        s3_config = S3BackupConfig(ctx.obj['s3_config'])
        s3_client = boto3.client('s3', region_name=s3_config.region)
        
        # Get sessions to verify
        if session_id:
            backups = db_session.query(S3BackupProcessedFiles).filter(
                S3BackupProcessedFiles.processing_session_id == session_id
            ).all()
        elif verify_all:
            backups = db_session.query(S3BackupProcessedFiles).all()
        else:
            click.echo("Error: Specify either --session-id or --all")
            return
        
        if not backups:
            click.echo("No backups found to verify.")
            return
        
        click.echo(f"\nVerifying {len(backups)} backup(s)...")
        
        results = {'verified': 0, 'failed': 0}
        
        with tqdm(total=len(backups), desc="Verifying", unit="backup") as pbar:
            for backup in backups:
                try:
                    # Check if object exists in S3
                    response = s3_client.head_object(
                        Bucket=backup.s3_bucket,
                        Key=backup.s3_key
                    )
                    
                    etag = response['ETag'].strip('"')
                    
                    # Update verification in database
                    backup.verified = True
                    backup.verified_at = datetime.utcnow()
                    backup.verification_etag = etag
                    db_session.commit()
                    
                    results['verified'] += 1
                    tqdm.write(f"✓ {backup.processing_session_id}: Verified")
                    
                except Exception as e:
                    backup.verified = False
                    db_session.commit()
                    
                    results['failed'] += 1
                    tqdm.write(f"❌ {backup.processing_session_id}: {str(e)}")
                
                pbar.update(1)
        
        # Print summary
        click.echo("\n" + "=" * 80)
        click.echo("VERIFICATION SUMMARY")
        click.echo("=" * 80)
        click.echo(f"Verified: {results['verified']}")
        click.echo(f"Failed: {results['failed']}")
        click.echo("=" * 80 + "\n")
        
    finally:
        db_session.close()
        db_manager.close()


@processed.command('list')
@click.option('--not-backed-up', is_flag=True, help='Show only sessions not backed up')
@click.pass_context
def processed_list(ctx, not_backed_up):
    """List processing sessions with final files."""
    from processed_catalog.models import ProcessedFile
    from s3_backup.models import S3BackupProcessedFiles
    
    config, cameras, telescopes, filter_mappings = load_config(ctx.obj['config'])
    db_manager = DatabaseManager(config.database.connection_string)
    db_session = db_manager.get_session()
    
    try:
        # Get all sessions with finals
        all_sessions_query = db_session.query(ProcessedFile.processing_session_id).filter(
            ProcessedFile.subfolder == 'final',
            ProcessedFile.file_type.in_(['jpg', 'jpeg', 'xisf'])
        ).distinct().all()
        
        all_sessions = [s[0] for s in all_sessions_query]
        
        # Get backed up sessions
        backed_up = db_session.query(S3BackupProcessedFiles.processing_session_id).all()
        backed_up_ids = {b[0] for b in backed_up}
        
        if not_backed_up:
            sessions = [s for s in all_sessions if s not in backed_up_ids]
            click.echo(f"\nProcessing sessions with final files (NOT backed up): {len(sessions)}")
        else:
            sessions = all_sessions
            click.echo(f"\nProcessing sessions with final files: {len(sessions)}")
        
        for session_id in sorted(sessions):
            # Get file count for this session
            files = db_session.query(ProcessedFile).filter(
                ProcessedFile.processing_session_id == session_id,
                ProcessedFile.subfolder == 'final',
                ProcessedFile.file_type.in_(['jpg', 'jpeg', 'xisf'])
            ).all()
            
            file_count = len(files)
            total_size = sum(f.file_size or 0 for f in files)
            
            status = "✓" if session_id in backed_up_ids else " "
            click.echo(f"{status} {session_id}: {file_count} files, "
                      f"{total_size / 1024 / 1024:.2f} MB")
        
        click.echo()
        
    finally:
        db_session.close()
        db_manager.close()


if __name__ == '__main__':
    cli()
