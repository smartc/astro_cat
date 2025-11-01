#!/usr/bin/env python3
"""
Diagnose why the database is 47 MB.
Checks for duplicate data, index sizes, and table sizes.
"""
import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import load_config

# Load config to get database path
config, _, _, _ = load_config()
db_path = config.paths.database_path

print("=" * 70)
print("DATABASE SIZE ANALYSIS")
print("=" * 70)
print(f"Database: {db_path}")

# Get database file size
db_size_mb = Path(db_path).stat().st_size / 1024 / 1024
print(f"Actual file size: {db_size_mb:.2f} MB")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get row counts
print("\n=== ROW COUNTS ===")
tables = [
    'fits_files',
    'imaging_sessions',
    'processing_sessions',
    'processed_files',
    'processing_session_files',
    's3_backup_archives',
    's3_backup_session_notes',
    's3_backup_processed_file_records',
    's3_backup_processing_session_summaries'
]

total_rows = 0
for table in tables:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        total_rows += count
        print(f"{table:45s}: {count:,}")
    except sqlite3.OperationalError:
        print(f"{table:45s}: (table not found)")

print(f"\nTotal rows across all tables: {total_rows:,}")

# Check for indexes
print("\n=== INDEXES ===")
cursor.execute("""
    SELECT name, tbl_name
    FROM sqlite_master
    WHERE type = 'index' AND sql IS NOT NULL
    ORDER BY tbl_name, name
""")
indexes = cursor.fetchall()
print(f"Total indexes: {len(indexes)}")
for name, table in indexes:
    print(f"  • {name:40s} on {table}")

# Check for duplicate records
print("\n=== CHECKING FOR DUPLICATES ===")

# fits_files
cursor.execute("SELECT COUNT(*) FROM fits_files")
fits_count = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(DISTINCT id) FROM fits_files")
fits_unique = cursor.fetchone()[0]

if fits_count != fits_unique:
    print(f"⚠️  WARNING: fits_files has {fits_count - fits_unique:,} duplicate IDs!")
else:
    print(f"✓ fits_files: {fits_count:,} rows, all unique IDs")

# imaging_sessions
cursor.execute("SELECT COUNT(*) FROM imaging_sessions")
sessions_count = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(DISTINCT id) FROM imaging_sessions")
sessions_unique = cursor.fetchone()[0]

if sessions_count != sessions_unique:
    print(f"⚠️  WARNING: imaging_sessions has {sessions_count - sessions_unique:,} duplicate IDs!")
else:
    print(f"✓ imaging_sessions: {sessions_count:,} rows, all unique IDs")

# Check database statistics
print("\n=== DATABASE STATISTICS ===")
cursor.execute("PRAGMA page_size")
page_size = cursor.fetchone()[0]
print(f"Page size: {page_size:,} bytes")

cursor.execute("PRAGMA page_count")
page_count = cursor.fetchone()[0]
print(f"Page count: {page_count:,}")
print(f"Calculated size: {page_size * page_count / 1024 / 1024:.2f} MB")

cursor.execute("PRAGMA freelist_count")
freelist = cursor.fetchone()[0]
print(f"Free pages: {freelist:,} ({freelist * page_size / 1024 / 1024:.2f} MB)")

# Check if ANALYZE has bloated the database
cursor.execute("SELECT COUNT(*) FROM sqlite_stat1")
stat_count = cursor.fetchone()[0]
print(f"\nANALYZE statistics entries: {stat_count:,}")

# List all tables and their approximate sizes
print("\n=== ALL TABLES (including internal) ===")
cursor.execute("""
    SELECT name, type
    FROM sqlite_master
    WHERE type IN ('table', 'index')
    ORDER BY type, name
""")
all_objects = cursor.fetchall()

tables_found = []
indexes_found = []
for name, obj_type in all_objects:
    if obj_type == 'table':
        tables_found.append(name)
    else:
        indexes_found.append(name)

print(f"\nTables found: {len(tables_found)}")
for table in tables_found:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table:45s}: {count:,} rows")
    except:
        print(f"  {table:45s}: (error reading)")

print(f"\nIndexes found: {len(indexes_found)}")

# Estimate data size
print("\n=== SIZE ESTIMATE ===")
print(f"Total rows in main tables: {total_rows:,}")
print(f"Database file size: {db_size_mb:.2f} MB")
print(f"Average bytes per row: {(db_size_mb * 1024 * 1024) / total_rows if total_rows > 0 else 0:.0f}")

# Check for bloat
expected_size_mb = total_rows * 1000 / 1024 / 1024  # Rough estimate: 1KB per row
print(f"\nExpected size (rough): {expected_size_mb:.2f} MB")
if db_size_mb > expected_size_mb * 2:
    print(f"⚠️  Database may be bloated (actual is {db_size_mb / expected_size_mb:.1f}x expected)")
else:
    print(f"✓ Size seems reasonable")

conn.close()

print("\n" + "=" * 70)
