"""
Backwards compatibility shim for processed_catalog.models.

All models now live in main models.py. This module provides
deprecated imports with warnings.
"""

import warnings

# Import consolidated models from main models.py
from models import (
    ProcessingSession,
    ProcessedFile,
    ImagingSession as Session,  # For any old code that might import Session from here
    Base,  # In case anything imports Base from here
)

# Issue deprecation warning when this module is imported
warnings.warn(
    "Importing from processed_catalog.models is deprecated. "
    "Use 'from models import ProcessingSession, ProcessedFile' instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = ['ProcessingSession', 'ProcessedFile', 'Session', 'Base']
