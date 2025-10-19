"""
Metadata extraction for processed astrophotography files.

Handles JPG, XISF, XOSM (with .data folders), and PXIPROJECT files.
"""

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    from PIL import Image
    # Disable decompression bomb warning for large astrophotography images
    Image.MAX_IMAGE_PIXELS = None
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("PIL/Pillow not available - JPG metadata will be limited")

try:
    from xisf import XISF
    XISF_AVAILABLE = True
except ImportError:
    XISF_AVAILABLE = False
    logger.info("xisf library not available - XISF metadata will be limited")


def calculate_md5(filepath: Path, chunk_size: int = 8192) -> str:
    """
    Calculate MD5 hash of a file.
    
    Args:
        filepath: Path to file
        chunk_size: Size of chunks to read
        
    Returns:
        MD5 hash as hex string
    """
    md5 = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(chunk_size), b''):
            md5.update(chunk)
    return md5.hexdigest()


def get_directory_size(path: Path) -> int:
    """
    Calculate total size of a directory recursively.
    
    Args:
        path: Directory path
        
    Returns:
        Total size in bytes
    """
    total = 0
    try:
        for entry in path.rglob('*'):
            if entry.is_file():
                total += entry.stat().st_size
    except Exception as e:
        logger.error(f"Error calculating directory size for {path}: {e}")
    return total


def extract_jpg_metadata(filepath: Path) -> Dict:
    """
    Extract metadata from JPG/JPEG files.
    
    Args:
        filepath: Path to JPG file
        
    Returns:
        Dictionary containing image metadata
    """
    metadata = {
        'image_width': None,
        'image_height': None,
        'bit_depth': None,
        'color_space': None,
        'metadata_json': {}
    }
    
    if not PIL_AVAILABLE:
        logger.warning(f"Cannot extract JPG metadata - PIL not available: {filepath}")
        return metadata
    
    try:
        with Image.open(filepath) as img:
            metadata['image_width'] = img.width
            metadata['image_height'] = img.height
            metadata['color_space'] = img.mode
            
            # Bit depth - approximate from mode
            if img.mode in ['1', 'L', 'P']:
                metadata['bit_depth'] = 8
            elif img.mode in ['RGB', 'YCbCr', 'LAB', 'HSV']:
                metadata['bit_depth'] = 24
            elif img.mode in ['RGBA', 'CMYK', 'I', 'F']:
                metadata['bit_depth'] = 32
            
            # Extract EXIF if present
            exif_data = {}
            if hasattr(img, '_getexif') and img._getexif():
                exif = img._getexif()
                # Store relevant EXIF tags
                exif_data['exif_present'] = True
                # Add more specific EXIF extraction if needed
            
            metadata['metadata_json'] = exif_data
            
    except Exception as e:
        logger.error(f"Error extracting JPG metadata from {filepath}: {e}")
    
    return metadata


def extract_xisf_metadata(filepath: Path) -> Dict:
    """
    Extract metadata from XISF files.
    
    Args:
        filepath: Path to XISF file
        
    Returns:
        Dictionary containing image metadata
    """
    metadata = {
        'image_width': None,
        'image_height': None,
        'bit_depth': None,
        'color_space': None,
        'metadata_json': {}
    }
    
    if not XISF_AVAILABLE:
        logger.info(f"xisf library not available - limited metadata for: {filepath}")
        return metadata
    
    try:
        xisf_file = XISF(str(filepath))
        
        # Get image metadata
        im_metadata = xisf_file.get_images_metadata()
        if im_metadata:
            first_image = im_metadata[0]
            
            # Geometry - handle both string "width:height:channels" and tuple (width, height, channels)
            geometry = first_image.get('geometry', '')
            if geometry:
                if isinstance(geometry, str):
                    # Format is "width:height:channels"
                    parts = geometry.split(':')
                    if len(parts) >= 2:
                        metadata['image_width'] = int(parts[0])
                        metadata['image_height'] = int(parts[1])
                elif isinstance(geometry, (tuple, list)):
                    # Format is (width, height, channels)
                    if len(geometry) >= 2:
                        metadata['image_width'] = int(geometry[0])
                        metadata['image_height'] = int(geometry[1])
            
            # Sample format and bit depth
            sample_format = first_image.get('sampleFormat', '')
            if 'UInt8' in sample_format or 'Int8' in sample_format:
                metadata['bit_depth'] = 8
            elif 'UInt16' in sample_format or 'Int16' in sample_format:
                metadata['bit_depth'] = 16
            elif 'UInt32' in sample_format or 'Int32' in sample_format or 'Float32' in sample_format:
                metadata['bit_depth'] = 32
            elif 'UInt64' in sample_format or 'Int64' in sample_format or 'Float64' in sample_format:
                metadata['bit_depth'] = 64
            
            # Color space
            color_space = first_image.get('colorSpace', 'Unknown')
            metadata['color_space'] = color_space
            
            # Store FITS keywords and XISF properties if present
            # Filter out non-serializable objects like numpy arrays
            fits_keywords = first_image.get('FITSKeywords', {})
            xisf_properties = first_image.get('XISFProperties', {})
            
            # Convert to JSON-serializable format (handle numpy arrays)
            def make_serializable(obj):
                """Convert object to JSON-serializable format."""
                import numpy as np
                
                if isinstance(obj, np.ndarray):
                    # Don't store large arrays, just note their presence
                    return f"<ndarray shape={obj.shape} dtype={obj.dtype}>"
                elif isinstance(obj, np.dtype):
                    # Convert numpy dtype to string
                    return str(obj)
                elif isinstance(obj, type) and hasattr(obj, '__module__') and 'numpy' in obj.__module__:
                    # Handle numpy dtype classes (like Float64DType)
                    return str(obj.__name__)
                elif isinstance(obj, dict):
                    return {k: make_serializable(v) for k, v in obj.items()}
                elif isinstance(obj, (list, tuple)):
                    return [make_serializable(item) for item in obj]
                elif isinstance(obj, (np.integer, np.floating)):
                    return obj.item()  # Convert numpy scalar to Python scalar
                else:
                    return obj
            
            metadata['metadata_json'] = {
                'fits_keywords': make_serializable(fits_keywords),
                'xisf_properties': make_serializable(xisf_properties),
                'sample_format': sample_format,
            }
            
    except Exception as e:
        logger.error(f"Error extracting XISF metadata from {filepath}: {e}")
    
    return metadata


