"""
Session ID generation for imaging sessions.

This module generates unique session identifiers based on observation
date and equipment configuration to group related images together.
"""

import hashlib
from typing import Optional


def generate_session_id_with_hash(obs_date: Optional[str], 
                                 instrument: str, 
                                 focal_length: Optional[float],
                                 naxis1: Optional[int] = None, 
                                 naxis2: Optional[int] = None,
                                 filter_wheel: Optional[str] = None,
                                 observer: Optional[str] = None,
                                 site_name: Optional[str] = None) -> str:
    """
    Generate session ID using rig hash approach.
    
    Creates a unique identifier for an imaging session based on the date
    and equipment configuration. Images taken on the same night with the
    same equipment will have the same session ID.
    
    Args:
        obs_date: Observation date in YYYY-MM-DD format
        instrument: Instrument/camera name
        focal_length: Telescope focal length
        naxis1: Image width in pixels
        naxis2: Image height in pixels
        filter_wheel: Filter wheel name
        observer: Observer name
        site_name: Observation site name
        
    Returns:
        Session ID in format: YYYYMMDD_HASH8
        
    Examples:
        >>> generate_session_id_with_hash(
        ...     "2024-03-15", "ASI2600MM", 530.0, 6248, 4176
        ... )
        '20240315_A7B3C2D1'
    """
    if not obs_date:
        return "UNKNOWN"
    
    # Format date without dashes
    date_str = obs_date.replace('-', '')
    
    # Build components list for hash (sorted for consistency)
    components = []
    
    # Add instrument if available
    if instrument and instrument not in ['N/A', 'None', 'ERROR']:
        components.append(f"INST:{instrument}")
    elif naxis1 and naxis2:
        # Use dimensions as fallback if no instrument name
        components.append(f"DIM:{naxis1}x{naxis2}")
    
    # Add focal length if available
    if focal_length:
        components.append(f"FL:{int(focal_length)}")
    
    # Add filter wheel if available
    if filter_wheel and filter_wheel not in ['N/A', 'None', 'ERROR']:
        components.append(f"FW:{filter_wheel}")
    
    # Add observer if available
    if observer and observer not in ['N/A', 'None', 'ERROR']:
        components.append(f"OBS:{observer}")
    
    # Add site if available
    if site_name and site_name not in ['N/A', 'None', 'ERROR']:
        components.append(f"SITE:{site_name}")
    
    # Create hash input from sorted components
    hash_input = "|".join(sorted(components))
    
    if not hash_input:
        return "UNKNOWN"
    
    # Generate MD5 hash and take first 8 characters
    full_hash = hashlib.md5(hash_input.encode()).hexdigest()
    short_hash = full_hash[:8].upper()
    
    # Combine date and hash
    session_id = f"{date_str}_{short_hash}"
    return session_id