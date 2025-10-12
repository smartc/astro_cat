"""Database models for S3 backup tracking."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, Text, ForeignKey, Index, Boolean
from sqlalchemy.ext.declarative import declarative_base

# Import Base from main models if extending existing schema
# For now, create backup-specific base that will be integrated
Base = declarative_base()


class S3BackupArchive(Base):
    """Track S3 backup archives for imaging sessions.
    
    Each archive is a tar.gz file containing all FITS files from one imaging session.
    """
    __tablename__ = 's3_backup_archives'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Session reference
    session_id = Column(String(50), unique=True, nullable=False, index=True)
    session_date = Column(String(10))  # YYYY-MM-DD for organization
    session_year = Column(Integer, index=True)  # Extracted year for S3 prefix
    
    # S3 information
    s3_bucket = Column(String(255), nullable=False)
    s3_key = Column(String(500), nullable=False)  # e.g., backups/raw/2024/SESSION_ID.tar.gz
    s3_region = Column(String(50), nullable=False)
    s3_etag = Column(String(100))  # For verification
    s3_version_id = Column(String(100))  # If versioning enabled
    
    # Archive metadata
    file_count = Column(Integer)  # Number of FITS files in archive
    original_size_bytes = Column(Integer)  # Total uncompressed size
    compressed_size_bytes = Column(Integer)  # Archive file size
    compression_ratio = Column(Float)  # compressed/original
    
    # Backup policies
    archive_policy = Column(String(20), default='fast')  # 'fast', 'normal', 'delayed'
    backup_policy = Column(String(20), default='deep-archive')  # 'deep-archive', 'flexible'
    
    # Current state
    current_storage_class = Column(String(50), default='STANDARD')
    expected_storage_class = Column(String(50))  # Based on lifecycle rules
    transition_date = Column(DateTime)  # When it should/did transition
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    uploaded_at = Column(DateTime)
    last_verified_at = Column(DateTime)
    
    # Verification
    verified = Column(Boolean, default=False)
    verification_method = Column(String(20))  # 'etag', 'md5', 'manual'
    
    # Restore tracking
    restore_requested_at = Column(DateTime)
    restore_expires_at = Column(DateTime)
    restore_status = Column(String(20))  # null, 'in-progress', 'available', 'expired'
    restore_tier = Column(String(20))  # 'Standard', 'Bulk', 'Expedited'
    
    # Additional metadata
    camera_name = Column(String(50))
    telescope_name = Column(String(50))
    notes = Column(Text)
    
    __table_args__ = (
        Index('idx_backup_archive_session', 'session_id'),
        Index('idx_backup_archive_year', 'session_year'),
        Index('idx_backup_archive_bucket_key', 's3_bucket', 's3_key'),
        Index('idx_backup_archive_storage', 'current_storage_class'),
        Index('idx_backup_archive_verified', 'verified'),
    )
    
    def __repr__(self):
        return f"<S3BackupArchive(session_id='{self.session_id}', size={self.compressed_size_bytes})>"


class S3BackupSessionNote(Base):
    """Track S3 backup for imaging session markdown notes.
    
    Session notes are stored as individual markdown files, not in archives.
    """
    __tablename__ = 's3_backup_session_notes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(50), unique=True, nullable=False, index=True)
    session_year = Column(Integer, index=True)
    
    # S3 information
    s3_bucket = Column(String(255), nullable=False)
    s3_key = Column(String(500), nullable=False)  # e.g., backups/sessions/2024/SESSION_ID_notes.md
    s3_region = Column(String(50), nullable=False)
    s3_etag = Column(String(100))
    
    # Backup metadata
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    file_size_bytes = Column(Integer)
    archive_policy = Column(String(20), default='normal')
    backup_policy = Column(String(20), default='deep-archive')
    current_storage_class = Column(String(50), default='STANDARD')
    
    # Verification
    last_verified_at = Column(DateTime)
    verified = Column(Boolean, default=False)
    
    __table_args__ = (
        Index('idx_backup_note_session', 'session_id'),
        Index('idx_backup_note_year', 'session_year'),
    )


class S3BackupProcessingSession(Base):
    """Track S3 backup for processing session markdown notes.
    
    Processing sessions backed up separately from raw data archives.
    """
    __tablename__ = 's3_backup_processing_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    processing_session_id = Column(String(50), unique=True, nullable=False, index=True)
    
    # S3 information
    s3_bucket = Column(String(255), nullable=False)
    s3_key = Column(String(500), nullable=False)
    s3_region = Column(String(50), nullable=False)
    s3_etag = Column(String(100))
    
    # Backup metadata
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    file_size_bytes = Column(Integer)
    archive_policy = Column(String(20), default='delayed')
    backup_policy = Column(String(20), default='flexible')
    current_storage_class = Column(String(50), default='STANDARD')
    
    __table_args__ = (
        Index('idx_backup_proc_session', 'processing_session_id'),
    )


class S3BackupLog(Base):
    """Audit log for all S3 backup operations.
    
    Tracks uploads, verifications, restores, and errors for troubleshooting.
    """
    __tablename__ = 's3_backup_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Operation details
    operation_type = Column(String(20), index=True)  # 'upload', 'verify', 'restore_request', 'delete'
    operation_status = Column(String(20), index=True)  # 'started', 'success', 'failed', 'in-progress'
    
    # References
    archive_id = Column(Integer, ForeignKey('s3_backup_archives.id', ondelete='SET NULL'))
    session_id = Column(String(50))
    
    # S3 details
    s3_bucket = Column(String(255))
    s3_key = Column(String(500))
    
    # Metrics
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    duration_seconds = Column(Float)
    bytes_transferred = Column(Integer)
    transfer_rate_mbps = Column(Float)  # Calculated MB/s
    
    # Error tracking
    error_message = Column(Text)
    error_code = Column(String(50))
    retry_count = Column(Integer, default=0)
    
    # Additional context
    user_initiated = Column(Boolean, default=True)
    auto_backup = Column(Boolean, default=False)
    notes = Column(Text)
    
    __table_args__ = (
        Index('idx_backup_log_timestamp', 'timestamp'),
        Index('idx_backup_log_operation', 'operation_type', 'operation_status'),
        Index('idx_backup_log_session', 'session_id'),
    )
    
    def __repr__(self):
        return f"<S3BackupLog(type='{self.operation_type}', status='{self.operation_status}', session='{self.session_id}')>"


class S3BackupConfig(Base):
    """Store S3 backup configuration in database.
    
    Allows web interface to manage backup settings without file access.
    """
    __tablename__ = 's3_backup_config'
    
    key = Column(String(50), primary_key=True)
    value = Column(Text, nullable=False)  # JSON string for complex values
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    description = Column(String(255))
    
    def __repr__(self):
        return f"<S3BackupConfig(key='{self.key}')>"


class S3BackupStats(Base):
    """Track backup statistics over time.
    
    Stores daily/weekly summaries for cost tracking and reporting.
    """
    __tablename__ = 's3_backup_stats'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    stat_date = Column(DateTime, default=datetime.utcnow, index=True)
    period_type = Column(String(10))  # 'daily', 'weekly', 'monthly'
    
    # Counts
    total_archives = Column(Integer)
    archives_in_standard = Column(Integer)
    archives_in_glacier = Column(Integer)
    archives_in_deep_archive = Column(Integer)
    
    # Sizes
    total_original_size_bytes = Column(Integer)
    total_compressed_size_bytes = Column(Integer)
    total_storage_cost_estimate = Column(Float)  # USD
    
    # Operations
    uploads_count = Column(Integer)
    uploads_bytes = Column(Integer)
    verifications_count = Column(Integer)
    restores_count = Column(Integer)
    
    __table_args__ = (
        Index('idx_backup_stats_date', 'stat_date'),
        Index('idx_backup_stats_period', 'period_type'),
    )