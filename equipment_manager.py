"""Equipment management for cameras, telescopes, and filters."""

import json
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, validator


class Camera(BaseModel):
    """Camera specification with optional fields for unknown equipment."""
    camera: str  # Camera name - required
    bin: int = 1
    x: int       # X resolution - required (from FITS NAXIS1)
    y: int       # Y resolution - required (from FITS NAXIS2)  
    type: Optional[str] = None     # CMOS/CCD - optional, may be unknown
    brand: str                     # Brand - can be "Unknown"
    pixel: Optional[float] = None  # Pixel size in microns - optional, may be unknown
    rgb: Optional[bool] = True     # True for OSC/color, False for mono
    comments: Optional[str] = None

    @validator('pixel', pre=True)
    def empty_string_to_none_float(cls, v):
        """Convert empty strings to None for optional float fields."""
        if v == "" or v is None:
            return None
        return float(v)

    @validator('type', 'comments', pre=True)
    def empty_string_to_none_str(cls, v):
        """Convert empty strings to None for optional string fields."""
        if v == "" or v is None:
            return None
        return v

    @validator('brand', pre=True)
    def handle_empty_brand(cls, v):
        """Convert empty brand to 'Unknown'."""
        if v == "" or v is None:
            return "Unknown"
        return v


class Telescope(BaseModel):
    """Telescope specification with optional fields for unknown equipment."""
    scope: str   # Telescope name - required
    focal: int   # Focal length - required (from FITS FOCALLEN)
    aperture: Optional[float] = None  # Aperture in mm - optional
    make: Optional[str] = None     # Manufacturer - optional, may be unknown
    type: Optional[str] = None     # Type (refractor/reflector/lens) - optional, may be unknown
    subtype: Optional[str] = None  # Subtype - optional
    comments: Optional[str] = None

    @validator('aperture', pre=True)
    def empty_string_to_none(cls, v):
        """Convert empty strings to None for optional float fields."""
        if v == "" or v is None:
            return None
        return float(v)

    @validator('make', 'type', 'subtype', 'comments', pre=True)
    def empty_string_to_none_str(cls, v):
        """Convert empty strings to None for optional string fields."""
        if v == "" or v is None:
            return None
        return v


class FilterMapping(BaseModel):
    """Filter name mapping."""
    raw_name: str
    proper_name: str


class EquipmentPaths(BaseModel):
    """Equipment data file paths."""
    cameras_file: str = "cameras.json"
    telescopes_file: str = "telescopes.json"
    filters_file: str = "filters.json"


class EquipmentManager:
    """Manages loading and validation of equipment data."""
    
    def __init__(self, equipment_paths: EquipmentPaths):
        self.equipment_paths = equipment_paths
        self.cameras: List[Camera] = []
        self.telescopes: List[Telescope] = []
        self.filter_mappings: Dict[str, str] = {}
    
    def load_equipment(self):
        """Load equipment data from JSON files with validation."""
        self.cameras = self._load_cameras()
        self.telescopes = self._load_telescopes()
        self.filter_mappings = self._load_filter_mappings()
        
        print(f"Loaded {len(self.cameras)} cameras, {len(self.telescopes)} telescopes, {len(self.filter_mappings)} filter mappings")
        return self.cameras, self.telescopes, self.filter_mappings
    
    def _load_cameras(self) -> List[Camera]:
        """Load cameras from JSON file with validation."""
        cameras = []
        camera_file = Path(self.equipment_paths.cameras_file)
        
        if not camera_file.exists():
            print(f"Warning: Camera file not found: {camera_file}")
            return cameras
            
        try:
            with open(camera_file, 'r') as f:
                cameras_data = json.load(f)
                
            for i, cam_data in enumerate(cameras_data):
                try:
                    # Validate each camera entry
                    camera = Camera(**cam_data)
                    cameras.append(camera)
                except Exception as e:
                    print(f"Warning: Invalid camera entry #{i+1} in {camera_file}: {e}")
                    print(f"Entry: {cam_data}")
                    continue
                    
        except Exception as e:
            print(f"Error loading cameras from {camera_file}: {e}")
            
        return cameras
    
    def _load_telescopes(self) -> List[Telescope]:
        """Load telescopes from JSON file with validation."""
        telescopes = []
        telescope_file = Path(self.equipment_paths.telescopes_file)
        
        if not telescope_file.exists():
            print(f"Warning: Telescope file not found: {telescope_file}")
            return telescopes
            
        try:
            with open(telescope_file, 'r') as f:
                telescopes_data = json.load(f)
                
            for i, tel_data in enumerate(telescopes_data):
                try:
                    # Validate each telescope entry
                    telescope = Telescope(**tel_data)
                    telescopes.append(telescope)
                except Exception as e:
                    print(f"Warning: Invalid telescope entry #{i+1} in {telescope_file}: {e}")
                    print(f"Entry: {tel_data}")
                    continue
                    
        except Exception as e:
            print(f"Error loading telescopes from {telescope_file}: {e}")
            
        return telescopes
    
    def _load_filter_mappings(self) -> Dict[str, str]:
        """Load filter mappings from JSON file."""
        filter_mappings = {}
        filter_file = Path(self.equipment_paths.filters_file)
        
        if not filter_file.exists():
            print(f"Warning: Filter file not found: {filter_file}")
            return filter_mappings
            
        try:
            with open(filter_file, 'r') as f:
                filters_data = json.load(f)
                
            filter_mappings = {f['raw_name']: f['proper_name'] for f in filters_data}
            
        except Exception as e:
            print(f"Error loading filters from {filter_file}: {e}")
            
        return filter_mappings
    
    def create_default_equipment_files(self):
        """Create default equipment files if they don't exist."""
        if not Path(self.equipment_paths.cameras_file).exists():
            default_cameras = [
                {
                    "camera": "ASI1600",
                    "bin": 1,
                    "x": 4656,
                    "y": 3520,
                    "type": "CMOS",
                    "brand": "ZWO",
                    "pixel": 3.8,
                    "rgb": False,
                    "comments": "Example monochrome camera"
                }
            ]
            with open(self.equipment_paths.cameras_file, 'w') as f:
                json.dump(default_cameras, f, indent=2)
            print(f"Created default cameras file: {self.equipment_paths.cameras_file}")
        
        if not Path(self.equipment_paths.telescopes_file).exists():
            default_telescopes = [
                {
                    "scope": "ES127",
                    "focal": 952,
                    "aperture": 127,
                    "make": "Explore Scientific",
                    "type": "Refractor",
                    "subtype": "Triplet APO",
                    "comments": "Example telescope"
                }
            ]
            with open(self.equipment_paths.telescopes_file, 'w') as f:
                json.dump(default_telescopes, f, indent=2)
            print(f"Created default telescopes file: {self.equipment_paths.telescopes_file}")
        
        if not Path(self.equipment_paths.filters_file).exists():
            default_filters = [
                {"raw_name": "Red", "proper_name": "R"},
                {"raw_name": "Green", "proper_name": "G"},
                {"raw_name": "Blue", "proper_name": "B"},
                {"raw_name": "Lum", "proper_name": "L"},
                {"raw_name": "Ha", "proper_name": "HA"},
                {"raw_name": "H-Alpha", "proper_name": "HA"},
                {"raw_name": "OIII", "proper_name": "OIII"},
                {"raw_name": "SII", "proper_name": "SII"}
            ]
            with open(self.equipment_paths.filters_file, 'w') as f:
                json.dump(default_filters, f, indent=2)
            print(f"Created default filters file: {self.equipment_paths.filters_file}")