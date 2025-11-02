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

from .software_profiles import get_profile_manager
from .timezone_utils import calculate_observation_date

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
    """Get value from header with multiple possible key names."""
    from astropy.io.fits.verify import VerifyError
    
    for key in keys:
        if key in header:
            try:
                value = header[key]
                if value_type and value is not None:
                    return value_type(value)
                return value
            except (ValueError, TypeError, VerifyError) as e:
                logger.debug(f"Error reading {key}: {e}")
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
                                cameras_dict: dict, 
                                telescopes_dict: dict, 
                                filter_mappings: dict) -> dict:
    """
    Extract metadata from FITS header with software profile support.
    """
    from .equipment_identifier import (
        identify_camera_simple, identify_telescope_simple,
        normalize_filter, calculate_field_of_view_simple
    )
    from .session_generator import generate_session_id_with_hash
    from object_processor import ObjectNameProcessor
    
    # Get profile manager (auto-loads from profiles/ directory)
    profile_manager = get_profile_manager()
    
    # Detect capture software
    detected_software = profile_manager.detect_software(header)
    
    # Extract basic metadata
    metadata = {
        'file': os.path.basename(filepath),
        'folder': os.path.dirname(filepath),
    }
    
    # Parse observation timestamp
    obs_timestamp = parse_observation_date(header, filepath)
    
    # Calculate observation date (shifted by 12 hours and adjusted for localtime at location)
    if obs_timestamp:
        # Get coordinates for timezone calculation
        latitude = get_header_value(header, ['SITELAT'], float)
        longitude = get_header_value(header, ['SITELONG'], float)
        
        # Calculate observation date in local time
        obs_date = calculate_observation_date(
            obs_timestamp, 
            latitude, 
            longitude,
            config_offset=getattr(config, 'timezone_offset', None) if 'config' in locals() else None
        )
        obs_timestamp_truncated = obs_timestamp.replace(second=0, microsecond=0)
    
    # =======================================================================
    # USE PROFILE-AWARE EXTRACTION
    # =======================================================================
    
    # Extract header values using profile system with fallbacks
    raw_object = profile_manager.get_value(header, 'target', detected_software)
    if not raw_object:
        raw_object = get_header_value(header, ['OBJECT', 'TARGET'])
    
    instrument = profile_manager.get_value(header, 'camera', detected_software)
    if not instrument:
        instrument = get_header_value(header, ['INSTRUME'])
    
    # Get filter NAME from profile
    filter_raw = profile_manager.get_value(header, 'filter', detected_software)
    if not filter_raw:
        filter_raw = get_header_value(header, ['FILTER'])

    # Get filter WHEEL device from profile
    filter_wheel = profile_manager.get_value(header, 'filter_wheel', detected_software)
    if not filter_wheel:
        filter_wheel = get_header_value(header, ['FWHEEL'])
    
    telescope_raw = profile_manager.get_value(header, 'telescope', detected_software)
    if not telescope_raw:
        telescope_raw = get_header_value(header, ['TELESCOP'])
    
    frame_type_raw = profile_manager.get_value(header, 'frame_type', detected_software)
    if not frame_type_raw:
        frame_type_raw = get_header_value(header, ['IMAGETYP', 'FRAMETYPE'])
    
    # Continue with existing extraction...
    focal_len_raw = get_header_value(header, ['FOCALLEN'], float)
    observer = get_header_value(header, ['OBSERVER'])
    site_name = get_header_value(header, ['SITENAME'])
    binning = get_header_value(header, ['XBINNING', 'BINNING'], int, 1)
    
    # Image dimensions
    width_pixels = get_header_value(header, ['NAXIS1'], int)
    height_pixels = get_header_value(header, ['NAXIS2'], int)
    
    # Normalize frame type (profile may have already mapped it)
    frame_type = normalize_frame_type(frame_type_raw)
    
    # Process object name
    object_processor = ObjectNameProcessor()
    if raw_object:
        object_name = object_processor.process_object_name(raw_object, frame_type)
    else:
        object_name = None
    
    # Identify equipment using current function signatures
    camera_name = identify_camera_simple(
        width_pixels, height_pixels, instrument, binning, cameras_dict
    )

    telescope_name = identify_telescope_simple(
        focal_len_raw, telescopes_dict
    )

    # For BIAS and DARK frames, telescope is not relevant (no optics involved)
    # Set to None instead of 'UNKNOWN'
    if frame_type in ['BIAS', 'DARK']:
        telescope_name = None

    filter_name = normalize_filter(filter_raw, filter_mappings)

    # Coordinates
    ra = parse_coordinate(header, ['OBJCTRA', 'RA'])
    dec = parse_coordinate(header, ['OBJCTDEC', 'DEC'])

    # Location
    latitude = get_header_value(header, ['SITELAT'], float)
    longitude = get_header_value(header, ['SITELONG'], float)
    elevation = get_header_value(header, ['SITEELEV'], float)

    # Calculate field of view
    fov_data = calculate_field_of_view_simple(
        camera_name, telescope_name, width_pixels, height_pixels, binning,
        cameras_dict, telescopes_dict
    )
    
    # Build metadata dict
    metadata.update({
        'object': object_name,
        'obs_date': obs_date,
        'obs_timestamp': obs_timestamp_truncated,
        'ra': str(ra) if ra is not None else None,
        'dec': str(dec) if dec is not None else None,
        'width_pixels': width_pixels,
        'height_pixels': height_pixels,
        'frame_type': frame_type,
        'filter': filter_name,
        'focal_length': focal_len_raw,
        'exposure': get_header_value(header, ['EXPTIME', 'EXPOSURE'], float),
        'camera': camera_name,
        'telescope': telescope_name,
        'latitude': latitude,
        'longitude': longitude,
        'elevation': elevation,
    })
    
    # Add FOV data
    metadata.update(fov_data)
    
    # Generate session ID
    session_id = generate_session_id_with_hash(
        obs_date, instrument, focal_len_raw, width_pixels, height_pixels,
        filter_wheel, observer, site_name
    )
    metadata['imaging_session_id'] = session_id

    # Store session data
    metadata['_session_data'] = {
        'id': session_id,
        'date': obs_date,
        'telescope': telescope_name,
        'camera': camera_name,
        'site_name': site_name,
        'latitude': latitude,
        'longitude': longitude,
        'elevation': elevation,
        'observer': observer,
        'notes': None
    }
    
    # Add extended metadata
    extended = extract_extended_metadata(header)
    metadata.update(extended)
    
    return metadata


