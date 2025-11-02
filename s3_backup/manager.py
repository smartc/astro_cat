"""S3 Backup Manager - Core backup operations for FITS Cataloger.

UPDATED: Added markdown backup functionality while maintaining full backwards compatibility.
"""

import os
import json
import tarfile
import tempfile
import logging
import hashlib
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
from tqdm import tqdm

from models import DatabaseService, FitsFile, ImagingSession as SessionModel

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


# NEW: Markdown backup result
@dataclass
class MarkdownBackupResult:
    """Result of markdown file backup."""
    success: bool
    file_path: str
    s3_key: Optional[str] = None
    s3_etag: Optional[str] = None
    file_size: int = 0
    needs_backup: bool = True
    reason: Optional[str] = None
    error: Optional[str] = None


class S3BackupConfig:
    """S3 backup configuration loader."""
    
    def __init__(self, config_path: str = 's3_config.json'):
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.base_dir = None  # Will be set by manager
    
    def _load_config(self) -> dict:
        """Load S3 configuration from file or create default disabled config."""
        if not self.config_path.exists():
            logger.info(f"S3 config not found at {self.config_path}, creating default disabled configuration")
            default_config = self._create_default_config()
            self._write_config(default_config)
            return default_config

        with open(self.config_path, 'r') as f:
            config = json.load(f)

        # Remove comments
        config = {k: v for k, v in config.items() if not k.startswith('_')}
        for section in config.values():
            if isinstance(section, dict):
                section = {k: v for k, v in section.items() if not k.startswith('_')}

        return config

    def _create_default_config(self) -> dict:
        """Create a default disabled S3 configuration."""
        return {
            "enabled": False,
            "aws_region": "us-east-1",
            "buckets": {
                "primary": "your-bucket-name",
                "backup": None
            },
            "s3_paths": {
                "raw_archives": "backups/raw",
                "session_notes": "backups/sessions",
                "processing_notes": "backups/processing",
                "final_outputs": "backups/final",
                "database_backups": "backups/database"
            },
            "backup_rules": {
                "raw_lights": {
                    "archive_policy": "fast",
                    "backup_policy": "deep",
                    "archive_days": 7,
                    "storage_class": "STANDARD"
                },
                "raw_calibration": {
                    "archive_policy": "fast",
                    "backup_policy": "deep",
                    "archive_days": 7,
                    "storage_class": "STANDARD"
                },
                "imaging_sessions": {
                    "archive_policy": "standard",
                    "backup_policy": "deep",
                    "archive_days": 30,
                    "storage_class": "STANDARD"
                },
                "processing_sessions": {
                    "archive_policy": "delayed",
                    "backup_policy": "flexible",
                    "archive_days": 90,
                    "storage_class": "STANDARD"
                }
            },
            "upload_settings": {
                "multipart_threshold_mb": 100,
                "multipart_chunksize_mb": 25,
                "max_concurrency": 4,
                "use_threads": True,
                "max_bandwidth_mbps": None
            },
            "restore_settings": {
                "default_tier": "Standard",
                "default_days": 7,
                "restore_path": "/path/to/restore"
            },
            "archive_settings": {
                "compression_level": 0,
                "use_pigz": False,
                "verify_after_upload": True,
                "keep_archive_index": True,
                "max_archive_size_gb": 50,
                "temp_dir": ".tmp/backup_archives"
            },
            "retry_settings": {
                "max_retries": 3,
                "initial_backoff_seconds": 2,
                "max_backoff_seconds": 60,
                "backoff_multiplier": 2
            },
            "logging": {
                "log_uploads": True,
                "log_verifications": True,
                "log_restores": True,
                "verbose": False
            },
            "cost_tracking": {
                "track_costs": True,
                "storage_cost_per_gb_per_month": {
                    "STANDARD": 0.025,
                    "STANDARD_IA": 0.0138,
                    "GLACIER_IR": 0.005,
                    "GLACIER_FLEXIBLE": 0.00405,
                    "DEEP_ARCHIVE": 0.0018
                },
                "data_transfer_cost_per_gb": {
                    "upload": 0.0,
                    "download": 0.09
                }
            },
            "notifications": {
                "email_on_complete": False,
                "email_address": None,
                "email_on_error": True
            }
        }

    def _write_config(self, config: dict):
        """Write configuration to disk."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info(f"Created default S3 configuration at {self.config_path}")
            logger.info("Edit this file and set 'enabled' to true when ready to use S3 backups")
        except Exception as e:
            logger.error(f"Failed to write default S3 config: {e}")
    
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
    
    # NEW: Get processing notes path
    def get_processing_note_path(self) -> str:
        """Get S3 path for processing session notes."""
        return self.config['s3_paths']['processing_notes']


class S3BackupManager:
    """Main S3 backup manager for session-based archives and markdown files."""

    def __init__(self, db_service: DatabaseService, s3_config: S3BackupConfig,
                 base_dir: Optional[Path] = None, dry_run: bool = False, auto_cleanup=True):
        self.db_service = db_service
        self.s3_config = s3_config
        self.dry_run = dry_run
        self.s3_client = None  # Will be None if S3 is disabled

        # Set base directory for resolving relative paths
        if base_dir:
            self.s3_config.set_base_dir(base_dir)

        if not s3_config.enabled:
            logger.warning("S3 backup is disabled in s3_config.json")
            logger.info("S3 Backup Manager initialized in DISABLED mode")
            logger.info("Set 'enabled' to true in s3_config.json and restart to enable S3 backups")
            # Still setup temp dir even when disabled for potential future use
            self._setup_temp_dir()
            return

        # Initialize S3 client only if enabled
        boto_config = BotoConfig(
            region_name=s3_config.region,
            retries={'max_attempts': 3, 'mode': 'adaptive'}
        )
        self.s3_client = boto3.client('s3', config=boto_config)

        self._verify_bucket_access()
        self._setup_temp_dir()

        if auto_cleanup:
            self._cleanup_orphaned_archives()

        logger.info(f"S3 Backup Manager initialized for bucket: {s3_config.bucket}")
        logger.info(f"  Temp directory: {self.temp_dir}")

    def safe_unlink(self, path: Optional[Path]) -> bool:
        """Safely delete a file if it exists, respecting dry-run."""
        if not path:
            return False
        try:
            if not path.exists():
                logger.debug(f"Already deleted or missing: {path}")
                return False

            if self.dry_run:
                logger.info(f"🧩 [Dry Run] Would delete: {path}")
                return True

            path.unlink()
            logger.debug(f"🧹 Deleted: {path}")
            return True

        except Exception as e:
            logger.warning(f"⚠️ Failed to delete {path}: {e}")
            return False
    
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
        
   
    def _cleanup_orphaned_archives(self):
        """Remove any leftover archive files from failed previous runs."""
        if not self.temp_dir.exists():
            return
        
        orphaned = list(self.temp_dir.glob("*.tar*"))
        if orphaned:
            logger.info(f"Cleaning up {len(orphaned)} orphaned archive(s) from previous runs...")
            for archive in orphaned:
                # Skip archives that may still be in use
                try:
                    if archive.name.endswith(".part") or archive.stat().st_size == 0:
                        continue
                    self.safe_unlink(archive)
                except Exception as e:
                    logger.warning(f"Could not remove {archive}: {e}")


    
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
        """Generate S3 key for session notes - updated for new naming."""
        path = self.s3_config.get_session_note_path(year)
        return f"{path}/{session_id}.md"
    
    def _get_processing_note_key(self, session_id: str) -> str:
        """Generate S3 key for processing session notes - updated for new structure."""
        path = self.s3_config.get_processing_note_path()
        return f"{path}/{session_id}.md"

    # NEW: Check if markdown needs backup
    def needs_markdown_backup(self, local_path: Path, s3_key: str) -> Tuple[bool, str]:
        """
        Check if a markdown file needs to be backed up to S3.
        
        Args:
            local_path: Local path to markdown file
            s3_key: S3 key (path) for the file
            
        Returns:
            Tuple of (needs_backup: bool, reason: str)
        """
        if not local_path.exists():
            return False, "Local file does not exist"
        
        try:
            # Try to get S3 object metadata
            response = self.s3_client.head_object(
                Bucket=self.s3_config.bucket,
                Key=s3_key
            )
            
            # File exists in S3, check modification time
            s3_last_modified = response['LastModified']
            local_mtime = datetime.fromtimestamp(local_path.stat().st_mtime, tz=timezone.utc)
            
            if local_mtime > s3_last_modified:
                return True, "Local file is newer than S3 version"
            else:
                return False, "S3 version is current"
                
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                # File doesn't exist in S3
                return True, "File not yet backed up to S3"
            else:
                logger.error(f"Error checking S3 object: {e}")
                return False, f"Error checking S3: {e}"
        except Exception as e:
            logger.error(f"Unexpected error checking backup status: {e}")
            return False, f"Error: {e}"
    
    # NEW: Upload markdown file
    def upload_markdown(
        self,
        local_path: Path,
        s3_key: str,
        rule_type: str,  # 'imaging_sessions' or 'processing_sessions'
        metadata: Optional[Dict] = None,
        force: bool = False
    ) -> MarkdownBackupResult:
        """
        Upload a markdown file to S3 if needed (new or modified).
        
        Args:
            local_path: Local path to markdown file
            s3_key: S3 key (path) for the file
            rule_type: Type of backup rule ('imaging_sessions' or 'processing_sessions')
            metadata: Optional metadata dictionary to attach
            force: If True, upload regardless of modification time
            
        Returns:
            MarkdownBackupResult with operation details
        """
        try:
            if not local_path.exists():
                return MarkdownBackupResult(
                    success=False,
                    file_path=str(local_path),
                    error="Local file not found"
                )
            
            # Check if upload needed (unless forced)
            if not force:
                needs_upload, reason = self.needs_markdown_backup(local_path, s3_key)
                
                if not needs_upload:
                    logger.debug(f"Skipping upload: {reason} - {local_path.name}")
                    return MarkdownBackupResult(
                        success=True,
                        file_path=str(local_path),
                        s3_key=s3_key,
                        needs_backup=False,
                        reason=reason
                    )
                else:
                    logger.info(f"Upload needed: {reason} - {local_path.name}")
            
            # Get tags from backup rules
            rules = self.s3_config.config.get('backup_rules', {}).get(rule_type, {})
            archive_policy = rules.get('archive_policy', 'never')
            backup_policy = rules.get('backup_policy', 'never')
            tags = f"archive_policy={archive_policy}&backup_policy={backup_policy}"
            
            # Prepare extra args
            extra_args = {
                'ContentType': 'text/markdown',
                'Tagging': tags
            }
            
            # Add metadata if provided
            if metadata:
                extra_args['Metadata'] = {k: str(v) for k, v in metadata.items()}
            
            # Upload file
            file_size = local_path.stat().st_size
            
            with open(local_path, 'rb') as f:
                self.s3_client.upload_fileobj(
                    f,
                    self.s3_config.bucket,
                    s3_key,
                    ExtraArgs=extra_args
                )
            
            # Get ETag
            response = self.s3_client.head_object(
                Bucket=self.s3_config.bucket,
                Key=s3_key
            )
            etag = response['ETag'].strip('"')
            
            logger.info(f"Uploaded markdown to S3: {s3_key}")
            
            return MarkdownBackupResult(
                success=True,
                file_path=str(local_path),
                s3_key=s3_key,
                s3_etag=etag,
                file_size=file_size,
                needs_backup=True,
                reason="Uploaded successfully"
            )
            
        except ClientError as e:
            logger.error(f"Failed to upload markdown to S3: {e}")
            return MarkdownBackupResult(
                success=False,
                file_path=str(local_path),
                error=f"S3 upload failed: {e}"
            )
        except Exception as e:
            logger.error(f"Unexpected error uploading markdown: {e}")
            return MarkdownBackupResult(
                success=False,
                file_path=str(local_path),
                error=str(e)
            )

    # ========================================================================
    # EXISTING FITS ARCHIVE METHODS (UNCHANGED)
    # ========================================================================
    
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
                SessionModel.id == session_id
            ).first()

            if not session:
                logger.error(f"Session not found: {session_id}")
                return None
            
            # Get all files for this session
            files = session_db.query(FitsFile).filter(
                FitsFile.imaging_session_id == session_id
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
                FitsFile.imaging_session_id == session_id,
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
        from sqlalchemy import func
        session_db = self.db_service.db_manager.get_session()
        try:
            # Find session with most LIGHT files (proxy for largest)
            result = session_db.query(
                FitsFile.imaging_session_id,
                func.count(FitsFile.id)
            ).filter(
                FitsFile.imaging_session_id.isnot(None),
                FitsFile.frame_type == 'LIGHT'
            ).group_by(
                FitsFile.imaging_session_id
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
            skip_existing: Skip if already backed up (checks DB first, then syncs from S3)
            cleanup_archive: Delete local archive after successful upload
        
        Returns:
            ArchiveResult with operation details
        """
        session_db = self.db_service.db_manager.get_session()
        
        try:
            # Get session info
            session = session_db.query(SessionModel).filter(
                SessionModel.id == session_id
            ).first()

            if not session:
                return ArchiveResult(
                    success=False,
                    session_id=session_id,
                    error="Session not found in database"
                )
            
            # Extract year
            try:
                year = datetime.strptime(session.date, '%Y-%m-%d').year
            except:
                return ArchiveResult(
                    success=False,
                    session_id=session_id,
                    error="Invalid session date format"
                )
            
            # NEW: Check database FIRST
            if skip_existing:
                existing_backup = session_db.query(S3BackupArchive).filter(
                    S3BackupArchive.session_id == session_id
                ).first()
                
                if existing_backup:
                    logger.info(f"Archive already in database for {session_id}, skipping")
                    return ArchiveResult(
                        success=True,
                        session_id=session_id,
                        error="Already backed up (in database, skipped)"
                    )
                
                # NEW: Not in database - check if it exists in S3
                if self.check_archive_exists(session_id, year):
                    logger.info(f"Archive exists in S3 but not in database for {session_id}, syncing...")
                    
                    # Get S3 metadata
                    s3_key = self._get_archive_key(session_id, year)
                    try:
                        response = self.s3_client.head_object(
                            Bucket=self.s3_config.bucket,
                            Key=s3_key
                        )
                        
                        # Create database record from S3 metadata
                        from s3_backup.models import S3BackupArchive
                        
                        backup_archive = S3BackupArchive(
                            session_id=session_id,
                            session_year=year,
                            s3_bucket=self.s3_config.bucket,
                            s3_key=s3_key,
                            s3_region=self.s3_config.region,
                            s3_etag=response['ETag'].strip('"'),
                            compressed_size_bytes=response['ContentLength'],
                            original_size_bytes=response['ContentLength'],  # We don't know original, use compressed
                            file_count=0,  # Unknown
                            uploaded_at=response['LastModified'],
                            current_storage_class=response.get('StorageClass', 'STANDARD'),
                            archive_policy='unknown',
                            backup_policy='unknown',
                            verified=True,
                            verification_method='head_object',
                            last_verified_at=datetime.now()
                        )
                        
                        session_db.add(backup_archive)
                        session_db.commit()
                        
                        logger.info(f"✓ Synced database record from S3 for {session_id}")
                        
                        return ArchiveResult(
                            success=True,
                            session_id=session_id,
                            s3_key=s3_key,
                            compressed_size=response['ContentLength'],
                            error="Already backed up (synced from S3)"
                        )
                        
                    except ClientError as e:
                        logger.warning(f"Failed to sync from S3 for {session_id}: {e}")
                        # Fall through to normal upload
            
            # PRE-FLIGHT SPACE CHECK
            # Get session files
            from models import FitsFile
            files = [
                f for f in session_db.query(FitsFile).filter(
                    FitsFile.imaging_session_id == session_id
                ).all()
                if Path(f.folder).joinpath(f.file).exists()
            ]
            
            if not files:
                return ArchiveResult(
                    success=False,
                    session_id=session_id,
                    error="No files found for session"
                )
            
            # Calculate total size
            total_size = sum(
                Path(f.folder).joinpath(f.file).stat().st_size 
                for f in files
            )
            
            # Check available space
            temp_dir = Path(self.s3_config.config.get('archive_settings', {}).get(
                'temp_dir', '/tmp/astrocat_archives'
            ))
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            import shutil
            stat = shutil.disk_usage(temp_dir)
            available = stat.free
            
            # Need at least total_size for the archive
            if available < total_size:
                shortage = total_size - available
                return ArchiveResult(
                    success=False,
                    session_id=session_id,
                    error=f"Insufficient space: need {self._format_bytes(total_size)}, "
                          f"have {self._format_bytes(available)}, "
                          f"short by {self._format_bytes(shortage)}"
                )
            
            # Create archive
            archive_path = self.create_session_archive(session_id)
            if not archive_path:
                return ArchiveResult(
                    success=False,
                    session_id=session_id,
                    error="Failed to create archive"
                )
            
            # Calculate statistics
            original_size = sum(
                Path(f.folder).joinpath(f.file).stat().st_size
                for f in session_db.query(FitsFile).filter(
                    FitsFile.imaging_session_id == session_id
                ).all()
                if Path(f.folder).joinpath(f.file).exists()
            )
            compressed_size = archive_path.stat().st_size
            
            # Get archive policies from config - default to 'fast' / 'deep' for raw data
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
            
            # Clean up temporary archive if requested
            if cleanup_archive and archive_path.exists():
                try:
                    archive_path.unlink()
                    logger.info(f"✓ Cleaned up local archive: {archive_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up archive {archive_path}: {e}")
            
            return ArchiveResult(
                success=True,
                session_id=session_id,
                archive_path=archive_path if not cleanup_archive else None,
                s3_key=s3_key,
                original_size=original_size,
                compressed_size=compressed_size,
                file_count=len(files)
            )
            
        finally:
            session_db.close()

        
