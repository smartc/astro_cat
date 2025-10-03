"""
Processing package for FITS file handling.

This package contains modular components for FITS metadata extraction,
equipment identification, session generation, and parallel processing.
"""

# Re-export main processor for backwards compatibility
from .fits_processor import OptimizedFitsProcessor

# Re-export commonly used functions for backwards compatibility
from .metadata_extractor import (
    extract_fits_metadata_simple,
    parse_observation_date,
    normalize_microseconds,
    fix_microseconds,
    get_header_value,
    normalize_frame_type,
    parse_coordinate
)

from .equipment_identifier import (
    identify_camera_simple,
    identify_telescope_simple,
    normalize_filter,
    calculate_field_of_view_simple
)

from .session_generator import generate_session_id_with_hash

from .parallel_processor import (
    extract_fits_metadata_worker,
    extract_fits_metadata_with_streaming_hash
)

__all__ = [
    # Main processor
    'OptimizedFitsProcessor',
    
    # Metadata extraction
    'extract_fits_metadata_simple',
    'parse_observation_date',
    'normalize_microseconds',
    'fix_microseconds',
    'get_header_value',
    'normalize_frame_type',
    'parse_coordinate',
    
    # Equipment identification
    'identify_camera_simple',
    'identify_telescope_simple',
    'normalize_filter',
    'calculate_field_of_view_simple',
    
    # Session generation
    'generate_session_id_with_hash',
    
    # Parallel processing
    'extract_fits_metadata_worker',
    'extract_fits_metadata_with_streaming_hash',
]