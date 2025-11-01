#!/usr/bin/env python3
"""
Fix Performance Issues After Phase 3 Migration

This script addresses performance regressions by:
1. Verifying all indexes exist
2. Running ANALYZE to rebuild query optimizer statistics
3. Showing query execution plans before/after

Run this after Phase 3 migration if queries are slow.
"""

import sqlite3
import sys
from pathlib import Path
import time


def verify_indexes(cursor):
    """Verify all critical indexes exist."""
    print("=" * 60)
    print("STEP 1: Verifying Indexes")
    print("=" * 60)

    # Expected indexes
    expected_indexes = {
        'imaging_sessions': [
            ('idx_session_date', 'date'),
            ('idx_session_telescope_camera', 'telescope, camera'),
        ],
        'fits_files': [
            ('idx_fits_imaging_session', 'imaging_session_id'),
            ('idx_fits_frame_type', 'frame_type'),
            ('idx_fits_object', 'object'),
            ('idx_fits_telescope_camera', 'telescope, camera'),
        ],
        'processing_session_files': [
            ('idx_processing_session_id', 'processing_session_id'),
            ('idx_processing_file_fits', 'fits_file_id'),
        ],
    }

    missing_indexes = []

    for table, indexes in expected_indexes.items():
        print(f"\n{table}:")

        # Get existing indexes
        cursor.execute(f"""
            SELECT name, sql
            FROM sqlite_master
            WHERE type='index' AND tbl_name='{table}'
            AND sql IS NOT NULL
        """)
        existing = {row[0]: row[1] for row in cursor.fetchall()}

        for idx_name, columns in indexes:
            if idx_name in existing:
                print(f"  ✓ {idx_name}")
            else:
                print(f"  ✗ MISSING: {idx_name} on ({columns})")
                missing_indexes.append((table, idx_name, columns))

    return missing_indexes


