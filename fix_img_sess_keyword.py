"""One-off utility to fix the IMGSESS keyword on the ~31k already-stamped files.

Two operations, determined by the frame type stored in the database:

  LIGHT / FLAT
    Rename the old IMG_SESS keyword (written with underscore before WBPP
    compatibility was discovered) to IMGSESS.  Files that already have
    IMGSESS (and no IMG_SESS) are skipped.

  DARK / BIAS
    Remove IMG_SESS and/or IMGSESS if present.  These frame types are
    reusable across sessions so the keyword is not needed and may confuse
    WBPP matching.

Safe by default
---------------
  -n / --dry-run   Preview every change without touching any files.
  --limit N        Cap the number of files actually modified (files that need
                   no change — already correct or not on disk — do not count
                   toward the limit).
  --verify         After each write, re-read the header to confirm the change.
  --output-json P  Write a JSON report to path P.

Usage
-----
    # Preview first 20 files
    python fix_img_sess_keyword.py --dry-run --limit 20 -v

    # Stamp 50 for real and verify
    python fix_img_sess_keyword.py --limit 50 --verify -v

    # Full run with JSON report
    python fix_img_sess_keyword.py --verify --output-json fix_report.json

Requirements
------------
    pip install astropy
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

OLD_KEYWORD = "IMG_SESS"
NEW_KEYWORD = "IMGSESS"
CALIBRATION_TYPES = {"DARK", "BIAS"}


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _find_db(explicit_path: str | None) -> Path:
    if explicit_path:
        p = Path(explicit_path)
        if not p.exists():
            print(f"ERROR: database not found: {p}", file=sys.stderr)
            sys.exit(1)
        return p

    script_dir = Path(__file__).parent
    for config_dir in (script_dir, Path.cwd()):
        config_file = config_dir / "config.json"
        if config_file.exists():
            try:
                cfg = json.loads(config_file.read_text(encoding="utf-8"))
                db_path_raw = cfg.get("paths", {}).get("database_path", "")
                db_path_expanded = os.path.expanduser(os.path.expandvars(db_path_raw))
                raw = (
                    cfg.get("database", {}).get("connection_string", "")
                    or db_path_raw
                )
                raw = raw.replace("{{database_path}}", db_path_expanded)
                raw = os.path.expanduser(os.path.expandvars(raw))
                for prefix in ("sqlite:///", "sqlite://"):
                    if raw.startswith(prefix):
                        raw = raw[len(prefix):]
                        break
                if raw:
                    return Path(raw)
            except Exception:
                pass

    print(
        "ERROR: could not find database path.\n"
        "Pass --db /path/to/catalog.db explicitly.",
        file=sys.stderr,
    )
    sys.exit(1)


def _connect(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        print(f"ERROR: database file not found: {db_path}", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_all_files(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Return every fits_file row regardless of imaging_session_id."""
    cur = conn.execute(
        """
        SELECT
            ff.id                 AS fits_file_id,
            ff.file               AS filename,
            ff.folder             AS folder,
            ff.frame_type         AS frame_type,
            ff.imaging_session_id AS imaging_session_id,
            ff.object             AS object,
            ff.obs_date           AS obs_date,
            ff.filter             AS filter,
            ff.exposure           AS exposure,
            ff.camera             AS camera,
            ff.telescope          AS telescope
        FROM fits_files ff
        ORDER BY ff.id
        """
    )
    return cur.fetchall()


# ---------------------------------------------------------------------------
# FITS helpers
# ---------------------------------------------------------------------------

def _get_astrofits():
    try:
        from astropy.io import fits as astrofits
        return astrofits
    except ImportError:
        print(
            "ERROR: astropy is required.  Install it with:  pip install astropy",
            file=sys.stderr,
        )
        sys.exit(1)


def _inspect_header(fits_path: Path) -> tuple[str | None, str | None]:
    """Return (old_kw_value, new_kw_value) — None if keyword absent."""
    astrofits = _get_astrofits()
    try:
        with astrofits.open(fits_path, mode="readonly") as hdul:
            hdr = hdul[0].header
            old_val = str(hdr[OLD_KEYWORD]).strip() if OLD_KEYWORD in hdr else None
            new_val = str(hdr[NEW_KEYWORD]).strip() if NEW_KEYWORD in hdr else None
            return old_val, new_val
    except Exception as exc:
        return f"error:{exc}", None


