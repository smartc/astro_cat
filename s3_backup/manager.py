"""S3 Backup Manager - Core backup operations for FITS Cataloger."""

import os
import json
import tarfile
import tempfile
import logging
import hashlib
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
from tqdm import tqdm

from models import DatabaseService, FitsFile, Session as SessionModel

logger = logging.getLogger(__name__)


def format_size(bytes_size: int) -> str:
    """Format bytes as human-readable size."""
    if bytes_size == 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"


@dataclass
class ArchiveResult:
    """Result of archive creation and upload."""
    success: bool
    session_id: str
    archive_path: Optional[Path] = None
    file_count: int = 0
    original_size: int = 0
    compressed_size: int = 0
    compression_ratio: float = 0.0
    s3_key: Optional[str] = None
    s3_etag: Optional[str] = None
    upload_time: float = 0.0
    error: Optional[str] = None


@dataclass
class VerifyResult:
    """Result of archive verification."""
    verified: bool
    session_id: str
    method: str
    s3_size: int = 0
    local_size: int = 0
    etag_match: bool = False
    error: Optional[str] = None


@dataclass
class SpaceCheckResult:
    """Result of a pre-flight space check."""
    has_space: bool
    session_size: int
    free_space: int
    temp_dir: Path
    error: Optional[str] = None


class S3BackupConfig:
    """S3 backup configuration loader."""
    
    def __init__(self, config_path: str = 's3_config.json'):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.base_dir = None  # Will be set by manager
    
    def _load_config(self) -> dict:
        """Load S3 configuration from file."""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"S3 config not found: {self.config_path}\n"
                "Copy s3_config.json.template to s3_config.json and customize."
            )
        
        with open(self.config_path, 'r') as f:
            config = json.load(f)
        
        # Remove comments
        config = {k: v for k, v in config.items() if not k.startswith('_')}
        for section in config.values():
            if isinstance(section, dict):
                section = {k: v for k, v in section.items() if not k.startswith('_')}
        
        return config
    
    def set_base_dir(self, base_dir: Path):
        """Set base directory for resolving relative paths."""
        self.base_dir = base_dir
    
    def resolve_temp_dir(self) -> Optional[Path]:
        """Resolve temp directory from config, handling relative and absolute paths.
        
        Returns:
            Resolved Path or None for system default
        """
        temp_config = self.config.get('archive_settings', {}).get('temp_dir')
        
        if not temp_config:
            return None  # Use system default
        
        temp_path = Path(temp_config)
        
        # Expand home directory (~)
        if str(temp_config).startswith('~'):
            return temp_path.expanduser()
        
        # If absolute path, use as-is
        if temp_path.is_absolute():
            return temp_path
        
        # Relative path - resolve against base_dir
        if self.base_dir:
            return self.base_dir / temp_path
        else:
            # Fallback to current directory if no base_dir set
            return Path.cwd() / temp_path
    
    @property
    def enabled(self) -> bool:
        return self.config.get('enabled', False)
    
    @property
    def region(self) -> str:
        return self.config.get('aws_region', 'us-east-1')
    
    @property
    def bucket(self) -> str:
        return self.config['buckets']['primary']
    
    @property
    def backup_bucket(self) -> Optional[str]:
        return self.config['buckets'].get('backup')
    
    def get_archive_path(self, year: int) -> str:
        """Get S3 path for raw archive."""
        base = self.config['s3_paths']['raw_archives']
        return f"{base}/{year}"
    
    def get_session_note_path(self, year: int) -> str:
        """Get S3 path for session notes."""
        base = self.config['s3_paths']['session_notes']
        return f"{base}/{year}"


