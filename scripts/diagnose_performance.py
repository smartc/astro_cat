#!/usr/bin/env python3
"""
Diagnose database performance issues after Phase 3 migration.

This script checks:
1. What indexes actually exist
2. Table statistics
3. Query execution plans
4. Index usage
"""

import sqlite3
import sys
from pathlib import Path
import time


def check_indexes(cursor):
    """Check what indexes exist on critical tables."""
    print("="*60)
    print("INDEX ANALYSIS")
    print("="*60)

    tables = ['fits_files', 'imaging_sessions', 'processing_session_files']

    for table in tables:
        print(f"\n{table}:")
        cursor.execute(f"""
            SELECT name, sql
            FROM sqlite_master
            WHERE type='index' AND tbl_name='{table}'
            ORDER BY name
        """)

        indexes = cursor.fetchall()
        if indexes:
            for idx_name, idx_sql in indexes:
                if idx_sql:  # Skip auto-created indexes
                    print(f"  ✓ {idx_name}")
                    print(f"    {idx_sql}")
        else:
            print("  ⚠ NO INDEXES FOUND")


def check_table_stats(cursor):
    """Check table sizes and row counts."""
    print("\n" + "="*60)
    print("TABLE STATISTICS")
    print("="*60)

    cursor.execute("SELECT COUNT(*) FROM fits_files")
    fits_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM imaging_sessions")
    session_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM processing_session_files")
    ps_file_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM processing_sessions")
    ps_count = cursor.fetchone()[0]

    print(f"\nfits_files: {fits_count:,} rows")
    print(f"imaging_sessions: {session_count:,} rows")
    print(f"processing_sessions: {ps_count:,} rows")
    print(f"processing_session_files: {ps_file_count:,} rows")


def analyze_query_plan(cursor, session_id):
    """Analyze the query execution plan for a processing session query."""
    print("\n" + "="*60)
    print("QUERY PLAN ANALYSIS")
    print("="*60)

    # The actual query used in the web app
    query = """
        EXPLAIN QUERY PLAN
        SELECT f.id, f.file, f.folder, f.imaging_session_id,
               f.frame_type, f.camera, f.telescope, f.filter,
               f.exposure, f.obs_date, f.object
        FROM fits_files f
        JOIN processing_session_files psf ON f.id = psf.fits_file_id
        WHERE psf.processing_session_id = ?
    """

    print(f"\nQuery plan for session: {session_id}")
    print("-" * 60)

    cursor.execute(query, (session_id,))
    plan = cursor.fetchall()

    for row in plan:
        print(f"  {row}")

    # Check if it's using indexes
    plan_str = str(plan).lower()
    if 'using index' in plan_str or 'search' in plan_str:
        print("\n✓ Query is using indexes")
    else:
        print("\n⚠ WARNING: Query might be doing table scans!")