def _fix_light_flat(
    fits_path: Path,
    imaging_session_id: str,
    dry_run: bool,
    verbose: bool,
) -> str:
    """Rename IMG_SESS → IMGSESS.

    Returns one of: 'renamed' | 'already_ok' | 'no_old_kw' | 'dry_run' | 'error'.
    """
    old_val, new_val = _inspect_header(fits_path)

    if isinstance(old_val, str) and old_val.startswith("error:"):
        print(f"  ERROR reading {fits_path}: {old_val[6:]}", file=sys.stderr)
        return "error"

    if old_val is None and new_val is not None:
        if verbose:
            print(f"  SKIP (already has {NEW_KEYWORD}={new_val!r}): {fits_path}")
        return "already_ok"

    if old_val is None and new_val is None:
        if verbose:
            print(f"  SKIP (neither keyword present): {fits_path}")
        return "no_old_kw"

    # old_val is set — need to rename (and possibly new_val is also set)
    if dry_run:
        if verbose:
            print(
                f"  [dry-run] rename {OLD_KEYWORD}={old_val!r} → {NEW_KEYWORD}  {fits_path}"
            )
        return "dry_run"

    astrofits = _get_astrofits()
    try:
        with astrofits.open(fits_path, mode="update") as hdul:
            hdr = hdul[0].header
            # Re-read inside update context (could have changed)
            if OLD_KEYWORD in hdr:
                value = str(hdr[OLD_KEYWORD])[:68]
                del hdr[OLD_KEYWORD]
                if NEW_KEYWORD in hdr:
                    hdr[NEW_KEYWORD] = value
                else:
                    hdr.append(
                        (NEW_KEYWORD, value, "astro_cat imaging session identifier"),
                        end=True,
                    )
            hdul.flush()
        if verbose:
            print(f"  RENAMED {OLD_KEYWORD} → {NEW_KEYWORD}  {fits_path}")
        return "renamed"
    except Exception as exc:
        print(f"  ERROR: {fits_path}: {exc}", file=sys.stderr)
        return "error"


def _fix_calibration(
    fits_path: Path,
    dry_run: bool,
    verbose: bool,
) -> str:
    """Remove IMG_SESS and/or IMGSESS from DARK/BIAS frames.

    Returns one of: 'removed' | 'already_clean' | 'dry_run' | 'error'.
    """
    old_val, new_val = _inspect_header(fits_path)

    if isinstance(old_val, str) and old_val.startswith("error:"):
        print(f"  ERROR reading {fits_path}: {old_val[6:]}", file=sys.stderr)
        return "error"

    keywords_present = [kw for kw, val in ((OLD_KEYWORD, old_val), (NEW_KEYWORD, new_val)) if val is not None]

    if not keywords_present:
        if verbose:
            print(f"  SKIP (no session keyword present): {fits_path}")
        return "already_clean"

    if dry_run:
        if verbose:
            print(
                f"  [dry-run] remove {', '.join(keywords_present)}  {fits_path}"
            )
        return "dry_run"

    astrofits = _get_astrofits()
    try:
        with astrofits.open(fits_path, mode="update") as hdul:
            hdr = hdul[0].header
            for kw in (OLD_KEYWORD, NEW_KEYWORD):
                if kw in hdr:
                    del hdr[kw]
            hdul.flush()
        if verbose:
            print(f"  REMOVED {', '.join(keywords_present)}  {fits_path}")
        return "removed"
    except Exception as exc:
        print(f"  ERROR: {fits_path}: {exc}", file=sys.stderr)
        return "error"


def _verify_light_flat(fits_path: Path) -> tuple[str, str | None]:
    """Confirm OLD keyword gone and NEW keyword present.  Returns (result, actual_new_val)."""
    astrofits = _get_astrofits()
    try:
        with astrofits.open(fits_path, mode="readonly") as hdul:
            hdr = hdul[0].header
            old_still_there = OLD_KEYWORD in hdr
            new_val = str(hdr[NEW_KEYWORD]).strip() if NEW_KEYWORD in hdr else None
            if old_still_there:
                return "old_still_present", new_val
            if new_val is None:
                return "new_missing", None
            return "pass", new_val
    except Exception as exc:
        return "error", str(exc)