def extract_extended_metadata(header) -> dict:
    """
    Extract extended metadata fields from FITS header.
    
    Args:
        header: FITS header object
        
    Returns:
        Dictionary of extended metadata fields
    """
    extended = {}
    
    # Camera/Sensor settings
    extended['gain'] = get_header_value(header, ['GAIN'], int)
    extended['offset'] = get_header_value(header, ['OFFSET'], int)
    extended['egain'] = get_header_value(header, ['EGAIN'], float)
    extended['binning_x'] = get_header_value(header, ['XBINNING'], int, 1)
    extended['binning_y'] = get_header_value(header, ['YBINNING'], int, 1)
    extended['sensor_temp'] = get_header_value(header, ['CCD-TEMP', 'TEMPERAT', 'SET-TEMP'], float)
    extended['readout_mode'] = get_header_value(header, ['READOUTM', 'READMODE'], str)
    extended['bayerpat'] = get_header_value(header, ['BAYERPAT'], str)
    extended['iso_speed'] = get_header_value(header, ['ISOSPEED'], int)
    
    # Guiding information
    extended['guide_rms'] = get_header_value(header, ['GUIDERMS'], float)
    extended['guide_fwhm'] = get_header_value(header, ['AVG_FWHM', 'GUIDEFWH'], float)
    extended['guide_rms_ra'] = get_header_value(header, ['GUIDERMSRA', 'GUIDERRMS'], float)
    extended['guide_rms_dec'] = get_header_value(header, ['GUIDERMSDEC', 'GUIDERMSDE'], float)
    
    # Weather conditions
    extended['ambient_temp'] = get_header_value(header, ['AMBTEMP', 'AOCAMBT'], float)
    extended['dewpoint'] = get_header_value(header, ['DEWPOINT', 'AOCDEW'], float)
    extended['humidity'] = get_header_value(header, ['HUMIDITY', 'AOCHUM'], float)
    extended['pressure'] = get_header_value(header, ['PRESSURE'], float)
    extended['sky_temp'] = get_header_value(header, ['SKYTEMP'], float)
    extended['sky_quality_mpsas'] = get_header_value(header, ['MPSAS', 'SQM'], float)
    extended['sky_brightness'] = get_header_value(header, ['SKYBRGHT'], float)
    extended['wind_speed'] = get_header_value(header, ['WINDSPD', 'AOCWIND'], float)
    extended['wind_direction'] = get_header_value(header, ['WINDDIR'], float)
    extended['wind_gust'] = get_header_value(header, ['WINDGUST'], float)
    extended['cloud_cover'] = get_header_value(header, ['CLOUDCVR'], float)
    extended['seeing_fwhm'] = get_header_value(header, ['SEEING', 'STARFWHM', 'AOCFWHM'], float)
    
    # Focus information
    extended['focuser_position'] = get_header_value(header, ['FOCUSPOS'], int)
    extended['focuser_temp'] = get_header_value(header, ['FOCUSTEM'], float)
    
    # Software and observer
    extended['software_creator'] = get_header_value(header, ['SWCREATE'], str)
    extended['software_modifier'] = get_header_value(header, ['SWMODIFY'], str)
    extended['observer'] = get_header_value(header, ['OBSERVER'], str)
    extended['site_name'] = get_header_value(header, ['SITENAME'], str)
    
    # Airmass and timing
    extended['airmass'] = get_header_value(header, ['AIRMASS'], float)
    
    # Additional quality metrics
    extended['star_count'] = get_header_value(header, ['STARCOUNT'], int)
    extended['median_fwhm'] = get_header_value(header, ['MEDFWHM', 'FWHM'], float)
    extended['eccentricity'] = get_header_value(header, ['ECCENTRIC'], float)
    
    # Boltwood Cloud Sensor fields
    extended['boltwood_cloud'] = get_header_value(header, ['BOLTCLOU'], float)
    extended['boltwood_wind'] = get_header_value(header, ['BOLTWIND'], float)
    extended['boltwood_rain'] = get_header_value(header, ['BOLTRAIN'], float)
    extended['boltwood_daylight'] = get_header_value(header, ['BOLTDAY'], float)
    
    return extended