"""FITS file processing with optimizations and multiprocessing support."""

import hashlib
import logging
import math
import os
import re
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import multiprocessing as mp

from astropy.io import fits
import polars as pl
from tqdm import tqdm

from object_processor import ObjectNameProcessor

logger = logging.getLogger(__name__)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def extract_fits_metadata_with_streaming_hash(filepath: str, cameras_dict: Dict, telescopes_dict: Dict, 
                                             filter_mappings: Dict[str, str]) -> Optional[Dict]:
    """Worker function that extracts metadata AND calculates MD5 hash in a single file read."""
    try:
        # Initialize MD5 hash
        hash_md5 = hashlib.md5()
        
        # Read entire file and calculate hash
        with open(filepath, 'rb') as f:
            file_data = f.read()
            hash_md5.update(file_data)
        
        file_md5 = hash_md5.hexdigest()
        
        # Now process FITS metadata from the file data in memory
        # Create a BytesIO object to simulate file for astropy
        from io import BytesIO
        file_like = BytesIO(file_data)
        
        with fits.open(file_like, lazy_load_hdus=True) as hdul:
            header = hdul[0].header
            
            # Extract basic metadata
            metadata = {
                'file': os.path.basename(filepath),
                'folder': os.path.dirname(filepath),
                'md5sum': file_md5,  # Hash already calculated!
            }
            
            # Parse observation timestamp with improved error handling
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
            
            # Process object name using extracted ObjectNameProcessor
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
            
            logger.debug(f"Successfully processed metadata + hash for {filepath}")
            return metadata
                
    except Exception as e:
        logger.error(f"Error processing FITS file {filepath}: {e}")
        return None



# =============================================================================
# FITS HEADER PROCESSING FUNCTIONS
# =============================================================================

def parse_observation_date(header, filepath: str = None) -> Optional[datetime]:
    """Parse observation date from various possible formats with file timestamp fallback."""
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
                                logger.warning(f"Corrupted date in {filepath or 'file'}: {date_str} (year {year})")
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
            import os
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
    """Normalize microseconds to max 6 digits for datetime parsing."""
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


def get_header_value(header, keys: List[str], value_type=str, default=None):
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


def normalize_frame_type(frame_type: str) -> str:
    """Normalize frame type names."""
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


def normalize_filter(filter_name: str, filter_mappings: Dict[str, str]) -> str:
    """Normalize filter names using mappings."""
    if not filter_name:
        return "NONE"
    
    filter_name = filter_name.strip()
    
    if filter_name in filter_mappings:
        return filter_mappings[filter_name]
    
    for raw, standard in filter_mappings.items():
        if filter_name.lower() == raw.lower():
            return standard
    
    return filter_name.upper()


def parse_coordinate(header, keys: List[str]) -> Optional[float]:
    """Parse coordinate from header, handling DMS format."""
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


# =============================================================================
# EQUIPMENT IDENTIFICATION FUNCTIONS
# =============================================================================

def identify_camera_simple(x_pixels: Optional[int], y_pixels: Optional[int],
                          instrument: Optional[str], binning: int, cameras_dict: Dict) -> str:
    """Simplified camera identification for parallel processing."""
    if x_pixels:
        actual_x = x_pixels * binning
        actual_y = y_pixels * binning if y_pixels else None
        
        for camera_name, camera in cameras_dict.items():
            if camera.x == actual_x:
                if actual_y is None or camera.y == actual_y:
                    return camera_name
    
    if instrument and instrument not in ['N/A', 'None', 'ERROR', 'UNKNOWN']:
        if instrument in cameras_dict:
            return instrument
        
        instrument_upper = instrument.upper()
        for camera_name in cameras_dict.keys():
            if camera_name.upper() in instrument_upper or instrument_upper in camera_name.upper():
                return camera_name
    
    return "UNKNOWN"


def identify_telescope_simple(focal_length: Optional[float], telescopes_dict: Dict) -> str:
    """Simplified telescope identification for parallel processing."""
    if not focal_length:
        return "UNKNOWN"
    
    for telescope_name, telescope in telescopes_dict.items():
        if telescope.focal == focal_length:
            return telescope_name
    
    return "UNKNOWN"


