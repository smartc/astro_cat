#!/usr/bin/env python3
"""
Profile Management Utility

Manage software profiles for FITS metadata extraction.

Usage:
    python manage_profiles.py list
    python manage_profiles.py detect <fits_file>
    python manage_profiles.py export SGPro profiles/sgpro_export.json
    python manage_profiles.py load profiles/nina_profile.json
"""

import argparse
import sys
from pathlib import Path
from astropy.io import fits

from processing.software_profiles import get_profile_manager, reset_profile_manager


def list_profiles(args):
    """List all loaded profiles."""
    pm = get_profile_manager(args.custom_profiles)
    
    profiles = pm.list_profiles()
    
    if not profiles:
        print("No profiles loaded")
        return
    
    print(f"\nLoaded Software Profiles ({len(profiles)}):")
    if args.custom_profiles:
        print(f"From: {args.custom_profiles}")
    else:
        print(f"From: profiles/ directory")
    print("=" * 70)
    
    for p in profiles:
        print(f"\n{p['name']} (Priority: {p['priority']})")
        print(f"  Detection: {', '.join(p['detection'])}")
        if p['notes']:
            print(f"  Notes: {p['notes']}")


def detect_software(args):
    """Detect software from FITS file."""
    fits_file = Path(args.fits_file)
    
    if not fits_file.exists():
        print(f"Error: File not found: {fits_file}")
        sys.exit(1)
    
    try:
        with fits.open(fits_file) as hdul:
            header = hdul[0].header
            
            pm = get_profile_manager(args.custom_profiles)
            detected = pm.detect_software(header)
            
            print(f"\nFile: {fits_file.name}")
            
            if detected:
                print(f"Detected Software: {detected}")
                profile = pm.get_profile(detected)
                if profile:
                    print(f"Priority: {profile.priority}")
            else:
                print("Software: Not detected")
            
            # Show SWCREATE if present
            if 'SWCREATE' in header:
                print(f"SWCREATE header: {header['SWCREATE']}")
            
    except Exception as e:
        print(f"Error reading FITS file: {e}")
        sys.exit(1)


def export_profile(args):
    """Export a profile to JSON."""
    pm = get_profile_manager(args.custom_profiles)
    
    try:
        pm.export_profile(args.profile_name, args.output_file)
        print(f"✓ Exported profile '{args.profile_name}' to {args.output_file}")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


def load_profiles(args):
    """Load profiles from JSON file."""
    profile_file = Path(args.profile_file)
    
    if not profile_file.exists():
        print(f"Error: Profile file not found: {profile_file}")
        sys.exit(1)
    
    # Reset and reload with new file
    reset_profile_manager()
    pm = get_profile_manager(str(profile_file))
    
    profiles = pm.list_profiles()
    print(f"✓ Loaded {len(profiles)} profile(s) from {profile_file}")
    
    for p in profiles:
        print(f"  - {p['name']} (Priority: {p['priority']})")


def test_extraction(args):
    """Test metadata extraction with profile system."""
    fits_file = Path(args.fits_file)
    
    if not fits_file.exists():
        print(f"Error: File not found: {fits_file}")
        sys.exit(1)
    
    try:
        with fits.open(fits_file) as hdul:
            header = hdul[0].header
            
            pm = get_profile_manager(args.custom_profiles)
            detected = pm.detect_software(header)
            
            print(f"\nFile: {fits_file.name}")
            print(f"Detected: {detected or 'Unknown'}")
            print("\nExtracted Values:")
            print("-" * 50)
            
            for field in ['camera', 'telescope', 'filter', 'target', 'frame_type']:
                try:
                    value = pm.get_value(header, field, detected)
                    print(f"  {field:12s}: {value}")
                except Exception as e:
                    print(f"  {field:12s}: Error - {e}")
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Manage FITS software profiles')
    parser.add_argument(
        '--custom-profiles',
        help='Path to custom profiles JSON file'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # List command
    subparsers.add_parser('list', help='List all profiles')
    
    # Detect command
    detect_parser = subparsers.add_parser('detect', help='Detect software from FITS file')
    detect_parser.add_argument('fits_file', help='Path to FITS file')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export profile to JSON')
    export_parser.add_argument('profile_name', help='Name of profile to export')
    export_parser.add_argument('output_file', help='Output JSON file')
    
    # Load command
    load_parser = subparsers.add_parser('load', help='Load profiles from JSON')
    load_parser.add_argument('profile_file', help='Path to profiles JSON file')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Test extraction with profile')
    test_parser.add_argument('fits_file', help='Path to FITS file')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    commands = {
        'list': list_profiles,
        'detect': detect_software,
        'export': export_profile,
        'load': load_profiles,
        'test': test_extraction
    }
    
    commands[args.command](args)


if __name__ == '__main__':
    main()