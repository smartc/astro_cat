#!/usr/bin/env python3
"""
Migration: Add astrobin_id column to filter_mappings table.

This migration adds support for tracking AstroBin equipment IDs for filters.
"""

import sqlite3
import sys
from pathlib import Path


def migrate(db_path: str):
    """Add astrobin_id column to filter_mappings table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(filter_mappings)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'astrobin_id' in columns:
            print("✓ astrobin_id column already exists in filter_mappings table")
            return True

        # Add the column
        print("Adding astrobin_id column to filter_mappings table...")
        cursor.execute("""
            ALTER TABLE filter_mappings
            ADD COLUMN astrobin_id INTEGER
        """)

        conn.commit()
        print("✓ Successfully added astrobin_id column")
        return True

    except Exception as e:
        print(f"✗ Migration failed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    # Default database path
    db_path = "astrocat.db"

    # Allow custom path as command line argument
    if len(sys.argv) > 1:
        db_path = sys.argv[1]

    if not Path(db_path).exists():
        print(f"✗ Database not found: {db_path}")
        sys.exit(1)

    print(f"Running migration on: {db_path}")
    success = migrate(db_path)
    sys.exit(0 if success else 1)
