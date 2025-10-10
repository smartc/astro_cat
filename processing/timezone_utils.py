"""
Timezone utilities for observation date calculation.

Determines timezone offset from coordinates or config to properly
calculate observation dates in local time.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import optional timezone libraries
try:
    from timezonefinder import TimezoneFinder
    import pytz
    TIMEZONE_AVAILABLE = True
except ImportError:
    TIMEZONE_AVAILABLE = False
    logger.debug("timezonefinder/pytz not available - will use config offset")


def get_timezone_offset_from_coords(latitude: float, longitude: float, 
                                    timestamp: datetime) -> Optional[int]:
    """
    Get timezone offset in hours from coordinates.
    
    Args:
        latitude: Site latitude in degrees
        longitude: Site longitude in degrees  
        timestamp: Timestamp to check (for DST)
        
    Returns:
        Offset in hours from UTC (e.g., -7 for MST) or None if unavailable
    """
    if not TIMEZONE_AVAILABLE:
        return None
    
    try:
        tf = TimezoneFinder()
        tz_name = tf.timezone_at(lat=latitude, lng=longitude)
        
        if tz_name:
            tz = pytz.timezone(tz_name)
            # Get offset at the specific timestamp (handles DST)
            offset = tz.utcoffset(timestamp)
            if offset:
                return int(offset.total_seconds() / 3600)
    
    except Exception as e:
        logger.debug(f"Could not determine timezone from coordinates: {e}")
    
    return None


def get_timezone_offset(latitude: Optional[float] = None,
                       longitude: Optional[float] = None,
                       timestamp: Optional[datetime] = None,
                       config_offset: Optional[int] = None) -> int:
    """
    Get timezone offset with fallback chain.
    
    Priority:
    1. Calculate from coordinates (if timezonefinder available)
    2. Use config setting
    3. Use system local timezone
    4. Default to -6 (Mountain Time)
    
    Args:
        latitude: Site latitude in degrees
        longitude: Site longitude in degrees
        timestamp: Timestamp to check for DST
        config_offset: Configured offset from config.json
        
    Returns:
        Offset in hours from UTC
    """
    # Try coordinates first
    if latitude is not None and longitude is not None and timestamp:
        offset = get_timezone_offset_from_coords(latitude, longitude, timestamp)
        if offset is not None:
            logger.debug(f"Using timezone offset from coordinates: UTC{offset:+d}")
            return offset
    
    # Try config setting
    if config_offset is not None:
        logger.debug(f"Using timezone offset from config: UTC{config_offset:+d}")
        return config_offset
    
    # Try system local timezone
    try:
        local_offset = -time.timezone / 3600
        if time.daylight:
            local_offset = -time.altzone / 3600
        logger.debug(f"Using system timezone offset: UTC{local_offset:+d}")
        return int(local_offset)
    except:
        pass
    
    # Default to Mountain Time
    logger.debug("Using default timezone offset: UTC-6 (Mountain)")
    return -6


def calculate_observation_date(utc_timestamp: datetime,
                               latitude: Optional[float] = None,
                               longitude: Optional[float] = None,
                               config_offset: Optional[int] = None) -> str:
    """
    Calculate observation date in local time.
    
    Applies timezone offset to convert UTC to local time, then shifts
    back 12 hours so that observations from noon-to-noon are grouped
    as a single "night".
    
    Args:
        utc_timestamp: Observation timestamp in UTC
        latitude: Site latitude for timezone calculation
        longitude: Site longitude for timezone calculation
        config_offset: Configured timezone offset
        
    Returns:
        Observation date string (YYYY-MM-DD)
    """
    # Get timezone offset
    offset_hours = get_timezone_offset(latitude, longitude, utc_timestamp, config_offset)
    
    # Convert UTC to local time
    local_timestamp = utc_timestamp + timedelta(hours=offset_hours)
    
    # Shift back 12 hours for observation night
    # (so midnight-noon stays as previous date, noon-midnight is current date)
    shifted_timestamp = local_timestamp - timedelta(hours=12)
    
    return shifted_timestamp.strftime('%Y-%m-%d')