# ========================================================================
    # DATABASE BACKUP METHODS WITH VERSIONING
    # Add these 3 methods to the end of your S3BackupManager class
    # ========================================================================
    
    def backup_database(self, db_path: Path, description: str = None) -> Dict:
        """
        Backup database file to S3 with versioning.
        
        Args:
            db_path: Path to the database file
            description: Optional description for this backup version
            
        Returns:
            Dict with backup results including version info
        """
        if not db_path.exists():
            return {'success': False, 'error': f'Database file not found: {db_path}'}
        
        try:
            # S3 key for database backups
            s3_key = f"backups/database/{db_path.name}"
            
            # Prepare metadata

            # Get archive policies from config - default to 'fast' / 'deep' for database files
            archive_policy = self.s3_config.config.get('backup_rules', {}).get('database_files', {}).get('archive_policy', 'standard')
            backup_policy = self.s3_config.config.get('backup_rules', {}).get('database_files', {}).get('backup_policy', 'flexible')
            
            # Prepare tags - use correct key names for AWS lifecycle rules
            tags = f"archive_policy={archive_policy}&backup_policy={backup_policy}"
                       
            metadata = {
                'original_filename': db_path.name,
                'backup_timestamp': datetime.now(timezone.utc).isoformat(),
                'file_size': str(db_path.stat().st_size)
            }
            
            if description:
                metadata['description'] = description[:255]  # S3 metadata limit
            
            logger.info(f"Uploading database backup to S3...")
            logger.info(f"  Source: {db_path}")
            logger.info(f"  Destination: s3://{self.s3_config.bucket}/{s3_key}")
            
            # Upload to S3
            file_size = db_path.stat().st_size
            
            with open(db_path, 'rb') as f:
                self.s3_client.upload_fileobj(
                    f,
                    self.s3_config.bucket,
                    s3_key,
                    ExtraArgs={
                        'StorageClass': 'STANDARD',
                        'Tagging': tags,
                        'Metadata': metadata,
                        'ContentType': 'application/x-sqlite3'
                    }
                )
            
            # Get version ID if versioning is enabled
            response = self.s3_client.head_object(
                Bucket=self.s3_config.bucket,
                Key=s3_key
            )
            
            version_id = response.get('VersionId')
            
            logger.info(f"✅ Database backup uploaded successfully")
            if version_id:
                logger.info(f"  Version ID: {version_id}")
            else:
                logger.warning(f"  No version ID (bucket versioning may not be enabled)")
            
            return {
                'success': True,
                's3_key': s3_key,
                'version_id': version_id,
                'size': file_size,
                'description': description
            }
            
        except Exception as e:
            logger.error(f"Error backing up database: {e}")
            return {'success': False, 'error': str(e)}
    
    def list_database_versions(self) -> List[dict]:
        """
        List all database backup versions from S3.
        
        Returns:
            List of version dictionaries with metadata
        """
        try:
            versions = []
            
            # Try to list versions - will work if bucket versioning is enabled
            try:
                paginator = self.s3_client.get_paginator('list_object_versions')
                
                for page in paginator.paginate(
                    Bucket=self.s3_config.bucket,
                    Prefix='backups/database/'
                ):
                    for version_obj in page.get('Versions', []):
                        # Get metadata for each version
                        try:
                            head_response = self.s3_client.head_object(
                                Bucket=self.s3_config.bucket,
                                Key=version_obj['Key'],
                                VersionId=version_obj['VersionId']
                            )
                            
                            metadata = head_response.get('Metadata', {})
                            
                            versions.append({
                                'version_id': version_obj['VersionId'],
                                's3_key': version_obj['Key'],
                                'timestamp': version_obj['LastModified'].isoformat(),
                                'size': version_obj['Size'],
                                'description': metadata.get('description', ''),
                                'original_filename': metadata.get('original_filename', ''),
                                'is_latest': version_obj.get('IsLatest', False)
                            })
                        except Exception as e:
                            logger.warning(f"Error reading version metadata: {e}")
                            continue
            
            except Exception as e:
                # Versioning might not be enabled - fall back to listing current objects
                logger.warning(f"Could not list versions (bucket versioning may not be enabled): {e}")
                
                response = self.s3_client.list_objects_v2(
                    Bucket=self.s3_config.bucket,
                    Prefix='backups/database/'
                )
                
                for obj in response.get('Contents', []):
                    head_response = self.s3_client.head_object(
                        Bucket=self.s3_config.bucket,
                        Key=obj['Key']
                    )
                    
                    metadata = head_response.get('Metadata', {})
                    
                    versions.append({
                        'version_id': None,
                        's3_key': obj['Key'],
                        'timestamp': obj['LastModified'].isoformat(),
                        'size': obj['Size'],
                        'description': metadata.get('description', ''),
                        'original_filename': metadata.get('original_filename', ''),
                        'is_latest': True
                    })
            
            # Sort by timestamp (newest first)
            versions.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return versions
            
        except Exception as e:
            logger.error(f"Error listing database versions: {e}")
            return []
    
    def restore_database(self, version_id: str, output_path: Path) -> Dict:
        """
        Restore a specific database version from S3.
        
        Args:
            version_id: S3 version ID to restore
            output_path: Where to save the restored database
            
        Returns:
            Dict with restore results
        """
        try:
            # Find the version
            versions = self.list_database_versions()
            target_version = next((v for v in versions if v['version_id'] == version_id), None)
            
            if not target_version:
                return {'success': False, 'error': f'Version {version_id} not found'}
            
            logger.info(f"Restoring database version {version_id}...")
            
            # Download from S3
            download_kwargs = {
                'Bucket': self.s3_config.bucket,
                'Key': target_version['s3_key'],
                'Filename': str(output_path)
            }
            
            # Only add VersionId if it exists (versioning might not be enabled)
            if version_id:
                download_kwargs['ExtraArgs'] = {'VersionId': version_id}
            
            self.s3_client.download_file(**download_kwargs)
            
            logger.info(f"✅ Database restored to {output_path}")
            
            return {
                'success': True,
                'version_id': version_id,
                'output_path': str(output_path),
                'size': output_path.stat().st_size
            }
            
        except Exception as e:
            logger.error(f"Error restoring database version {version_id}: {e}")
            return {'success': False, 'error': str(e)}


    @staticmethod
    def _format_bytes(bytes_size: int) -> str:
        """Format bytes to human readable string."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.2f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.2f} PB"