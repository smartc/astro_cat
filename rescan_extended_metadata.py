#!/usr/bin/env python3
"""
Rescan existing FITS files to populate extended metadata fields.

This utility reads FITS headers from files already in the database
and updates their records with extended metadata (weather, guiding, etc.).

Usage:
    python rescan_extended_metadata.py [options]
    
Options:
    --limit N           Process only N files (default: all)
    --dry-run          Show what would be updated without changing DB
    --frame-type TYPE  Only process specific frame type (LIGHT, DARK, etc.)
    --camera NAME      Only process files from specific camera
    --missing-only     Only update records where extended fields are NULL
    --config PATH      Path to config file (default: config.json)
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

from astropy.io import fits
from sqlalchemy import and_, or_
from tqdm import tqdm

# Import project modules
from config import load_config
from models import DatabaseManager, FitsFile
from processing.metadata_extractor import extract_extended_metadata

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ExtendedMetadataRescanner:
    """Rescans FITS files to populate extended metadata."""
    
    def __init__(self, config):
        self.config = config
        self.db_manager = DatabaseManager(config.database.connection_string)
        self.stats = {
            'total': 0,
            'updated': 0,
            'skipped_missing': 0,
            'skipped_error': 0,
            'fields_populated': {}
        }
    
    def build_query(self, session, frame_type: Optional[str] = None,
                   camera: Optional[str] = None, 
                   missing_only: bool = False):
        """Build query with optional filters."""
        query = session.query(FitsFile)
        
        # Filter by frame type
        if frame_type:
            query = query.filter(FitsFile.frame_type == frame_type.upper())
        
        # Filter by camera
        if camera:
            query = query.filter(FitsFile.camera == camera)
        
        # Only update records where extended fields are NULL
        if missing_only:
            query = query.filter(
                and_(
                    FitsFile.gain.is_(None),
                    FitsFile.software_creator.is_(None)
                )
            )
        
        return query
    
    def get_file_path(self, record: FitsFile) -> Optional[Path]:
        """Construct full file path from database record."""
        file_path = Path(record.folder) / record.file
        
        if file_path.exists():
            return file_path
        
        # Try original location if moved
        if record.orig_folder and record.orig_file:
            orig_path = Path(record.orig_folder) / record.orig_file
            if orig_path.exists():
                return orig_path
        
        return None
    
    def extract_and_update(self, record: FitsFile, dry_run: bool = False) -> bool:
        """
        Extract extended metadata and update database record.
        
        Returns:
            True if updated, False if skipped
        """
        # Get file path
        file_path = self.get_file_path(record)
        
        if not file_path:
            logger.debug(f"File not found: {record.file}")
            self.stats['skipped_missing'] += 1
            return False
        
        try:
            # Read FITS header
            with fits.open(file_path, memmap=True, lazy_load_hdus=True) as hdul:
                header = hdul[0].header
                
                # Extract extended metadata
                extended = extract_extended_metadata(header)
                
                # Update record fields
                if not dry_run:
                    for key, value in extended.items():
                        if value is not None:
                            setattr(record, key, value)
                            
                            # Track which fields get populated
                            if key not in self.stats['fields_populated']:
                                self.stats['fields_populated'][key] = 0
                            self.stats['fields_populated'][key] += 1
                
                return True
                
        except Exception as e:
            logger.error(f"Error processing {record.file}: {e}")
            self.stats['skipped_error'] += 1
            return False
    
    def rescan(self, limit: Optional[int] = None, 
              frame_type: Optional[str] = None,
              camera: Optional[str] = None,
              missing_only: bool = False,
              dry_run: bool = False):
        """
        Rescan files and update database.
        
        Args:
            limit: Maximum number of files to process
            frame_type: Filter by frame type
            camera: Filter by camera name
            missing_only: Only update NULL extended fields
            dry_run: Don't commit changes
        """
        session = self.db_manager.get_session()
        
        try:
            # Build query
            query = self.build_query(session, frame_type, camera, missing_only)
            
            # Apply limit
            if limit:
                query = query.limit(limit)
            
            # Get records
            records = query.all()
            self.stats['total'] = len(records)
            
            if self.stats['total'] == 0:
                logger.info("No records found matching criteria")
                return
            
            logger.info(f"Processing {self.stats['total']} files...")
            if dry_run:
                logger.info("DRY RUN - No changes will be committed")
            
            # Process each record
            with tqdm(total=self.stats['total'], desc="Scanning files") as pbar:
                for record in records:
                    if self.extract_and_update(record, dry_run):
                        self.stats['updated'] += 1
                    
                    pbar.update(1)
                    
                    # Commit in batches of 100
                    if not dry_run and self.stats['updated'] % 100 == 0:
                        session.commit()
            
            # Final commit
            if not dry_run:
                session.commit()
                logger.info("Changes committed to database")
            
        except Exception as e:
            session.rollback()
            logger.error(f"Rescan failed: {e}")
            raise
        finally:
            session.close()
    
    def print_summary(self):
        """Print summary statistics."""
        print("\n" + "=" * 70)
        print("RESCAN SUMMARY")
        print("=" * 70)
        print(f"Total files processed:    {self.stats['total']}")
        print(f"Successfully updated:     {self.stats['updated']}")
        print(f"Skipped (missing):        {self.stats['skipped_missing']}")
        print(f"Skipped (error):          {self.stats['skipped_error']}")
        print()
        
        if self.stats['fields_populated']:
            print("Fields populated (with non-NULL values):")
            # Sort by count
            sorted_fields = sorted(
                self.stats['fields_populated'].items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            for field, count in sorted_fields[:10]:  # Show top 10
                print(f"  {field:25s} {count:6d} files")
            
            if len(sorted_fields) > 10:
                print(f"  ... and {len(sorted_fields) - 10} more fields")
        print("=" * 70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Rescan FITS files to populate extended metadata'
    )
    parser.add_argument(
        '--config',
        default='config.json',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of files to process'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be updated without changing database'
    )
    parser.add_argument(
        '--frame-type',
        choices=['LIGHT', 'DARK', 'FLAT', 'BIAS'],
        help='Only process specific frame type'
    )
    parser.add_argument(
        '--camera',
        help='Only process files from specific camera'
    )
    parser.add_argument(
        '--missing-only',
        action='store_true',
        help='Only update records where extended fields are NULL'
    )
    
    args = parser.parse_args()
    
    try:
        # Load configuration
        logger.info(f"Loading configuration from {args.config}")
        config, cameras, telescopes, filter_mappings = load_config(args.config)
        
        # Create rescanner
        rescanner = ExtendedMetadataRescanner(config)
        
        # Display scan parameters
        logger.info("Scan parameters:")
        if args.limit:
            logger.info(f"  Limit: {args.limit} files")
        else:
            logger.info("  Limit: All files")
        
        if args.frame_type:
            logger.info(f"  Frame type: {args.frame_type}")
        
        if args.camera:
            logger.info(f"  Camera: {args.camera}")
        
        if args.missing_only:
            logger.info("  Mode: Update only NULL fields")
        
        if args.dry_run:
            logger.info("  DRY RUN MODE - No changes will be saved")
        
        print()
        
        # Run rescan
        rescanner.rescan(
            limit=args.limit,
            frame_type=args.frame_type,
            camera=args.camera,
            missing_only=args.missing_only,
            dry_run=args.dry_run
        )
        
        # Print summary
        rescanner.print_summary()
        
        if args.dry_run:
            print("\nℹ  DRY RUN completed - no changes were saved")
            print("   Run without --dry-run to apply changes")
        else:
            print("\n✓ Rescan completed successfully!")
        
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Rescan failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()