def calculate_field_of_view_simple(camera_name: str, telescope_name: str, 
                                  x_pixels: Optional[int], y_pixels: Optional[int], 
                                  binning: int, cameras_dict: Dict, telescopes_dict: Dict) -> Dict[str, Optional[float]]:
    """Simplified field of view calculation."""
    result = {
        'fov_x': None,
        'fov_y': None,
        'pixel_scale': None
    }
    
    camera = cameras_dict.get(camera_name)
    telescope = telescopes_dict.get(telescope_name)
    
    if not camera or not telescope:
        return result
    
    if not (camera.pixel and telescope.focal and x_pixels and y_pixels):
        return result
    
    try:
        effective_pixel_size = camera.pixel * binning
        pixel_scale_arcsec = (effective_pixel_size / telescope.focal) * 206.265
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


def generate_session_id_with_hash(obs_date: Optional[str], 
                                 instrument: str, focal_length: Optional[float],
                                 naxis1: Optional[int] = None, naxis2: Optional[int] = None,
                                 filter_wheel: Optional[str] = None,
                                 observer: Optional[str] = None,
                                 site_name: Optional[str] = None) -> str:
    """Generate session ID using rig hash approach."""
    if not obs_date:
        return "UNKNOWN"
    
    date_str = obs_date.replace('-', '')
    
    components = []
    
    if instrument and instrument not in ['N/A', 'None', 'ERROR']:
        components.append(f"INST:{instrument}")
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
    
    if not hash_input:
        return "UNKNOWN"
    
    full_hash = hashlib.md5(hash_input.encode()).hexdigest()
    short_hash = full_hash[:8].upper()
    
    session_id = f"{date_str}_{short_hash}"
    return session_id


# =============================================================================
# WORKER FUNCTION FOR PARALLEL PROCESSING
# =============================================================================

def extract_fits_metadata_worker(filepath: str, cameras_dict: Dict, telescopes_dict: Dict, 
                                filter_mappings: Dict[str, str]) -> Optional[Dict]:
    """Worker function for parallel FITS metadata extraction."""
    try:
        # Use memory mapping and lazy loading for performance
        with fits.open(filepath, memmap=True, lazy_load_hdus=True) as hdul:
            header = hdul[0].header
            
            # Extract basic metadata
            metadata = {
                'file': os.path.basename(filepath),
                'folder': os.path.dirname(filepath),
            }
            
            # Parse observation timestamp - now pass filepath for fallback
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
            
            # Process object name using extracted ObjectNameProcessor
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
            
            logger.debug(f"Successfully processed metadata for {filepath}")
            return metadata
                
    except Exception as e:
        logger.error(f"Error processing FITS file {filepath}: {e}")
        return None


# =============================================================================
# MAIN PROCESSOR CLASS
# =============================================================================