def extract_xosm_metadata(filepath: Path) -> Tuple[Dict, Optional[Path], int]:
    """
    Extract metadata from XOSM files and associated .data folder.
    
    Args:
        filepath: Path to .xosm file
        
    Returns:
        Tuple of (metadata dict, companion path, companion size)
    """
    metadata = {
        'image_width': None,
        'image_height': None,
        'bit_depth': None,
        'color_space': None,
        'metadata_json': {'file_type': 'PixInsight XOSM project'}
    }
    
    companion_path = None
    companion_size = 0
    
    # Look for associated .data folder
    data_folder = filepath.parent / f"{filepath.stem}.data"
    if data_folder.exists() and data_folder.is_dir():
        companion_path = data_folder
        companion_size = get_directory_size(data_folder)
        
        # Try to extract project info from .xosm file
        try:
            # XOSM files are XML-based, could parse for project info
            # For now, just record that we found the companion
            metadata['metadata_json']['has_data_folder'] = True
            metadata['metadata_json']['data_folder_files'] = len(list(data_folder.rglob('*')))
        except Exception as e:
            logger.error(f"Error reading XOSM project {filepath}: {e}")
    else:
        logger.warning(f"XOSM file without .data folder: {filepath}")
    
    return metadata, companion_path, companion_size


def extract_pxiproject_metadata(project_path: Path) -> Dict:
    """
    Extract metadata from PixInsight Project (.pxiproject) folders.
    
    Args:
        project_path: Path to .pxiproject directory
        
    Returns:
        Dictionary containing project metadata
    """
    metadata = {
        'image_width': None,
        'image_height': None,
        'bit_depth': None,
        'color_space': None,
        'metadata_json': {'file_type': 'PixInsight Project Bundle'}
    }
    
    try:
        # Count files in project
        file_count = len(list(project_path.rglob('*')))
        metadata['metadata_json']['project_files'] = file_count
        
        # Look for project manifest or metadata files
        # PixInsight projects may have .xosm or other metadata files inside
        xosm_files = list(project_path.glob('*.xosm'))
        if xosm_files:
            metadata['metadata_json']['has_xosm'] = True
            metadata['metadata_json']['xosm_count'] = len(xosm_files)
        
        # Check for common image files to estimate project content
        image_extensions = ['.xisf', '.fits', '.fit', '.jpg', '.jpeg', '.png', '.tif', '.tiff']
        image_files = []
        for ext in image_extensions:
            image_files.extend(project_path.rglob(f'*{ext}'))
        
        if image_files:
            metadata['metadata_json']['image_files'] = len(image_files)
        
    except Exception as e:
        logger.error(f"Error extracting PXIPROJECT metadata from {project_path}: {e}")
    
    return metadata


def extract_processed_file_metadata(filepath: Path, file_type: str) -> Dict:
    """
    Extract metadata from a processed file based on its type.
    
    Args:
        filepath: Path to file
        file_type: File type (jpg, jpeg, xisf, xosm, pxiproject)
        
    Returns:
        Dictionary containing all extracted metadata
    """
    # Basic file info
    stat = filepath.stat()
    
    result = {
        'filename': filepath.name,
        'file_path': str(filepath),
        'file_type': file_type.lower(),
        'file_size': stat.st_size,
        'created_date': datetime.fromtimestamp(stat.st_ctime),
        'modified_date': datetime.fromtimestamp(stat.st_mtime),
        'has_companion': False,
        'companion_path': None,
        'companion_size': None,
        'md5sum': None,
        'image_width': None,
        'image_height': None,
        'bit_depth': None,
        'color_space': None,
        'metadata_json': None,
    }
    
    # Type-specific metadata extraction
    type_metadata = {}
    
    if file_type.lower() in ['jpg', 'jpeg']:
        type_metadata = extract_jpg_metadata(filepath)
        result['md5sum'] = calculate_md5(filepath)
        
    elif file_type.lower() == 'xisf':
        type_metadata = extract_xisf_metadata(filepath)
        result['md5sum'] = calculate_md5(filepath)
        
    elif file_type.lower() == 'xosm':
        type_metadata, companion_path, companion_size = extract_xosm_metadata(filepath)
        if companion_path:
            result['has_companion'] = True
            result['companion_path'] = str(companion_path)
            result['companion_size'] = companion_size
            # Total size includes both .xosm and .data
            result['file_size'] = stat.st_size + companion_size
        result['md5sum'] = calculate_md5(filepath)
        
    elif file_type.lower() == 'pxiproject':
        type_metadata = extract_pxiproject_metadata(filepath)
        # For directories, calculate total size
        result['file_size'] = get_directory_size(filepath)
        # MD5 for directories is complex, skip for now
        
    # Merge type-specific metadata
    result.update(type_metadata)
    
    # Convert metadata_json to JSON string (always, even if empty/None)
    if result['metadata_json'] is not None:
        result['metadata_json'] = json.dumps(result['metadata_json'])
    else:
        result['metadata_json'] = json.dumps({})
    
    return result