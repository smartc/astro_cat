"""File monitoring for quarantine directory."""

import asyncio
import logging
import time
from pathlib import Path
from typing import Callable, List, Set

from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent
from watchdog.observers import Observer

from config import Config

logger = logging.getLogger(__name__)


class FitsFileHandler(FileSystemEventHandler):
    """Handler for FITS file system events."""
    
    def __init__(self, config: Config, callback: Callable[[List[str]], None]):
        self.config = config
        self.callback = callback
        self.extensions = tuple(config.file_monitoring.extensions)
        self.pending_files: Set[str] = set()
        self.last_scan = time.time()
        
    def on_created(self, event):
        """Handle file creation events."""
        if not event.is_directory and self._is_fits_file(event.src_path):
            logger.info(f"New FITS file detected: {event.src_path}")
            self.pending_files.add(event.src_path)
            self._schedule_callback()
    
    def on_moved(self, event):
        """Handle file move events."""
        if not event.is_directory and self._is_fits_file(event.dest_path):
            logger.info(f"FITS file moved to quarantine: {event.dest_path}")
            self.pending_files.add(event.dest_path)
            self._schedule_callback()
    
    def _is_fits_file(self, filepath: str) -> bool:
        """Check if file is a FITS file."""
        return filepath.lower().endswith(self.extensions)
    
    def _schedule_callback(self):
        """Schedule callback to process pending files."""
        current_time = time.time()
        
        # Only trigger callback if enough time has passed (debouncing)
        if current_time - self.last_scan > 5:  # 5 second debounce
            self.last_scan = current_time
            
            if self.pending_files:
                files_to_process = list(self.pending_files)
                self.pending_files.clear()
                
                # Verify files still exist and are complete
                valid_files = []
                for filepath in files_to_process:
                    if self._is_file_ready(filepath):
                        valid_files.append(filepath)
                    else:
                        logger.warning(f"File not ready or missing: {filepath}")
                
                if valid_files:
                    logger.info(f"Processing {len(valid_files)} new files")
                    self.callback(valid_files)
    
    def _is_file_ready(self, filepath: str) -> bool:
        """Check if file exists and is not being written to."""
        try:
            path = Path(filepath)
            if not path.exists():
                return False
            
            # Check if file size is stable (simple way to detect if still being written)
            initial_size = path.stat().st_size
            time.sleep(0.5)
            final_size = path.stat().st_size
            
            return initial_size == final_size and final_size > 0
            
        except Exception as e:
            logger.error(f"Error checking file readiness {filepath}: {e}")
            return False


class QuarantineMonitor:
    """Monitor quarantine directory for new FITS files."""
    
    def __init__(self, config: Config, on_new_files: Callable[[List[str]], None]):
        self.config = config
        self.on_new_files = on_new_files
        self.observer = None
        self.is_running = False
        
    def start_monitoring(self):
        """Start monitoring the quarantine directory."""
        quarantine_path = Path(self.config.paths.quarantine_dir)
        
        if not quarantine_path.exists():
            logger.error(f"Quarantine directory does not exist: {quarantine_path}")
            raise FileNotFoundError(f"Quarantine directory not found: {quarantine_path}")
        
        # Create event handler
        event_handler = FitsFileHandler(self.config, self.on_new_files)
        
        # Set up observer
        self.observer = Observer()
        self.observer.schedule(
            event_handler, 
            str(quarantine_path), 
            recursive=True
        )
        
        self.observer.start()
        self.is_running = True
        
        logger.info(f"Started monitoring quarantine directory: {quarantine_path}")
    
    def stop_monitoring(self):
        """Stop monitoring the quarantine directory."""
        if self.observer and self.is_running:
            self.observer.stop()
            self.observer.join()
            self.is_running = False
            logger.info("Stopped quarantine monitoring")
    
    def scan_existing_files(self) -> List[str]:
        """Scan for existing files in quarantine directory."""
        from fits_processor import FitsProcessor
        from config import load_config
        
        config, cameras, telescopes, filter_mappings = load_config()
        processor = FitsProcessor(config, cameras, telescopes, filter_mappings)
        return processor.find_fits_files(self.config.paths.quarantine_dir)


class PeriodicScanner:
    """Periodic scanner for quarantine directory as backup to file monitoring."""
    
    def __init__(self, config: Config, on_new_files: Callable[[List[str]], None]):
        self.config = config
        self.on_new_files = on_new_files
        self.last_scan_files: Set[str] = set()
        self.running = False
        
    async def start_periodic_scan(self):
        """Start periodic scanning of quarantine directory."""
        self.running = True
        logger.info("Started periodic quarantine scanning")
        
        while self.running:
            try:
                await self._scan_for_changes()
                await asyncio.sleep(self.config.file_monitoring.scan_interval_seconds)
            except Exception as e:
                logger.error(f"Error during periodic scan: {e}")
                await asyncio.sleep(30)  # Wait before retrying
    
    def stop_periodic_scan(self):
        """Stop periodic scanning."""
        self.running = False
        logger.info("Stopped periodic scanning")
    
    async def _scan_for_changes(self):
        """Scan for new or changed files."""
        from fits_processor import FitsProcessor
        from config import load_config
        
        config, cameras, telescopes, filter_mappings = load_config()
        processor = FitsProcessor(config, cameras, telescopes, filter_mappings)
        current_files = set(processor.find_fits_files(self.config.paths.quarantine_dir))
        
        # Find new files
        new_files = current_files - self.last_scan_files
        
        if new_files:
            logger.info(f"Periodic scan found {len(new_files)} new files")
            self.on_new_files(list(new_files))
        
        self.last_scan_files = current_files


class FileMonitorService:
    """Combined file monitoring service with both real-time and periodic scanning."""
    
    def __init__(self, config: Config, on_new_files: Callable[[List[str]], None]):
        self.config = config
        self.quarantine_monitor = QuarantineMonitor(config, on_new_files)
        self.periodic_scanner = PeriodicScanner(config, on_new_files)
    
    def start(self):
        """Start both monitoring services."""
        try:
            # Start real-time monitoring
            self.quarantine_monitor.start_monitoring()
            
            # Start periodic scanning as backup
            asyncio.create_task(self.periodic_scanner.start_periodic_scan())
            
            logger.info("File monitoring services started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start file monitoring: {e}")
            raise
    
    def stop(self):
        """Stop all monitoring services."""
        self.quarantine_monitor.stop_monitoring()
        self.periodic_scanner.stop_periodic_scan()
        logger.info("All file monitoring services stopped")
    
    def scan_existing(self) -> List[str]:
        """Perform initial scan of existing files."""
        return self.quarantine_monitor.scan_existing_files()