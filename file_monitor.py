"""Simplified file monitoring for quarantine directory."""

import asyncio
import logging
import time
from pathlib import Path
from typing import Callable, List

from config import Config

logger = logging.getLogger(__name__)


class FileMonitor:
    """Simple file monitoring with manual and periodic scan capabilities."""
    
    def __init__(self, config: Config, on_new_files: Callable[[List[str]], None]):
        self.config = config
        self.on_new_files = on_new_files
        self.is_monitoring = False
        self.last_scan_files: set = set()
        
    def find_fits_files(self, directory: str) -> List[str]:
        """Find all FITS files in directory and subdirectories."""
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
        
        logger.info(f"Found {len(fits_files)} FITS files in {directory}")
        return sorted(fits_files)
    
    def _is_bad_file(self, filepath: str) -> bool:
        """Check if file is marked as bad."""
        filename = Path(filepath).name
        bad_markers = ['BAD_', 'CORRUPT_', 'ERROR_']
        return any(marker in filename.upper() for marker in bad_markers)
    
    def scan_quarantine(self) -> List[str]:
        """Perform manual scan of quarantine directory."""
        logger.info("Performing manual quarantine scan...")
        return self.find_fits_files(self.config.paths.quarantine_dir)
    
    def scan_for_new_files(self) -> List[str]:
        """Scan for new files since last scan."""
        current_files = set(self.find_fits_files(self.config.paths.quarantine_dir))
        
        # Find new files
        new_files = current_files - self.last_scan_files
        self.last_scan_files = current_files
        
        if new_files:
            logger.info(f"Found {len(new_files)} new files since last scan")
            return list(new_files)
        
        return []
    
    async def start_periodic_monitoring(self, interval_minutes: int = 30):
        """Start periodic monitoring of quarantine directory."""
        self.is_monitoring = True
        interval_seconds = interval_minutes * 60
        
        logger.info(f"Starting periodic monitoring (every {interval_minutes} minutes)")
        
        # Perform initial scan to establish baseline
        self.last_scan_files = set(self.find_fits_files(self.config.paths.quarantine_dir))
        logger.info(f"Initial scan found {len(self.last_scan_files)} existing files")
        
        while self.is_monitoring:
            try:
                # Wait for the interval
                await asyncio.sleep(interval_seconds)
                
                if not self.is_monitoring:
                    break
                
                # Scan for new files
                new_files = self.scan_for_new_files()
                
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
            'quarantine_dir': self.config.paths.quarantine_dir,
            'extensions': self.config.file_monitoring.extensions
        }