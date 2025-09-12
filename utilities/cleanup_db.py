#!/usr/bin/env python3
"""Clean up database for fresh scan."""

import sqlite3
import sys
from pathlib import Path

def cleanup_database(db_path: str):
    """Clear all FITS files from database."""
    if not Path(db_path).exists():
        print(f"Database {db_path} does not exist")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get current count
    cursor.execute("SELECT COUNT(*) FROM fits_files")
    count = cursor.fetchone()[0]
    print(f"Found {count} existing records")
    
    if count > 0:
        response = input("Delete all existing records? (y/n): ").lower().strip()
        if response == 'y':
            cursor.execute("DELETE FROM fits_files")
            cursor.execute("DELETE FROM process_log")
            conn.commit()
            print("Database cleaned successfully")
        else:
            print("Cleanup cancelled")
    else:
        print("Database is already empty")
    
    conn.close()

if __name__ == "__main__":
    db_path = "/mnt/calisto/Astro/fits_catalog.db"
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    cleanup_database(db_path)