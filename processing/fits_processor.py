"""
FITS file processor with optimizations and multiprocessing support.

This is the main entry point for FITS file processing, orchestrating
metadata extraction, equipment identification, and parallel processing.
"""

import logging
import multiprocessing as mp
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
from pathlib import Path
from typing import Dict, List, Tuple

import polars as pl
from tqdm import tqdm

from .parallel_processor import extract_fits_metadata_with_streaming_hash

logger = logging.getLogger(__name__)


class OptimizedFitsProcessor:
    """
    Optimized FITS processor with multiprocessing and memory mapping.
    
    This class orchestrates the processing of FITS files, including:
    - Finding FITS files in directories
    - Extracting metadata in parallel
    - Computing MD5 hashes
    - Managing sessions
    - Creating DataFrames for database insertion
    """
    
    def __init__(self, config, cameras: List, telescopes: List, 
                 filter_mappings: Dict[str, str], db_service=None):
        """
        Initialize the FITS processor.
        
        Args:
            config: Configuration object
            cameras: List of camera objects
            telescopes: List of telescope objects
            filter_mappings: Dictionary of filter name mappings
            db_service: Optional database service for advanced operations
        """
        self.config = config
        self.cameras = {cam.camera: cam for cam in cameras}
        self.telescopes = {tel.scope: tel for tel in telescopes}
        self.filter_mappings = filter_mappings
        self.db_service = db_service
        
        # Determine optimal number of workers
        self.cpu_count = mp.cpu_count()
        # Leave two cores free, max 12 workers
        self.metadata_workers = min(self.cpu_count - 2, 12)
        self.md5_workers = min(self.cpu_count - 2, 12)
        
        logger.info(
            f"Initialized with {self.metadata_workers} metadata workers, "
            f"{self.md5_workers} MD5 workers"
        )
    
    def find_fits_files(self, directory: str) -> List[str]:
        """
        Find all FITS files in directory and subdirectories with progress reporting.
        
        Args:
            directory: Root directory to search
            
        Returns:
            List of FITS file paths
        """
        logger.info(f"Scanning for FITS files in {directory}...")
        
        # Get file extensions from config
        extensions = tuple(self.config.file_monitoring.extensions)
        
        fits_files = []
        dir_path = Path(directory)
        
        # Count total files first for better progress reporting
        all_files = list(dir_path.rglob('*'))
        
        with tqdm(total=len(all_files), desc="Scanning files", unit="files") as pbar:
            for file_path in all_files:
                pbar.update(1)
                
                if file_path.is_file():
                    # Check file extension
                    if file_path.suffix.lower() in extensions:
                        # Skip files marked as bad
                        if not self._is_bad_file(str(file_path)):
                            fits_files.append(str(file_path))
        
        logger.info(f"Found {len(fits_files)} FITS files")
        return fits_files
    
    def _is_bad_file(self, filepath: str) -> bool:
        """
        Check if filename is marked as bad/corrupt.
        
        Args:
            filepath: Path to file
            
        Returns:
            True if file is marked as bad
        """
        filename = os.path.basename(filepath)
        bad_markers = ['BAD_', 'CORRUPT_', 'ERROR_']
        return any(marker in filename.upper() for marker in bad_markers)
    
    def process_files_optimized(self, filepaths: List[str]) -> Tuple[pl.DataFrame, List[dict]]:
        """
        Process multiple FITS files with streaming optimization (metadata + MD5 in one pass).
        
        This is the main entry point for batch processing of FITS files.
        It uses parallel processing to extract metadata and calculate MD5
        hashes in a single pass through each file.
        
        Args:
            filepaths: List of FITS file paths to process
            
        Returns:
            Tuple of (DataFrame with all results, list of session dictionaries)
        """
        results = []
        failed_files = []
        sessions = {}
        
        logger.info(f"Processing {len(filepaths)} files with streaming optimization...")
        
        # Single phase: Extract metadata AND calculate MD5 in one pass
        with tqdm(total=len(filepaths), desc="Processing files (streaming)", 
                 unit="files") as pbar:
            
            # Create worker function with bound parameters
            worker_func = partial(
                extract_fits_metadata_with_streaming_hash,
                cameras_dict=self.cameras,
                telescopes_dict=self.telescopes,
                filter_mappings=self.filter_mappings
            )
            
            # Process in parallel with ProcessPoolExecutor
            with ProcessPoolExecutor(max_workers=self.metadata_workers) as executor:
                future_to_file = {
                    executor.submit(worker_func, filepath): filepath 
                    for filepath in filepaths
                }
                
                for future in as_completed(future_to_file):
                    filepath = future_to_file[future]
                    try:
                        metadata = future.result()
                        if metadata:
                            # Extract session data
                            session_data = metadata.pop('_session_data', None)
                            if session_data and session_data['session_id'] != 'UNKNOWN':
                                sessions[session_data['session_id']] = session_data
                            
                            results.append(metadata)
                        else:
                            failed_files.append(filepath)
                    except Exception as e:
                        logger.error(f"Failed to process {filepath}: {e}")
                        failed_files.append(filepath)
                    
                    pbar.update(1)
                    
                    # Update progress info every 50 files
                    if len(results) % 50 == 0:
                        pbar.set_postfix({
                            'success': len(results),
                            'failed': len(failed_files),
                            'sessions': len(sessions)
                        })
        
        # Report results
        logger.info(f"Successfully processed: {len(results)} files")
        if failed_files:
            logger.warning(f"Failed to process: {len(failed_files)} files")
        logger.info(f"Identified {len(sessions)} unique imaging sessions")
        
        # Convert to DataFrame
        if results:
            df = pl.DataFrame(results)
            # Convert session dict to list
            session_list = list(sessions.values())
            return df, session_list
        else:
            # Return empty DataFrame with expected schema
            return pl.DataFrame(), []
    
    def process_files_metadata_only(self, filepaths: List[str]) -> Tuple[pl.DataFrame, List[dict]]:
        """
        Process files extracting only metadata (no MD5 calculation).
        
        This method is faster but doesn't compute MD5 hashes. Use when
        hash calculation is not needed or will be done separately.
        
        Args:
            filepaths: List of FITS file paths to process
            
        Returns:
            Tuple of (DataFrame with all results, list of session dictionaries)
        """
        from .parallel_processor import extract_fits_metadata_worker
        
        results = []
        failed_files = []
        sessions = {}
        
        logger.info(f"Processing {len(filepaths)} files (metadata only)...")
        
        with tqdm(total=len(filepaths), desc="Extracting metadata", 
                 unit="files") as pbar:
            
            # Create worker function with bound parameters
            worker_func = partial(
                extract_fits_metadata_worker,
                cameras_dict=self.cameras,
                telescopes_dict=self.telescopes,
                filter_mappings=self.filter_mappings
            )
            
            # Process in parallel
            with ProcessPoolExecutor(max_workers=self.metadata_workers) as executor:
                future_to_file = {
                    executor.submit(worker_func, filepath): filepath 
                    for filepath in filepaths
                }
                
                for future in as_completed(future_to_file):
                    filepath = future_to_file[future]
                    try:
                        metadata = future.result()
                        if metadata:
                            # Extract session data
                            session_data = metadata.pop('_session_data', None)
                            if session_data and session_data['session_id'] != 'UNKNOWN':
                                sessions[session_data['session_id']] = session_data
                            
                            results.append(metadata)
                        else:
                            failed_files.append(filepath)
                    except Exception as e:
                        logger.error(f"Failed to process {filepath}: {e}")
                        failed_files.append(filepath)
                    
                    pbar.update(1)
        
        # Report results
        logger.info(f"Successfully processed: {len(results)} files")
        if failed_files:
            logger.warning(f"Failed to process: {len(failed_files)} files")
        
        # Convert to DataFrame
        if results:
            df = pl.DataFrame(results)
            session_list = list(sessions.values())
            return df, session_list
        else:
            return pl.DataFrame(), []
    
    def scan_quarantine(self) -> Tuple[pl.DataFrame, List[dict]]:
        """
        Scan the quarantine directory and process all FITS files.
        
        This is a convenience method that combines find_fits_files() and
        process_files_optimized() in a single call. Primarily used by
        the web interface and CLI.
        
        Returns:
            Tuple of (DataFrame with all results, list of session dictionaries)
        """
        logger.info(f"Scanning quarantine directory: {self.config.paths.quarantine_dir}")
        
        # Find all FITS files
        filepaths = self.find_fits_files(self.config.paths.quarantine_dir)
        
        if not filepaths:
            logger.info("No FITS files found in quarantine directory")
            return pl.DataFrame(), []
        
        # Process the files
        logger.info(f"Processing {len(filepaths)} files...")
        df, sessions = self.process_files_optimized(filepaths)
        
        return df, sessions
    
    def get_statistics(self, df: pl.DataFrame) -> Dict:
        """
        Generate statistics from processed DataFrame.
        
        Args:
            df: DataFrame of processed FITS files
            
        Returns:
            Dictionary of statistics
        """
        if df.is_empty():
            return {
                'total_files': 0,
                'unique_sessions': 0,
                'unique_cameras': 0,
                'unique_telescopes': 0,
                'unique_filters': 0,
                'frame_type_counts': {}
            }
        
        stats = {
            'total_files': len(df),
            'unique_sessions': df['imaging_session_id'].n_unique(),
            'unique_cameras': df['camera'].n_unique(),
            'unique_telescopes': df['telescope'].n_unique(),
            'unique_filters': df['filter'].n_unique(),
        }
        
        # Frame type counts
        if 'frame_type' in df.columns:
            frame_counts = df.group_by('frame_type').count()
            stats['frame_type_counts'] = {
                row['frame_type']: row['count'] 
                for row in frame_counts.to_dicts()
            }
        
        return stats