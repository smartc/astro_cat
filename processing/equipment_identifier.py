"""
Equipment identification and normalization functions.

This module handles camera, telescope, and filter identification
and normalization based on FITS header data.
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def identify_camera_simple(x_pixels: Optional[int], y_pixels: Optional[int],
                          instrument: Optional[str], binning: int, 
                          cameras_dict: Dict) -> str:
    """
    Identify camera from pixel dimensions and instrument name.
    
    Simplified version for parallel processing that doesn't require
    access to complex objects.
    
    Args:
        x_pixels: Number of X pixels
        y_pixels: Number of Y pixels
        instrument: Instrument name from FITS header
        binning: Binning factor
        cameras_dict: Dictionary mapping camera names to camera objects
        
    Returns:
        Camera name or "UNKNOWN"
    """
    # Try to identify by pixel dimensions first
    if x_pixels:
        actual_x = x_pixels * binning
        actual_y = y_pixels * binning if y_pixels else None
        
        for camera_name, camera in cameras_dict.items():
            if camera.x == actual_x:
                if actual_y is None or camera.y == actual_y:
                    return camera_name
    
    # Try to identify by instrument name
    if instrument and instrument not in ['N/A', 'None', 'ERROR', 'UNKNOWN']:
        # Direct match
        if instrument in cameras_dict:
            return instrument
        
        # Fuzzy match
        instrument_upper = instrument.upper()
        for camera_name in cameras_dict.keys():
            if camera_name.upper() in instrument_upper or \
               instrument_upper in camera_name.upper():
                return camera_name
    
    return "UNKNOWN"


def identify_telescope_simple(focal_length: Optional[float], 
                             telescopes_dict: Dict) -> str:
    """
    Identify telescope from focal length.
    
    Simplified version for parallel processing.
    
    Args:
        focal_length: Telescope focal length in mm
        telescopes_dict: Dictionary mapping telescope names to telescope objects
        
    Returns:
        Telescope name or "UNKNOWN"
    """
    if not focal_length:
        return "UNKNOWN"
    
    # Look for exact focal length match
    for telescope_name, telescope in telescopes_dict.items():
        if telescope.focal == focal_length:
            return telescope_name
    
    return "UNKNOWN"


def normalize_filter(filter_name: str, filter_mappings: Dict[str, str]) -> str:
    """
    Normalize filter names using mappings.
    
    This handles variations in filter naming conventions (e.g., "HA-3", 
    "Ha 3nm", "Hydrogen Alpha 3nm") by mapping them to standard names.
    
    Args:
        filter_name: Raw filter name from FITS header
        filter_mappings: Dictionary mapping raw names to standard names
        
    Returns:
        Normalized filter name
    """
    if not filter_name:
        return "NONE"
    
    filter_name = filter_name.strip()
    
    # Check for exact match first
    if filter_name in filter_mappings:
        return filter_mappings[filter_name]
    
    # Check for case-insensitive match
    for raw, standard in filter_mappings.items():
        if filter_name.lower() == raw.lower():
            return standard
    
    # No mapping found, return uppercase version
    return filter_name.upper()


def calculate_field_of_view_simple(camera_name: str, telescope_name: str, 
                                  x_pixels: Optional[int], y_pixels: Optional[int], 
                                  binning: int, cameras_dict: Dict, 
                                  telescopes_dict: Dict) -> Dict[str, Optional[float]]:
    """
    Calculate field of view and pixel scale.
    
    Simplified version for parallel processing.
    
    Args:
        camera_name: Identified camera name
        telescope_name: Identified telescope name
        x_pixels: Number of X pixels
        y_pixels: Number of Y pixels
        binning: Binning factor
        cameras_dict: Dictionary of camera configurations
        telescopes_dict: Dictionary of telescope configurations
        
    Returns:
        Dictionary with fov_x, fov_y (in arcminutes), and pixel_scale (arcsec/pixel)
    """
    result = {
        'fov_x': None,
        'fov_y': None,
        'pixel_scale': None
    }
    
    # Get camera and telescope objects
    camera = cameras_dict.get(camera_name)
    telescope = telescopes_dict.get(telescope_name)
    
    if not camera or not telescope:
        return result
    
    if not (camera.pixel and telescope.focal and x_pixels and y_pixels):
        return result
    
    try:
        # Calculate effective pixel size after binning
        effective_pixel_size = camera.pixel * binning
        
        # Calculate pixel scale (arcseconds per pixel)
        # Formula: pixel_scale = (pixel_size / focal_length) * 206.265
        pixel_scale_arcsec = (effective_pixel_size / telescope.focal) * 206.265
        
        # Calculate field of view in arcminutes
        fov_x_arcmin = (pixel_scale_arcsec * x_pixels) / 60.0
        fov_y_arcmin = (pixel_scale_arcsec * y_pixels) / 60.0
        
        result = {
            'fov_x': round(fov_x_arcmin, 2),
            'fov_y': round(fov_y_arcmin, 2),
            'pixel_scale': round(pixel_scale_arcsec, 3)
        }
    except Exception as e:
        logger.error(f"Error calculating field of view: {e}")
    
    return result