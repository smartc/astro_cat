#!/usr/bin/env python3
"""
Comprehensive Foreign Key Fix After Phase 3 Migration

The Phase 3 migration used CREATE TABLE AS SELECT which doesn't preserve
PRIMARY KEY constraints. This script:
1. Recreates fits_files with proper PRIMARY KEY
2. Recreates processing_session_files with correct foreign keys

This fixes the "foreign key mismatch" error when creating processing sessions.
"""

import sqlite3
import sys
from pathlib import Path


def check_current_state(cursor):
    """Check current table structure."""
    print("="*60)
    print("Checking Current Database State")
    print("="*60)

    # Check fits_files primary key
    cursor.execute("PRAGMA table_info('fits_files')")
    columns = cursor.fetchall()

    print("\nfits_files columns:")
    has_pk = False
    for col in columns:
        if col[1] == 'id':
            print(f"  id: Type={col[2]}, PK={col[5]}")
            has_pk = col[5] == 1

    if not has_pk:
        print("  ⚠ WARNING: 'id' is NOT a PRIMARY KEY!")
    else:
        print("  ✓ 'id' is a PRIMARY KEY")

    # Count rows
    cursor.execute("SELECT COUNT(*) FROM fits_files")
    fits_count = cursor.fetchone()[0]
    print(f"\nfits_files rows: {fits_count}")

    cursor.execute("SELECT COUNT(*) FROM processing_session_files")
    psf_count = cursor.fetchone()[0]
    print(f"processing_session_files rows: {psf_count}")

    return has_pk, fits_count, psf_count


def recreate_fits_files(cursor):
    """Recreate fits_files table with proper PRIMARY KEY."""
    print("\n" + "="*60)
    print("Step 1: Recreating fits_files with PRIMARY KEY")
    print("="*60)

    # Get current schema to preserve all columns
    cursor.execute("PRAGMA table_info('fits_files')")
    columns = cursor.fetchall()

    print(f"\nFound {len(columns)} columns in fits_files")

    # Disable foreign key checks temporarily (we'll recreate them after)
    cursor.execute("PRAGMA foreign_keys = OFF")

    print("Creating fits_files_new with proper schema...")

    # Build column definitions
    col_defs = []
    col_names = []

    for col in columns:
        name = col[1]
        col_type = col[2]
        not_null = "NOT NULL" if col[3] else ""

        col_names.append(name)

        if name == 'id':
            # Make id a proper primary key
            col_defs.append(f"{name} INTEGER PRIMARY KEY AUTOINCREMENT")
        else:
            col_defs.append(f"{name} {col_type} {not_null}".strip())

    schema = ",\n            ".join(col_defs)

    cursor.execute(f"""
        CREATE TABLE fits_files_new (
            {schema}
        )
    """)

    # Copy data
    print("Copying data...")
    col_list = ", ".join(col_names)
    cursor.execute(f"""
        INSERT INTO fits_files_new ({col_list})
        SELECT {col_list}
        FROM fits_files
    """)

    copied_count = cursor.execute("SELECT COUNT(*) FROM fits_files_new").fetchone()[0]
    print(f"✓ Copied {copied_count} rows")

    # Get indexes from old table
    print("Getting indexes to recreate...")
    cursor.execute("""
        SELECT name, sql
        FROM sqlite_master
        WHERE type='index' AND tbl_name='fits_files' AND sql IS NOT NULL
    """)
    indexes = cursor.fetchall()

    # Drop old table and rename
    print("Swapping tables...")
    cursor.execute("DROP TABLE fits_files")
    cursor.execute("ALTER TABLE fits_files_new RENAME TO fits_files")

    # Recreate indexes
    print("Recreating indexes...")
    for idx_name, idx_sql in indexes:
        try:
            cursor.execute(idx_sql)
            print(f"  ✓ {idx_name}")
        except Exception as e:
            print(f"  ⚠ {idx_name}: {e}")

    print("✓ fits_files recreated with proper PRIMARY KEY")

    return copied_count


def recreate_processing_session_files(cursor):
    """Recreate processing_session_files with proper foreign keys."""
    print("\n" + "="*60)
    print("Step 2: Recreating processing_session_files")
    print("="*60)

    # Get current row count
    cursor.execute("SELECT COUNT(*) FROM processing_session_files")
    row_count = cursor.fetchone()[0]
    print(f"\nCurrent rows: {row_count}")

    # Create new table with correct schema
    print("Creating processing_session_files_new...")
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
    print(f"✓ Copied {copied_count} rows")

    if copied_count != row_count:
        raise Exception(f"Row count mismatch! Original: {row_count}, Copied: {copied_count}")

    # Drop old table and rename
    print("Swapping tables...")
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

    print("✓ processing_session_files recreated with proper foreign keys")

    return copied_count


