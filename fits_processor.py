"""FITS file processing and metadata extraction with hash-based session IDs."""

import hashlib
import os
import logging
import re
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from astropy.io import fits
from astropy.time import Time
import polars as pl


logger = logging.getLogger(__name__)

class ObjectNameProcessor:
    """Simplified object name processor for integration."""
    
    def __init__(self):
        self.catalog_patterns = {
            'NGC': [r'ngc[-\s]*(\d+)', r'n[-\s]*(\d+)'],
            'IC': [r'ic[-\s]*(\d+)', r'i[-\s]*(\d+)'],
            'M': [r'm[-\s]*(\d+)', r'messier[-\s]*(\d+)'],
            'SH2': [r'sh\s*2\s*(\d+)', r'sharpless[-\s]*(\d+)'],
            'Abell': [r'abell[-\s]*(\d+)', r'a[-\s]*(\d+)', r'aco[-\s]*(\d+)'],
            'C': [r'c[-\s]*(\d+)', r'caldwell[-\s]*(\d+)'],
            'B': [r'b[-\s]*(\d+)', r'barnard[-\s]*(\d+)'],
            'LDN': [r'ldn[-\s]*(\d+)', r'lynds\s+dark[-\s]*(\d+)'],
            'LBN': [r'lbn[-\s]*(\d+)', r'lynds\s+bright[-\s]*(\d+)'],
            'VdB': [r'vdb[-\s]*(\d+)', r'van\s+den\s+bergh[-\s]*(\d+)'],
            'Arp': [r'arp[-\s]*(\d+)'],
            'RCW': [r'rcw[-\s]*(\d+)'],
            'Gum': [r'gum[-\s]*(\d+)'],
            'PK': [r'pk[-\s]*(\d+[-+]\d+\.\d+)', r'perek[-\s]*kohoutek[-\s]*(\d+[-+]\d+\.\d+)'],
            'Ced': [r'ced[-\s]*(\d+)', r'cederblad[-\s]*(\d+)'],
            'Stock': [r'stock[-\s]*(\d+)', r'st[-\s]*(\d+)'],
            'Collinder': [r'collinder[-\s]*(\d+)', r'cr[-\s]*(\d+)', r'col[-\s]*(\d+)'],
            'Melotte': [r'melotte[-\s]*(\d+)', r'mel[-\s]*(\d+)'],
            'Trumpler': [r'trumpler[-\s]*(\d+)', r'tr[-\s]*(\d+)'],
            'PGC': [r'pgc[-\s]*(\d+)'],
            'UGC': [r'ugc[-\s]*(\d+)'],
            'ESO': [r'eso[-\s]*(\d+[-]\d+)'],
            'IRAS': [r'iras[-\s]*(\d{5}[+-]\d{4})'],
        }
    
    def normalize_input(self, name: str) -> str:
        if not name or name in ['nan', 'None', '', 'null']:
            return ""
        name = str(name).lower().strip()
        name = re.sub(r'(flat\s+frame.*|save\s+to\s+disk|test\s+image)', '', name)
        name = re.sub(r'[_\-\s]+', ' ', name).strip()
        name = re.sub(r'[^\w\s\-\+]', ' ', name)
        return name
    
    def extract_catalog_object(self, name: str) -> Optional[str]:
        normalized = self.normalize_input(name)
        for catalog, patterns in self.catalog_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, normalized, re.IGNORECASE)
                if match:
                    number = match.group(1)
                    # Special handling for SH2 to ensure proper formatting
                    if catalog == 'SH2':
                        return f"SH2-{number}"
                    return f"{catalog}{number}"
        return None
    
    def process_object_name(self, raw_name: str, frame_type: str = "LIGHT") -> str:
        if not raw_name or raw_name in ['nan', 'None', '', 'null']:
            return None
        
        if frame_type.upper() in ['FLAT', 'DARK', 'BIAS']:
            return 'CALIBRATION'
        
        catalog_obj = self.extract_catalog_object(raw_name)
        if catalog_obj:
            return catalog_obj
        
        cleaned = self.normalize_input(raw_name)
        if cleaned and cleaned not in ['', 'unknown', 'test']:
            return cleaned.title()
        
        return None