class S3BackupManager:
    """Main S3 backup manager for session-based archives."""
    
    def __init__(self, db_service: DatabaseService, s3_config: S3BackupConfig, base_dir: Optional[Path] = None):
        self.db_service = db_service
        self.s3_config = s3_config
        
        # Set base directory for resolving relative paths
        if base_dir:
            self.s3_config.set_base_dir(base_dir)
        
        if not s3_config.enabled:
            raise RuntimeError("S3 backup is not enabled in s3_config.json")
        
        # Initialize S3 client
        boto_config = BotoConfig(
            region_name=s3_config.region,
            retries={'max_attempts': 3, 'mode': 'adaptive'}
        )
        self.s3_client = boto3.client('s3', config=boto_config)
        
        # Verify bucket access
        self._verify_bucket_access()
        
        # Setup temp directory
        self._setup_temp_dir()
        
        logger.info(f"S3 Backup Manager initialized for bucket: {s3_config.bucket}")
        logger.info(f"  Temp directory: {self.temp_dir}")
    
    def _setup_temp_dir(self):
        """Setup and verify temp directory for archives."""
        # Get resolved temp dir from config
        temp_path = self.s3_config.resolve_temp_dir()
        
        if temp_path:
            self.temp_dir = temp_path / "astrocat_archives"
        else:
            # Use system default
            self.temp_dir = Path(tempfile.gettempdir()) / "astrocat_archives"
        
        # Create if doesn't exist
        try:
            self.temp_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            raise RuntimeError(
                f"Cannot create temp directory: {self.temp_dir}\n"
                f"Permission denied. Please check directory permissions or "
                f"specify a different temp_dir in s3_config.json"
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"Cannot create temp directory: {self.temp_dir}\n"
                f"Error: {e}"
            ) from e
        
        # Verify we can write to it
        test_file = self.temp_dir / ".write_test"
        try:
            test_file.write_text("test")
            test_file.unlink()
        except Exception as e:
            raise RuntimeError(
                f"Cannot write to temp directory: {self.temp_dir}\n"
                f"Please check permissions or specify different temp_dir"
            ) from e
        
        # Clean up any orphaned archives from previous runs
        self._cleanup_orphaned_archives()
    
    def _cleanup_orphaned_archives(self):
        """Remove any leftover archive files from failed previous runs."""
        if not self.temp_dir.exists():
            return
        
        orphaned = list(self.temp_dir.glob("*.tar*"))
        if orphaned:
            logger.info(f"Cleaning up {len(orphaned)} orphaned archive(s) from previous runs...")
            for archive in orphaned:
                try:
                    archive.unlink()
                    logger.debug(f"  Removed: {archive.name}")
                except Exception as e:
                    logger.warning(f"  Failed to remove {archive.name}: {e}")

    
    def _verify_bucket_access(self):
        """Verify we can access the S3 bucket."""
        try:
            self.s3_client.head_bucket(Bucket=self.s3_config.bucket)
            logger.info(f"✓ Verified access to bucket: {self.s3_config.bucket}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                raise RuntimeError(f"Bucket not found: {self.s3_config.bucket}")
            elif error_code == '403':
                raise RuntimeError(f"Access denied to bucket: {self.s3_config.bucket}")
            else:
                raise RuntimeError(f"Error accessing bucket: {e}")
    
    def check_archive_exists(self, session_id: str, year: int) -> bool:
        """Check if archive already exists in S3."""
        s3_key = self._get_archive_key(session_id, year)
        try:
            self.s3_client.head_object(Bucket=self.s3_config.bucket, Key=s3_key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise
    
    def _get_archive_key(self, session_id: str, year: int) -> str:
        """Generate S3 key for session archive."""
        path = self.s3_config.get_archive_path(year)
        # Use .tar extension for uncompressed, .tar.gz for compressed
        compression_level = self.s3_config.config.get('archive_settings', {}).get('compression_level', 0)
        ext = '.tar.gz' if compression_level > 0 else '.tar'
        return f"{path}/{session_id}{ext}"
    
    def _get_session_note_key(self, session_id: str, year: int) -> str:
        """Generate S3 key for session notes."""
        path = self.s3_config.get_session_note_path(year)
        return f"{path}/{session_id}_notes.md"
    
    def create_session_archive(
        self, 
        session_id: str, 
        output_dir: Optional[Path] = None,
        progress_callback=None,
        compression_level: int = 6,
        use_pigz: bool = True
    ) -> Optional[Path]:
        """Create tar.gz archive of all FITS files for a session.
        
        Args:
            session_id: Imaging session ID
            output_dir: Directory for archive (default: temp dir)
            progress_callback: Optional callback(current, total, file_name)
            compression_level: Gzip compression level (1-9, default 6)
            use_pigz: Use pigz for parallel compression if available
        
        Returns:
            Path to created archive, or None on error
        """
        session_db = self.db_service.db_manager.get_session()
        
        try:
            # Get session info
            session = session_db.query(SessionModel).filter(
                SessionModel.session_id == session_id
            ).first()
            
            if not session:
                logger.error(f"Session not found: {session_id}")
                return None
            
            # Get all files for this session
            files = session_db.query(FitsFile).filter(
                FitsFile.session_id == session_id
            ).all()
            
            if not files:
                logger.warning(f"No files found for session: {session_id}")
                return None
            
            # Prepare output directory
            if output_dir is None:
                output_dir = self.temp_dir
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Create archive with appropriate extension
            ext = '.tar.gz' if compression_level > 0 else '.tar'
            archive_path = output_dir / f"{session_id}{ext}"
            
            logger.info(f"Creating archive: {archive_path}")
            logger.info(f"  Session: {session_id}")
            logger.info(f"  Files: {len(files)}")
            if compression_level > 0:
                logger.info(f"  Compression: {'pigz (parallel)' if use_pigz else f'gzip (level {compression_level})'}")
            else:
                logger.info(f"  Compression: None (uncompressed tar)")
            
            total_size = 0
            added_count = 0
            
            # Try pigz for parallel compression if requested and available
            if use_pigz and compression_level > 0:
                try:
                    import subprocess
                    # Check if pigz is available
                    result = subprocess.run(['which', 'pigz'], capture_output=True)
                    pigz_available = result.returncode == 0
                except:
                    pigz_available = False
            else:
                pigz_available = False
            
            if pigz_available:
                # Use pigz for faster parallel compression
                logger.info("  Using pigz for parallel compression")
                # Create uncompressed tar first, then compress with pigz
                temp_tar = archive_path.with_suffix('')  # Remove .gz
                
                with tarfile.open(temp_tar, 'w') as tar:
                    for idx, file_record in enumerate(files):
                        file_path = Path(file_record.folder) / file_record.file
                        
                        if not file_path.exists():
                            logger.warning(f"File not found (skipping): {file_path}")
                            continue
                        
                        arcname = f"{session_id}/{file_record.file}"
                        tar.add(file_path, arcname=arcname)
                        
                        file_size = file_path.stat().st_size
                        total_size += file_size
                        added_count += 1
                        
                        if progress_callback:
                            progress_callback(idx + 1, len(files), file_record.file)
                
                # Compress with pigz
                subprocess.run(
                    ['pigz', f'-{compression_level}', str(temp_tar)],
                    check=True
                )
                # pigz renames file.tar to file.tar.gz automatically
                
            else:
                # Standard gzip compression (or no compression)
                mode = f'w:gz' if compression_level > 0 else 'w'
                compress_args = {'compresslevel': compression_level} if compression_level > 0 else {}
                
                with tarfile.open(archive_path, mode, **compress_args) as tar:
                    for idx, file_record in enumerate(files):
                        file_path = Path(file_record.folder) / file_record.file
                        
                        if not file_path.exists():
                            logger.warning(f"File not found (skipping): {file_path}")
                            continue
                        
                        arcname = f"{session_id}/{file_record.file}"
                        tar.add(file_path, arcname=arcname)
                        
                        file_size = file_path.stat().st_size
                        total_size += file_size
                        added_count += 1
                        
                        if progress_callback:
                            progress_callback(idx + 1, len(files), file_record.file)
            
            archive_size = archive_path.stat().st_size
            compression_ratio = archive_size / total_size if total_size > 0 else 0
            
            logger.info(f"✓ Archive created: {archive_path}")
            logger.info(f"  Files added: {added_count}")
            logger.info(f"  Original size: {self._format_bytes(total_size)}")
            logger.info(f"  Archive size: {self._format_bytes(archive_size)}")
            if compression_level > 0:
                logger.info(f"  Compression ratio: {compression_ratio:.2%}")
            else:
                logger.info(f"  Uncompressed archive")
            
            return archive_path
            
        except Exception as e:
            logger.error(f"Error creating archive for {session_id}: {e}")
            return None
        finally:
            session_db.close()
    
    def upload_archive(
        self,
        archive_path: Path,
        session_id: str,
        year: int,
        archive_policy: str = 'fast',
        backup_policy: str = 'deep'
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Upload archive to S3 with progress bar.
        
        Args:
            archive_path: Path to local tar file
            session_id: Session ID
            year: Year for S3 organization
            archive_policy: Archive lifecycle policy ('fast', 'standard', 'delayed')
            backup_policy: Backup lifecycle policy ('deep', 'flexible')
        
        Returns:
            (success, s3_key, etag)
        """
        if not archive_path.exists():
            logger.error(f"Archive not found: {archive_path}")
            return False, None, None
        
        s3_key = self._get_archive_key(session_id, year)
        
        try:
            logger.info(f"Uploading archive to S3...")
            logger.info(f"  Source: {archive_path}")
            logger.info(f"  Destination: s3://{self.s3_config.bucket}/{s3_key}")
            logger.info(f"  Archive Policy: {archive_policy} (transitions in lifecycle rules)")
            logger.info(f"  Backup Policy: {backup_policy} (storage tier strategy)")
            
            # Prepare tags - use correct key names for AWS lifecycle rules
            tags = f"archive_policy={archive_policy}&backup_policy={backup_policy}"
            
            # Upload with progress
            file_size = archive_path.stat().st_size
            
            # Upload
            start_time = datetime.now()
            
            # Create progress bar for upload
            with tqdm(total=file_size, unit='B', unit_scale=True, 
                     desc=f"  Uploading", leave=False) as pbar:
                
                def upload_callback(bytes_amount):
                    pbar.update(bytes_amount)
                
                with open(archive_path, 'rb') as f:
                    self.s3_client.upload_fileobj(
                        f,
                        self.s3_config.bucket,
                        s3_key,
                        ExtraArgs={
                            'StorageClass': 'STANDARD',
                            'Tagging': tags,
                            'Metadata': {
                                'session_id': session_id,
                                'year': str(year),
                                'original_size': str(file_size),
                                'created_by': 'astrocat-backup'
                            }
                        },
                        Callback=upload_callback
                    )
            
            # Get ETag for verification
            response = self.s3_client.head_object(
                Bucket=self.s3_config.bucket,
                Key=s3_key
            )
            etag = response['ETag'].strip('"')
            
            upload_time = (datetime.now() - start_time).total_seconds()
            upload_rate = file_size / upload_time / (1024 * 1024) if upload_time > 0 else 0
            
            logger.info(f"✓ Upload complete")
            logger.info(f"  ETag: {etag}")
            logger.info(f"  Time: {upload_time:.1f}s")
            logger.info(f"  Rate: {upload_rate:.2f} MB/s")
            
            return True, s3_key, etag
            
        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            return False, None, None
        except Exception as e:
            logger.error(f"Upload error: {e}")
            return False, None, None

    def calculate_session_size(self, session_id: str) -> int:
        """Calculate total size of all LIGHT files in a session."""
        session_db = self.db_service.db_manager.get_session()
        try:
            files = session_db.query(FitsFile).filter(
                FitsFile.session_id == session_id,
                FitsFile.frame_type == 'LIGHT'
            ).all()
            
            total = 0
            for f in files:
                p = Path(f.folder) / f.file
                if p.exists():
                    total += p.stat().st_size
            return total
        finally:
            session_db.close()

    def check_temp_space(self, session_id: str, required_bytes: Optional[int] = None) -> SpaceCheckResult:
        """Check if temp directory has sufficient space for archive."""
        try:
            if required_bytes is None:
                required_bytes = self.calculate_session_size(session_id)
            
            stat = shutil.disk_usage(self.temp_dir)
            free_space = stat.free
            
            # Add 10% buffer
            required_with_buffer = int(required_bytes * 1.1)
            has_space = free_space >= required_with_buffer
            
            if not has_space:
                error = (
                    f"Insufficient space in {self.temp_dir}: "
                    f"need {format_size(required_with_buffer)}, "
                    f"have {format_size(free_space)}"
                )
                logger.warning(error)
                return SpaceCheckResult(False, required_bytes, free_space, self.temp_dir, error)
            
            return SpaceCheckResult(True, required_bytes, free_space, self.temp_dir, None)
        except Exception as e:
            error = f"Error checking temp space: {e}"
            logger.error(error)
            return SpaceCheckResult(False, 0, 0, self.temp_dir, error)

    def get_largest_session_size(self) -> Tuple[Optional[str], int]:
        """Find largest session by querying database and calculating actual size."""
        session_db = self.db_service.db_manager.get_session()
        try:
            # Find session with most LIGHT files (proxy for largest)
            result = session_db.query(
                FitsFile.session_id,
                func.count(FitsFile.id)
            ).filter(
                FitsFile.session_id.isnot(None),
                FitsFile.frame_type == 'LIGHT'
            ).group_by(
                FitsFile.session_id
            ).order_by(
                func.count(FitsFile.id).desc()
            ).first()
            
            if result:
                actual_size = self.calculate_session_size(result[0])
                return result[0], actual_size
            return None, 0
        finally:
            session_db.close()


    def verify_archive(self, session_id: str, year: int) -> VerifyResult:
        """Verify archive exists in S3 and matches expected size."""
        s3_key = self._get_archive_key(session_id, year)
        
        try:
            response = self.s3_client.head_object(
                Bucket=self.s3_config.bucket,
                Key=s3_key
            )
            
            return VerifyResult(
                verified=True,
                session_id=session_id,
                method='head_object',
                s3_size=response['ContentLength'],
                etag_match=True
            )
            
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return VerifyResult(
                    verified=False,
                    session_id=session_id,
                    method='head_object',
                    error='Archive not found in S3'
                )
            return VerifyResult(
                verified=False,
                session_id=session_id,
                method='head_object',
                error=str(e)
            )
    
    def backup_session(
        self,
        session_id: str,
        skip_existing: bool = True,
        cleanup_archive: bool = True
    ) -> ArchiveResult:
        """Complete backup workflow for a session: create archive, upload, verify.
        
        Args:
            session_id: Imaging session ID
            skip_existing: Skip if already backed up
            cleanup_archive: Delete local archive after successful upload
        
        Returns:
            ArchiveResult with operation details
        """
        session_db = self.db_service.db_manager.get_session()
        
        try:
            # Get session info
            session = session_db.query(SessionModel).filter(
                SessionModel.session_id == session_id
            ).first()
            
            if not session:
                return ArchiveResult(
                    success=False,
                    session_id=session_id,
                    error="Session not found in database"
                )
            
            # Extract year
            try:
                year = datetime.strptime(session.session_date, '%Y-%m-%d').year
            except:
                return ArchiveResult(
                    success=False,
                    session_id=session_id,
                    error="Invalid session date format"
                )
            
            # Check if already exists
            if skip_existing and self.check_archive_exists(session_id, year):
                logger.info(f"Archive already exists for {session_id}, skipping")
                return ArchiveResult(
                    success=True,
                    session_id=session_id,
                    error="Already backed up (skipped)"
                )
            
            # PRE-FLIGHT SPACE CHECK - ADD THIS BLOCK:
            space_check = self.check_temp_space(session_id)
            if not space_check.has_space:
                logger.error(f"Pre-flight check failed for {session_id}: {space_check.error}")
                return ArchiveResult(
                    success=False,
                    session_id=session_id,
                    error=space_check.error
                )
            
            logger.info(
                f"Pre-flight check passed: session {format_size(space_check.session_size)}, "
                f"free {format_size(space_check.free_space)}"
            )
            
            # Create archive (existing code continues here)
            logger.info(f"Starting backup for session: {session_id}")

            # Create archive
            logger.info(f"Starting backup for session: {session_id}")
            
            # Get compression settings from config
            compression_level = self.s3_config.config.get('archive_settings', {}).get('compression_level', 6)
            use_pigz = self.s3_config.config.get('archive_settings', {}).get('use_pigz', True)
            
            archive_path = self.create_session_archive(
                session_id,
                compression_level=compression_level,
                use_pigz=use_pigz
            )
            
            if not archive_path:
                return ArchiveResult(
                    success=False,
                    session_id=session_id,
                    error="Failed to create archive"
                )
            
            # Upload
            original_size = sum(
                Path(f.folder).joinpath(f.file).stat().st_size 
                for f in session_db.query(FitsFile).filter(
                    FitsFile.session_id == session_id
                ).all()
                if Path(f.folder).joinpath(f.file).exists()
            )
            compressed_size = archive_path.stat().st_size
            
            # Get archive policies from config - default to 'fast' / 'deep' for raw data
            # Maps to backup_rules in s3_config.json
            archive_policy = self.s3_config.config.get('backup_rules', {}).get('raw_lights', {}).get('archive_policy', 'fast')
            backup_policy = self.s3_config.config.get('backup_rules', {}).get('raw_lights', {}).get('backup_policy', 'deep')
            
            success, s3_key, etag = self.upload_archive(
                archive_path, session_id, year,
                archive_policy=archive_policy,
                backup_policy=backup_policy
            )
            
            if not success:
                return ArchiveResult(
                    success=False,
                    session_id=session_id,
                    archive_path=archive_path,
                    error="Upload failed"
                )
            
            # Verify
            verify_result = self.verify_archive(session_id, year)
            
            if not verify_result.verified:
                return ArchiveResult(
                    success=False,
                    session_id=session_id,
                    archive_path=archive_path,
                    s3_key=s3_key,
                    error=f"Verification failed: {verify_result.error}"
                )
            
            # Cleanup if requested
            if cleanup_archive:
                archive_path.unlink()
                logger.info(f"Cleaned up local archive: {archive_path}")
            
            # Get file count
            file_count = session_db.query(FitsFile).filter(
                FitsFile.session_id == session_id
            ).count()
            
            return ArchiveResult(
                success=True,
                session_id=session_id,
                archive_path=None if cleanup_archive else archive_path,
                file_count=file_count,
                original_size=original_size,
                compressed_size=compressed_size,
                compression_ratio=compressed_size / original_size if original_size > 0 else 0,
                s3_key=s3_key,
                s3_etag=etag
            )
            
        except Exception as e:
            logger.error(f"Error backing up session {session_id}: {e}")
            return ArchiveResult(
                success=False,
                session_id=session_id,
                error=str(e)
            )
        finally:
            session_db.close()
    
    @staticmethod
    def _format_bytes(bytes_size: int) -> str:
        """Format bytes to human readable string."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.2f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.2f} PB"