def create_missing_indexes(cursor, missing_indexes):
    """Create any missing indexes."""
    if not missing_indexes:
        print("\n✓ All indexes exist")
        return

    print("\n" + "=" * 60)
    print("STEP 2: Creating Missing Indexes")
    print("=" * 60)

    for table, idx_name, columns in missing_indexes:
        print(f"\nCreating {idx_name} on {table}({columns})...")

        try:
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS {idx_name}
                ON {table}({columns})
            """)
            print(f"  ✓ Created")
        except Exception as e:
            print(f"  ✗ Error: {e}")


def show_query_plan_before(cursor, session_id):
    """Show query execution plan BEFORE ANALYZE."""
    print("\n" + "=" * 60)
    print("STEP 3: Query Execution Plan (BEFORE ANALYZE)")
    print("=" * 60)

    query = """
        SELECT f.id, f.file, f.frame_type
        FROM fits_files f
        JOIN processing_session_files psf ON f.id = psf.fits_file_id
        WHERE psf.processing_session_id = ?
    """

    print(f"\nQuery plan for session: {session_id}")
    print("-" * 60)

    cursor.execute(f"EXPLAIN QUERY PLAN {query}", (session_id,))
    plan = cursor.fetchall()

    for row in plan:
        print(f"  {row}")

    # Check if using indexes
    plan_str = ' '.join(str(row) for row in plan).lower()
    if 'scan' in plan_str and 'using index' not in plan_str:
        print("\n⚠ WARNING: Query is doing TABLE SCANS (very slow!)")
    elif 'using index' in plan_str:
        print("\n✓ Query is using indexes")
    else:
        print("\n? Unable to determine if indexes are being used")


def run_analyze(cursor):
    """Run ANALYZE to rebuild query optimizer statistics."""
    print("\n" + "=" * 60)
    print("STEP 4: Running ANALYZE")
    print("=" * 60)

    print("\nAnalyzing database (this may take a few seconds)...")

    start = time.time()
    cursor.execute("ANALYZE")
    elapsed = time.time() - start

    print(f"✓ ANALYZE completed in {elapsed:.1f}s")

    # Show statistics
    cursor.execute("""
        SELECT COUNT(*) FROM sqlite_stat1
    """)
    count = cursor.fetchone()[0]
    print(f"✓ Generated {count} statistics entries")

    # Show sample statistics
    cursor.execute("""
        SELECT tbl, idx, stat
        FROM sqlite_stat1
        WHERE tbl IN ('fits_files', 'processing_session_files', 'imaging_sessions')
        ORDER BY tbl, idx
        LIMIT 20
    """)

    stats = cursor.fetchall()
    if stats:
        print("\nKey statistics:")
        current_table = None
        for tbl, idx, stat in stats:
            if tbl != current_table:
                print(f"\n  {tbl}:")
                current_table = tbl
            print(f"    {idx}: {stat}")


def show_query_plan_after(cursor, session_id):
    """Show query execution plan AFTER ANALYZE."""
    print("\n" + "=" * 60)
    print("STEP 5: Query Execution Plan (AFTER ANALYZE)")
    print("=" * 60)

    query = """
        SELECT f.id, f.file, f.frame_type
        FROM fits_files f
        JOIN processing_session_files psf ON f.id = psf.fits_file_id
        WHERE psf.processing_session_id = ?
    """

    print(f"\nQuery plan for session: {session_id}")
    print("-" * 60)

    cursor.execute(f"EXPLAIN QUERY PLAN {query}", (session_id,))
    plan = cursor.fetchall()

    for row in plan:
        print(f"  {row}")

    # Check if using indexes
    plan_str = ' '.join(str(row) for row in plan).lower()
    if 'using index' in plan_str or 'search' in plan_str:
        print("\n✓ Query is now using indexes efficiently")
    else:
        print("\n⚠ Query may still need optimization")


def test_query_performance(cursor, session_id):
    """Test actual query performance."""
    print("\n" + "=" * 60)
    print("STEP 6: Performance Test")
    print("=" * 60)

    # Count files
    cursor.execute("""
        SELECT COUNT(*)
        FROM processing_session_files
        WHERE processing_session_id = ?
    """, (session_id,))
    file_count = cursor.fetchone()[0]

    print(f"\nTesting with session: {session_id}")
    print(f"Files in session: {file_count}")

    # Test 1: Simple count
    start = time.time()
    cursor.execute("""
        SELECT COUNT(*)
        FROM fits_files f
        JOIN processing_session_files psf ON f.id = psf.fits_file_id
        WHERE psf.processing_session_id = ?
    """, (session_id,))
    cursor.fetchone()
    elapsed_count = (time.time() - start) * 1000

    print(f"\nTest 1: COUNT(*) query")
    print(f"  Time: {elapsed_count:.1f}ms")
    if elapsed_count > 100:
        print(f"  ⚠ Still slow")
    else:
        print(f"  ✓ Fast")

    # Test 2: Fetch minimal columns
    start = time.time()
    cursor.execute("""
        SELECT f.id, f.frame_type
        FROM fits_files f
        JOIN processing_session_files psf ON f.id = psf.fits_file_id
        WHERE psf.processing_session_id = ?
    """, (session_id,))
    rows = cursor.fetchall()
    elapsed_fetch = (time.time() - start) * 1000

    print(f"\nTest 2: Fetch file IDs and frame types")
    print(f"  Rows: {len(rows)}")
    print(f"  Time: {elapsed_fetch:.1f}ms")
    print(f"  Per-row: {elapsed_fetch/len(rows) if rows else 0:.2f}ms")

    if elapsed_fetch > 500:
        print(f"  ⚠ Very slow - may need more optimization")
    elif elapsed_fetch > 100:
        print(f"  ⚠ Slow")
    else:
        print(f"  ✓ Fast")

    # Test 3: GROUP BY aggregation (like optimized query)
    start = time.time()
    cursor.execute("""
        SELECT
            COALESCE(f.object, 'UNKNOWN') as object_name,
            COALESCE(f.filter, 'No Filter') as filter_name,
            f.exposure,
            COUNT(f.id) as file_count,
            SUM(f.exposure) as total_exposure
        FROM fits_files f
        JOIN processing_session_files psf ON f.id = psf.fits_file_id
        WHERE psf.processing_session_id = ?
        AND f.frame_type = 'LIGHT'
        AND f.exposure IS NOT NULL
        GROUP BY
            COALESCE(f.object, 'UNKNOWN'),
            COALESCE(f.filter, 'No Filter'),
            f.exposure
    """, (session_id,))
    rows = cursor.fetchall()
    elapsed_agg = (time.time() - start) * 1000

    print(f"\nTest 3: GROUP BY aggregation (optimized query)")
    print(f"  Groups: {len(rows)}")
    print(f"  Time: {elapsed_agg:.1f}ms")

    if elapsed_agg > 500:
        print(f"  ⚠ Very slow")
    elif elapsed_agg > 100:
        print(f"  ⚠ Slow")
    else:
        print(f"  ✓ Fast")


def main():
    """Main entry point."""
    db_path = Path.home() / 'Astro' / 'fits_catalog.db'

    print("=" * 60)
    print("POST-MIGRATION PERFORMANCE FIX")
    print("=" * 60)
    print(f"\nDatabase: {db_path}\n")

    if not db_path.exists():
        print(f"✗ Error: Database not found: {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Step 1: Verify indexes
        missing_indexes = verify_indexes(cursor)

        # Step 2: Create missing indexes
        if missing_indexes:
            create_missing_indexes(cursor, missing_indexes)
            conn.commit()

        # Get a test processing session
        cursor.execute("""
            SELECT ps.id
            FROM processing_sessions ps
            JOIN processing_session_files psf ON ps.id = psf.processing_session_id
            GROUP BY ps.id
            HAVING COUNT(psf.fits_file_id) > 50
            ORDER BY COUNT(psf.fits_file_id) DESC
            LIMIT 1
        """)
        result = cursor.fetchone()

        if not result:
            print("\n⚠ No processing sessions with >50 files found for testing")
            print("   Skipping query plan analysis")
            session_id = None
        else:
            session_id = result[0]

            # Step 3: Show query plan BEFORE ANALYZE
            show_query_plan_before(cursor, session_id)

        # Step 4: Run ANALYZE
        run_analyze(cursor)
        conn.commit()

        if session_id:
            # Step 5: Show query plan AFTER ANALYZE
            show_query_plan_after(cursor, session_id)

            # Step 6: Test performance
            test_query_performance(cursor, session_id)

        print("\n" + "=" * 60)
        print("✓ PERFORMANCE FIX COMPLETE")
        print("=" * 60)
        print("""
Next steps:
1. Restart your web server if running
2. Test the Processing Sessions modal
3. It should now load in <500ms instead of 5+ seconds

If still slow, run the diagnostic script:
  python scripts/diagnose_performance.py
""")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        conn.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