class OptimizedFitsProcessor:
    """Optimized FITS processor with multiprocessing and memory mapping."""
    
    def __init__(self, config, cameras: List, telescopes: List, filter_mappings: Dict[str, str], db_service=None):
        self.config = config
        self.cameras = {cam.camera: cam for cam in cameras}
        self.telescopes = {tel.scope: tel for tel in telescopes}
        self.filter_mappings = filter_mappings
        self.db_service = db_service
        
        # Determine optimal number of workers
        self.cpu_count = mp.cpu_count()
        self.metadata_workers = min(self.cpu_count - 2, 12)  # Leave two cores free, max 12
        self.md5_workers = min(self.cpu_count - 2, 12)       # Leave two cores free, max 12 
        
        logger.info(f"Initialized with {self.metadata_workers} metadata workers, {self.md5_workers} MD5 workers")
    
    def find_fits_files(self, directory: str) -> List[str]:
        """Find all FITS files in directory and subdirectories with progress reporting."""
        fits_files = []
        directory_path = Path(directory)
        
        if not directory_path.exists():
            logger.warning(f"Directory does not exist: {directory}")
            return fits_files
        
        logger.info(f"Scanning directory: {directory}")
        
        with tqdm(desc="Scanning for FITS files", unit="pattern") as pbar:
            for extension in self.config.file_monitoring.extensions:
                pbar.set_postfix_str(f"*{extension}")
                pattern = f"**/*{extension}"
                files = list(directory_path.glob(pattern))
                fits_files.extend([str(f) for f in files])
                pbar.update(1)
        
        # Filter out files marked as bad
        original_count = len(fits_files)
        fits_files = [f for f in fits_files if not self._is_bad_file(f)]
        bad_count = original_count - len(fits_files)
        
        if bad_count > 0:
            logger.info(f"Filtered out {bad_count} bad files")
        
        logger.info(f"Found {len(fits_files)} FITS files in {directory}")
        return sorted(fits_files)
    
    def _is_bad_file(self, filepath: str) -> bool:
        """Check if file is marked as bad."""
        filename = os.path.basename(filepath)
        bad_markers = ['BAD_', 'CORRUPT_', 'ERROR_']
        return any(marker in filename.upper() for marker in bad_markers)
    
    def process_files_optimized(self, filepaths: List[str]) -> Tuple[pl.DataFrame, List[dict]]:
        """Process multiple FITS files with streaming optimization (metadata + MD5 in one pass)."""
        results = []
        failed_files = []
        sessions = {}
        
        logger.info(f"Processing {len(filepaths)} files with streaming optimization...")
        
        # Single phase: Extract metadata AND calculate MD5 in one pass
        with tqdm(total=len(filepaths), desc="Processing files (streaming)", unit="files") as pbar:
            
            # Create worker function with bound parameters
            worker_func = partial(
                extract_fits_metadata_with_streaming_hash,  # Use new streaming function
                cameras_dict=self.cameras,
                telescopes_dict=self.telescopes,
                filter_mappings=self.filter_mappings
            )
            
            # Process in parallel with ProcessPoolExecutor
            with ProcessPoolExecutor(max_workers=self.metadata_workers) as executor:
                future_to_file = {
                    executor.submit(worker_func, filepath): filepath 
                    for filepath in filepaths
                }
                
                for future in as_completed(future_to_file):
                    filepath = future_to_file[future]
                    try:
                        metadata = future.result()
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
                    
                    pbar.update(1)
                    
                    # Update progress info every 50 files
                    if len(results) % 50 == 0:
                        pbar.set_postfix({
                            'success': len(results),
                            'failed': len(failed_files),
                            'sessions': len(sessions)
                        })
        
        # No separate MD5 phase needed - it's already done!
        
        if failed_files:
            logger.warning(f"Failed to process {len(failed_files)} files")
        
        if results:
            # Create DataFrame with improved schema handling
            try:
                df = pl.DataFrame(results, infer_schema_length=None)
            except Exception as e:
                logger.warning(f"Schema inference failed, using fallback method: {e}")
                try:
                    df = pl.DataFrame(results, infer_schema_length=min(len(results), 1000))
                except Exception as e2:
                    logger.warning(f"Extended schema inference failed, forcing string types: {e2}")
                    df = pl.DataFrame(results, infer_schema_length=10)
                    
                    for col in df.columns:
                        if df[col].dtype == pl.Object:
                            try:
                                df = df.with_columns(pl.col(col).cast(pl.Utf8))
                            except:
                                pass
            
            logger.info(f"Successfully processed {len(results)} files with streaming optimization")
            logger.info(f"Found {len(sessions)} unique sessions")
            return df, list(sessions.values())
        else:
            logger.warning("No files were successfully processed")
            return pl.DataFrame(), []
    
    def scan_quarantine(self) -> Tuple[pl.DataFrame, List[dict]]:
        """Scan quarantine directory for new FITS files with optimization."""
        logger.info(f"Scanning quarantine directory: {self.config.paths.quarantine_dir}")
        
        fits_files = self.find_fits_files(self.config.paths.quarantine_dir)
        
        if not fits_files:
            logger.info("No FITS files found in quarantine")
            return pl.DataFrame(), []
        
        return self.process_files_optimized(fits_files)