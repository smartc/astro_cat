"""
Metadata extraction functions for FITS files.

This module handles all FITS header parsing, date/time processing,
and metadata normalization operations.
"""

import logging
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from astropy.io import fits

logger = logging.getLogger(__name__)


def parse_observation_date(header, filepath: str = None) -> Optional[datetime]:
    """
    Parse observation date from various possible formats with file timestamp fallback.
    
    Args:
        header: FITS header object
        filepath: Path to FITS file for fallback timestamp
        
    Returns:
        datetime object or None if parsing fails
    """
    date_keys = ['DATE-OBS', 'DATE_OBS', 'DATEOBS']
    
    for key in date_keys:
        if key in header:
            try:
                date_str = header[key]
                if isinstance(date_str, str):
                    if 'T' in date_str:
                        # Check for corrupted years before parsing
                        year_match = re.match(r'^(\d{4})', date_str)
                        if year_match:
                            year = int(year_match.group(1))
                            if year < 1900 or year > 2030:  # Reasonable range check
                                logger.warning(
                                    f"Corrupted date in {filepath or 'file'}: "
                                    f"{date_str} (year {year})"
                                )
                                break  # Fall through to file timestamp fallback
                        
                        date_str = normalize_microseconds(date_str)
                        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    else:
                        return datetime.strptime(date_str, '%Y-%m-%d')
                elif hasattr(date_str, 'datetime'):
                    return date_str.datetime
            except Exception as e:
                logger.warning(f"Could not parse date {date_str} in {filepath or 'file'}: {e}")
                continue
    
    # Fallback to file system timestamps if DATE-OBS is corrupted or missing
    if filepath:
        try:
            stat = os.stat(filepath)
            # Use the earlier of creation time or modification time
            creation_time = datetime.fromtimestamp(stat.st_ctime)
            modification_time = datetime.fromtimestamp(stat.st_mtime)
            
            # Take the earlier timestamp (likely the real observation time)
            fallback_time = min(creation_time, modification_time)
            
            logger.info(f"Using file timestamp fallback for {filepath}: {fallback_time}")
            return fallback_time
            
        except Exception as e:
            logger.error(f"Could not get file timestamps for {filepath}: {e}")
    
    return None


def normalize_microseconds(timestamp_str: str) -> str:
    """
    Normalize microseconds to max 6 digits for datetime parsing.
    
    Args:
        timestamp_str: Timestamp string with potential > 6 digit microseconds
        
    Returns:
        Normalized timestamp string
    """
    pattern = r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\.(\d+)'
    match = re.match(pattern, timestamp_str)
    
    if match:
        base_time = match.group(1)
        microseconds = match.group(2)
        
        if len(microseconds) > 6:
            microseconds = microseconds[:6]
        elif len(microseconds) < 6:
            microseconds = microseconds.ljust(6, '0')
        
        return f"{base_time}.{microseconds}"
    
    return timestamp_str


# Alias for backwards compatibility
fix_microseconds = normalize_microseconds


def get_header_value(header, keys: List[str], value_type=str, default=None):
    """
    Get value from header with multiple possible key names.
    
    Args:
        header: FITS header object
        keys: List of possible header key names to try
        value_type: Type to cast the value to (default: str)
        default: Default value if key not found
        
    Returns:
        Header value or default
    """
    for key in keys:
        if key in header:
            try:
                value = header[key]
                if value_type and value is not None:
                    return value_type(value)
                return value
            except (ValueError, TypeError):
                continue
    return default


def normalize_frame_type(frame_type: str) -> str:
    """
    Normalize frame type names to standard values.
    
    Args:
        frame_type: Raw frame type from FITS header
        
    Returns:
        Normalized frame type (LIGHT, DARK, BIAS, FLAT, or original)
    """
    if not frame_type:
        return "UNKNOWN"
    
    frame_type = frame_type.upper().strip()
    
    mappings = {
        'LIGHT': 'LIGHT',
        'SCIENCE': 'LIGHT',
        'OBJECT': 'LIGHT',
        'DARK': 'DARK',
        'BIAS': 'BIAS',
        'ZERO': 'BIAS',
        'FLAT': 'FLAT',
        'FLATFIELD': 'FLAT',
        'FLAT-FIELD': 'FLAT',
    }
    
    return mappings.get(frame_type, frame_type)


def parse_coordinate(header, keys: List[str]) -> Optional[float]:
    """
    Parse coordinate from header, handling DMS format.
    
    Args:
        header: FITS header object
        keys: List of possible coordinate key names
        
    Returns:
        Decimal coordinate value or None
    """
    for key in keys:
        if key in header:
            try:
                value = header[key]
                
                if isinstance(value, (int, float)):
                    return float(value)
                
                if isinstance(value, str):
                    value = value.strip()
                    negative = value.startswith('-')
                    if negative:
                        value = value[1:]
                    
                    parts = value.split()
                    if len(parts) >= 3:
                        degrees = float(parts[0])
                        minutes = float(parts[1])
                        seconds = float(parts[2])
                        
                        decimal = degrees + minutes/60.0 + seconds/3600.0
                        if negative:
                            decimal = -decimal
                        return decimal
                    
                    return float(value)
                        
            except (ValueError, TypeError, IndexError):
                continue
    
    return None


