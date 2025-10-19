#!/usr/bin/env python3
"""
Command-line interface for processed file cataloger.

Usage:
    python -m processed_catalog.cli --processing-dir /path/to/processing
    python -m processed_catalog.cli --session-id 20241015_ABC123
    python -m processed_catalog.cli --help
"""

import argparse
import logging
import sys
from pathlib import Path

from .cataloger import ProcessedFileCataloger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Catalog processed astrophotography files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan all processing sessions
  python -m processed_catalog.cli --processing-dir /mnt/ganymede/Astro/Processing
  
  # Scan specific session
  python -m processed_catalog.cli --session-id 20241015_ABC123
  
  # Initialize database only
  python -m processed_catalog.cli --init-db --database /path/to/db.sqlite
        """
    )
    
    parser.add_argument(
        '--processing-dir',
        type=str,
        help='Root processing directory (required unless using --session-id)'
    )
    
    parser.add_argument(
        '--session-id',
        type=str,
        help='Process only this specific session ID'
    )
    
    parser.add_argument(
        '--database',
        type=str,
        default='fits_catalog.db',
        help='Path to SQLite database (default: fits_catalog.db)'
    )
    
    parser.add_argument(
        '--init-db',
        action='store_true',
        help='Initialize database tables and exit'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create cataloger
    cataloger = ProcessedFileCataloger(args.database)
    
    # Initialize database if requested
    if args.init_db:
        cataloger.init_database()
        logger.info("Database initialized successfully")
        return 0
    
    # Validate arguments
    if not args.processing_dir and not args.session_id:
        parser.error("Either --processing-dir or --session-id is required")
        return 1
    
    # Determine processing directory
    if args.processing_dir:
        processing_dir = Path(args.processing_dir)
        if not processing_dir.exists():
            logger.error(f"Processing directory not found: {processing_dir}")
            return 1
    else:
        # When using session-id, we'll get the path from the database
        processing_dir = Path('.')
    
    # Run cataloger
    try:
        cataloger.run(processing_dir, args.session_id)
        return 0
    except Exception as e:
        logger.error(f"Cataloging failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())