#!/usr/bin/env python3
"""
Fix Foreign Key Constraints After Phase 3 Migration

The Phase 3 migration recreated fits_files table, which can cause
foreign key mismatch errors in processing_session_files.

This script recreates the processing_session_files table with correct
foreign key constraints.
"""

import sqlite3
import sys
from pathlib import Path


def check_foreign_keys(cursor):
    """Check current foreign key definitions."""
    print("="*60)
    print("Checking Foreign Key Constraints")
    print("="*60)

    # Check FK constraints on processing_session_files
    cursor.execute("PRAGMA foreign_key_list('processing_session_files')")
    fks = cursor.fetchall()

    print("\nCurrent foreign keys on processing_session_files:")
    for fk in fks:
        print(f"  ID: {fk[0]}, Seq: {fk[1]}, Table: {fk[2]}, From: {fk[3]}, To: {fk[4]}")

    # Check if fits_files has proper primary key
    cursor.execute("PRAGMA table_info('fits_files')")
    columns = cursor.fetchall()

    print("\nfits_files primary key:")
    for col in columns:
        if col[5] == 1:  # pk column
            print(f"  Column: {col[1]}, Type: {col[2]}, PK: {col[5]}")

    return fks


def recreate_processing_session_files(cursor):
    """Recreate processing_session_files table with correct foreign keys."""
    print("\n" + "="*60)
    print("Recreating processing_session_files Table")
    print("="*60)

    # Get current row count
    cursor.execute("SELECT COUNT(*) FROM processing_session_files")
    row_count = cursor.fetchone()[0]
    print(f"\nCurrent rows: {row_count}")

    # Create new table with correct schema
    print("\nCreating processing_session_files_new...")
    cursor.execute("""
        CREATE TABLE processing_session_files_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            processing_session_id VARCHAR(50) NOT NULL,
            fits_file_id INTEGER NOT NULL,
            original_path VARCHAR(500) NOT NULL,
            original_filename VARCHAR(255) NOT NULL,
            staged_path VARCHAR(500) NOT NULL,
            staged_filename VARCHAR(255) NOT NULL,
            subfolder VARCHAR(50) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            file_size INTEGER,
            frame_type VARCHAR(20),

            FOREIGN KEY (processing_session_id)
                REFERENCES processing_sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (fits_file_id)
                REFERENCES fits_files(id) ON DELETE CASCADE
        )
    """)

    # Copy data
    print("Copying data...")
    cursor.execute("""
        INSERT INTO processing_session_files_new
            (id, processing_session_id, fits_file_id, original_path,
             original_filename, staged_path, staged_filename, subfolder,
             created_at, file_size, frame_type)
        SELECT
            id, processing_session_id, fits_file_id, original_path,
            original_filename, staged_path, staged_filename, subfolder,
            created_at, file_size, frame_type
        FROM processing_session_files
    """)

    copied_count = cursor.execute("SELECT COUNT(*) FROM processing_session_files_new").fetchone()[0]
    print(f"Copied {copied_count} rows")

    if copied_count != row_count:
        raise Exception(f"Row count mismatch! Original: {row_count}, Copied: {copied_count}")

    # Drop old table and rename new one
    print("Replacing old table...")
    cursor.execute("DROP TABLE processing_session_files")
    cursor.execute("ALTER TABLE processing_session_files_new RENAME TO processing_session_files")

    # Recreate indexes
    print("Creating indexes...")
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_processing_file_session
        ON processing_session_files(processing_session_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_processing_file_fits
        ON processing_session_files(fits_file_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_processing_file_type
        ON processing_session_files(frame_type)
    """)

    print("✓ Table recreated successfully")


def verify_fix(cursor):
    """Verify the fix worked."""
    print("\n" + "="*60)
    print("Verifying Fix")
    print("="*60)

    # Check new foreign keys
    cursor.execute("PRAGMA foreign_key_list('processing_session_files')")
    fks = cursor.fetchall()

    print("\nNew foreign keys on processing_session_files:")
    for fk in fks:
        print(f"  ID: {fk[0]}, Seq: {fk[1]}, Table: {fk[2]}, From: {fk[3]}, To: {fk[4]}")

    # Check row count
    cursor.execute("SELECT COUNT(*) FROM processing_session_files")
    count = cursor.fetchone()[0]
    print(f"\nFinal row count: {count}")

    # Test a foreign key constraint
    print("\nTesting foreign key constraints...")
    cursor.execute("""
        SELECT COUNT(*)
        FROM processing_session_files psf
        JOIN fits_files f ON psf.fits_file_id = f.id
    """)
    join_count = cursor.fetchone()[0]
    print(f"  Rows with valid fits_file_id: {join_count}")

    cursor.execute("""
        SELECT COUNT(*)
        FROM processing_session_files psf
        JOIN processing_sessions ps ON psf.processing_session_id = ps.id
    """)
    join_count2 = cursor.fetchone()[0]
    print(f"  Rows with valid processing_session_id: {join_count2}")

    print("\n✓ Foreign keys verified")


def main():
    """Main entry point."""
    db_path = Path.home() / 'Astro' / 'fits_catalog.db'

    print("="*60)
    print("FOREIGN KEY CONSTRAINT FIX")
    print("="*60)
    print(f"\nDatabase: {db_path}\n")

    if not db_path.exists():
        print(f"✗ Error: Database not found: {db_path}")
        return 1

    # Create backup
    backup_path = db_path.parent / f"{db_path.stem}_backup_fk_fix.db"
    print(f"Creating backup: {backup_path}")
    import shutil
    shutil.copy2(db_path, backup_path)
    print("✓ Backup created")

    conn = sqlite3.connect(db_path)

    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")

    cursor = conn.cursor()

    try:
        # Step 1: Check current state
        check_foreign_keys(cursor)

        # Step 2: Recreate table
        recreate_processing_session_files(cursor)

        # Step 3: Verify
        verify_fix(cursor)

        # Commit changes
        conn.commit()

        print("\n" + "="*60)
        print("✓ FOREIGN KEY FIX COMPLETE")
        print("="*60)
        print("""
Next steps:
1. Restart your web server
2. Try creating a new processing session
3. It should now work without foreign key errors

If issues persist, restore from backup:
  cp {0} {1}
        """.format(backup_path, db_path))

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        print("\nChanges rolled back. Database unchanged.")
        return 1
    finally:
        conn.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