def extract_fits_metadata_simple(filepath: str, header, 
                                 cameras_dict: Dict, 
                                 telescopes_dict: Dict, 
                                 filter_mappings: Dict[str, str]) -> Dict:
    """
    Extract metadata from FITS header (simplified for in-memory processing).
    
    This function assumes the header is already loaded and focuses on
    extracting and normalizing the metadata values.
    
    Args:
        filepath: Path to FITS file
        header: Already-loaded FITS header object
        cameras_dict: Dictionary of camera configurations
        telescopes_dict: Dictionary of telescope configurations
        filter_mappings: Dictionary of filter name mappings
        
    Returns:
        Dictionary of extracted metadata
    """
    from .equipment_identifier import (
        identify_camera_simple, identify_telescope_simple,
        normalize_filter, calculate_field_of_view_simple
    )
    from .session_generator import generate_session_id_with_hash
    from object_processor import ObjectNameProcessor
    
    # Extract basic metadata
    metadata = {
        'file': os.path.basename(filepath),
        'folder': os.path.dirname(filepath),
    }
    
    # Parse observation timestamp
    obs_timestamp = parse_observation_date(header, filepath)
    
    # Calculate observation date (shifted by 12 hours)
    if obs_timestamp:
        shifted_time = obs_timestamp - timedelta(hours=12)
        obs_date = shifted_time.strftime('%Y-%m-%d')
        obs_timestamp_truncated = obs_timestamp.replace(second=0, microsecond=0)
    else:
        obs_date = None
        obs_timestamp_truncated = None
    
    # Extract header values with fallbacks
    raw_object = get_header_value(header, ['OBJECT', 'TARGET'])
    instrument = get_header_value(header, ['INSTRUME'])
    filter_wheel = get_header_value(header, ['FWHEEL'])
    observer = get_header_value(header, ['OBSERVER'])
    site_name = get_header_value(header, ['SITENAME'])
    binning = get_header_value(header, ['XBINNING', 'BINNING'], int, 1)
    
    metadata.update({
        'obs_date': obs_date,
        'obs_timestamp': obs_timestamp_truncated,
        'ra': get_header_value(header, ['RA', 'OBJCTRA', 'CRVAL1']),
        'dec': get_header_value(header, ['DEC', 'OBJCTDEC', 'CRVAL2']),
        'x': get_header_value(header, ['NAXIS1'], int),
        'y': get_header_value(header, ['NAXIS2'], int),
        'frame_type': normalize_frame_type(
            get_header_value(header, ['IMAGETYP', 'FRAME'])
        ),
        'filter': normalize_filter(
            get_header_value(header, ['FILTER', 'FILTERS']), filter_mappings
        ),
        'focal_length': get_header_value(header, ['FOCALLEN'], float),
        'exposure': get_header_value(header, ['EXPOSURE', 'EXPTIME'], float),
    })
    
    # Process object name
    object_processor = ObjectNameProcessor()
    frame_type = metadata['frame_type']
    processed_object = object_processor.process_object_name(raw_object, frame_type)
    metadata['object'] = processed_object
    
    # Extract location data
    metadata.update({
        'latitude': parse_coordinate(header, ['SITELAT', 'LAT-OBS', 'LATITUDE']),
        'longitude': parse_coordinate(header, ['SITELONG', 'LONG-OBS', 'LONGITUDE']),
        'elevation': get_header_value(header, ['SITEELEV', 'ALT-OBS', 'ELEVATION'], float),
    })
    
    # Identify camera and telescope
    metadata['camera'] = identify_camera_simple(
        metadata['x'], metadata['y'], instrument, binning, cameras_dict
    )
    metadata['telescope'] = identify_telescope_simple(
        metadata['focal_length'], telescopes_dict
    )
    
    # Calculate field of view and pixel scale
    fov_data = calculate_field_of_view_simple(
        metadata['camera'], metadata['telescope'], 
        metadata['x'], metadata['y'], binning, cameras_dict, telescopes_dict
    )
    metadata.update(fov_data)
    
    # Generate session ID
    metadata['session_id'] = generate_session_id_with_hash(
        metadata['obs_date'], instrument, metadata['focal_length'],
        metadata['x'], metadata['y'], filter_wheel, observer, site_name
    )
    
    # Store session data for later extraction
    metadata['_session_data'] = {
        'session_id': metadata['session_id'],
        'session_date': obs_date,
        'telescope': metadata['telescope'],
        'camera': metadata['camera'],
        'site_name': site_name,
        'latitude': metadata['latitude'],
        'longitude': metadata['longitude'],
        'elevation': metadata['elevation'],
        'observer': observer,
        'notes': None
    }
    
    return metadata