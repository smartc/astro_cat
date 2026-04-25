#!/usr/bin/env python3
"""
Migration: Add any columns present in the SQLAlchemy models but missing from
the database tables.

This handles databases that were created or last migrated before new columns
were added to the models (e.g. extended metadata fields, Boltwood sensor
columns, quality metrics).  Safe to run multiple times — it skips columns
that already exist.

Usage:
    python migrations/add_missing_columns.py /path/to/fits_catalog.db
    python migrations/add_missing_columns.py  # uses default ~/astro/fits_catalog.db
"""

import sys
import sqlite3
from pathlib import Path

# Allow running from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from models import Base, DatabaseManager


def migrate(db_path: str) -> bool:
    db_path = Path(db_path).expanduser()
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return False

    print(f"Database: {db_path}")

    # Use raw sqlite3 to inspect existing columns before ORM touches them
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    added = 0
    skipped = 0

    try:
        for table_name, table in Base.metadata.tables.items():
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            if not cursor.fetchone():
                continue

            cursor.execute(f"PRAGMA table_info({table_name})")
            existing = {row[1] for row in cursor.fetchall()}

            for column in table.columns:
                if column.name in existing:
                    skipped += 1
                    continue

                # Derive a SQLite type string from the SQLAlchemy type
                sa_type = column.type
                type_name = type(sa_type).__name__.upper()
                type_map = {
                    "INTEGER": "INTEGER",
                    "FLOAT": "REAL",
                    "BOOLEAN": "INTEGER",
                    "STRING": "TEXT",
                    "TEXT": "TEXT",
                    "DATETIME": "DATETIME",
                }
                sqlite_type = type_map.get(type_name, "TEXT")

                try:
                    cursor.execute(
                        f"ALTER TABLE {table_name} ADD COLUMN {column.name} {sqlite_type}"
                    )
                    print(f"  + {table_name}.{column.name} ({sqlite_type})")
                    added += 1
                except sqlite3.OperationalError as e:
                    print(f"  ! {table_name}.{column.name}: {e}")

        conn.commit()
    finally:
        conn.close()

    print(f"\nAdded {added} column(s), skipped {skipped} existing column(s).")
    return True


if __name__ == "__main__":
    if len(sys.argv) > 1:
        db = sys.argv[1]
    else:
        db = "~/astro/fits_catalog.db"

    success = migrate(db)
    sys.exit(0 if success else 1)
