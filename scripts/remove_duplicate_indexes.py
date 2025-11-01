#!/usr/bin/env python3
"""
Remove duplicate indexes from the database.

Many tables have both manual indexes (idx_*) and SQLAlchemy auto-generated
indexes (ix_*) on the same columns. This script removes the duplicates.
"""

import sys
import sqlite3
from pathlib import Path
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import load_config

def get_index_info(cursor, index_name):
    """Get the columns that an index indexes."""
    cursor.execute(f"PRAGMA index_info({index_name})")
    columns = [row[2] for row in cursor.fetchall()]
    return tuple(columns)

def find_duplicate_indexes(cursor):
    """Find all duplicate indexes grouped by table and columns."""
    # Get all indexes
    cursor.execute("""
        SELECT name, tbl_name, sql
        FROM sqlite_master
        WHERE type = 'index' AND sql IS NOT NULL
        ORDER BY tbl_name, name
    """)
    indexes = cursor.fetchall()

    # Group indexes by table and columns
    table_indexes = defaultdict(lambda: defaultdict(list))

    for idx_name, table_name, sql in indexes:
        columns = get_index_info(cursor, idx_name)
        if columns:  # Skip if we can't get column info
            key = (table_name, columns)
            table_indexes[table_name][columns].append(idx_name)

    return table_indexes

def analyze_duplicates(table_indexes):
    """Analyze and categorize duplicate indexes."""
    duplicates = []

    for table_name, columns_dict in table_indexes.items():
        for columns, index_names in columns_dict.items():
            if len(index_names) > 1:
                # Found duplicates!
                # Prefer ix_* (SQLAlchemy) over idx_* (manual)
                ix_indexes = [n for n in index_names if n.startswith('ix_')]
                idx_indexes = [n for n in index_names if n.startswith('idx_')]
                other_indexes = [n for n in index_names if not n.startswith('ix_') and not n.startswith('idx_')]

                # Decide which to keep and which to drop
                if ix_indexes:
                    # Keep SQLAlchemy auto-generated, drop manual ones
                    keep = ix_indexes[0]
                    drop = idx_indexes + other_indexes + ix_indexes[1:]
                elif idx_indexes:
                    # Keep first manual one, drop others
                    keep = idx_indexes[0]
                    drop = idx_indexes[1:] + other_indexes
                else:
                    # Keep first, drop rest
                    keep = index_names[0]
                    drop = index_names[1:]

                if drop:
                    duplicates.append({
                        'table': table_name,
                        'columns': columns,
                        'keep': keep,
                        'drop': drop
                    })

    return duplicates

def main():
    import argparse

    parser = argparse.ArgumentParser(description='Remove duplicate indexes from database')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be removed without doing it')
    parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation prompt')
    args = parser.parse_args()

    # Load config to get database path
    config, _, _, _ = load_config()
    db_path = config.paths.database_path

    print("=" * 70)
    print("DUPLICATE INDEX REMOVAL")
    print("=" * 70)
    print(f"Database: {db_path}")

    if args.dry_run:
        print("MODE: DRY RUN (no changes will be made)")

    # Get initial size
    initial_size = Path(db_path).stat().st_size / 1024 / 1024
    print(f"Initial size: {initial_size:.2f} MB")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get initial index count
    cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL")
    initial_count = cursor.fetchone()[0]
    print(f"Initial indexes: {initial_count}")

    # Find duplicates
    print("\nAnalyzing indexes...")
    table_indexes = find_duplicate_indexes(cursor)
    duplicates = analyze_duplicates(table_indexes)

    if not duplicates:
        print("\n✓ No duplicate indexes found!")
        conn.close()
        return

    # Display duplicates
    print(f"\n=== FOUND {len(duplicates)} DUPLICATE INDEX GROUPS ===\n")

    total_to_drop = 0
    for dup in duplicates:
        total_to_drop += len(dup['drop'])
        print(f"Table: {dup['table']}")
        print(f"  Columns: {', '.join(dup['columns'])}")
        print(f"  KEEP:    {dup['keep']}")
        for idx in dup['drop']:
            print(f"  DROP:    {idx}")
        print()

    print(f"Total indexes to drop: {total_to_drop}")

    if args.dry_run:
        print("\nDRY RUN: No changes made.")
        print(f"Run without --dry-run to actually remove {total_to_drop} duplicate indexes")
        conn.close()
        return

    # Confirm
    if not args.yes:
        response = input(f"\nDrop {total_to_drop} duplicate indexes? (yes/no): ")
        if response.lower() not in ('yes', 'y'):
            print("Cancelled.")
            conn.close()
            return

    # Drop indexes
    print("\nDropping duplicate indexes...")
    dropped_count = 0

    for dup in duplicates:
        for idx_name in dup['drop']:
            try:
                cursor.execute(f"DROP INDEX {idx_name}")
                dropped_count += 1
                print(f"  ✓ Dropped {idx_name}")
            except sqlite3.Error as e:
                print(f"  ✗ Failed to drop {idx_name}: {e}")

    conn.commit()

    # Vacuum to reclaim space
    print("\nVacuuming database to reclaim space...")
    cursor.execute("VACUUM")

    # Get final stats
    cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL")
    final_count = cursor.fetchone()[0]

    conn.close()

    final_size = Path(db_path).stat().st_size / 1024 / 1024

    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"Indexes before:  {initial_count}")
    print(f"Indexes after:   {final_count}")
    print(f"Indexes dropped: {dropped_count}")
    print(f"\nSize before:     {initial_size:.2f} MB")
    print(f"Size after:      {final_size:.2f} MB")
    print(f"Space saved:     {initial_size - final_size:.2f} MB ({(initial_size - final_size) / initial_size * 100:.1f}%)")
    print("\n✓ Duplicate indexes removed successfully!")
    print("=" * 70)

if __name__ == '__main__':
    main()
