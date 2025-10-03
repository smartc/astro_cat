"""
FITS file processing - Backwards Compatibility Module

This module maintains backwards compatibility with code that imports
from fits_processor.py directly. All functionality has been moved to
the processing/ package, but is re-exported here.

DEPRECATED: New code should import from the processing package:
    from processing import OptimizedFitsProcessor
    from processing.metadata_extractor import parse_observation_date
    etc.

This file will be removed in a future version.
"""

import warnings

# Issue deprecation warning for direct imports
warnings.warn(
    "Importing from fits_processor.py is deprecated. "
    "Please update imports to use: from processing import OptimizedFitsProcessor",
    DeprecationWarning,
    stacklevel=2
)

# Re-export all public APIs from the processing package
from processing import (
    # Main processor class
    OptimizedFitsProcessor,
    
    # Metadata extraction functions
    extract_fits_metadata_simple,
    parse_observation_date,
    normalize_microseconds,
    fix_microseconds,
    get_header_value,
    normalize_frame_type,
    parse_coordinate,
    
    # Equipment identification functions
    identify_camera_simple,
    identify_telescope_simple,
    normalize_filter,
    calculate_field_of_view_simple,
    
    # Session generation
    generate_session_id_with_hash,
    
    # Parallel processing workers
    extract_fits_metadata_worker,
    extract_fits_metadata_with_streaming_hash,
)

# Define what gets exported with "from fits_processor import *"
__all__ = [
    'OptimizedFitsProcessor',
    'extract_fits_metadata_simple',
    'parse_observation_date',
    'normalize_microseconds',
    'fix_microseconds',
    'get_header_value',
    'normalize_frame_type',
    'parse_coordinate',
    'identify_camera_simple',
    'identify_telescope_simple',
    'normalize_filter',
    'calculate_field_of_view_simple',
    'generate_session_id_with_hash',
    'extract_fits_metadata_worker',
    'extract_fits_metadata_with_streaming_hash',
]