def _verify_calibration(fits_path: Path) -> str:
    """Confirm neither session keyword is present.  Returns 'pass' | 'keywords_remain' | 'error'."""
    astrofits = _get_astrofits()
    try:
        with astrofits.open(fits_path, mode="readonly") as hdul:
            hdr = hdul[0].header
            remaining = [kw for kw in (OLD_KEYWORD, NEW_KEYWORD) if kw in hdr]
            return "keywords_remain" if remaining else "pass"
    except Exception as exc:
        return f"error:{exc}"


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def _row_to_dict(
    row: sqlite3.Row,
    fits_path: Path | None,
    status: str,
    skip_reason: str | None,
    verify_result: str | None,
) -> dict:
    d = {
        "fits_file_id":       row["fits_file_id"],
        "filename":           row["filename"],
        "folder":             row["folder"],
        "path":               str(fits_path) if fits_path else None,
        "frame_type":         (row["frame_type"] or "UNKNOWN").upper(),
        "imaging_session_id": row["imaging_session_id"],
        "object":             row["object"],
        "obs_date":           row["obs_date"],
        "filter":             row["filter"],
        "exposure":           row["exposure"],
        "camera":             row["camera"],
        "telescope":          row["telescope"],
        "status":             status,
    }
    if skip_reason:
        d["skip_reason"] = skip_reason
    if verify_result is not None:
        d["verify_result"] = verify_result
    return d