class FitsProcessor:
    """FITS file processing and metadata extraction."""
    
    def __init__(self, config, cameras: List, telescopes: List, filter_mappings: Dict[str, str], db_service=None):
        self.config = config
        self.cameras = {cam.camera: cam for cam in cameras}
        self.telescopes = {tel.scope: tel for tel in telescopes}
        self.filter_mappings = filter_mappings
        self.object_processor = ObjectNameProcessor()
        self.db_service = db_service
    
    def get_file_md5(self, filepath: str) -> str:
        """Calculate MD5 hash of file."""
        hash_md5 = hashlib.md5()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating MD5 for {filepath}: {e}")
            return ""
    
    def extract_fits_metadata(self, filepath: str) -> Optional[Dict]:
        """Extract metadata from a FITS file."""
        try:
            with fits.open(filepath) as hdul:
                header = hdul[0].header
                
                # Extract basic metadata
                metadata = {
                    'file': os.path.basename(filepath),
                    'folder': os.path.dirname(filepath),
                    'md5sum': self.get_file_md5(filepath),
                }
                
                # Parse observation timestamp
                obs_timestamp = self._parse_observation_date(header)
                
                # Calculate observation date (shifted by 12 hours)
                if obs_timestamp:
                    shifted_time = obs_timestamp - timedelta(hours=12)
                    obs_date = shifted_time.strftime('%Y-%m-%d')
                    obs_timestamp_truncated = obs_timestamp.replace(second=0, microsecond=0)
                else:
                    obs_date = None
                    obs_timestamp_truncated = None
                
                # Extract header values with fallbacks
                raw_object = self._get_header_value(header, ['OBJECT', 'TARGET'])
                
                metadata.update({
                    'obs_date': obs_date,
                    'obs_timestamp': obs_timestamp_truncated,
                    'ra': self._get_header_value(header, ['RA', 'OBJCTRA', 'CRVAL1']),
                    'dec': self._get_header_value(header, ['DEC', 'OBJCTDEC', 'CRVAL2']),
                    'x': self._get_header_value(header, ['NAXIS1'], int),
                    'y': self._get_header_value(header, ['NAXIS2'], int),
                    'frame_type': self._normalize_frame_type(
                        self._get_header_value(header, ['IMAGETYP', 'FRAME'])
                    ),
                    'filter': self._normalize_filter(
                        self._get_header_value(header, ['FILTER', 'FILTERS'])
                    ),
                    'focal_length': self._get_header_value(header, ['FOCALLEN'], float),
                    'exposure': self._get_header_value(header, ['EXPOSURE', 'EXPTIME'], float),
                })
                
                # Process object name
                frame_type = metadata['frame_type']
                processed_object = self._process_object_name_with_fallback(
                    raw_object, frame_type, metadata['file']
                )
                metadata['object'] = processed_object
                
                # Extract location data
                metadata.update({
                    'latitude': self._parse_coordinate(header, ['SITELAT', 'LAT-OBS', 'LATITUDE']),
                    'longitude': self._parse_coordinate(header, ['SITELONG', 'LONG-OBS', 'LONGITUDE']),
                    'elevation': self._get_header_value(header, ['SITEELEV', 'ALT-OBS', 'ELEVATION'], float),
                })
                
                # Extract additional headers for session ID generation (don't add to metadata)
                instrument = self._get_header_value(header, ['INSTRUME'])
                filter_wheel = self._get_header_value(header, ['FWHEEL'])
                observer = self._get_header_value(header, ['OBSERVER'])
                site_name = self._get_header_value(header, ['SITENAME'])
                binning = self._get_header_value(header, ['XBINNING', 'BINNING'], int, 1)
                
                # Identify camera and telescope
                metadata['camera'] = self._identify_camera_enhanced(
                    metadata['x'], metadata['y'], instrument, binning
                )
                metadata['telescope'] = self._identify_telescope(metadata['focal_length'])
                
                # Calculate field of view and pixel scale
                fov_data = self._calculate_field_of_view(
                    metadata['camera'], metadata['telescope'], 
                    metadata['x'], metadata['y'], binning
                )
                metadata.update(fov_data)
                
                # Generate session ID using extra fields (no binning)
                metadata['session_id'] = self._generate_session_id_with_hash(
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
                
                logger.debug(f"Successfully processed metadata for {filepath}")
                return metadata
                
        except Exception as e:
            logger.error(f"Error processing FITS file {filepath}: {e}")
            return None

    def _calculate_field_of_view(self, camera_name: str, telescope_name: str, 
                                x_pixels: Optional[int], y_pixels: Optional[int], 
                                binning: int = 1) -> Dict[str, Optional[float]]:
        """Calculate field of view and pixel scale."""
        result = {
            'fov_x': None,
            'fov_y': None,
            'pixel_scale': None
        }
        
        # Get camera and telescope objects
        camera = self.cameras.get(camera_name)
        telescope = self.telescopes.get(telescope_name)
        
        if not camera or not telescope:
            logger.debug(f"Cannot calculate FOV: camera={camera_name}, telescope={telescope_name}")
            return result
        
        # Check if we have required parameters
        if not (camera.pixel and telescope.focal and x_pixels and y_pixels):
            logger.debug("Missing required parameters for FOV calculation")
            return result
        
        try:
            # Adjust pixel size for binning
            effective_pixel_size = camera.pixel * binning
            
            # Calculate pixel scale in arcseconds per pixel
            # Formula: pixel_scale = (pixel_size_microns / focal_length_mm) * 206.265
            pixel_scale_arcsec = (effective_pixel_size / telescope.focal) * 206.265
            
            # Calculate field of view in arcminutes
            fov_x_arcmin = (pixel_scale_arcsec * x_pixels) / 60.0
            fov_y_arcmin = (pixel_scale_arcsec * y_pixels) / 60.0
            
            result = {
                'fov_x': round(fov_x_arcmin, 2),
                'fov_y': round(fov_y_arcmin, 2),
                'pixel_scale': round(pixel_scale_arcsec, 3)
            }
            
            logger.debug(f"Calculated FOV: {fov_x_arcmin:.2f}' x {fov_y_arcmin:.2f}', "
                        f"pixel scale: {pixel_scale_arcsec:.3f}\"/px")
            
        except Exception as e:
            logger.error(f"Error calculating field of view: {e}")
        
        return result

    def _process_object_name_with_fallback(self, raw_object: str, frame_type: str, filename: str) -> str:
        """Process object name with fallback and failure logging."""
        if not raw_object:
            return None
            
        try:
            # Try to process with object name processor
            processed = self.object_processor.process_object_name(raw_object, frame_type)
            if processed:
                logger.debug(f"Successfully processed object name: '{raw_object}' -> '{processed}'")
                return processed
            else:
                # Processing returned None/empty, use raw name
                logger.debug(f"Object processing returned None for '{raw_object}', using raw name")
                return raw_object
                
        except Exception as e:
            # Log failure to database if service available
            if self.db_service:
                try:
                    self.db_service.log_object_processing_failure(
                        filename=filename,
                        raw_name=raw_object,
                        proposed_name=None,
                        error=str(e)
                    )
                except Exception as log_error:
                    logger.error(f"Failed to log object processing failure: {log_error}")
            
            logger.warning(f"Object name processing failed for '{raw_object}' in {filename}: {e}")
            return raw_object  # Fall back to raw name

    def _parse_coordinate(self, header, keys: List[str]) -> Optional[float]:
        """Parse coordinate from header, handling DMS format."""
        for key in keys:
            if key in header:
                try:
                    value = header[key]
                    logger.debug(f"Found coordinate key '{key}' with value: {value}")
                    
                    if isinstance(value, (int, float)):
                        # Already decimal degrees
                        return float(value)
                    
                    if isinstance(value, str):
                        # Parse DMS format: "50 41 57.800" or "-114 0 20.500"
                        value = value.strip()
                        
                        # Handle negative sign
                        negative = value.startswith('-')
                        if negative:
                            value = value[1:]
                        
                        # Split degrees, minutes, seconds
                        parts = value.split()
                        if len(parts) >= 3:
                            degrees = float(parts[0])
                            minutes = float(parts[1])
                            seconds = float(parts[2])
                            
                            # Convert to decimal degrees
                            decimal = degrees + minutes/60.0 + seconds/3600.0
                            if negative:
                                decimal = -decimal
                                
                            logger.debug(f"Parsed coordinate: {value} -> {decimal}")
                            return decimal
                        
                        # Try direct float conversion as fallback
                        return float(value)
                        
                except (ValueError, TypeError, IndexError) as e:
                    logger.debug(f"Failed to parse coordinate '{key}' value '{value}': {e}")
                    continue
        
        logger.debug(f"No coordinate found for keys: {keys}")
        return None

    def _get_header_value(self, header, keys: List[str], 
                         value_type=str, default=None):
        """Get value from header with multiple possible key names."""
        for key in keys:
            if key in header:
                try:
                    value = header[key]
                    logger.debug(f"Found header key '{key}' with value: {value}")
                    if value_type and value is not None:
                        converted = value_type(value)
                        logger.debug(f"Converted to {value_type.__name__}: {converted}")
                        return converted
                    return value
                except (ValueError, TypeError) as e:
                    logger.debug(f"Failed to convert header key '{key}' value '{value}' to {value_type.__name__}: {e}")
                    continue
        logger.debug(f"No header keys found from {keys}, returning default: {default}")
        return default
    
    def _parse_observation_date(self, header) -> Optional[datetime]:
        """Parse observation date from various possible formats."""
        date_keys = ['DATE-OBS', 'DATE_OBS', 'DATEOBS']
        
        logger.debug(f"Looking for date keys: {date_keys}")
        
        for key in date_keys:
            if key in header:
                try:
                    date_str = header[key]
                    logger.debug(f"Found date key '{key}' with value: {date_str}")
                    if isinstance(date_str, str):
                        # Try ISO format first
                        if 'T' in date_str:
                            # Handle microseconds with more than 6 digits
                            date_str = self._normalize_microseconds(date_str)
                            result = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            logger.debug(f"Parsed date: {result}")
                            return result
                        else:
                            # Try date only
                            result = datetime.strptime(date_str, '%Y-%m-%d')
                            logger.debug(f"Parsed date (date only): {result}")
                            return result
                    elif hasattr(date_str, 'datetime'):
                        # Astropy Time object
                        result = date_str.datetime
                        logger.debug(f"Extracted from astropy Time: {result}")
                        return result
                except Exception as e:
                    logger.warning(f"Could not parse date {date_str}: {e}")
                    continue
        
        logger.debug("No date headers found")
        return None
    
    def _normalize_microseconds(self, timestamp_str: str) -> str:
        """Normalize microseconds to max 6 digits for datetime parsing."""
        # Pattern to match timestamp with microseconds
        pattern = r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\.(\d+)'
        match = re.match(pattern, timestamp_str)
        
        if match:
            base_time = match.group(1)
            microseconds = match.group(2)
            
            # Truncate or pad microseconds to 6 digits
            if len(microseconds) > 6:
                microseconds = microseconds[:6]
            elif len(microseconds) < 6:
                microseconds = microseconds.ljust(6, '0')
            
            return f"{base_time}.{microseconds}"
        
        return timestamp_str
    
    def _normalize_frame_type(self, frame_type: str) -> str:
        """Normalize frame type names."""
        if not frame_type:
            return "UNKNOWN"
        
        frame_type = frame_type.upper().strip()
        
        # Standard FITS frame type mappings - these are FITS standard, not user-specific
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
    
    def _normalize_filter(self, filter_name: str) -> str:
        """Normalize filter names using mappings."""
        if not filter_name:
            return "NONE"
        
        filter_name = filter_name.strip()
        
        # Check direct mappings first
        if filter_name in self.filter_mappings:
            return self.filter_mappings[filter_name]
        
        # Check case-insensitive mappings
        for raw, standard in self.filter_mappings.items():
            if filter_name.lower() == raw.lower():
                return standard
        
        # Return original if no mapping found
        return filter_name.upper()
    
    def _identify_camera_enhanced(self, x_pixels: Optional[int], y_pixels: Optional[int], 
                             instrument: Optional[str], binning: int = 1) -> str:
        """Enhanced camera identification - dimension-based with INSTRUME as fallback."""
        logger.debug(f"Identifying camera: dimensions={x_pixels}x{y_pixels}, instrument='{instrument}', binning={binning}")
        
        # PRIMARY: Try dimension-based identification first (most reliable)
        if x_pixels:
            # Adjust for binning
            actual_x = x_pixels * binning
            actual_y = y_pixels * binning if y_pixels else None
            
            logger.debug(f"Looking for camera with dimensions {actual_x}x{actual_y}")
            
            # Check against config cameras
            for camera in self.cameras.values():
                logger.debug(f"Checking camera {camera.camera}: {camera.x}x{camera.y}")
                if camera.x == actual_x:
                    if actual_y is None or camera.y == actual_y:
                        logger.debug(f"Matched camera by dimensions: {camera.camera}")
                        return camera.camera
        
        # FALLBACK: Try to match INSTRUME header directly to camera names
        if instrument and instrument not in ['N/A', 'None', 'ERROR', 'UNKNOWN']:
            # Try exact match first
            if instrument in self.cameras:
                logger.debug(f"Exact INSTRUME match: {instrument}")
                return instrument
            
            # Try partial matches (case insensitive)
            instrument_upper = instrument.upper()
            for camera_name in self.cameras.keys():
                if camera_name.upper() in instrument_upper or instrument_upper in camera_name.upper():
                    logger.debug(f"Partial INSTRUME match: {camera_name}")
                    return camera_name
        
        # Camera not found - prompt user
        logger.warning(f"Camera not found for dimensions {x_pixels}x{y_pixels}, instrument '{instrument}'")
        return self._handle_unknown_camera(x_pixels or 0, y_pixels)
    
    def _generate_rig_hash(self, instrument: Optional[str], focal_length: Optional[float],
                      filter_wheel: Optional[str], observer: Optional[str], 
                      site_name: Optional[str], naxis1: Optional[int], 
                      naxis2: Optional[int]) -> str:
        """Generate hash using RAW uncleaned values for maximum uniqueness."""
        components = []
        
        # Use RAW instrument name (don't clean it)
        if instrument and instrument not in ['N/A', 'None', 'ERROR']:
            components.append(f"INST:{instrument}")  # Raw value
        elif naxis1 and naxis2:
            components.append(f"DIM:{naxis1}x{naxis2}")
        
        if focal_length:
            components.append(f"FL:{int(focal_length)}")
        
        if filter_wheel and filter_wheel not in ['N/A', 'None', 'ERROR']:
            components.append(f"FW:{filter_wheel}")
        
        if observer and observer not in ['N/A', 'None', 'ERROR']:
            components.append(f"OBS:{observer}")
        
        if site_name and site_name not in ['N/A', 'None', 'ERROR']:
            components.append(f"SITE:{site_name}")
        
        hash_input = "|".join(sorted(components))
        logger.debug(f"Rig hash input: {hash_input}")
        
        if not hash_input:
            logger.warning("No identifying components found for rig hash")
            return "UNKNOWN"
        
        full_hash = hashlib.md5(hash_input.encode()).hexdigest()
        short_hash = full_hash[:8].upper()
        
        logger.debug(f"Generated rig hash: {short_hash}")
        return short_hash
        
    def _generate_session_id_with_hash(self, obs_date: Optional[str], 
                                      instrument: str, focal_length: Optional[float],
                                      naxis1: Optional[int] = None, naxis2: Optional[int] = None,
                                      filter_wheel: Optional[str] = None,
                                      observer: Optional[str] = None,
                                      site_name: Optional[str] = None) -> str:
        """
        Generate session ID using rig hash approach.
        
        Format: {night_date}_{rig_hash}
        Example: 20250824_A1B2C3D4
        """
        if not obs_date:
            logger.debug("No observation date for session ID")
            return "UNKNOWN"
        
        # Get night date (already shifted by 12 hours in obs_date)
        date_str = obs_date.replace('-', '')  # YYYYMMDD
        
        # Generate rig hash from multiple identifying fields
        rig_hash = self._generate_rig_hash(
            instrument, focal_length, filter_wheel, 
            observer, site_name, naxis1, naxis2
        )
        
        # Session ID format: date_righash
        session_id = f"{date_str}_{rig_hash}"
        
        logger.debug(f"Generated hash-based session ID: {session_id}")
        return session_id

    def _identify_telescope(self, focal_length: Optional[float]) -> str:
        """Identify telescope based on EXACT focal length match."""
        if not focal_length:
            logger.debug("No focal length provided")
            return "UNKNOWN"
        
        logger.debug(f"Looking for telescope with EXACT focal length {focal_length}mm")
        
        # EXACT match only - no tolerance
        for telescope in self.telescopes.values():
            logger.debug(f"Checking telescope {telescope.scope}: {telescope.focal}mm")
            if telescope.focal == focal_length:  # Exact match only
                logger.debug(f"Exact match found: {telescope.scope}")
                return telescope.scope
        
        # No exact match found
        logger.warning(f"No exact telescope match found for focal length {focal_length}mm")
        return self._handle_unknown_telescope(focal_length)
    
    def _handle_unknown_camera(self, x_pixels: int, y_pixels: Optional[int]) -> str:
        """Handle unknown camera by prompting user for action."""
        print(f"\nUnknown camera detected: {x_pixels}x{y_pixels or '?'} pixels")
        print("Existing cameras:")
        for i, camera in enumerate(self.cameras.values(), 1):
            print(f"  {i}. {camera.camera}: {camera.x}x{camera.y} ({camera.brand} {camera.type})")
        
        print("\nOptions:")
        print("1. Add new camera")
        print("2. Map to existing camera") 
        print("3. Skip (mark as UNKNOWN)")
        
        while True:
            choice = input("Choose option (1-3): ").strip()
            
            if choice == "1":
                return self._add_new_camera(x_pixels, y_pixels)
            elif choice == "2":
                return self._map_to_existing_camera()
            elif choice == "3":
                return "UNKNOWN"
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")
    
    def _add_new_camera(self, x_pixels: int, y_pixels: Optional[int]) -> str:
        """Add a new camera to the configuration."""
        print("\nAdding new camera:")
        name = input("Camera name: ").strip()
        brand = input("Brand: ").strip() or "Unknown"
        cam_type = input("Type (CMOS/CCD): ").strip() or "CMOS"
        pixel_size = input("Pixel size (microns): ").strip()
        
        try:
            pixel_size = float(pixel_size) if pixel_size else 4.0
        except ValueError:
            pixel_size = 4.0
        
        new_camera = {
            "camera": name,
            "bin": 1,
            "x": x_pixels,
            "y": y_pixels or 0,
            "type": cam_type,
            "brand": brand,
            "pixel": pixel_size,
            "comments": "Auto-added during processing"
        }
        
        # Save to cameras.json
        self._save_new_camera(new_camera)
        
        # Add to current session
        from config import Camera
        camera_obj = Camera(**new_camera)
        self.cameras[name] = camera_obj
        
        print(f"Added camera: {name}")
        return name
    
    def _map_to_existing_camera(self) -> str:
        """Map to an existing camera."""
        cameras_list = list(self.cameras.values())
        while True:
            try:
                choice = int(input(f"Select camera (1-{len(cameras_list)}): ")) - 1
                if 0 <= choice < len(cameras_list):
                    return cameras_list[choice].camera
                else:
                    print(f"Please enter a number between 1 and {len(cameras_list)}")
            except ValueError:
                print("Please enter a valid number")
    
    def _save_new_camera(self, camera_data: dict):
        """Save new camera to cameras.json file."""
        import json
        from pathlib import Path
        
        cameras_file = Path("cameras.json")
        if cameras_file.exists():
            with open(cameras_file, 'r') as f:
                cameras = json.load(f)
        else:
            cameras = []
        
        cameras.append(camera_data)
        
        with open(cameras_file, 'w') as f:
            json.dump(cameras, f, indent=2)
    
    def _handle_unknown_telescope(self, focal_length: float) -> str:
        """Handle unknown telescope by prompting user for action."""
        print(f"\nUnknown telescope detected: {focal_length}mm focal length")
        print("Existing telescopes:")
        for i, telescope in enumerate(self.telescopes.values(), 1):
            print(f"  {i}. {telescope.scope}: {telescope.focal}mm ({telescope.make} {telescope.type})")
        
        print("\nOptions:")
        print("1. Add new telescope")
        print("2. Map to existing telescope")
        print("3. Skip (mark as UNKNOWN)")
        
        while True:
            choice = input("Choose option (1-3): ").strip()
            
            if choice == "1":
                return self._add_new_telescope(focal_length)
            elif choice == "2":
                return self._map_to_existing_telescope()
            elif choice == "3":
                return "UNKNOWN"
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")
    
    def _add_new_telescope(self, focal_length: float) -> str:
        """Add a new telescope to the configuration."""
        print("\nAdding new telescope:")
        name = input("Telescope name: ").strip()
        make = input("Manufacturer: ").strip() or "Unknown"
        tel_type = input("Type (Refractor/Reflector/Lens): ").strip() or "Unknown"
        
        new_telescope = {
            "scope": name,
            "focal": int(focal_length),
            "make": make,
            "type": tel_type,
            "comments": "Auto-added during processing"
        }
        
        # Save to telescopes.json
        self._save_new_telescope(new_telescope)
        
        # Add to current session
        from config import Telescope
        telescope_obj = Telescope(**new_telescope)
        self.telescopes[name] = telescope_obj
        
        print(f"Added telescope: {name}")
        return name
    
    def _map_to_existing_telescope(self) -> str:
        """Map to an existing telescope."""
        telescopes_list = list(self.telescopes.values())
        while True:
            try:
                choice = int(input(f"Select telescope (1-{len(telescopes_list)}): ")) - 1
                if 0 <= choice < len(telescopes_list):
                    return telescopes_list[choice].scope
                else:
                    print(f"Please enter a number between 1 and {len(telescopes_list)}")
            except ValueError:
                print("Please enter a valid number")
    
    def _save_new_telescope(self, telescope_data: dict):
        """Save new telescope to telescopes.json file."""
        import json
        from pathlib import Path
        
        telescopes_file = Path("telescopes.json")
        if telescopes_file.exists():
            with open(telescopes_file, 'r') as f:
                telescopes = json.load(f)
        else:
            telescopes = []
        
        telescopes.append(telescope_data)
        
        with open(telescopes_file, 'w') as f:
            json.dump(telescopes, f, indent=2)
    
    def find_fits_files(self, directory: str) -> List[str]:
        """Find all FITS files in directory and subdirectories."""
        fits_files = []
        directory_path = Path(directory)
        
        if not directory_path.exists():
            logger.warning(f"Directory does not exist: {directory}")
            return fits_files
        
        for extension in self.config.file_monitoring.extensions:
            pattern = f"**/*{extension}"
            files = list(directory_path.glob(pattern))
            fits_files.extend([str(f) for f in files])
        
        # Filter out files marked as bad
        fits_files = [f for f in fits_files if not self._is_bad_file(f)]
        
        logger.info(f"Found {len(fits_files)} FITS files in {directory}")
        return sorted(fits_files)
    
    def _is_bad_file(self, filepath: str) -> bool:
        """Check if file is marked as bad."""
        filename = os.path.basename(filepath)
        bad_markers = ['BAD_', 'CORRUPT_', 'ERROR_']
        return any(marker in filename.upper() for marker in bad_markers)
    
    def process_files(self, filepaths: List[str]) -> Tuple[pl.DataFrame, List[dict]]:
        """Process multiple FITS files and return metadata DataFrame and session data."""
        results = []
        failed_files = []
        sessions = {}
        
        logger.info(f"Processing {len(filepaths)} files...")
        
        for filepath in filepaths:
            try:
                metadata = self.extract_fits_metadata(filepath)
                if metadata:
                    # Extract session data
                    session_data = metadata.pop('_session_data', None)
                    if session_data and session_data['session_id'] != 'UNKNOWN':
                        sessions[session_data['session_id']] = session_data
                    
                    results.append(metadata)
                else:
                    failed_files.append(filepath)
            except Exception as e:
                logger.error(f"Failed to process {filepath}: {e}")
                failed_files.append(filepath)
        
        if failed_files:
            logger.warning(f"Failed to process {len(failed_files)} files")
        
        if results:
            df = pl.DataFrame(results)
            logger.info(f"Successfully processed {len(results)} files")
            logger.info(f"Found {len(sessions)} unique sessions")
            return df, list(sessions.values())
        else:
            logger.warning("No files were successfully processed")
            return pl.DataFrame(), []
    
    def scan_quarantine(self) -> Tuple[pl.DataFrame, List[dict]]:
        """Scan quarantine directory for new FITS files."""
        logger.info(f"Scanning quarantine directory: {self.config.paths.quarantine_dir}")
        
        fits_files = self.find_fits_files(self.config.paths.quarantine_dir)
        
        if not fits_files:
            logger.info("No FITS files found in quarantine")
            return pl.DataFrame(), []
        
        return self.process_files(fits_files)


def calculate_image_scale(camera, telescope) -> Tuple[float, float]:
    """Calculate image scale in arcseconds per pixel."""
    if not camera.pixel or not telescope.focal:
        return 0.0, 0.0
    
    # Formula: pixel_scale = (pixel_size / focal_length) * 206265
    pixel_scale = (camera.pixel / telescope.focal) * 206.265
    
    x_scale = pixel_scale * camera.x / 60  # arcminutes
    y_scale = pixel_scale * camera.y / 60  # arcminutes
    
    return x_scale, y_scale