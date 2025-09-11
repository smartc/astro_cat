#!/usr/bin/env python3
"""
Debug script to analyze exactly what's wrong with FLAT frame scoring.
Save as flat_debug.py and run to see detailed scoring breakdown.
"""

import sys
from pathlib import Path

# Add your project path
sys.path.append(str(Path(__file__).parent))

from config import load_config
from models import DatabaseManager, DatabaseService, FitsFile


def debug_flat_scoring():
    """Debug FLAT frame scoring in detail."""
    
    # Load configuration
    config, cameras, telescopes, filter_mappings = load_config()
    
    # Initialize database
    db_manager = DatabaseManager(config.database.connection_string)
    db_service = DatabaseService(db_manager)
    
    session = db_service.db_manager.get_session()
    
    try:
        print("FLAT FRAME SCORING DEBUG")
        print("=" * 60)
        
        # Get some FLAT frames that need review
        problem_flats = session.query(FitsFile).filter(
            FitsFile.frame_type == 'FLAT',
            FitsFile.validation_score < 95,
            FitsFile.validation_score >= 80
        ).limit(10).all()
        
        if not problem_flats:
            print("No FLAT frames found in the 80-94 score range")
            return
        
        # Create equipment lookup dictionaries
        known_cameras = {cam.camera: cam for cam in cameras}
        known_telescopes = {tel.scope: tel for tel in telescopes}
        known_filters = set(filter_mappings.values())
        
        print(f"Analyzing {len(problem_flats)} FLAT frames with scores 80-94...")
        print("\nKnown Equipment:")
        print(f"  Cameras: {', '.join(known_cameras.keys())}")
        print(f"  Telescopes: {', '.join(known_telescopes.keys())}")
        print(f"  Filters: {', '.join(sorted(known_filters))}")
        
        print("\n" + "="*100)
        print("DETAILED SCORING ANALYSIS")
        print("="*100)
        
        for i, flat in enumerate(problem_flats, 1):
            print(f"\nFILE {i}: {flat.file}")
            print(f"Current Score: {flat.validation_score:.1f}")
            print("-" * 50)
            
            # Simulate the FLAT scoring criteria
            scores = {}
            total_possible = 100
            
            # Telescope scoring (30 points)
            telescope_score = 0
            if not flat.telescope:
                telescope_issue = "Missing telescope"
            elif flat.telescope == 'UNKNOWN':
                telescope_issue = "Telescope marked as UNKNOWN"
            elif flat.telescope in known_telescopes:
                telescope_score = 30
                telescope_issue = "✓ Telescope identified"
            else:
                telescope_score = 21  # 70% for unrecognized but present
                telescope_issue = f"Unrecognized telescope: '{flat.telescope}'"
            
            scores['telescope'] = telescope_score
            print(f"  Telescope (30 pts): {telescope_score:2d} - {telescope_issue}")
            
            # Camera scoring (25 points)
            camera_score = 0
            if not flat.camera:
                camera_issue = "Missing camera"
            elif flat.camera == 'UNKNOWN':
                camera_issue = "Camera marked as UNKNOWN"
            elif flat.camera in known_cameras:
                camera_score = 25
                camera_issue = "✓ Camera identified"
            else:
                camera_score = 17  # 70% for unrecognized but present
                camera_issue = f"Unrecognized camera: '{flat.camera}'"
            
            scores['camera'] = camera_score
            print(f"  Camera (25 pts):    {camera_score:2d} - {camera_issue}")
            
            # Filter scoring (25 points)
            filter_score = 0
            if not flat.filter:
                filter_issue = "Missing filter"
            elif flat.filter == 'UNKNOWN':
                filter_issue = "Filter marked as UNKNOWN"
            elif flat.filter in known_filters:
                filter_score = 25
                filter_issue = "✓ Filter identified"
            else:
                filter_score = 15  # 60% for unrecognized but present
                filter_issue = f"Unrecognized filter: '{flat.filter}'"
            
            scores['filter'] = filter_score
            print(f"  Filter (25 pts):    {filter_score:2d} - {filter_issue}")
            
            # Exposure scoring (10 points)
            exposure_score = 0
            if not flat.exposure:
                exposure_issue = "Missing exposure time"
            elif flat.exposure <= 0:
                exposure_issue = "Invalid exposure time"
            elif 0.001 <= flat.exposure <= 30:
                exposure_score = 10
                exposure_issue = f"✓ Valid exposure: {flat.exposure}s"
            else:
                exposure_score = 3  # 30% for unusual but present
                exposure_issue = f"Unusual exposure: {flat.exposure}s"
            
            scores['exposure'] = exposure_score
            print(f"  Exposure (10 pts):  {exposure_score:2d} - {exposure_issue}")
            
            # Frame type clarity (5 points)
            frame_score = 5 if flat.frame_type == 'FLAT' else 0
            frame_issue = "✓ Correct frame type" if frame_score else "Incorrect frame type"
            scores['frame_type'] = frame_score
            print(f"  Frame Type (5 pts):  {frame_score:2d} - {frame_issue}")
            
            # Timestamp scoring (5 points)
            timestamp_score = 5 if flat.obs_timestamp else 0
            timestamp_issue = "✓ Has timestamp" if timestamp_score else "Missing timestamp"
            scores['timestamp'] = timestamp_score
            print(f"  Timestamp (5 pts):   {timestamp_score:2d} - {timestamp_issue}")
            
            # Calculate total
            calculated_score = sum(scores.values())
            print(f"\n  CALCULATED TOTAL: {calculated_score}/100")
            print(f"  DATABASE SCORE:   {flat.validation_score:.1f}/100")
            
            # Show what would get this to 95+
            needed_points = 95 - calculated_score
            if needed_points > 0:
                print(f"  NEEDS {needed_points} MORE POINTS TO AUTO-MIGRATE")
                
                fixes = []
                if telescope_score < 30:
                    potential_gain = 30 - telescope_score
                    fixes.append(f"Fix telescope (+{potential_gain} pts)")
                if filter_score < 25:
                    potential_gain = 25 - filter_score
                    fixes.append(f"Fix filter (+{potential_gain} pts)")
                if camera_score < 25:
                    potential_gain = 25 - camera_score
                    fixes.append(f"Fix camera (+{potential_gain} pts)")
                
                if fixes:
                    print(f"  SUGGESTED FIXES: {', '.join(fixes[:2])}")
        
        # Summary of common issues
        print("\n" + "="*100)
        print("SUMMARY OF COMMON FLAT FRAME ISSUES")
        print("="*100)
        
        telescope_issues = {}
        filter_issues = {}
        camera_issues = {}
        
        for flat in problem_flats:
            # Telescope issues
            if not flat.telescope:
                telescope_issues['Missing'] = telescope_issues.get('Missing', 0) + 1
            elif flat.telescope == 'UNKNOWN':
                telescope_issues['Unknown'] = telescope_issues.get('Unknown', 0) + 1
            elif flat.telescope not in known_telescopes:
                telescope_issues[f"Unrecognized: {flat.telescope}"] = telescope_issues.get(f"Unrecognized: {flat.telescope}", 0) + 1
            
            # Filter issues
            if not flat.filter:
                filter_issues['Missing'] = filter_issues.get('Missing', 0) + 1
            elif flat.filter == 'UNKNOWN':
                filter_issues['Unknown'] = filter_issues.get('Unknown', 0) + 1
            elif flat.filter not in known_filters:
                filter_issues[f"Unrecognized: {flat.filter}"] = filter_issues.get(f"Unrecognized: {flat.filter}", 0) + 1
            
            # Camera issues
            if not flat.camera:
                camera_issues['Missing'] = camera_issues.get('Missing', 0) + 1
            elif flat.camera == 'UNKNOWN':
                camera_issues['Unknown'] = camera_issues.get('Unknown', 0) + 1
            elif flat.camera not in known_cameras:
                camera_issues[f"Unrecognized: {flat.camera}"] = camera_issues.get(f"Unrecognized: {flat.camera}", 0) + 1
        
        print("\nTelescope Issues:")
        for issue, count in telescope_issues.items():
            print(f"  {issue}: {count} files")
        
        print("\nFilter Issues:")
        for issue, count in filter_issues.items():
            print(f"  {issue}: {count} files")
        
        print("\nCamera Issues:")
        for issue, count in camera_issues.items():
            print(f"  {issue}: {count} files")
        
        print("\nRECOMMENDATIONS:")
        print("1. Add missing equipment to your JSON files")
        print("2. Check focal length matching for telescopes")
        print("3. Add filter name mappings for unrecognized filters")
        print("4. Verify FITS header keywords are being read correctly")
        
    finally:
        session.close()
        db_manager.close()


if __name__ == "__main__":
    try:
        debug_flat_scoring()
    except Exception as e:
        print(f"Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)