"""
Equipment identification and normalization functions.

This module handles camera, telescope, and filter identification
and normalization based on FITS header data.
"""

import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_INVALID_INSTRUMENT_VALUES = {'N/A', 'NONE', 'ERROR', 'UNKNOWN', ''}


def _clean_instrument(instrument: Optional[str]) -> Optional[str]:
    """Normalize an INSTRUME value; return None if it carries no information."""
    if not instrument:
        return None
    stripped = instrument.strip()
    if not stripped or stripped.upper() in _INVALID_INSTRUMENT_VALUES:
        return None
    return stripped


def _instrument_alias_score(instrument: Optional[str], camera) -> int:
    """
    Score how well `instrument` corroborates `camera`.

    +2 if it contains one of the camera's curated instrument_match aliases
    (a specific, high-confidence signal). +1 if it merely contains the
    camera's brand (a generic driver string with no model info). 0 otherwise.
    """
    if not instrument:
        return 0
    instrument_upper = instrument.upper()

    for alias in (camera.instrument_match or []):
        if alias and alias.upper() in instrument_upper:
            return 2

    if camera.brand and camera.brand.upper() not in ('', 'UNKNOWN') \
            and camera.brand.upper() in instrument_upper:
        return 1

    return 0


def _color_score(bayerpat: Optional[str], camera) -> int:
    """
    Score mono/color agreement from BAYERPAT vs. the camera's `rgb` flag.

    +1/-1 if BAYERPAT's presence (color) or explicit absence-marker (mono)
    agrees/disagrees with the camera's rgb flag. 0 if there's no signal
    either way (BAYERPAT simply missing from the header, or camera.rgb unset)
    -- absence of a signal is never treated as a contradiction.
    """
    if camera.rgb is None:
        return 0
    bayerpat = (bayerpat or '').strip().upper()
    if bayerpat and bayerpat != 'NONE':
        is_color = True
    elif bayerpat == 'NONE':
        is_color = False
    else:
        return 0
    return 1 if is_color == camera.rgb else -1


def _instrument_only_fallback(instrument: Optional[str], cameras_dict: Dict) -> str:
    """Fuzzy name-substring match used only when pixel dims match nothing at all."""
    if not instrument:
        return "UNKNOWN"
    if instrument in cameras_dict:
        return instrument
    instrument_upper = instrument.upper()
    for camera_name in cameras_dict:
        if camera_name.upper() in instrument_upper or instrument_upper in camera_name.upper():
            return camera_name
    return "UNKNOWN"


def identify_camera_simple(x_pixels: Optional[int], y_pixels: Optional[int],
                          instrument: Optional[str], binning: int,
                          cameras_dict: Dict, bayerpat: Optional[str] = None,
                          fingerprints: Optional[Dict[Tuple[int, int, Optional[str]], str]] = None) -> str:
    """
    Identify camera from pixel dimensions, corroborated by instrument name
    and mono/color reading.

    Pixel dimensions alone aren't enough once two cameras share a sensor
    (identical x/y/pixel) -- every candidate at those dimensions must also be
    checked against the INSTRUME string and, when available, BAYERPAT before
    being trusted. A candidate is accepted only if it uniquely corroborates:
    via a curated `instrument_match` alias or brand name on the camera, via a
    previously learned fingerprint for this exact (dims, instrument) pair, or
    (as a tiebreaker) via mono/color agreement. Anything that doesn't clear
    that bar returns "UNKNOWN" rather than guessing, so it can be resolved
    once via the review queue and remembered from then on.

    Args:
        x_pixels: Number of X pixels
        y_pixels: Number of Y pixels
        instrument: Instrument name from FITS header
        binning: Binning factor
        cameras_dict: Dictionary mapping camera names to camera objects
        bayerpat: Raw BAYERPAT header value, if present
        fingerprints: Previously learned {(x, y, instrument): camera_name}
            mappings, keyed on the exact pixel dims and INSTRUME string
            (None instrument included) resolved for that signature

    Returns:
        Camera name or "UNKNOWN"
    """
    if not x_pixels:
        return _instrument_only_fallback(_clean_instrument(instrument), cameras_dict)

    actual_x = x_pixels * binning
    actual_y = y_pixels * binning if y_pixels else None

    candidates = [
        (name, camera) for name, camera in cameras_dict.items()
        if camera.x == actual_x and (actual_y is None or camera.y == actual_y)
    ]

    if not candidates:
        return _instrument_only_fallback(_clean_instrument(instrument), cameras_dict)

    clean_instrument = _clean_instrument(instrument)
    fingerprints = fingerprints or {}
    fingerprint_key = (actual_x, actual_y, clean_instrument)
    learned_camera = fingerprints.get(fingerprint_key)

    scored = []
    for name, camera in candidates:
        score = 2 if learned_camera == name else _instrument_alias_score(clean_instrument, camera)
        score += _color_score(bayerpat, camera)
        scored.append((score, name))

    scored.sort(reverse=True)
    top_score = scored[0][0]
    tied = [name for score, name in scored if score == top_score]

    if top_score > 0 and len(tied) == 1:
        return tied[0]

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