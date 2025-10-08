"""Simplified file monitoring for quarantine directory."""

import asyncio
import logging
import time
from pathlib import Path
from typing import Callable, List, Optional

from config import Config

logger = logging.getLogger(__name__)


class FileMonitor:
    """Simple file monitoring with manual and periodic scan capabilities."""
    
    def __init__(self, config: Config, on_new_files: Callable[[List[str]], None], 
                 db_service=None):
        self.config = config
        self.on_new_files = on_new_files
        self.db_service = db_service
        self.is_monitoring = False
        self.last_scan_files: set = set()
        self.last_scan_time: Optional[float] = None
        
    def find_fits_files(self, directory: str, skip_recent: bool = False, 
                       skip_minutes: Optional[int] = None) -> List[str]:
        """
        Find all FITS files in directory and subdirectories.
        
        Args:
            directory: Path to scan
            skip_recent: If True, skip files modified recently
            skip_minutes: Minutes to look back (defaults to monitoring interval)
        """
        fits_files = []
        directory_path = Path(directory)
        
        if not directory_path.exists():
            logger.warning(f"Directory does not exist: {directory}")
            return fits_files
        
        logger.info(f"Scanning directory: {directory}")
        
        # Find files with configured extensions
        for extension in self.config.file_monitoring.extensions:
            pattern = f"**/*{extension}"
            files = list(directory_path.glob(pattern))
            fits_files.extend([str(f) for f in files])
        
        # Filter out files marked as bad
        original_count = len(fits_files)
        fits_files = [f for f in fits_files if not self._is_bad_file(f)]
        bad_count = original_count - len(fits_files)
        
        if bad_count > 0:
            logger.info(f"Filtered out {bad_count} bad files")
        
        # Filter out locked files
        unlocked_files = []
        for f in fits_files:
            if not self._is_file_locked(f):
                unlocked_files.append(f)
            else:
                logger.debug(f"Skipping locked file: {f}")
        
        locked_count = len(fits_files) - len(unlocked_files)
        if locked_count > 0:
            logger.info(f"Skipping {locked_count} locked files")
        fits_files = unlocked_files
        
        # Filter out recently modified files (for auto-scan)
        if skip_recent:
            if skip_minutes is None:
                # Get from database settings, fallback to config
                if self.db_service:
                    skip_minutes = self.db_service.get_setting(
                        'monitoring.ignore_files_newer_than_minutes', 
                        30
                    )
                else:
                    skip_minutes = 30
            
            cutoff_time = time.time() - (skip_minutes * 60)
            stable_files = []
            
            for f in fits_files:
                try:
                    mtime = Path(f).stat().st_mtime
                    if mtime < cutoff_time:
                        stable_files.append(f)
                    else:
                        logger.debug(f"Skipping recent file: {f}")
                except Exception as e:
                    logger.warning(f"Error checking mtime for {f}: {e}")
                    stable_files.append(f)  # Include if we can't check
            
            recent_count = len(fits_files) - len(stable_files)
            if recent_count > 0:
                logger.info(f"Skipping {recent_count} recently modified files")
            fits_files = stable_files
        
        logger.info(f"Found {len(fits_files)} FITS files in {directory}")
        return sorted(fits_files)
    
    def _is_bad_file(self, filepath: str) -> bool:
        """Check if file is marked as bad."""
        filename = Path(filepath).name
        bad_markers = ['BAD_', 'CORRUPT_', 'ERROR_']
        return any(marker in filename.upper() for marker in bad_markers)
    
    def _is_file_locked(self, filepath: str) -> bool:
        """
        Check if file is locked (being written to).
        
        This prevents processing files that are actively being copied.
        """
        try:
            # Try to open in read+write mode (fails if locked on Windows)
            with open(filepath, 'r+b'):
                return False
        except (IOError, PermissionError, OSError):
            return True
    
    def scan_quarantine(self, skip_recent: bool = False) -> List[str]:
        """
        Perform manual scan of quarantine directory.
        
        Args:
            skip_recent: If True, skip recently modified files (for auto-scan)
        """
        logger.info(f"Performing quarantine scan (skip_recent={skip_recent})...")
        files = self.find_fits_files(self.config.paths.quarantine_dir, skip_recent=skip_recent)
        self.last_scan_time = time.time()
        return files
    
    def scan_for_new_files(self, skip_recent: bool = True) -> List[str]:
        """
        Scan for new files since last scan.
        
        Args:
            skip_recent: If True, skip recently modified files (default for auto-scan)
        """
        current_files = set(self.find_fits_files(
            self.config.paths.quarantine_dir, 
            skip_recent=skip_recent
        ))
        
        # Find new files
        new_files = current_files - self.last_scan_files
        self.last_scan_files = current_files
        self.last_scan_time = time.time()
        
        if new_files:
            logger.info(f"Found {len(new_files)} new files since last scan")
            return list(new_files)
        
        return []
    
    async def start_periodic_monitoring(self, interval_minutes: Optional[int] = None):
        """
        Start periodic monitoring of quarantine directory.
        
        Args:
            interval_minutes: Override interval from config/database
        """
        self.is_monitoring = True
        
        # Get interval from database or config
        if interval_minutes is None:
            if self.db_service:
                interval_minutes = self.db_service.get_setting(
                    'monitoring.interval_minutes', 
                    30
                )
            else:
                interval_minutes = 30
        
        interval_seconds = interval_minutes * 60
        
        logger.info(f"Starting periodic monitoring (every {interval_minutes} minutes)")
        
        # Perform initial scan to establish baseline
        self.last_scan_files = set(self.find_fits_files(
            self.config.paths.quarantine_dir,
            skip_recent=True  # Skip recent files on initial scan too
        ))
        self.last_scan_time = time.time()
        logger.info(f"Initial scan found {len(self.last_scan_files)} existing files")
        
        while self.is_monitoring:
            try:
                # Wait for the interval
                await asyncio.sleep(interval_seconds)
                
                if not self.is_monitoring:
                    break
                
                # Reload interval from database in case it changed
                if self.db_service:
                    interval_minutes = self.db_service.get_setting(
                        'monitoring.interval_minutes',
                        interval_minutes
                    )
                    interval_seconds = interval_minutes * 60
                
                # Scan for new files (skip recent ones)
                new_files = self.scan_for_new_files(skip_recent=True)
                
                if new_files and self.on_new_files:
                    logger.info(f"Processing {len(new_files)} new files found during monitoring")
                    self.on_new_files(new_files)
                
            except Exception as e:
                logger.error(f"Error during periodic monitoring: {e}")
                await asyncio.sleep(30)  # Wait before retrying
    
    def stop_monitoring(self):
        """Stop periodic monitoring."""
        self.is_monitoring = False
        logger.info("Stopped periodic monitoring")
    
    def get_monitoring_stats(self) -> dict:
        """Get monitoring statistics."""
        return {
            'is_monitoring': self.is_monitoring,
            'last_scan_file_count': len(self.last_scan_files),
            'last_scan_time': self.last_scan_time,
            'quarantine_dir': self.config.paths.quarantine_dir,
            'extensions': self.config.file_monitoring.extensions
        }