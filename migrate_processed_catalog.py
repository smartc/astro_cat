#!/usr/bin/env python3
"""
Database migration script for processed catalog feature.

Adds new columns to processing_sessions table for target metadata tracking.
"""

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def add_column_if_missing(cursor, table_name, column_name, column_def):
    """Add a column to a table if it doesn't already exist."""
    if not column_exists(cursor, table_name, column_name):
        logger.info(f"Adding column {column_name} to {table_name}...")
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
        return True
    else:
        logger.info(f"Column {column_name} already exists in {table_name}, skipping")
        return False


def migrate_database(db_path):
    """
    Perform database migration to add processed catalog fields.
    
    Adds the following columns to processing_sessions:
    - primary_target (String)
    - target_type (String)
    - image_type (String)
    - ra (String)
    - dec (String)
    - total_integration_seconds (Integer)
    - date_range_start (DateTime)
    - date_range_end (DateTime)
    """
    db_path = Path(db_path)
    
    if not db_path.exists():
        logger.error(f"Database file not found: {db_path}")
        return False
    
    # Backup database
    backup_path = db_path.with_suffix('.db.backup')
    logger.info(f"Creating backup: {backup_path}")
    import shutil
    shutil.copy2(db_path, backup_path)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if processing_sessions table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='processing_sessions'
        """)
        if not cursor.fetchone():
            logger.error("processing_sessions table does not exist!")
            return False
        
        logger.info("Migrating processing_sessions table...")
        
        # Add new columns
        changes_made = False
        
        # Primary target information
        changes_made |= add_column_if_missing(
            cursor, 'processing_sessions', 'primary_target', 'VARCHAR(255)'
        )
        changes_made |= add_column_if_missing(
            cursor, 'processing_sessions', 'target_type', 'VARCHAR(50)'
        )
        changes_made |= add_column_if_missing(
            cursor, 'processing_sessions', 'image_type', 'VARCHAR(50)'
        )
        
        # Coordinates
        changes_made |= add_column_if_missing(
            cursor, 'processing_sessions', 'ra', 'VARCHAR(50)'
        )
        changes_made |= add_column_if_missing(
            cursor, 'processing_sessions', 'dec', 'VARCHAR(50)'
        )
        
        # Integration metadata
        changes_made |= add_column_if_missing(
            cursor, 'processing_sessions', 'total_integration_seconds', 'INTEGER'
        )
        changes_made |= add_column_if_missing(
            cursor, 'processing_sessions', 'date_range_start', 'DATETIME'
        )
        changes_made |= add_column_if_missing(
            cursor, 'processing_sessions', 'date_range_end', 'DATETIME'
        )
        
        # Create indexes if they don't exist
        logger.info("Creating indexes...")
        
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_processing_target 
                ON processing_sessions(primary_target)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_processing_target_type 
                ON processing_sessions(target_type)
            """)
            logger.info("Indexes created successfully")
        except Exception as e:
            logger.warning(f"Error creating indexes (may already exist): {e}")
        
        # Create processed_files table if it doesn't exist
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='processed_files'
        """)
        if not cursor.fetchone():
            logger.info("Creating processed_files table...")
            cursor.execute("""
                CREATE TABLE processed_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    processing_session_id VARCHAR(50),
                    file_path VARCHAR(500) NOT NULL UNIQUE,
                    filename VARCHAR(255) NOT NULL,
                    file_type VARCHAR(20) NOT NULL,
                    subfolder VARCHAR(50),
                    file_size INTEGER,
                    created_date DATETIME,
                    modified_date DATETIME,
                    md5sum VARCHAR(32),
                    has_companion BOOLEAN DEFAULT 0,
                    companion_path VARCHAR(500),
                    companion_size INTEGER,
                    image_width INTEGER,
                    image_height INTEGER,
                    bit_depth INTEGER,
                    color_space VARCHAR(50),
                    associated_object VARCHAR(255),
                    processing_stage VARCHAR(50),
                    metadata_json TEXT,
                    notes TEXT,
                    cataloged_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (processing_session_id) 
                        REFERENCES processing_sessions(id) 
                        ON DELETE CASCADE
                )
            """)
            
            # Create indexes for processed_files
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_processed_session 
                ON processed_files(processing_session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_processed_type 
                ON processed_files(file_type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_processed_subfolder 
                ON processed_files(subfolder)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_processed_object 
                ON processed_files(associated_object)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_processed_stage 
                ON processed_files(processing_stage)
            """)
            
            logger.info("processed_files table created successfully")
            changes_made = True
        else:
            logger.info("processed_files table already exists")
        
        conn.commit()
        
        if changes_made:
            logger.info("✓ Migration completed successfully!")
        else:
            logger.info("✓ Database already up to date, no changes needed")
        
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        conn.rollback()
        return False
        
    finally:
        conn.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Migrate database for processed catalog feature'
    )
    parser.add_argument(
        '--database',
        type=str,
        required=True,
        help='Path to SQLite database file'
    )
    
    args = parser.parse_args()
    
    success = migrate_database(args.database)
    
    if success:
        logger.info("Migration completed successfully!")
        return 0
    else:
        logger.error("Migration failed!")
        return 1


if __name__ == '__main__':
    sys.exit(main())