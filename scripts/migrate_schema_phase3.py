#!/usr/bin/env python3
"""
Phase 3 Schema Migration Script

Direct SQL approach for SQLite database migration.
Renames tables and columns to match Python model names.
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime
import sys
import os


def backup_database(db_path):
    """Create timestamped backup."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Create backups in same directory as database
    db_dir = db_path.parent
    backup_dir = db_dir / "backups"
    backup_dir.mkdir(exist_ok=True)

    backup_path = backup_dir / f"fits_catalog_pre_phase3_{timestamp}.db"

    print(f"Creating backup: {backup_path}")
    shutil.copy2(db_path, backup_path)

    print(f"✓ Backup created: {backup_path}")
    return backup_path


def verify_backup(backup_path):
    """Verify backup is valid."""
    try:
        conn = sqlite3.connect(backup_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM fits_files")
        fits_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM sessions")
        session_count = cursor.fetchone()[0]

        conn.close()

        print(f"✓ Backup verified: {session_count} sessions, {fits_count} FITS files")
        return True

    except Exception as e:
        print(f"✗ Backup verification failed: {e}")
        return False


def check_prerequisites(db_path):
    """Check database is ready for migration."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check for schema_version table
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='schema_version'
    """)

    if not cursor.fetchone():
        print("✗ schema_version table not found")
        print("  Phase 2 must be completed before Phase 3")
        conn.close()
        return False

    # Check current schema version
    cursor.execute("SELECT MAX(version) FROM schema_version")
    result = cursor.fetchone()
    version = result[0] if result and result[0] else 0

    if version >= 2:
        print(f"✗ Database already at schema version {version}")
        print("  Migration already applied")
        conn.close()
        return False

    # Check if imaging_sessions table already exists (partial migration?)
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='imaging_sessions'
    """)

    if cursor.fetchone():
        print("✗ Table 'imaging_sessions' already exists")
        print("  Database may be partially migrated or corrupted")
        print("  Please restore from backup before attempting migration")
        conn.close()
        return False

    conn.close()
    return True


def migrate_schema(db_path):
    """Apply Phase 3 schema migration."""

    print("\nStarting Phase 3 schema migration...")
    print("This will rename tables and columns to match Python code.")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Start transaction
        cursor.execute("BEGIN TRANSACTION")

        # ====================================================================
        # STEP 1: Rename sessions → imaging_sessions
        # ====================================================================
        print("\n[1/5] Creating imaging_sessions table...")
        cursor.execute("""
            CREATE TABLE imaging_sessions (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                telescope TEXT,
                camera TEXT,
                site_name TEXT,
                latitude REAL,
                longitude REAL,
                elevation REAL,
                observer TEXT,
                notes TEXT,
                avg_seeing REAL,
                avg_sky_quality REAL,
                avg_cloud_cover REAL,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)

        print("      Copying data from sessions...")
        cursor.execute("""
            INSERT INTO imaging_sessions
            (id, date, telescope, camera, site_name,
             latitude, longitude, elevation, observer, notes,
             avg_seeing, avg_sky_quality, avg_cloud_cover,
             created_at, updated_at)
            SELECT session_id, session_date, telescope, camera, site_name,
                   latitude, longitude, elevation, observer, notes,
                   avg_seeing, avg_sky_quality, avg_cloud_cover,
                   created_at, updated_at
            FROM sessions
        """)

        rows = cursor.rowcount
        print(f"      ✓ Copied {rows} imaging sessions")

        # ====================================================================
        # STEP 2: Update fits_files with renamed columns
        # ====================================================================
        print("\n[2/5] Creating new fits_files table with renamed columns...")

        # Get all column names from existing fits_files
        cursor.execute("PRAGMA table_info(fits_files)")
        existing_columns = [row[1] for row in cursor.fetchall()]

        # Build column list for CREATE TABLE AS SELECT
        # Start with required columns
        select_parts = [
            "id",
            "file",
            "folder",
            "object",
            "obs_date",
            "obs_timestamp",
            "ra",
            "dec",
            "x as width_pixels",
            "y as height_pixels",
            "frame_type",
            "filter",
            "focal_length",
            "exposure",
            "camera",
            "telescope",
            "md5sum",
            "latitude",
            "longitude",
            "elevation",
            "fov_x",
            "fov_y",
            "pixel_scale"
        ]

        # Add optional columns if they exist
        optional_columns = [
            'gain', 'offset', 'egain', 'binning_x', 'binning_y',
            'readout_mode', 'sensor_temp', 'set_temp', 'cooler_power',
            'airmass', 'altitude', 'azimuth', 'software',
            'validation_score', 'validation_notes', 'migration_status'
        ]

        for col in optional_columns:
            if col in existing_columns:
                select_parts.append(col)

        # Add the renamed foreign key
        select_parts.append("session_id as imaging_session_id")

        # Add timestamps
        select_parts.append("created_at")
        select_parts.append("updated_at")

        # Build the query
        select_clause = ",\n                ".join(select_parts)

        cursor.execute(f"""
            CREATE TABLE fits_files_new AS
            SELECT
                {select_clause}
            FROM fits_files
        """)

        # Get actual count (rowcount doesn't work for CREATE TABLE AS SELECT)
        cursor.execute("SELECT COUNT(*) FROM fits_files_new")
        rows = cursor.fetchone()[0]
        print(f"      ✓ Copied {rows} FITS files")

        print("      Swapping tables...")
        cursor.execute("DROP TABLE fits_files")
        cursor.execute("ALTER TABLE fits_files_new RENAME TO fits_files")

        # ====================================================================
        # STEP 3: Recreate indexes
        # ====================================================================
        print("\n[3/5] Recreating indexes...")

        # Imaging sessions indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_date ON imaging_sessions(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_telescope_camera ON imaging_sessions(telescope, camera)")
        print("      ✓ Imaging sessions indexes created")

        # FITS files indexes
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_fits_md5 ON fits_files(md5sum)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fits_imaging_session ON fits_files(imaging_session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fits_object ON fits_files(object)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fits_obs_date ON fits_files(obs_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fits_camera ON fits_files(camera)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fits_telescope ON fits_files(telescope)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fits_frame_type ON fits_files(frame_type)")
        print("      ✓ FITS files indexes created")

        # ====================================================================
        # STEP 4: Drop old tables
        # ====================================================================
        print("\n[4/5] Dropping old sessions table...")
        cursor.execute("DROP TABLE sessions")
        print("      ✓ Old table removed")

        # ====================================================================
        # STEP 5: Update schema version
        # ====================================================================
        print("\n[5/5] Updating schema version...")
        cursor.execute("""
            INSERT INTO schema_version (version, description, applied_at)
            VALUES (2, 'Phase 3: Renamed tables and columns', CURRENT_TIMESTAMP)
        """)
        print("      ✓ Schema version updated to 2")

        # Commit transaction
        conn.commit()
        print("\n✓ Migration completed successfully!")

        return True

    except Exception as e:
        conn.rollback()
        print(f"\n✗ Migration failed: {e}")
        print("  Transaction rolled back - database unchanged")
        import traceback
        traceback.print_exc()
        return False

    finally:
        conn.close()


def verify_migration(db_path):
    """Verify migration was successful."""
    print("\n" + "="*60)
    print("Verifying migration...")
    print("="*60)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    errors = []

    # Check tables exist with new names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]

    if 'imaging_sessions' not in tables:
        errors.append("imaging_sessions table not found")
    else:
        print("✓ imaging_sessions table exists")

    if 'sessions' in tables:
        errors.append("Old sessions table still exists")
    else:
        print("✓ Old sessions table removed")

    # Check columns renamed in fits_files
    cursor.execute("PRAGMA table_info(fits_files)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}  # name: type

    required_columns = ['width_pixels', 'height_pixels', 'imaging_session_id']
    old_columns = ['x', 'y', 'session_id']

    for col in required_columns:
        if col not in columns:
            errors.append(f"Column {col} not found in fits_files")
        else:
            print(f"✓ Column {col} exists")

    for col in old_columns:
        if col in columns:
            errors.append(f"Old column {col} still exists in fits_files")

    # Check data integrity
    cursor.execute("SELECT COUNT(*) FROM imaging_sessions")
    session_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM fits_files")
    fits_count = cursor.fetchone()[0]

    print(f"✓ Data integrity: {session_count} sessions, {fits_count} files")

    # Check schema version
    cursor.execute("SELECT version, description FROM schema_version ORDER BY version DESC LIMIT 1")
    row = cursor.fetchone()
    version, description = row if row else (None, None)

    if version == 2:
        print(f"✓ Schema version: {version} - {description}")
    else:
        errors.append(f"Schema version is {version}, expected 2")

    # Check indexes exist
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND tbl_name='imaging_sessions'
    """)
    imaging_indexes = [row[0] for row in cursor.fetchall()]

    if 'idx_session_date' in imaging_indexes:
        print("✓ Imaging sessions indexes exist")
    else:
        errors.append("Missing imaging_sessions indexes")

    conn.close()

    if errors:
        print("\n" + "!"*60)
        print("VERIFICATION FAILED:")
        for error in errors:
            print(f"  ✗ {error}")
        print("!"*60)
        return False
    else:
        print("\n" + "="*60)
        print("✓ All verification checks passed!")
        print("="*60)
        return True


def main():
    """Main migration process."""

    # Use actual database path
    db_path = Path.home() / 'Astro' / 'fits_catalog.db'

    print("="*60)
    print("FITS Cataloger - Phase 3 Schema Migration")
    print("="*60)
    print(f"\nDatabase: {db_path}")
    print("\nThis script will:")
    print("  • Rename 'sessions' table to 'imaging_sessions'")
    print("  • Rename columns: session_id→id, session_date→date")
    print("  • Rename fits_files columns: x→width_pixels, y→height_pixels")
    print("  • Update foreign key: session_id→imaging_session_id")
    print()

    # Check database exists
    if not db_path.exists():
        print(f"✗ Error: Database not found: {db_path}")
        return 1

    # Check prerequisites
    if not check_prerequisites(db_path):
        return 1

    # Create backup
    backup_path = backup_database(db_path)
    if not verify_backup(backup_path):
        print("✗ Error: Backup verification failed")
        return 1

    # Confirm with user
    print("\n" + "!"*60)
    print("WARNING: This will modify your database schema")
    print("A backup has been created at:")
    print(f"  {backup_path}")
    print("!"*60)

    response = input("\nType 'yes' to proceed with migration: ")

    if response.lower() != 'yes':
        print("\nMigration cancelled by user")
        return 0

    # Run migration
    if not migrate_schema(db_path):
        print("\n" + "="*60)
        print("Migration failed. Database unchanged.")
        print("="*60)
        return 1

    # Verify migration
    if not verify_migration(db_path):
        print("\n" + "="*60)
        print("CRITICAL: Verification failed!")
        print("Restore from backup:")
        print(f"  cp {backup_path} {db_path}")
        print("="*60)
        return 1

    # Success
    print("\n" + "="*60)
    print("MIGRATION COMPLETE!")
    print("="*60)
    print("\nNext steps:")
    print("  1. Update models.py to remove column mapping")
    print("  2. Test CLI commands:")
    print("     python main_v2.py list imaging-sessions --recent 5")
    print("     python main_v2.py list raw --imaging-session <ID>")
    print("  3. Test web interface:")
    print("     python run_web.py")
    print("\nIf any issues occur, restore from backup:")
    print(f"  cp {backup_path} {db_path}")
    print("="*60)

    return 0


if __name__ == '__main__':
    sys.exit(main())
