"""
S3 Backup Manager for Processing Session Files (Individual File Backup)
Backs up intermediate and final files individually rather than as tarballs.
"""

import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

import boto3
from botocore.exceptions import ClientError
from tqdm import tqdm

# Import all models from main models.py
from models import ProcessingSession, ProcessedFile, DatabaseManager
from s3_backup.models import S3BackupProcessedFileRecord

logger = logging.getLogger(__name__)


@dataclass
class FileBackupResult:
    """Result of backing up a single file."""
    success: bool
    file_path: str
    s3_key: Optional[str] = None
    s3_etag: Optional[str] = None
    file_size: int = 0
    md5sum: Optional[str] = None
    needs_backup: bool = True
    reason: str = ""
    error: Optional[str] = None


class UploadProgressCallback:
    """Callback for S3 upload progress."""
    def __init__(self, file_num: int, total_files: int, file_size: int):
        self.pbar = tqdm(
            total=file_size,
            unit='B',
            unit_scale=True,
            desc=f"File {file_num}/{total_files}"
        )
    
    def __call__(self, bytes_transferred):
        self.pbar.update(bytes_transferred)
    
    def close(self):
        self.pbar.close()


class ProcessingSessionFileBackup:
    """Manages individual file backups for processing sessions to S3."""
    
    def __init__(self, config, s3_config, db_service):
        """
        Initialize backup manager.
        
        Args:
            config: Application configuration
            s3_config: S3BackupConfig object (from s3_backup.manager)
            db_service: Database service
        """
        from boto3.s3.transfer import TransferConfig

        self.config = config
        self.s3_config = s3_config
        self.db_service = db_service

        # Setup temp directory
        temp_dir = s3_config.resolve_temp_dir()
        if temp_dir:
            self.temp_dir = temp_dir / "processed_backups"
        else:
            from pathlib import Path
            import tempfile
            self.temp_dir = Path(tempfile.gettempdir()) / "astrocat_processed"
        
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self._cleanup_orphaned_tarballs()  # Clean up any leftover files

        # Initialize S3 client
        self.s3_client = boto3.client(
            's3',
            region_name=s3_config.region
        )
        
        upload_settings = self.s3_config.config.get('upload_settings', {})
        self.transfer_config = TransferConfig(
            multipart_threshold=upload_settings.get('multipart_threshold_mb', 100) * 1024 * 1024,
            multipart_chunksize=upload_settings.get('multipart_chunksize_mb', 25) * 1024 * 1024,
            max_concurrency=upload_settings.get('max_concurrency', 4),
            use_threads=upload_settings.get('use_threads', True)
        )

        self.bucket = s3_config.bucket


        
    def calculate_md5(self, filepath: Path) -> str:
        """Calculate MD5 hash of a file."""
        hash_md5 = hashlib.md5()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating MD5 for {filepath}: {e}")
            return ""

    def _cleanup_orphaned_tarballs(self):
        """Remove any leftover temp tarballs from previous failed runs."""
        if not self.temp_dir.exists():
            return
        
        for tarball in self.temp_dir.glob("*.tar"):
            try:
                tarball.unlink()
                logger.debug(f"Cleaned up orphaned tarball: {tarball.name}")
            except Exception as e:
                logger.warning(f"Could not remove {tarball}: {e}")

  
    def _get_file_s3_key(self, session_id: str, subfolder: str, filename: str) -> str:
        """
        Generate S3 key for a processing session file.
        
        Structure: backups/processed/YEAR/SESSION_ID/subfolder/filename
        Example: backups/processed/2025/20250115_ABC123/final/M31_final.xisf
        """
        try:
            year = int(session_id[:4])
        except (ValueError, IndexError):
            year = datetime.now().year
        
        return f"backups/processed/{year}/{session_id}/{subfolder}/{filename}"
    
    def check_file_needs_backup(self, file_record: ProcessedFile) -> Tuple[bool, str]:
        """
        Check if a file needs to be backed up.
        
        Returns:
            (needs_backup, reason)
        """
        session = self.db_service.db_manager.get_session()
        
        try:
            backup_record = session.query(S3BackupProcessedFileRecord).filter(
                S3BackupProcessedFileRecord.processed_file_id == file_record.id
            ).first()
            
            if not backup_record:
                return True, "No backup record exists"
            
            file_path = Path(file_record.file_path)
            if not file_path.exists():
                return False, "Source file not found locally"
            
            current_md5 = file_record.md5sum
            if not current_md5:
                current_md5 = self.calculate_md5(file_path)
                file_record.md5sum = current_md5
                session.commit()
            
            if backup_record.md5sum != current_md5:
                return True, f"File modified (old: {backup_record.md5sum[:8]}..., new: {current_md5[:8]}...)"
            
            current_size = file_path.stat().st_size
            if backup_record.file_size != current_size:
                return True, f"File size changed ({backup_record.file_size} -> {current_size})"
            
            return False, "File already backed up and unchanged"
            
        finally:
            session.close()
    

    def backup_file(
        self,
        file_record: ProcessedFile,
        force: bool = False,
        file_num: int = 1,
        total_files: int = 1
    ) -> FileBackupResult:
        """Backup a single processed file to S3."""
        file_path = Path(file_record.file_path)
        
        if not file_path.exists():
            return FileBackupResult(
                success=False,
                file_path=str(file_path),
                error=f"File not found: {file_path}"
            )
        
        # Check if this is a directory that needs tarballing
        needs_tarball = file_path.is_dir()
        temp_tarball = None
        upload_path = file_path
        
        # Skip re-uploading existing directory backups BEFORE creating tarball
        if needs_tarball and not force:
            session = self.db_service.db_manager.get_session()
            backup_record = session.query(S3BackupProcessedFileRecord).filter(
                S3BackupProcessedFileRecord.processed_file_id == file_record.id
            ).first()
            session.close()
            
            if backup_record:
                return FileBackupResult(
                    success=True,
                    file_path=str(file_path),
                    needs_backup=False,
                    reason="Directory already backed up (use --force to re-upload)"
                )
        
        if needs_tarball:
            import tarfile
            import tempfile
            
            temp_tarball = self.temp_dir / f"{file_path.name}.tar"
            
            try:
                with tarfile.open(temp_tarball, 'w') as tar:
                    tar.add(file_path, arcname=file_path.name)
                upload_path = temp_tarball
                logger.info(f"Created tarball: {temp_tarball.name}")
            except Exception as e:
                return FileBackupResult(
                    success=False,
                    file_path=str(file_path),
                    error=f"Failed to create tarball: {e}"
                )
        
        if not force:
            needs_backup, reason = self.check_file_needs_backup(file_record)
            if not needs_backup:
                if temp_tarball and temp_tarball.exists():
                    temp_tarball.unlink()
                return FileBackupResult(
                    success=True,
                    file_path=str(file_path),
                    needs_backup=False,
                    reason=reason
                )
        
        # Calculate MD5 of upload file (tarball for directories, original file otherwise)
        # Always recalculate for tarballs since directory content may have changed
        if not file_record.md5sum or needs_tarball:
            file_record.md5sum = self.calculate_md5(upload_path)
            session = self.db_service.db_manager.get_session()
            session.merge(file_record)
            session.commit()
            session.close()
        
        # Add .tar to S3 key if tarballed
        s3_filename = file_record.filename + '.tar' if needs_tarball else file_record.filename
        s3_key = self._get_file_s3_key(
            file_record.processing_session_id,
            file_record.subfolder,
            s3_filename
        )
        
        file_size = upload_path.stat().st_size
        
        try:
            logger.info(f"Uploading {file_record.filename} to S3...")
            
            rules = self.s3_config.config.get('backup_rules', {}).get('final_outputs', {})
            archive_policy = rules.get('archive_policy', 'standard')
            backup_policy = rules.get('backup_policy', 'flexible')
            tags = f"archive_policy={archive_policy}&backup_policy={backup_policy}"
            
            content_type = 'application/x-tar' if needs_tarball else {
                'xisf': 'application/octet-stream',
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'xosm': 'application/octet-stream',
                'pxiproject': 'application/octet-stream'
            }.get(file_record.file_type, 'application/octet-stream')
            
            progress_callback = UploadProgressCallback(file_num, total_files, file_size)
            
            with open(upload_path, 'rb') as f:
                upload_kwargs = {
                    'ExtraArgs': {
                        'ContentType': content_type,
                        'Tagging': tags
                    }
                }
                
                if progress_callback:
                    upload_kwargs['Callback'] = progress_callback
                
                self.s3_client.upload_fileobj(
                    f,
                    self.bucket,
                    s3_key,
                    Config=self.transfer_config,
                    **upload_kwargs
                )
            
            progress_callback.close()
            
            response = self.s3_client.head_object(
                Bucket=self.bucket,
                Key=s3_key
            )
            etag = response['ETag'].strip('"')
            
            self._update_backup_record(
                file_record,
                s3_key,
                etag,
                file_size
            )
            
            logger.info(f"✓ Uploaded: {file_record.filename}")
            
            return FileBackupResult(
                success=True,
                file_path=str(file_path),
                s3_key=s3_key,
                s3_etag=etag,
                file_size=file_size,
                md5sum=file_record.md5sum,
                needs_backup=True,
                reason="Uploaded successfully"
            )
            
        except ClientError as e:
            logger.error(f"Failed to upload {file_record.filename}: {e}")
            return FileBackupResult(
                success=False,
                file_path=str(file_path),
                error=f"S3 upload failed: {e}"
            )
        except Exception as e:
            logger.error(f"Unexpected error uploading {file_record.filename}: {e}")
            return FileBackupResult(
                success=False,
                file_path=str(file_path),
                error=str(e)
            )
        finally:
            if temp_tarball and temp_tarball.exists():
                temp_tarball.unlink()
                logger.debug(f"Cleaned up temp tarball")


    def _update_backup_record(
        self,
        file_record: ProcessedFile,
        s3_key: str,
        etag: str,
        file_size: int
    ):
        """Update or create backup record in database."""
        session = self.db_service.db_manager.get_session()
        
        try:
            backup_record = session.query(S3BackupProcessedFileRecord).filter(
                S3BackupProcessedFileRecord.processed_file_id == file_record.id
            ).first()
            
            if backup_record:
                backup_record.s3_key = s3_key
                backup_record.s3_etag = etag
                backup_record.s3_bucket = self.bucket
                backup_record.s3_region = self.s3_config.region
                backup_record.file_size = file_size
                backup_record.md5sum = file_record.md5sum
                backup_record.uploaded_at = datetime.utcnow()
            else:
                backup_record = S3BackupProcessedFileRecord(
                    processed_file_id=file_record.id,
                    processing_session_id=file_record.processing_session_id,
                    s3_bucket=self.bucket,
                    s3_key=s3_key,
                    s3_region=self.s3_config.region,
                    s3_etag=etag,
                    file_size=file_size,
                    md5sum=file_record.md5sum,
                    uploaded_at=datetime.utcnow()
                )
                session.add(backup_record)
            
            session.commit()
            
        finally:
            session.close()
    
    def backup_session_files(
        self,
        session_id: str,
        subfolders: Optional[List[str]] = None,
        file_types: Optional[List[str]] = None,
        force: bool = False
    ) -> Dict:
        """Backup all files from a processing session."""
        session = self.db_service.db_manager.get_session()
        
        try:
            query = session.query(ProcessedFile).filter(
                ProcessedFile.processing_session_id == session_id
            )
            
            if subfolders:
                query = query.filter(ProcessedFile.subfolder.in_(subfolders))
            
            if file_types:
                query = query.filter(ProcessedFile.file_type.in_(file_types))
            
            files = query.all()
            
            if not files:
                logger.warning(f"No files found for session {session_id}")
                return {
                    'success': True,
                    'total_files': 0,
                    'uploaded': 0,
                    'skipped': 0,
                    'failed': 0,
                    'total_size': 0
                }
            
            stats = {
                'total_files': len(files),
                'uploaded': 0,
                'skipped': 0,
                'failed': 0,
                'total_size': 0,
                'errors': []
            }
            
            logger.info(f"Backing up {len(files)} files from session {session_id}...")
            
            with tqdm(total=len(files), desc="Backing up files", unit="files") as pbar:
                for idx, file_record in enumerate(files, 1):
                    result = self.backup_file(file_record, force=force, file_num=idx, total_files=len(files))
                    
                    if result.success:
                        if result.needs_backup:
                            stats['uploaded'] += 1
                            stats['total_size'] += result.file_size
                        else:
                            stats['skipped'] += 1
                    else:
                        stats['failed'] += 1
                        stats['errors'].append({
                            'file': file_record.filename,
                            'error': result.error
                        })
                    
                    pbar.update(1)
                    pbar.set_postfix({
                        'uploaded': stats['uploaded'],
                        'skipped': stats['skipped'],
                        'failed': stats['failed']
                    })
            
            stats['success'] = stats['failed'] == 0
            
            logger.info(f"Backup complete for session {session_id}:")
            logger.info(f"  Uploaded: {stats['uploaded']}")
            logger.info(f"  Skipped: {stats['skipped']}")
            logger.info(f"  Failed: {stats['failed']}")
            logger.info(f"  Total size: {self._format_bytes(stats['total_size'])}")
            
            return stats
            
        finally:
            session.close()
    
    def verify_backup(self, file_record: ProcessedFile) -> bool:
        """Verify that a file's backup matches the local file."""
        session = self.db_service.db_manager.get_session()
        
        try:
            backup_record = session.query(S3BackupProcessedFileRecord).filter(
                S3BackupProcessedFileRecord.processed_file_id == file_record.id
            ).first()
            
            if not backup_record:
                logger.warning(f"No backup record for {file_record.filename}")
                return False
            
            try:
                response = self.s3_client.head_object(
                    Bucket=backup_record.s3_bucket,
                    Key=backup_record.s3_key
                )
                
                s3_etag = response['ETag'].strip('"')
                
                if s3_etag != backup_record.s3_etag:
                    logger.error(f"ETag mismatch for {file_record.filename}")
                    return False
                
                s3_size = response['ContentLength']
                if s3_size != backup_record.file_size:
                    logger.error(f"Size mismatch for {file_record.filename}")
                    return False
                
                return True
                
            except ClientError as e:
                if e.response['Error']['Code'] == '404':
                    logger.error(f"File not found in S3: {backup_record.s3_key}")
                else:
                    logger.error(f"Error checking S3: {e}")
                return False
                
        finally:
            session.close()
    
    def list_session_backups(self, session_id: str) -> Dict:
        """List all backed up files for a processing session."""
        session = self.db_service.db_manager.get_session()
        
        try:
            backup_records = session.query(S3BackupProcessedFileRecord).filter(
                S3BackupProcessedFileRecord.processing_session_id == session_id
            ).all()
            
            if not backup_records:
                return {
                    'session_id': session_id,
                    'total_files': 0,
                    'total_size': 0,
                    'files': []
                }
            
            files = []
            total_size = 0
            
            for record in backup_records:
                file_info = session.query(ProcessedFile).filter(
                    ProcessedFile.id == record.processed_file_id
                ).first()
                
                if file_info:
                    files.append({
                        'filename': file_info.filename,
                        'subfolder': file_info.subfolder,
                        'file_type': file_info.file_type,
                        's3_key': record.s3_key,
                        'file_size': record.file_size,
                        'uploaded_at': record.uploaded_at,
                        'md5sum': record.md5sum
                    })
                    total_size += record.file_size or 0
            
            return {
                'session_id': session_id,
                'total_files': len(files),
                'total_size': total_size,
                'total_size_mb': round(total_size / 1024 / 1024, 2),
                'files': sorted(files, key=lambda x: x['subfolder'] + x['filename'])
            }
            
        finally:
            session.close()
    
    def _format_bytes(self, size: int) -> str:
        """Format bytes to human readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"