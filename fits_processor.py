"""FITS file processing and metadata extraction."""

import hashlib
import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from astropy.io import fits
from astropy.time import Time
import polars as pl


logger = logging.getLogger(__name__)


class FitsProcessor:
    """FITS file processing and metadata extraction."""
    
    def __init__(self, config, cameras: List, telescopes: List, filter_mappings: Dict[str, str]):
        self.config = config
        self.cameras = {cam.camera: cam for cam in cameras}  # Use 'camera' field
        self.telescopes = {tel.scope: tel for tel in telescopes}  # Use 'scope' field
        self.filter_mappings = filter_mappings
    
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
                
                # Extract header values with fallbacks
                metadata.update({
                    'object': self._get_header_value(header, ['OBJECT', 'TARGET']),
                    'obs_date': self._parse_observation_date(header),
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
                
                # Identify camera and telescope
                metadata['camera'] = self._identify_camera(
                    metadata['x'], metadata['y'], 
                    self._get_header_value(header, ['XBINNING', 'BINNING'], int, 1)
                )
                metadata['telescope'] = self._identify_telescope(metadata['focal_length'])
                
                # Generate session ID
                metadata['session_id'] = self._generate_session_id(
                    metadata['obs_date'], metadata['camera'], metadata['telescope']
                )
                
                return metadata
                
        except Exception as e:
            logger.error(f"Error processing FITS file {filepath}: {e}")
            return None
    
    def _get_header_value(self, header, keys: List[str], 
                         value_type=str, default=None):
        """Get value from header with multiple possible key names."""
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
    
    def _parse_observation_date(self, header) -> Optional[datetime]:
        """Parse observation date from various possible formats."""
        date_keys = ['DATE-OBS', 'DATE_OBS', 'DATEOBS']
        
        for key in date_keys:
            if key in header:
                try:
                    date_str = header[key]
                    if isinstance(date_str, str):
                        # Try ISO format first
                        if 'T' in date_str:
                            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        else:
                            # Try date only
                            return datetime.strptime(date_str, '%Y-%m-%d')
                    elif hasattr(date_str, 'datetime'):
                        # Astropy Time object
                        return date_str.datetime
                except Exception as e:
                    logger.warning(f"Could not parse date {date_str}: {e}")
                    continue
        
        return None
    
    def _normalize_frame_type(self, frame_type: str) -> str:
        """Normalize frame type names."""
        if not frame_type:
            return "UNKNOWN"
        
        frame_type = frame_type.upper().strip()
        
        # Common mappings
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
    
    def _identify_camera(self, x_pixels: Optional[int], y_pixels: Optional[int], 
                        binning: int = 1) -> str:
        """Identify camera based on image dimensions."""
        if not x_pixels:
            return "UNKNOWN"
        
        # Adjust for binning
        actual_x = x_pixels * binning
        actual_y = y_pixels * binning if y_pixels else None
        
        for camera in self.cameras.values():
            if camera.x == actual_x:  # Use 'x' field
                if actual_y is None or camera.y == actual_y:  # Use 'y' field
                    return camera.camera  # Return 'camera' field
        
        return "UNKNOWN"
    
    def _identify_telescope(self, focal_length: Optional[float]) -> str:
        """Identify telescope based on focal length."""
        if not focal_length:
            return "UNKNOWN"
        
        # Find exact match first
        for telescope in self.telescopes.values():
            if abs(telescope.focal - focal_length) < 0.1:  # Use 'focal' field
                return telescope.scope  # Return 'scope' field
        
        # Find closest match within 5% tolerance
        best_match = None
        min_diff = float('inf')
        
        for telescope in self.telescopes.values():
            diff = abs(telescope.focal - focal_length)  # Use 'focal' field
            tolerance = telescope.focal * 0.05
            
            if diff < tolerance and diff < min_diff:
                min_diff = diff
                best_match = telescope.scope  # Return 'scope' field
        
        return best_match if best_match else "UNKNOWN"
    
    def _generate_session_id(self, obs_date: Optional[datetime], 
                           camera: str, telescope: str) -> str:
        """Generate a session ID for grouping related images."""
        if not obs_date:
            return "UNKNOWN"
        
        # Adjust date by 12 hours to get observation night
        session_date = obs_date - timedelta(hours=12)
        date_str = session_date.strftime('%Y%m%d')
        
        return f"{date_str}_{camera}_{telescope}"
    
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
    
    def process_files(self, filepaths: List[str]) -> pl.DataFrame:
        """Process multiple FITS files and return metadata DataFrame."""
        results = []
        failed_files = []
        
        logger.info(f"Processing {len(filepaths)} files...")
        
        for filepath in filepaths:
            try:
                metadata = self.extract_fits_metadata(filepath)
                if metadata:
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
            return df
        else:
            logger.warning("No files were successfully processed")
            return pl.DataFrame()
    
    def scan_quarantine(self) -> pl.DataFrame:
        """Scan quarantine directory for new FITS files."""
        logger.info(f"Scanning quarantine directory: {self.config.paths.quarantine_dir}")
        
        fits_files = self.find_fits_files(self.config.paths.quarantine_dir)
        
        if not fits_files:
            logger.info("No FITS files found in quarantine")
            return pl.DataFrame()
        
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