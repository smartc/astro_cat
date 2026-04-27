#!/usr/bin/env python3
"""
Re-catalog FITS files that exist on disk but are missing from the database.

Reads the list of missing files from a reconcile_report_*.txt file (produced
by reconcile_library.py), then processes them through the same pipeline as
the normal catalog command and inserts them into the database.

Usage:
    # First generate the report
    python migrations/reconcile_library.py

    # Then re-catalog the missing files
    python migrations/recatalog_library.py reconcile_report_YYYYMMDD_HHMMSS.txt
    python migrations/recatalog_library.py reconcile_report_YYYYMMDD_HHMMSS.txt --dry-run

Options:
    --dry-run   Show what would be cataloged without writing to the database
    --batch N   Files per processing batch (default: 50)
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import load_config
from cli.utils import get_db_service
from processing.fits_processor import OptimizedFitsProcessor


def parse_report(report_path: Path) -> list[str]:
    """Extract the 'ON DISK, NOT IN DATABASE' file list from a reconcile report."""
    paths = []
    in_section = False
    with open(report_path) as f:
        for line in f:
            stripped = line.rstrip()
            if stripped == "ON DISK, NOT IN DATABASE:":
                in_section = True
                continue
            if in_section:
                if stripped.startswith("  /"):
                    paths.append(stripped.strip())
                elif stripped == "" or (stripped and not stripped.startswith("  ")):
                    break
    return paths


def recatalog(report_path: Path, dry_run: bool = False, batch_size: int = 50,
              config_path: str = "config.json"):
    config, cameras, telescopes, filter_mappings = load_config(config_path)
    db_service = get_db_service(config, cameras, telescopes, filter_mappings)
    processor = OptimizedFitsProcessor(config, cameras, telescopes, filter_mappings, db_service)

    missing = parse_report(report_path)
    if not missing:
        print("No 'ON DISK, NOT IN DATABASE' entries found in report.")
        return

    print(f"Files to re-catalog: {len(missing):,}")
    if dry_run:
        print("DRY RUN — no changes will be written\n")
        for p in missing[:20]:
            print(f"  would catalog: {p}")
        if len(missing) > 20:
            print(f"  ... and {len(missing) - 20:,} more")
        return

    total_added = 0
    total_duplicate = 0
    total_error = 0
    batches = [missing[i:i + batch_size] for i in range(0, len(missing), batch_size)]

    print(f"Processing {len(batches)} batch(es) of up to {batch_size} files each\n")
    t_start = time.time()

    for batch_num, batch in enumerate(batches, 1):
        print(f"Batch {batch_num}/{len(batches)} ({len(batch)} files)...", flush=True)
        try:
            df, session_data = processor.process_files_optimized(batch)
        except Exception as e:
            print(f"  ERROR processing batch: {e}")
            total_error += len(batch)
            continue

        # Insert sessions first (FK constraint)
        for session in session_data:
            if not session.get("id") or session["id"] == "UNKNOWN":
                continue
            try:
                db_service.add_imaging_session(session)
            except Exception:
                pass  # Already exists

        # Insert file records
        batch_added = 0
        batch_dup = 0
        batch_err = 0
        if not df.is_empty():
            for row in df.iter_rows(named=True):
                try:
                    success, is_duplicate = db_service.add_fits_file(row)
                    if is_duplicate:
                        batch_dup += 1
                    elif success:
                        batch_added += 1
                    else:
                        batch_err += 1
                except Exception as e:
                    print(f"  ERROR adding {row.get('file', '?')}: {e}")
                    batch_err += 1

        print(f"  added={batch_added}  duplicates={batch_dup}  errors={batch_err}")
        total_added += batch_added
        total_duplicate += batch_dup
        total_error += batch_err

    elapsed = time.time() - t_start
    print()
    print("=" * 60)
    print("RE-CATALOG COMPLETE")
    print("=" * 60)
    print(f"Added:      {total_added:>6,}")
    print(f"Duplicates: {total_duplicate:>6,}")
    print(f"Errors:     {total_error:>6,}")
    print(f"Time:       {elapsed:.1f}s")
    print()
    if total_added > 0:
        print("Run reconcile_library.py again to verify the gap is closed.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)

    report = Path(args[0])
    if not report.exists():
        print(f"Report file not found: {report}")
        sys.exit(1)

    dry_run = "--dry-run" in args
    batch_size = 50
    for a in args:
        if a.startswith("--batch="):
            batch_size = int(a.split("=", 1)[1])

    config_path = "config.json"
    for a in args:
        if a.endswith(".json") and "config" in a:
            config_path = a

    recatalog(report, dry_run=dry_run, batch_size=batch_size, config_path=config_path)
