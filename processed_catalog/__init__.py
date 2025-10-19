"""
Processed file cataloging module.

This module handles cataloging of processed astrophotography output files
(JPG, XISF, XOSM, PXIPROJECT) from processing sessions.
"""

from .cataloger import ProcessedFileCataloger
from .models import ProcessedFile, ProcessingSession
from .metadata_extractor import (
    extract_processed_file_metadata,
    extract_jpg_metadata,
    extract_xisf_metadata,
    extract_xosm_metadata,
    extract_pxiproject_metadata,
)

__all__ = [
    'ProcessedFileCataloger',
    'ProcessedFile',
    'ProcessingSession',
    'extract_processed_file_metadata',
    'extract_jpg_metadata',
    'extract_xisf_metadata',
    'extract_xosm_metadata',
    'extract_pxiproject_metadata',
]

__version__ = '1.0.0'