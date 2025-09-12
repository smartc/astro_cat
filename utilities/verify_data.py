#!/usr/bin/env python3
"""Verify database data with clear formatting."""

import sqlite3
from pathlib import Path

def verify_database(db_path: str):
    """Show database contents with clear formatting."""
    if not Path(db_path).exists():
        print(f"Database {db_path} does not exist")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get column names
    cursor.execute("PRAGMA table_info(fits_files)")
    columns = [row[1] for row in cursor.fetchall()]
    print("Available columns:", columns)
    print()
    
    # Check if obs_timestamp column exists
    cursor.execute("PRAGMA table_info(fits_files)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'obs_timestamp' in columns:
        cursor.execute("SELECT file, camera, telescope, obs_date, obs_timestamp, object, frame_type FROM fits_files")
        headers = f"{'File':<25} {'Camera':<10} {'Telescope':<10} {'Date':<12} {'Timestamp':<17} {'Object':<8} {'Type':<6}"
        separator = "-" * 95
    else:
        cursor.execute("SELECT file, camera, telescope, obs_date, object, frame_type FROM fits_files")
        headers = f"{'File':<25} {'Camera':<10} {'Telescope':<10} {'Date':<12} {'Object':<8} {'Type':<6}"
        separator = "-" * 80
    
    rows = cursor.fetchall()
    
    print(f"Found {len(rows)} records:")
    print(separator)
    print(headers)
    print(separator)
    
    for row in rows:
        if 'obs_timestamp' in columns and len(row) > 4:
            timestamp = row[4].strftime("%Y-%m-%d %H:%M") if row[4] else "None"
            print(f"{row[0]:<25} {row[1]:<10} {row[2]:<10} {row[3]:<12} {timestamp:<17} {row[5]:<8} {row[6]:<6}")
        else:
            print(f"{row[0]:<25} {row[1]:<10} {row[2]:<10} {row[3]:<12} {row[4]:<8} {row[5]:<6}")
    
    conn.close()

if __name__ == "__main__":
    verify_database("/mnt/calisto/Astro/fits_catalog.db")