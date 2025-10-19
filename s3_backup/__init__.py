"""S3 Backup Module for FITS Cataloger.

Provides session-based archive backup to AWS S3 Glacier with lifecycle management.
"""

from .manager import S3BackupManager, S3BackupConfig, ArchiveResult, VerifyResult
from .models import (
    S3BackupArchive,
    S3BackupSessionNote,
    S3BackupProcessingSession,
    S3BackupProcessedFiles,
    S3BackupLog,
    S3BackupConfig as S3BackupConfigModel,
    S3BackupStats
)

__version__ = '1.0.0'
__all__ = [
    'S3BackupManager',
    'S3BackupConfig',
    'ArchiveResult',
    'VerifyResult',
    'S3BackupArchive',
    'S3BackupSessionNote',
    'S3BackupProcessingSession',
    'S3BackupProcessedFiles',
    'S3BackupLog',
    'S3BackupConfigModel',
    'S3BackupStats',
]