def _write_json(output_path: Path, payload: dict) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)
    print(f"\nJSON report written to: {output_path}")


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> None:
    db_path = _find_db(args.db)
    conn = _connect(db_path)

    print(f"Database : {db_path}")
    mode_parts = []
    if args.dry_run:
        mode_parts.append("DRY RUN — no files will be modified")
    if args.verify:
        mode_parts.append("verify ON" + (" (read-only)" if args.dry_run else ""))
    if mode_parts:
        print(f"Mode     : {', '.join(mode_parts)}")
    if args.limit:
        print(f"Limit    : {args.limit} files needing changes")
    print(f"Plan     : LIGHT/FLAT → rename {OLD_KEYWORD} → {NEW_KEYWORD}")
    print(f"           DARK/BIAS  → remove {OLD_KEYWORD} and {NEW_KEYWORD}")
    print()

    rows = _fetch_all_files(conn)
    conn.close()

    print(f"Total files in database : {len(rows)}")

    counters = {
        "renamed":        0,   # LIGHT/FLAT: IMG_SESS → IMGSESS written
        "lf_dry_run":     0,   # LIGHT/FLAT: would rename (dry-run)
        "already_ok":     0,   # LIGHT/FLAT: IMGSESS already present, no IMG_SESS
        "no_old_kw":      0,   # LIGHT/FLAT: neither keyword in header
        "removed":        0,   # DARK/BIAS:  keywords deleted
        "cal_dry_run":    0,   # DARK/BIAS:  would delete (dry-run)
        "already_clean":  0,   # DARK/BIAS:  no keywords present
        "not_on_disk":    0,
        "error":          0,
        "verify_pass":    0,
        "verify_fail":    0,
    }

    json_records: list[dict] = []
    changes_made = 0

    for row in rows:
        folder   = row["folder"] or ""
        filename = row["filename"] or ""
        fits_path = Path(folder) / filename if folder and filename else None
        ft = (row["frame_type"] or "").upper()

        if fits_path is None or not fits_path.exists():
            counters["not_on_disk"] += 1
            if args.verbose:
                print(f"  SKIP (not on disk): {fits_path or filename}")
            if args.output_json:
                json_records.append(_row_to_dict(row, fits_path, "skip", "not_on_disk", None))
            continue

        # Apply limit only to files that will actually be changed
        if args.limit and changes_made >= args.limit:
            break

        is_calibration = ft in CALIBRATION_TYPES

        if is_calibration:
            status = _fix_calibration(fits_path, args.dry_run, args.verbose)
            if status == "dry_run":
                counters["cal_dry_run"] += 1
                changes_made += 1
            else:
                counters[status] = counters.get(status, 0) + 1
                if status == "removed":
                    changes_made += 1

            verify_result = None
            if args.verify and status in ("removed", "dry_run"):
                vr = _verify_calibration(fits_path)
                verify_result = vr
                if vr == "pass":
                    counters["verify_pass"] += 1
                    if args.verbose:
                        print(f"    [✓] verified: no session keywords remain")
                else:
                    counters["verify_fail"] += 1
                    if not args.dry_run:
                        print(f"    [✗] verify FAILED ({vr}): {fits_path}", file=sys.stderr)
                    elif args.verbose:
                        print(f"    [?] current header: keywords still present (expected after dry-run)")

        else:
            img_sess = row["imaging_session_id"] or ""
            status = _fix_light_flat(fits_path, img_sess, args.dry_run, args.verbose)
            if status == "dry_run":
                counters["lf_dry_run"] += 1
                changes_made += 1
            else:
                counters[status] = counters.get(status, 0) + 1
                if status == "renamed":
                    changes_made += 1

            verify_result = None
            if args.verify and status in ("renamed", "dry_run"):
                vr, actual = _verify_light_flat(fits_path)
                verify_result = vr
                if vr == "pass":
                    counters["verify_pass"] += 1
                    if args.verbose:
                        print(f"    [✓] verified: {NEW_KEYWORD}={actual!r}, {OLD_KEYWORD} gone")
                else:
                    counters["verify_fail"] += 1
                    if not args.dry_run:
                        print(f"    [✗] verify FAILED ({vr}): {fits_path}", file=sys.stderr)
                    elif args.verbose:
                        print(f"    [?] current header: {vr} (expected before dry-run write)")

        if args.output_json:
            json_records.append(_row_to_dict(row, fits_path, status, None, verify_result))

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    action = "Would change" if args.dry_run else "Changed"
    print(f"{action}               : {changes_made}")
    print()
    print("LIGHT / FLAT:")
    lf_changed = counters["renamed"] + counters["lf_dry_run"]
    print(f"  Renamed {OLD_KEYWORD} → {NEW_KEYWORD} : {lf_changed}")
    print(f"  Already had {NEW_KEYWORD}        : {counters['already_ok']}")
    print(f"  Neither keyword present   : {counters['no_old_kw']}")
    print()
    print("DARK / BIAS:")
    cal_changed = counters["removed"] + counters["cal_dry_run"]
    print(f"  Keywords removed          : {cal_changed}")
    print(f"  Already clean             : {counters['already_clean']}")
    print()
    print(f"Not on disk               : {counters['not_on_disk']}")
    print(f"Errors                    : {counters['error']}")

    if args.verify and changes_made:
        print()
        print("Verification:")
        print(f"  Pass : {counters['verify_pass']}")
        if counters["verify_fail"]:
            print(f"  FAIL : {counters['verify_fail']}")

    # ------------------------------------------------------------------
    # JSON
    # ------------------------------------------------------------------
    if args.output_json and json_records:
        groups: dict[str, list[dict]] = {}
        for rec in json_records:
            ft_key = rec["frame_type"]
            groups.setdefault(ft_key, []).append(rec)

        payload = {
            "generated_at":  datetime.now(timezone.utc).isoformat(),
            "old_keyword":   OLD_KEYWORD,
            "new_keyword":   NEW_KEYWORD,
            "dry_run":       args.dry_run,
            "summary": {
                "total_in_db":           len(json_records),
                "changes_made":          changes_made,
                "lf_renamed":            counters["renamed"] + counters["lf_dry_run"],
                "lf_already_ok":         counters["already_ok"],
                "lf_neither_keyword":    counters["no_old_kw"],
                "cal_keywords_removed":  counters["removed"] + counters["cal_dry_run"],
                "cal_already_clean":     counters["already_clean"],
                "not_on_disk":           counters["not_on_disk"],
                "errors":                counters["error"],
                "verify_pass":           counters["verify_pass"],
                "verify_fail":           counters["verify_fail"],
            },
            "files_by_type": {ft: groups[ft] for ft in sorted(groups)},
        }
        _write_json(Path(args.output_json), payload)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            f"One-off utility to fix the session keyword on already-stamped files.\n\n"
            f"  LIGHT / FLAT : rename {OLD_KEYWORD} → {NEW_KEYWORD}\n"
            f"  DARK  / BIAS : remove {OLD_KEYWORD} and {NEW_KEYWORD} if present\n\n"
            "Files that already have the correct state are skipped silently."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Preview first 20 files that need a change\n"
            "  %(prog)s --dry-run --limit 20 -v\n\n"
            "  # Fix 100 files and verify each one\n"
            "  %(prog)s --limit 100 --verify -v\n\n"
            "  # Full run with JSON report\n"
            "  %(prog)s --verify --output-json fix_report.json\n"
        ),
    )

    parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Show what would change without modifying any FITS files.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help=(
            "After each write, re-read the header to confirm the change took effect. "
            "In --dry-run mode, reports the current header state instead."
        ),
    )
    parser.add_argument(
        "--limit",
        metavar="N",
        type=int,
        default=0,
        help=(
            "Stop after making N changes. Files already in the correct state and "
            "files not found on disk do not count toward the limit. 0 = no limit."
        ),
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print each file path as it is processed.",
    )
    parser.add_argument(
        "--output-json",
        metavar="PATH",
        help="Write a JSON report of every processed file to PATH, grouped by frame type.",
    )
    parser.add_argument(
        "--db",
        metavar="PATH",
        help=(
            "Path to the astro_cat SQLite database. "
            "Auto-detected from config.json if omitted."
        ),
    )

    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
