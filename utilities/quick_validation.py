#!/usr/bin/env python3
"""
Quick validation analysis script - save as validation_analysis.py and run immediately
to understand what's causing your validation score issues.
"""

import sys
from pathlib import Path
from collections import defaultdict, Counter
from sqlalchemy import func

# Add your project path
sys.path.append(str(Path(__file__).parent))

from config import load_config
from models import DatabaseManager, DatabaseService, FitsFile


def analyze_validation_issues():
    """Analyze what's causing validation score issues."""
    
    # Load configuration
    config, cameras, telescopes, filter_mappings = load_config()
    
    # Initialize database
    db_manager = DatabaseManager(config.database.connection_string)
    db_service = DatabaseService(db_manager)
    
    session = db_service.db_manager.get_session()
    
    try:
        print("VALIDATION ISSUE ANALYSIS")
        print("=" * 60)
        
        # Get files by frame type and score ranges
        frame_types = ['LIGHT', 'DARK', 'FLAT', 'BIAS']
        
        for frame_type in frame_types:
            print(f"\n{frame_type} FRAMES")
            print("-" * 30)
            
            # Get all files of this type
            all_files = session.query(FitsFile).filter(
                FitsFile.frame_type == frame_type
            ).all()
            
            if not all_files:
                print("  No files found")
                continue
            
            # Separate by score ranges
            auto_migrate = [f for f in all_files if f.validation_score and f.validation_score >= 95]
            needs_review = [f for f in all_files if f.validation_score and 80 <= f.validation_score < 95]
            manual_only = [f for f in all_files if f.validation_score and f.validation_score < 80]
            no_score = [f for f in all_files if f.validation_score is None]
            
            total = len(all_files)
            print(f"  Total files: {total}")
            print(f"  Auto-migrate (≥95):  {len(auto_migrate):>4} ({len(auto_migrate)/total*100:5.1f}%)")
            print(f"  Needs review (80-94): {len(needs_review):>4} ({len(needs_review)/total*100:5.1f}%)")
            print(f"  Manual only (<80):   {len(manual_only):>4} ({len(manual_only)/total*100:5.1f}%)")
            print(f"  No score:            {len(no_score):>4} ({len(no_score)/total*100:5.1f}%)")
            
            # Analyze issues in files that need review
            problem_files = needs_review + manual_only
            if problem_files:
                print(f"\n  Issues in {len(problem_files)} files needing review:")
                
                issues = Counter()
                
                for file_record in problem_files:
                    # Check for missing/unknown values
                    if not file_record.telescope or file_record.telescope == 'UNKNOWN':
                        issues['Missing/Unknown Telescope'] += 1
                    
                    if not file_record.camera or file_record.camera == 'UNKNOWN':
                        issues['Missing/Unknown Camera'] += 1
                    
                    if not file_record.filter or file_record.filter == 'UNKNOWN':
                        issues['Missing/Unknown Filter'] += 1
                    
                    if not file_record.exposure:
                        issues['Missing Exposure'] += 1
                    elif file_record.exposure <= 0:
                        issues['Invalid Exposure'] += 1
                    
                    if not file_record.obs_timestamp:
                        issues['Missing Timestamp'] += 1
                    
                    if frame_type == 'LIGHT' and (not file_record.ra or not file_record.dec):
                        issues['Missing Coordinates'] += 1
                    
                    if not file_record.object or file_record.object in ['UNKNOWN', 'None']:
                        issues['Missing/Unknown Object'] += 1
                
                # Show top issues
                for issue, count in issues.most_common(8):
                    percentage = count / len(problem_files) * 100
                    print(f"    {issue:<25}: {count:>4} files ({percentage:5.1f}%)")
        
        # Overall equipment analysis
        print("\n" + "=" * 60)
        print("EQUIPMENT IDENTIFICATION ISSUES")
        print("=" * 60)
        
        # Telescope analysis
        telescope_counts = session.query(
            FitsFile.telescope, func.count(FitsFile.id)
        ).group_by(FitsFile.telescope).all()
        
        print("\nTelescope Distribution:")
        total_files = sum(count for _, count in telescope_counts)
        for telescope, count in sorted(telescope_counts, key=lambda x: x[1], reverse=True):
            percentage = count / total_files * 100
            print(f"  {telescope or 'NULL':<20}: {count:>5} files ({percentage:5.1f}%)")
        
        # Camera analysis
        camera_counts = session.query(
            FitsFile.camera, func.count(FitsFile.id)
        ).group_by(FitsFile.camera).all()
        
        print("\nCamera Distribution:")
        for camera, count in sorted(camera_counts, key=lambda x: x[1], reverse=True):
            percentage = count / total_files * 100
            print(f"  {camera or 'NULL':<20}: {count:>5} files ({percentage:5.1f}%)")
        
        # Filter analysis
        filter_counts = session.query(
            FitsFile.filter, func.count(FitsFile.id)
        ).group_by(FitsFile.filter).all()
        
        print("\nFilter Distribution:")
        for filter_name, count in sorted(filter_counts, key=lambda x: x[1], reverse=True):
            percentage = count / total_files * 100
            print(f"  {filter_name or 'NULL':<20}: {count:>5} files ({percentage:5.1f}%)")
        
        # Specific recommendations
        print("\n" + "=" * 60)
        print("RECOMMENDATIONS")
        print("=" * 60)
        
        # Count UNKNOWN telescopes
        unknown_telescopes = session.query(FitsFile).filter(
            FitsFile.telescope == 'UNKNOWN'
        ).count()
        
        # Count unrecognized telescopes (not in known list)
        known_telescope_names = [tel.scope for tel in telescopes]
        unrecognized_telescopes = session.query(FitsFile).filter(
            FitsFile.telescope.notin_(known_telescope_names + ['UNKNOWN', None])
        ).count()
        
        # Count missing exposures in DARK frames
        dark_missing_exposure = session.query(FitsFile).filter(
            FitsFile.frame_type == 'DARK',
            FitsFile.exposure.is_(None)
        ).count()
        
        # Count UNKNOWN filters in FLAT frames
        flat_unknown_filters = session.query(FitsFile).filter(
            FitsFile.frame_type == 'FLAT',
            FitsFile.filter == 'UNKNOWN'
        ).count()
        
        # Count unrecognized filters in FLAT frames
        known_filter_names = list(filter_mappings.values())
        flat_unrecognized_filters = session.query(FitsFile).filter(
            FitsFile.frame_type == 'FLAT',
            FitsFile.filter.notin_(known_filter_names + ['UNKNOWN', None])
        ).count()
        
        # Sample some problematic FLAT files for detailed analysis
        problem_flats = session.query(FitsFile).filter(
            FitsFile.frame_type == 'FLAT',
            FitsFile.validation_score < 95
        ).limit(10).all()
        
        print(f"\n1. TELESCOPE IDENTIFICATION:")
        print(f"   - {unknown_telescopes} files have 'UNKNOWN' telescope")
        print(f"   - {unrecognized_telescopes} files have unrecognized telescope names")
        print(f"   - Known telescopes: {', '.join(known_telescope_names)}")
        print(f"   - Check focal length matching in telescopes.json")
        
        print(f"\n2. FILTER ISSUES:")
        print(f"   - {flat_unknown_filters} FLAT frames have 'UNKNOWN' filter")
        print(f"   - {flat_unrecognized_filters} FLAT frames have unrecognized filter names")
        print(f"   - Known filters: {', '.join(known_filter_names[:10])}...")  # Show first 10
        
        print(f"\n3. EXPOSURE TIME ISSUES:")
        print(f"   - {dark_missing_exposure} DARK frames missing exposure time")
        
        # Show sample problematic FLAT files
        if problem_flats:
            print(f"\n4. SAMPLE PROBLEMATIC FLAT FILES:")
            print(f"   Score | Telescope    | Camera    | Filter    | File")
            print(f"   ------|--------------|-----------|-----------|------------------")
            for flat in problem_flats[:5]:
                score = flat.validation_score or 0
                telescope = (flat.telescope or 'NULL')[:12]
                camera = (flat.camera or 'NULL')[:9] 
                filter_name = (flat.filter or 'NULL')[:9]
                filename = flat.file[:18] + '...' if len(flat.file) > 18 else flat.file
                print(f"   {score:5.1f} | {telescope:<12} | {camera:<9} | {filter_name:<9} | {filename}")
        
        print(f"\n5. QUICK FIXES:")
        print(f"   - Run the enhanced validation for detailed breakdown")
        print(f"   - Check if telescope focal lengths in FITS match telescopes.json")
        print(f"   - Add missing filter mappings to filters.json")
        print(f"   - Consider manual review of unrecognized equipment names")
        
    finally:
        session.close()
        db_manager.close()


if __name__ == "__main__":
    try:
        analyze_validation_issues()
    except Exception as e:
        print(f"Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)