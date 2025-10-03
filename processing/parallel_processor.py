"""
Parallel processing worker functions for FITS files.

This module contains worker functions designed for multiprocessing
that extract metadata and calculate MD5 hashes efficiently.
"""

import hashlib
import logging
import os
from io import BytesIO
from typing import Dict, Optional

from astropy.io import fits

from .metadata_extractor import extract_fits_metadata_simple

logger = logging.getLogger(__name__)


def extract_fits_metadata_worker(filepath: str, cameras_dict: Dict, 
                                telescopes_dict: Dict, 
                                filter_mappings: Dict[str, str]) -> Optional[Dict]:
    """
    Worker function for parallel FITS metadata extraction (no MD5).
    
    This function is designed to be called by multiprocessing workers
    and extracts only metadata without calculating MD5 hash.
    
    Args:
        filepath: Path to FITS file
        cameras_dict: Dictionary of camera configurations
        telescopes_dict: Dictionary of telescope configurations
        filter_mappings: Dictionary of filter name mappings
        
    Returns:
        Dictionary of extracted metadata or None on error
    """
    try:
        # Use memory mapping and lazy loading for performance
        with fits.open(filepath, memmap=True, lazy_load_hdus=True) as hdul:
            header = hdul[0].header
            
            # Use the common metadata extraction function
            metadata = extract_fits_metadata_simple(
                filepath, header, cameras_dict, 
                telescopes_dict, filter_mappings
            )
            
            logger.debug(f"Successfully processed metadata for {filepath}")
            return metadata
                
    except Exception as e:
        logger.error(f"Error processing FITS file {filepath}: {e}")
        return None


def extract_fits_metadata_with_streaming_hash(filepath: str, cameras_dict: Dict, 
                                             telescopes_dict: Dict, 
                                             filter_mappings: Dict[str, str]) -> Optional[Dict]:
    """
    Worker function that extracts metadata AND calculates MD5 hash in a single file read.
    
    This optimized version reads the file once and performs both MD5 calculation
    and metadata extraction, reducing I/O overhead.
    
    Args:
        filepath: Path to FITS file
        cameras_dict: Dictionary of camera configurations
        telescopes_dict: Dictionary of telescope configurations
        filter_mappings: Dictionary of filter name mappings
        
    Returns:
        Dictionary of extracted metadata with md5sum field or None on error
    """
    try:
        # Initialize MD5 hash
        hash_md5 = hashlib.md5()
        
        # Read entire file and calculate hash
        with open(filepath, 'rb') as f:
            file_data = f.read()
            hash_md5.update(file_data)
        
        file_md5 = hash_md5.hexdigest()
        
        # Now process FITS metadata from the file data in memory
        # Create a BytesIO object to simulate file for astropy
        file_like = BytesIO(file_data)
        
        with fits.open(file_like, lazy_load_hdus=True) as hdul:
            header = hdul[0].header
            
            # Use the common metadata extraction function
            metadata = extract_fits_metadata_simple(
                filepath, header, cameras_dict, 
                telescopes_dict, filter_mappings
            )
            
            # Add MD5 hash to metadata
            metadata['md5sum'] = file_md5
            
            logger.debug(f"Successfully processed metadata + hash for {filepath}")
            return metadata
                
    except Exception as e:
        logger.error(f"Error processing FITS file {filepath}: {e}")
        return None


def _compute_md5_worker(filepath: str) -> tuple[str, str]:
    """
    Worker function to compute MD5 hash of a file.
    
    This is used when MD5 calculation needs to be done separately
    from metadata extraction.
    
    Args:
        filepath: Path to file
        
    Returns:
        Tuple of (filepath, md5_hash)
    """
    try:
        hash_md5 = hashlib.md5()
        with open(filepath, 'rb') as f:
            # Read in chunks for better memory efficiency
            for chunk in iter(lambda: f.read(8192), b""):
                hash_md5.update(chunk)
        return filepath, hash_md5.hexdigest()
    except Exception as e:
        logger.error(f"Error computing MD5 for {filepath}: {e}")
        return filepath, None


def _process_single_file_worker(filepath: str, cameras_dict: Dict,
                               telescopes_dict: Dict,
                               filter_mappings: Dict[str, str],
                               compute_hash: bool = True) -> Optional[Dict]:
    """
    Generic worker function for processing a single FITS file.
    
    This wrapper function can be used for different processing modes.
    
    Args:
        filepath: Path to FITS file
        cameras_dict: Dictionary of camera configurations
        telescopes_dict: Dictionary of telescope configurations
        filter_mappings: Dictionary of filter name mappings
        compute_hash: Whether to compute MD5 hash
        
    Returns:
        Dictionary of extracted metadata or None on error
    """
    if compute_hash:
        return extract_fits_metadata_with_streaming_hash(
            filepath, cameras_dict, telescopes_dict, filter_mappings
        )
    else:
        return extract_fits_metadata_worker(
            filepath, cameras_dict, telescopes_dict, filter_mappings
        )