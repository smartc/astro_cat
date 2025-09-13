#!/usr/bin/env python3
"""
Simple script to examine the specific FITS files that are causing date parsing errors.
"""

from astropy.io import fits
from datetime import datetime, timedelta
import sys


def examine_fits_file(filepath: str):
    """Examine a specific FITS file's headers, focusing on date-related fields."""
    print(f"\n{'='*80}")
    print(f"Examining file: {filepath}")
    print(f"{'='*80}")
    
    try:
        with fits.open(filepath) as hdul:
            header = hdul[0].header
            
            print(f"File opened successfully. Header has {len(header)} cards.")
            
            # Look for all date-related keys
            date_keys = ['DATE-OBS', 'DATE_OBS', 'DATEOBS', 'DATE', 'TIME-OBS', 'TIME_OBS']
            
            print(f"\nDATE-RELATED HEADERS:")
            print(f"{'-'*50}")
            found_date_keys = False
            
            for key in date_keys:
                if key in header:
                    found_date_keys = True
                    value = header[key]
                    value_type = type(value).__name__
                    print(f"  {key:<15}: '{value}' (type: {value_type})")
                    
                    # Try to understand what this value represents
                    if isinstance(value, str):
                        print(f"                    Length: {len(value)} characters")
                        if len(value) > 0:
                            print(f"                    First char ASCII: {ord(value[0]) if value else 'N/A'}")
                            print(f"                    Repr: {repr(value)}")
            
            if not found_date_keys:
                print("  No standard date keys found!")
            
            # Show all headers to look for any date-like content
            print(f"\nALL HEADERS (first 20):")
            print(f"{'-'*50}")
            for i, (key, value) in enumerate(header.items()):
                if i >= 20:
                    print("  ... (truncated)")
                    break
                value_str = str(value)[:50] if len(str(value)) > 50 else str(value)
                print(f"  {key:<8}: {value_str} ({type(value).__name__})")
            
            # Try the current parsing logic to see what fails
            print(f"\nTESTING CURRENT PARSING LOGIC:")
            print(f"{'-'*50}")
            
            for key in ['DATE-OBS', 'DATE_OBS', 'DATEOBS']:
                if key in header:
                    try:
                        date_str = header[key]
                        print(f"  Trying to parse {key}: '{date_str}'")
                        
                        if isinstance(date_str, str):
                            if 'T' in date_str:
                                print(f"    -> Contains 'T', treating as ISO format")
                                # This is probably where it's failing
                                result = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                                print(f"    -> SUCCESS: {result}")
                            else:
                                print(f"    -> Date only format")
                                result = datetime.strptime(date_str, '%Y-%m-%d')
                                print(f"    -> SUCCESS: {result}")
                        elif hasattr(date_str, 'datetime'):
                            print(f"    -> Has datetime attribute")
                            result = date_str.datetime
                            print(f"    -> SUCCESS: {result}")
                        else:
                            print(f"    -> Unknown type: {type(date_str)}")
                            
                    except Exception as e:
                        print(f"    -> FAILED: {e}")
                        print(f"    -> Error type: {type(e).__name__}")
            
            # Check file creation/modification times for comparison
            import os
            stat = os.stat(filepath)
            print(f"\nFILE SYSTEM TIMESTAMPS:")
            print(f"{'-'*50}")
            print(f"  Created:  {datetime.fromtimestamp(stat.st_ctime)}")
            print(f"  Modified: {datetime.fromtimestamp(stat.st_mtime)}")
            
    except Exception as e:
        print(f"ERROR opening file: {e}")
        print(f"Error type: {type(e).__name__}")
        
        # Try to get basic file info
        try:
            import os
            stat = os.stat(filepath)
            print(f"File size: {stat.st_size} bytes")
            print(f"File exists: {os.path.exists(filepath)}")
        except:
            print("Cannot get basic file info")


def main():
    # The specific files mentioned in the error
    problem_files = [
        "/mnt/phoebe/Astro/Quarantine/Images/Flat/NGC6946_1sec_1x1__0053.fit",
        "/mnt/phoebe/Astro/Quarantine/Images/Flat/NGC6946_1sec_1x1__0054.fit",
        "/mnt/phoebe/Astro/Quarantine/Images/Flat/NGC6946_1sec_1x1__0055.fit",
        "/mnt/phoebe/Astro/Quarantine/Images/Flat/NGC6946_1sec_1x1__0056.fit",
        "/mnt/phoebe/Astro/Quarantine/Images/Flat/NGC6946_1sec_1x1__0057.fit",
    ]
    
    # Allow command line arguments too
    if len(sys.argv) > 1:
        problem_files = sys.argv[1:]
    
    print("FITS FILE DATE HEADER EXAMINATION")
    print("This script will examine the specific files causing date parsing errors")
    
    for filepath in problem_files:
        examine_fits_file(filepath)
    
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Examined {len(problem_files)} files.")
    print("Look for patterns in the date values that might be causing 'date value out of range' errors.")
    print("Common issues could be:")
    print("  - Invalid dates like February 30th")
    print("  - Years outside normal range (e.g., year 0000 or 9999)")
    print("  - Malformed date strings")
    print("  - Timezone issues")
    print("  - Microsecond precision issues")


if __name__ == "__main__":
    main()