def test_query_performance(cursor, session_id):
    """Time the actual query."""
    print("\n" + "="*60)
    print("QUERY PERFORMANCE TEST")
    print("="*60)

    # Test 1: Get file count
    start = time.time()
    cursor.execute("""
        SELECT COUNT(*)
        FROM fits_files f
        JOIN processing_session_files psf ON f.id = psf.fits_file_id
        WHERE psf.processing_session_id = ?
    """, (session_id,))
    count = cursor.fetchone()[0]
    elapsed = (time.time() - start) * 1000

    print(f"\nTest 1: Count files in session")
    print(f"  Files: {count}")
    print(f"  Time: {elapsed:.1f}ms")

    if elapsed > 100:
        print(f"  ⚠ WARNING: Count query is slow ({elapsed:.1f}ms)")
    else:
        print(f"  ✓ Count query is fast")

    # Test 2: Get actual files (minimal columns)
    start = time.time()
    cursor.execute("""
        SELECT f.id, f.frame_type
        FROM fits_files f
        JOIN processing_session_files psf ON f.id = psf.fits_file_id
        WHERE psf.processing_session_id = ?
    """, (session_id,))
    rows = cursor.fetchall()
    elapsed = (time.time() - start) * 1000

    print(f"\nTest 2: Fetch file IDs and frame types")
    print(f"  Rows: {len(rows)}")
    print(f"  Time: {elapsed:.1f}ms")
    print(f"  Per-row: {elapsed/len(rows) if rows else 0:.2f}ms")

    if elapsed > 500:
        print(f"  ⚠ WARNING: Join query is VERY slow ({elapsed:.1f}ms for {len(rows)} rows)")
    elif elapsed > 100:
        print(f"  ⚠ WARNING: Join query is slow ({elapsed:.1f}ms)")
    else:
        print(f"  ✓ Join query is fast")

    # Test 3: Get with all columns (like before optimization)
    start = time.time()
    cursor.execute("""
        SELECT f.*
        FROM fits_files f
        JOIN processing_session_files psf ON f.id = psf.fits_file_id
        WHERE psf.processing_session_id = ?
    """, (session_id,))
    rows = cursor.fetchall()
    elapsed = (time.time() - start) * 1000

    print(f"\nTest 3: Fetch all columns (70+)")
    print(f"  Rows: {len(rows)}")
    print(f"  Time: {elapsed:.1f}ms")
    print(f"  Per-row: {elapsed/len(rows) if rows else 0:.2f}ms")

    if elapsed > 1000:
        print(f"  ⚠ WARNING: Full column query is VERY slow ({elapsed:.1f}ms)")


def check_analyze_stats(cursor):
    """Check if ANALYZE has been run."""
    print("\n" + "="*60)
    print("QUERY OPTIMIZER STATISTICS")
    print("="*60)

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='sqlite_stat1'
    """)

    if cursor.fetchone():
        print("\n✓ Statistics table (sqlite_stat1) exists")
        cursor.execute("SELECT COUNT(*) FROM sqlite_stat1")
        count = cursor.fetchone()[0]
        print(f"  {count} statistics entries")

        # Show some stats
        cursor.execute("""
            SELECT tbl, idx, stat
            FROM sqlite_stat1
            WHERE tbl IN ('fits_files', 'processing_session_files', 'imaging_sessions')
            LIMIT 10
        """)
        stats = cursor.fetchall()
        if stats:
            print("\n  Sample statistics:")
            for tbl, idx, stat in stats:
                print(f"    {tbl}.{idx}: {stat}")
    else:
        print("\n⚠ WARNING: No statistics table found")
        print("  Run ANALYZE to improve query performance")


def main():
    """Run all diagnostics."""
    db_path = Path.home() / 'Astro' / 'fits_catalog.db'

    print("="*60)
    print("DATABASE PERFORMANCE DIAGNOSTICS")
    print("="*60)
    print(f"\nDatabase: {db_path}\n")

    if not db_path.exists():
        print(f"✗ Error: Database not found: {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Run diagnostics
    check_indexes(cursor)
    check_table_stats(cursor)
    check_analyze_stats(cursor)

    # Get a processing session ID to test with
    cursor.execute("""
        SELECT id FROM processing_sessions
        ORDER BY created_at DESC
        LIMIT 1
    """)
    result = cursor.fetchone()

    if result:
        session_id = result[0]
        analyze_query_plan(cursor, session_id)
        test_query_performance(cursor, session_id)
    else:
        print("\n⚠ No processing sessions found to test with")

    conn.close()

    print("\n" + "="*60)
    print("RECOMMENDATIONS")
    print("="*60)
    print("""
If you see warnings above:

1. Slow count/join queries:
   - Missing or inefficient indexes
   - Run: sqlite3 ~/Astro/fits_catalog.db "ANALYZE;"

2. No statistics table:
   - SQLite query optimizer needs statistics
   - Run: sqlite3 ~/Astro/fits_catalog.db "ANALYZE;"

3. Table scans detected:
   - Indexes aren't being used
   - Check index definitions above
   - Might need to rebuild indexes

4. To rebuild all indexes:
   python scripts/rebuild_indexes.py
""")

    return 0


if __name__ == '__main__':
    sys.exit(main())
