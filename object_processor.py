"""Object name processing and normalization module."""

import re
from typing import Optional


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
        """Normalize input name for processing."""
        if not name or name in ['nan', 'None', '', 'null']:
            return ""
        name = str(name).lower().strip()
        name = re.sub(r'(flat\s+frame.*|save\s+to\s+disk|test\s+image)', '', name)
        name = re.sub(r'[_\-\s]+', ' ', name).strip()
        name = re.sub(r'[^\w\s\-\+]', ' ', name)
        return name
    
    def extract_catalog_object(self, name: str) -> Optional[str]:
        """Extract catalog object name from input."""
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
    
    def process_object_name(self, raw_name: str, frame_type: str = "LIGHT") -> Optional[str]:
        """Process and normalize object name."""
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