#!/usr/bin/env python3
"""
Reconcile the FITS library directory against the database.

Walks image_dir (migrated files) and compares every .fits file found
on disk against database records, producing two lists:

  1. On disk, NOT in database  — files that exist but have no DB record
                                 (likely lost during DB recovery)
  2. In database, NOT on disk  — DB records pointing to missing files
                                 (orphaned records / moved files)

Also reports how many files in the DB have a NULL imaging_session_id.

Usage:
    python migrations/reconcile_library.py [config.json]
    python migrations/reconcile_library.py        # uses default config.json
"""

import sys
import sqlite3
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import load_config

FITS_SUFFIXES = {'.fits', '.fit', '.fts'}


def reconcile(config_path: str = "config.json"):
    config, *_ = load_config(config_path)

    db_path = Path(config.paths.database_path).expanduser().resolve()
    image_dir = Path(config.paths.image_dir).expanduser().resolve()

    print(f"Database : {db_path}")
    print(f"Library  : {image_dir}")
    print()

    if not db_path.exists():
        print(f"ERROR: database not found: {db_path}")
        return False
    if not image_dir.exists():
        print(f"ERROR: library directory not found: {image_dir}")
        return False

    # ── 1. Collect all FITS files on disk ────────────────────────────────
    print("Scanning library directory...", flush=True)
    disk_files: set[Path] = set()
    for p in image_dir.rglob("*"):
        if p.suffix.lower() in FITS_SUFFIXES and p.is_file():
            disk_files.add(p.resolve())
    print(f"  {len(disk_files):,} FITS files on disk")

    # ── 2. Load DB records ────────────────────────────────────────────────
    print("Loading database records...", flush=True)
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cursor.execute("SELECT folder, file FROM fits_files")
    rows = cursor.fetchall()
    db_paths: set[Path] = set()
    for folder, filename in rows:
        if folder and filename:
            db_paths.add(Path(folder).resolve() / filename)

    cursor.execute(
        "SELECT COUNT(*) FROM fits_files WHERE imaging_session_id IS NULL"
    )
    null_session_count = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM fits_files WHERE imaging_session_id IS NOT NULL"
    )
    assigned_session_count = cursor.fetchone()[0]

    conn.close()
    print(f"  {len(db_paths):,} records in database")
    print(f"  {assigned_session_count:,} records with imaging session assigned")
    print(f"  {null_session_count:,} records with NULL imaging_session_id")

    # ── 3. Compare ────────────────────────────────────────────────────────
    on_disk_not_in_db = sorted(disk_files - db_paths)
    in_db_not_on_disk = sorted(db_paths - disk_files)

    print()
    print("=" * 70)
    print("RECONCILIATION RESULTS")
    print("=" * 70)
    print(f"Files on disk, not in database:  {len(on_disk_not_in_db):>7,}")
    print(f"DB records with no file on disk: {len(in_db_not_on_disk):>7,}")
    print(f"Files with no session assigned:  {null_session_count:>7,}")

    # ── 4. Print samples ──────────────────────────────────────────────────
    SAMPLE = 30

    if on_disk_not_in_db:
        print(f"\nON DISK, NOT IN DATABASE (first {SAMPLE}):")
        for p in on_disk_not_in_db[:SAMPLE]:
            print(f"  {p}")
        if len(on_disk_not_in_db) > SAMPLE:
            print(f"  ... and {len(on_disk_not_in_db) - SAMPLE:,} more (see report file)")

    if in_db_not_on_disk:
        print(f"\nIN DATABASE, NOT ON DISK (first {SAMPLE}):")
        for p in list(in_db_not_on_disk)[:SAMPLE]:
            print(f"  {p}")
        if len(in_db_not_on_disk) > SAMPLE:
            print(f"  ... and {len(in_db_not_on_disk) - SAMPLE:,} more (see report file)")

    # ── 5. Write full report ──────────────────────────────────────────────
    report_path = Path(f"reconcile_report_{datetime.now():%Y%m%d_%H%M%S}.txt")
    with open(report_path, "w") as f:
        f.write("Reconciliation Report\n")
        f.write(f"Generated : {datetime.now()}\n")
        f.write(f"Database  : {db_path}\n")
        f.write(f"Library   : {image_dir}\n\n")
        f.write(f"Files on disk              : {len(disk_files):,}\n")
        f.write(f"Records in database        : {len(db_paths):,}\n")
        f.write(f"On disk, not in database   : {len(on_disk_not_in_db):,}\n")
        f.write(f"In database, not on disk   : {len(in_db_not_on_disk):,}\n")
        f.write(f"NULL imaging_session_id    : {null_session_count:,}\n\n")

        if on_disk_not_in_db:
            f.write("ON DISK, NOT IN DATABASE:\n")
            for p in on_disk_not_in_db:
                f.write(f"  {p}\n")
            f.write("\n")

        if in_db_not_on_disk:
            f.write("IN DATABASE, NOT ON DISK:\n")
            for p in in_db_not_on_disk:
                f.write(f"  {p}\n")
            f.write("\n")

    print(f"\nFull report written to: {report_path}")
    return True


if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    success = reconcile(config_path)
    sys.exit(0 if success else 1)
