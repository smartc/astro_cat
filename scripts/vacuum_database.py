#!/usr/bin/env python3
"""
Vacuum Database - Reclaim wasted space

After Phase 3 migration, the database may be fragmented due to
table recreation. This script runs VACUUM to reclaim space.
"""

import sqlite3
import sys
from pathlib import Path


def vacuum_database(db_path):
    """Run VACUUM on database and report space saved."""

    print("="*60)
    print("Database Optimization - VACUUM")
    print("="*60)
    print(f"\nDatabase: {db_path}")
    print()

    if not db_path.exists():
        print(f"✗ Error: Database not found: {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get size before VACUUM
    print("Analyzing database...")
    cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
    size_before = cursor.fetchone()[0]
    size_before_mb = size_before / (1024 * 1024)

    print(f"  Current size: {size_before_mb:.2f} MB")
    print()

    # Run VACUUM
    print("Running VACUUM (this may take a few seconds)...")
    cursor.execute("VACUUM")
    conn.close()

    # Get size after VACUUM
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
    size_after = cursor.fetchone()[0]
    conn.close()

    size_after_mb = size_after / (1024 * 1024)
    size_saved = size_before - size_after
    size_saved_mb = size_saved / (1024 * 1024)

    print()
    print("="*60)
    print("✓ VACUUM Complete!")
    print("="*60)
    print(f"  Size before: {size_before_mb:.2f} MB")
    print(f"  Size after:  {size_after_mb:.2f} MB")

    if size_saved > 0:
        print(f"  Space reclaimed: {size_saved_mb:.2f} MB ({size_saved * 100 / size_before:.1f}%)")
    else:
        print("  No space reclaimed (database was already optimal)")

    print()
    print("Database is now optimized!")
    print("="*60)

    return 0


def main():
    """Main entry point."""
    db_path = Path.home() / 'Astro' / 'fits_catalog.db'
    return vacuum_database(db_path)


if __name__ == '__main__':
    sys.exit(main())