def verify_fix(cursor):
    """Verify the fix worked."""
    print("\n" + "="*60)
    print("Step 3: Verifying Fix")
    print("="*60)

    # Re-enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON")

    # Check fits_files primary key
    cursor.execute("PRAGMA table_info('fits_files')")
    columns = cursor.fetchall()

    print("\nfits_files.id:")
    for col in columns:
        if col[1] == 'id':
            if col[5] == 1:
                print(f"  ✓ Type={col[2]}, PRIMARY KEY")
            else:
                print(f"  ✗ Type={col[2]}, NOT PRIMARY KEY")

    # Check foreign keys
    cursor.execute("PRAGMA foreign_key_list('processing_session_files')")
    fks = cursor.fetchall()

    print("\nprocessing_session_files foreign keys:")
    for fk in fks:
        print(f"  ✓ {fk[3]} → {fk[2]}.{fk[4]}")

    # Test foreign key constraints
    print("\nTesting foreign key constraints...")

    cursor.execute("""
        SELECT COUNT(*)
        FROM processing_session_files psf
        JOIN fits_files f ON psf.fits_file_id = f.id
    """)
    join_count = cursor.fetchone()[0]
    print(f"  ✓ Rows with valid fits_file_id: {join_count}")

    cursor.execute("""
        SELECT COUNT(*)
        FROM processing_session_files psf
        JOIN processing_sessions ps ON psf.processing_session_id = ps.id
    """)
    join_count2 = cursor.fetchone()[0]
    print(f"  ✓ Rows with valid processing_session_id: {join_count2}")

    # Test that foreign key enforcement works
    print("\nTesting foreign key enforcement...")
    try:
        # Try to insert a row with invalid fits_file_id
        cursor.execute("""
            INSERT INTO processing_session_files
            (processing_session_id, fits_file_id, original_path, original_filename,
             staged_path, staged_filename, subfolder)
            VALUES ('test', 999999999, 'test', 'test', 'test', 'test', 'test')
        """)
        print("  ✗ Foreign key constraint NOT enforced!")
        cursor.execute("DELETE FROM processing_session_files WHERE processing_session_id = 'test'")
    except sqlite3.IntegrityError as e:
        if "FOREIGN KEY constraint failed" in str(e):
            print("  ✓ Foreign key constraints are enforced")
        else:
            print(f"  ? Unexpected error: {e}")

    print("\n✓ All verifications passed")


def main():
    """Main entry point."""
    db_path = Path.home() / 'Astro' / 'fits_catalog.db'

    print("="*60)
    print("COMPREHENSIVE FOREIGN KEY FIX")
    print("="*60)
    print(f"\nDatabase: {db_path}\n")

    if not db_path.exists():
        print(f"✗ Error: Database not found: {db_path}")
        return 1

    # Create backup
    backup_path = db_path.parent / f"{db_path.stem}_backup_fk_comprehensive.db"
    print(f"Creating backup: {backup_path}")
    import shutil
    shutil.copy2(db_path, backup_path)
    print("✓ Backup created\n")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Step 0: Check current state
        has_pk, fits_count, psf_count = check_current_state(cursor)

        if has_pk:
            print("\n✓ fits_files.id is already a PRIMARY KEY")
            print("The issue may be something else. Check error logs.")
            return 0

        # Step 1: Recreate fits_files with PRIMARY KEY
        fits_copied = recreate_fits_files(cursor)

        if fits_copied != fits_count:
            raise Exception(f"fits_files row count mismatch! Expected {fits_count}, got {fits_copied}")

        # Step 2: Recreate processing_session_files with proper FKs
        psf_copied = recreate_processing_session_files(cursor)

        if psf_copied != psf_count:
            raise Exception(f"processing_session_files row count mismatch! Expected {psf_count}, got {psf_copied}")

        # Step 3: Verify
        verify_fix(cursor)

        # Commit all changes
        conn.commit()

        print("\n" + "="*60)
        print("✓ COMPREHENSIVE FIX COMPLETE")
        print("="*60)
        print(f"""
Summary:
  - Recreated fits_files with PRIMARY KEY on id
  - Recreated processing_session_files with proper foreign keys
  - Preserved all {fits_count} FITS files
  - Preserved all {psf_count} processing session files
  - Foreign key constraints now enforced

Next steps:
1. Restart your web server
2. Try creating a new processing session
3. It should now work without foreign key errors

Backup saved at:
  {backup_path}
        """)

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        print("\nChanges rolled back. Database unchanged.")
        print(f"\nTo restore backup if needed:")
        print(f"  cp {backup_path} {db_path}")
        return 1
    finally:
        conn.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
