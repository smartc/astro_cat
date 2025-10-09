"""
Software profile configuration for FITS metadata extraction.

Supports multiple capture software packages with configurable keyword mappings.
All profiles are loaded from JSON files in the profiles/ directory.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any

logger = logging.getLogger(__name__)


@dataclass
class SoftwareProfile:
    """Profile for specific capture software."""
    name: str
    priority: int = 50  # Higher = check first (0-100)
    
    # Equipment keywords (in priority order)
    camera_keys: List[str] = field(default_factory=lambda: ['INSTRUME', 'CAMERA'])
    telescope_keys: List[str] = field(default_factory=lambda: ['TELESCOP'])
    filter_keys: List[str] = field(default_factory=lambda: ['FILTER'])
    target_keys: List[str] = field(default_factory=lambda: ['OBJECT'])
    
    # Frame type keywords and value mappings
    frame_type_keys: List[str] = field(default_factory=lambda: ['IMAGETYP'])
    frame_type_mappings: Dict[str, str] = field(default_factory=dict)
    
    # Software detection patterns (key: pattern to match)
    detection_keywords: Dict[str, str] = field(default_factory=dict)
    
    # Software-specific notes
    notes: str = ""
    
    def matches(self, header) -> bool:
        """Check if this profile matches the FITS header."""
        for key, pattern in self.detection_keywords.items():
            if key in header:
                value = str(header[key]).lower()
                if pattern.lower() in value:
                    return True
        return False


class ProfileManager:
    """Manage software profiles for FITS metadata extraction."""
    
    def __init__(self, custom_profiles_path: Optional[str] = None):
        self.profiles: Dict[str, SoftwareProfile] = {}
        
        # Auto-load from profiles directory if not specified
        if custom_profiles_path is None:
            profiles_dir = Path('profiles')
            if profiles_dir.exists() and profiles_dir.is_dir():
                self.load_profiles_from_directory(str(profiles_dir))
            else:
                logger.warning("No profiles directory found - no profiles loaded")
        elif Path(custom_profiles_path).is_dir():
            self.load_profiles_from_directory(custom_profiles_path)
        elif Path(custom_profiles_path).is_file():
            self.load_custom_profiles(custom_profiles_path)
    
    def load_custom_profiles(self, profiles_path: str):
        """
        Load custom profiles from JSON file.
        
        Expected format:
        {
            "profiles": [
                {
                    "name": "NINA",
                    "priority": 95,
                    "camera_keys": ["INSTRUME", "CAMERA"],
                    ...
                }
            ]
        }
        """
        try:
            path = Path(profiles_path)
            if not path.exists():
                logger.warning(f"Custom profiles file not found: {profiles_path}")
                return
            
            with open(path, 'r') as f:
                data = json.load(f)
            
            for profile_data in data.get('profiles', []):
                try:
                    profile = SoftwareProfile(**profile_data)
                    self.profiles[profile.name] = profile
                    logger.info(f"Loaded custom profile: {profile.name}")
                except Exception as e:
                    logger.error(f"Error loading profile from {profiles_path}: {e}")
        
        except Exception as e:
            logger.error(f"Error loading custom profiles file {profiles_path}: {e}")
    
    def load_profiles_from_directory(self, directory_path: str):
        """Load all .json files from a directory as profile files."""
        try:
            dir_path = Path(directory_path)
            if not dir_path.exists():
                return
            
            json_files = sorted(dir_path.glob('*.json'))
            if not json_files:
                logger.debug(f"No .json files found in {directory_path}")
                return
            
            for json_file in json_files:
                try:
                    self.load_custom_profiles(str(json_file))
                except Exception as e:
                    logger.warning(f"Skipping {json_file.name}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error reading directory {directory_path}: {e}")
    
    def detect_software(self, header) -> Optional[str]:
        """
        Detect capture software from FITS header.
        
        Returns profile name or None if not detected.
        """
        # Try profiles in priority order
        sorted_profiles = sorted(
            self.profiles.values(),
            key=lambda p: p.priority,
            reverse=True
        )
        
        for profile in sorted_profiles:
            if profile.matches(header):
                return profile.name
        
        return None
    
    def get_profile(self, name: str) -> Optional[SoftwareProfile]:
        """Get profile by name."""
        return self.profiles.get(name)
    
    def get_value(self, header, field_type: str, 
                  profile_name: Optional[str] = None) -> Any:
        """
        Extract value using profile-based keyword priority.
        
        Args:
            header: FITS header
            field_type: Type of field ('camera', 'telescope', 'filter', 'target')
            profile_name: Specific profile to use, or None for auto-detect
            
        Returns:
            Value from header or None
        """
        if profile_name and profile_name in self.profiles:
            profiles_to_try = [self.profiles[profile_name]]
        else:
            # Try all profiles in priority order
            profiles_to_try = sorted(
                self.profiles.values(),
                key=lambda p: p.priority,
                reverse=True
            )
        
        # Map field type to profile attribute
        key_attr_map = {
            'camera': 'camera_keys',
            'telescope': 'telescope_keys',
            'filter': 'filter_keys',
            'target': 'target_keys',
            'frame_type': 'frame_type_keys'
        }
        
        key_attr = key_attr_map.get(field_type)
        if not key_attr:
            return None
        
        for profile in profiles_to_try:
            keys = getattr(profile, key_attr, [])
            for key in keys:
                try:
                    if key in header:
                        value = header[key]
                        
                        # Apply frame type mapping if applicable
                        if field_type == 'frame_type' and profile.frame_type_mappings:
                            value = profile.frame_type_mappings.get(value, value)
                        
                        return value
                except Exception as e:
                    # Skip malformed header cards
                    logger.debug(f"Error reading {key}: {e}")
                    continue
        
        return None
    
    def list_profiles(self) -> List[Dict]:
        """Get list of all profiles with basic info."""
        return [
            {
                'name': p.name,
                'priority': p.priority,
                'detection': list(p.detection_keywords.keys()),
                'notes': p.notes
            }
            for p in sorted(self.profiles.values(), key=lambda x: x.priority, reverse=True)
        ]
    
    def export_profile(self, profile_name: str, output_path: str):
        """Export a profile to JSON file."""
        profile = self.profiles.get(profile_name)
        if not profile:
            raise ValueError(f"Profile '{profile_name}' not found")
        
        with open(output_path, 'w') as f:
            json.dump({'profiles': [asdict(profile)]}, f, indent=2)
        
        logger.info(f"Exported profile '{profile_name}' to {output_path}")


# Module-level singleton
_profile_manager: Optional[ProfileManager] = None


def get_profile_manager(custom_profiles_path: Optional[str] = None) -> ProfileManager:
    """
    Get or create the global ProfileManager instance.
    
    Args:
        custom_profiles_path: Path to custom profiles JSON (only used on first call)
    """
    global _profile_manager
    
    if _profile_manager is None:
        _profile_manager = ProfileManager(custom_profiles_path)
    
    return _profile_manager


def reset_profile_manager():
    """Reset the global ProfileManager (mainly for testing)."""
    global _profile_manager
    _profile_manager = None