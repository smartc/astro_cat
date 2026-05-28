"""Stamp the Imaging Session ID into raw FITS file headers.

Reads a Processing Session from the astro_cat database, finds all staged
source files that belong to it, and writes the IMGSESS (or a custom
keyword) FITS header card so that downstream tools can identify which
imaging session each frame came from.

Keywords written
----------------
IMGSESS  – imaging_session_id from the astro_cat catalog (e.g. 20241103_A3F2C1D9)
            Can be overridden with --keyword.

Safe by default
---------------
  -n / --dry-run   Print what would be written without touching any files.
  --limit N        Cap the number of files processed (useful for spot checks).
  --verify         After writing, re-read the header to confirm the value was
                   stored correctly.  In dry-run mode performs a read-only
                   check of whatever is currently in the header.
  --output-json P  Write a JSON report (grouped by frame type, with key
                   metadata) to path P.

Usage
-----
    python stamp_imaging_session.py <processing_session_id> [options]

    # Dry run — preview lights and flats, then check existing header values
    python stamp_imaging_session.py PS-20241103-001 -LF --dry-run --verify -v

    # Test stamp + verify 5 files
    python stamp_imaging_session.py PS-20241103-001 -LF --limit 5 --verify -v

    # Full run with JSON report
    python stamp_imaging_session.py PS-20241103-001 --verify --output-json report.json

Frame-type flags (default: all frame types)
-------------------------------------------
  -L / --lights         Light frames only
  -C / --calibrations   All calibration frames (darks + flats + bias)
  -D / --darks          Dark frames only
  -F / --flats          Flat frames only
  -B / --bias           Bias frames only

Flags may be combined: -L -D processes lights AND darks.

Requirements
------------
    pip install astropy

The script is intentionally standalone — the only astro_cat dependency is
the SQLite database (located automatically via config.json in the script
directory, or supplied with --db).
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _find_db(explicit_path: str | None) -> Path:
    """Locate the SQLite database.

    Priority:
    1. --db argument
    2. config.json next to this script
    3. config.json in the current working directory
    """
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

                # Resolve the {{database_path}} template the same way the
                # main app does: substitute paths.database_path first.
                db_path_raw = cfg.get("paths", {}).get("database_path", "")
                db_path_expanded = os.path.expanduser(os.path.expandvars(db_path_raw))

                raw = (
                    cfg.get("database", {}).get("connection_string", "")
                    or db_path_raw
                )
                # Substitute template placeholder before stripping prefix
                raw = raw.replace("{{database_path}}", db_path_expanded)
                raw = os.path.expanduser(os.path.expandvars(raw))

                # Strip SQLAlchemy prefix if present
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


def _fetch_session(conn: sqlite3.Connection, session_id: str) -> sqlite3.Row | None:
    cur = conn.execute(
        "SELECT id, name, status FROM processing_sessions WHERE id = ?",
        (session_id,),
    )
    return cur.fetchone()


def _fetch_files(
    conn: sqlite3.Connection,
    session_id: str,
    frame_types: set[str] | None,
) -> list[sqlite3.Row]:
    """Return rows with path, frame_type, imaging_session_id, and key metadata.

    Joins processing_session_files → fits_files to get the full picture.
    """
    placeholders = ""
    params: list = [session_id]

    if frame_types:
        ph = ",".join("?" * len(frame_types))
        placeholders = f" AND UPPER(psf.frame_type) IN ({ph})"
        params.extend(f.upper() for f in frame_types)

    sql = f"""
        SELECT
            psf.id                  AS psf_id,
            psf.staged_path         AS staged_path,
            psf.original_path       AS original_path,
            psf.frame_type          AS frame_type,
            ff.id                   AS fits_file_id,
            ff.imaging_session_id   AS imaging_session_id,
            ff.file                 AS filename,
            ff.folder               AS folder,
            ff.object               AS object,
            ff.obs_date             AS obs_date,
            ff.filter               AS filter,
            ff.exposure             AS exposure,
            ff.camera               AS camera,
            ff.telescope            AS telescope,
            ff.gain                 AS gain,
            ff.offset               AS offset,
            ff.binning_x            AS binning_x,
            ff.binning_y            AS binning_y,
            ff.sensor_temp          AS sensor_temp,
            ff.width_pixels         AS width_pixels,
            ff.height_pixels        AS height_pixels
        FROM processing_session_files psf
        JOIN fits_files ff ON ff.id = psf.fits_file_id
        WHERE psf.processing_session_id = ?
        {placeholders}
        ORDER BY psf.frame_type, psf.id
    """
    cur = conn.execute(sql, params)
    return cur.fetchall()


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def _resolve_path(row: sqlite3.Row, fits_root: Path | None) -> Path | None:
    """Return the best available path for a file row."""
    if fits_root:
        folder = row["folder"] or ""
        filename = row["filename"] or ""
        if folder and filename:
            candidate = fits_root / folder.lstrip("/") / filename
            if candidate.exists():
                return candidate
        if filename:
            candidate = fits_root / filename
            if candidate.exists():
                return candidate

    # Try staged path first (where files were copied for processing)
    if row["staged_path"]:
        p = Path(row["staged_path"])
        if p.exists():
            return p

    # Fall back to original ingest location
    if row["original_path"]:
        p = Path(row["original_path"])
        if p.exists():
            return p

    # Reconstruct from folder + filename stored in fits_files table
    folder = row["folder"]
    filename = row["filename"]
    if folder and filename:
        p = Path(folder) / filename
        if p.exists():
            return p

    return None


# ---------------------------------------------------------------------------
# FITS header writing and verification
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


def _write_header(
    fits_path: Path,
    imaging_session_id: str,
    keyword: str,
    dry_run: bool,
    verbose: bool,
) -> str:
    """Write keyword to a FITS file.  Returns: 'ok' | 'dry_run' | 'error'."""
    if dry_run:
        if verbose:
            print(f"  [dry-run] {fits_path}")
            print(f"    {keyword} = {imaging_session_id!r}")
        return "dry_run"

    astrofits = _get_astrofits()
    try:
        with astrofits.open(fits_path, mode="update") as hdul:
            hdr = hdul[0].header
            value = str(imaging_session_id)[:68]
            comment = "astro_cat imaging session identifier"
            if keyword in hdr:
                hdr[keyword] = value
            else:
                hdr.append((keyword, value, comment), end=True)
            hdul.flush()

        if verbose:
            print(f"  OK: {fits_path}  [{keyword}={imaging_session_id!r}]")
        return "ok"

    except Exception as exc:
        print(f"  ERROR: {fits_path}: {exc}", file=sys.stderr)
        return "error"


def _verify_header(
    fits_path: Path,
    keyword: str,
    expected: str,
) -> tuple[str, str | None]:
    """Read back the keyword from the FITS header.

    Returns (result, actual_value) where result is one of:
      'pass'    – keyword present and matches expected
      'mismatch'– keyword present but value differs
      'missing' – keyword not in header
      'error'   – could not open file
    """
    astrofits = _get_astrofits()
    try:
        with astrofits.open(fits_path, mode="readonly") as hdul:
            hdr = hdul[0].header
            if keyword not in hdr:
                return ("missing", None)
            actual = str(hdr[keyword]).strip()
            if actual == str(expected).strip():
                return ("pass", actual)
            return ("mismatch", actual)
    except Exception as exc:
        return ("error", str(exc))


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def _row_to_dict(row: sqlite3.Row, fits_path: Path | None, status: str,
                 verify_result: str | None, verify_actual: str | None,
                 keyword: str) -> dict:
    """Build the per-file dict for JSON output."""
    binx = row["binning_x"]
    biny = row["binning_y"]
    binning = f"{binx}x{biny}" if (binx and biny) else None

    d = {
        "fits_file_id":       row["fits_file_id"],
        "filename":           row["filename"],
        "path":               str(fits_path) if fits_path else None,
        "staged_path":        row["staged_path"],
        "original_path":      row["original_path"],
        "frame_type":         (row["frame_type"] or "UNKNOWN").upper(),
        "imaging_session_id": row["imaging_session_id"],
        "object":             row["object"],
        "obs_date":           row["obs_date"],
        "filter":             row["filter"],
        "exposure":           row["exposure"],
        "camera":             row["camera"],
        "telescope":          row["telescope"],
        "gain":               row["gain"],
        "offset":             row["offset"],
        "binning":            binning,
        "sensor_temp":        row["sensor_temp"],
        "width_pixels":       row["width_pixels"],
        "height_pixels":      row["height_pixels"],
        "stamp_status":       status,
    }

    if verify_result is not None:
        d["verify_result"] = verify_result
        d[f"{keyword}_in_header"] = verify_actual

    return d


def _write_json(output_path: Path, payload: dict) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=str)
    print(f"\nJSON report written to: {output_path}")


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def _build_frame_type_set(args: argparse.Namespace) -> set[str] | None:
    """Return the set of frame types to include, or None for 'all'."""
    requested: set[str] = set()
    if args.lights:
        requested.add("LIGHT")
    if args.darks:
        requested.add("DARK")
    if args.flats:
        requested.add("FLAT")
    if args.bias:
        requested.add("BIAS")
    if args.calibrations:
        requested.update({"DARK", "FLAT", "BIAS"})
    return requested if requested else None


def run(args: argparse.Namespace):
    db_path = _find_db(args.db)
    conn = _connect(db_path)

    # Validate processing session
    session_row = _fetch_session(conn, args.processing_session_id)
    if session_row is None:
        print(
            f"ERROR: Processing session '{args.processing_session_id}' not found in database.",
            file=sys.stderr,
        )
        sys.exit(1)

    session_name = session_row["name"] or args.processing_session_id
    print(f"Processing session : {args.processing_session_id}")
    print(f"  Name             : {session_name}")
    print(f"  Status           : {session_row['status']}")
    print(f"Database           : {db_path}")

    frame_types = _build_frame_type_set(args)
    if frame_types:
        print(f"Frame type filter  : {', '.join(sorted(frame_types))}")
    else:
        print("Frame type filter  : ALL")

    mode_parts = []
    if args.dry_run:
        mode_parts.append("DRY RUN — no files will be modified")
    if args.verify:
        mode_parts.append("verify ON" + (" (read-only check)" if args.dry_run else ""))
    if mode_parts:
        print(f"Mode               : {', '.join(mode_parts)}")
    if args.limit:
        print(f"Limit              : {args.limit} files")
    print(f"Header keyword     : {args.keyword}")
    if args.output_json:
        print(f"JSON output        : {args.output_json}")
    print()

    rows = _fetch_files(conn, args.processing_session_id, frame_types)
    conn.close()

    if not rows:
        filter_msg = f" with frame type in {frame_types}" if frame_types else ""
        print(f"No files found for this session{filter_msg}.")
        return

    print(f"Files found in session : {len(rows)}")

    if args.limit:
        rows = rows[: args.limit]
        print(f"Files after limit      : {len(rows)}")

    print()

    fits_root = Path(args.fits_root) if args.fits_root else None

    counters = {
        "ok": 0, "dry_run": 0, "skip": 0, "error": 0, "no_session": 0,
        "verify_pass": 0, "verify_mismatch": 0, "verify_missing": 0, "verify_error": 0,
    }
    type_counts: dict[str, int] = {}

    # Accumulate records for JSON output
    json_records: list[dict] = []

    for row in rows:
        ft = (row["frame_type"] or "UNKNOWN").upper()
        img_sess = row["imaging_session_id"]

        if not img_sess:
            if args.verbose:
                path_hint = row["staged_path"] or row["original_path"] or row["filename"]
                print(f"  SKIP (no imaging_session_id): {path_hint}")
            counters["no_session"] += 1
            if args.output_json:
                json_records.append(
                    _row_to_dict(row, None, "no_session_id", None, None, args.keyword)
                )
            continue

        fits_path = _resolve_path(row, fits_root)
        if fits_path is None:
            if args.verbose:
                print(
                    f"  SKIP (file not found on disk): "
                    f"{row['staged_path'] or row['original_path'] or row['filename']}"
                )
            counters["skip"] += 1
            if args.output_json:
                json_records.append(
                    _row_to_dict(row, None, "file_not_found", None, None, args.keyword)
                )
            continue

        write_status = _write_header(
            fits_path, img_sess, args.keyword, args.dry_run, args.verbose
        )
        counters[write_status] = counters.get(write_status, 0) + 1
        type_counts[ft] = type_counts.get(ft, 0) + 1

        # Verification
        verify_result = verify_actual = None
        if args.verify and write_status in ("ok", "dry_run"):
            verify_result, verify_actual = _verify_header(fits_path, args.keyword, img_sess)
            counters[f"verify_{verify_result}"] = counters.get(f"verify_{verify_result}", 0) + 1

            if args.verbose or verify_result != "pass":
                icon = {"pass": "✓", "mismatch": "✗", "missing": "?", "error": "!"}.get(
                    verify_result, "?"
                )
                if args.dry_run:
                    label = "current header"
                    if verify_result == "pass":
                        msg = f"already set to {verify_actual!r}"
                    elif verify_result == "missing":
                        msg = "keyword not yet present"
                    elif verify_result == "mismatch":
                        msg = f"currently set to {verify_actual!r} (expected {img_sess!r})"
                    else:
                        msg = verify_actual or "unknown error"
                    print(f"    [{icon}] {label}: {msg}")
                else:
                    if verify_result == "pass":
                        print(f"    [{icon}] verified: {verify_actual!r}")
                    elif verify_result == "mismatch":
                        print(
                            f"    [{icon}] MISMATCH: header has {verify_actual!r}, "
                            f"expected {img_sess!r}",
                            file=sys.stderr,
                        )
                    elif verify_result == "missing":
                        print(f"    [{icon}] MISSING: keyword not found after write", file=sys.stderr)
                    else:
                        print(f"    [{icon}] verify error: {verify_actual}", file=sys.stderr)

        if args.output_json:
            json_records.append(
                _row_to_dict(row, fits_path, write_status, verify_result, verify_actual, args.keyword)
            )

    # ------------------------------------------------------------------
    # Console summary
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    action = "Would write" if args.dry_run else "Written"
    written = counters["ok"] + counters["dry_run"]
    print(f"{action}  : {written}")
    print(f"Skipped   : {counters['skip']} (file not found on disk)")
    if counters["no_session"]:
        print(f"No session: {counters['no_session']} (no imaging_session_id in catalog)")
    print(f"Errors    : {counters['error']}")

    if args.verify and (written > 0):
        print()
        print("Verification:")
        print(f"  Pass     : {counters['verify_pass']}")
        if counters["verify_missing"]:
            print(f"  Missing  : {counters['verify_missing']}")
        if counters["verify_mismatch"]:
            print(f"  Mismatch : {counters['verify_mismatch']}")
        if counters["verify_error"]:
            print(f"  Error    : {counters['verify_error']}")

    if type_counts:
        print()
        print("By frame type:")
        for ft, cnt in sorted(type_counts.items()):
            print(f"  {ft:<8}: {cnt}")

    # ------------------------------------------------------------------
    # JSON output
    # ------------------------------------------------------------------
    if args.output_json and json_records:
        # Group by frame type
        groups: dict[str, list[dict]] = {}
        for rec in json_records:
            ft = rec["frame_type"]
            groups.setdefault(ft, []).append(rec)

        payload = {
            "processing_session_id": args.processing_session_id,
            "session_name":          session_name,
            "generated_at":          datetime.now(timezone.utc).isoformat(),
            "keyword":               args.keyword,
            "dry_run":               args.dry_run,
            "summary": {
                "total":            len(json_records),
                "written":          written,
                "skipped":          counters["skip"],
                "no_session_id":    counters["no_session"],
                "errors":           counters["error"],
                "verify_pass":      counters["verify_pass"],
                "verify_missing":   counters["verify_missing"],
                "verify_mismatch":  counters["verify_mismatch"],
                "verify_error":     counters["verify_error"],
            },
            "files_by_type": {ft: groups[ft] for ft in sorted(groups)},
        }
        _write_json(Path(args.output_json), payload)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Stamp the astro_cat Imaging Session ID into raw FITS file headers.\n\n"
            "Reads all source files belonging to a Processing Session and writes\n"
            "the IMGSESS header keyword to each file on disk."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Dry run with header verification (read-only check)\n"
            "  %(prog)s PS-20241103-001 -LF --dry-run --verify -v\n\n"
            "  # Stamp + verify first 5 files\n"
            "  %(prog)s PS-20241103-001 -LF --limit 5 --verify -v\n\n"
            "  # Full run with verification and JSON report\n"
            "  %(prog)s PS-20241103-001 --verify --output-json report.json\n"
        ),
    )

    parser.add_argument(
        "processing_session_id",
        metavar="PROCESSING_SESSION_ID",
        help="ID of the Processing Session whose files should be stamped.",
    )

    # Frame type flags
    ft_group = parser.add_argument_group(
        "frame type filters",
        "Select which frame types to process. Default: all frame types.\n"
        "Flags may be combined (e.g. -L -D processes lights AND darks).",
    )
    ft_group.add_argument("-L", "--lights",       action="store_true", help="Include light frames.")
    ft_group.add_argument("-C", "--calibrations", action="store_true", help="Include all calibration frames (darks + flats + bias).")
    ft_group.add_argument("-D", "--darks",        action="store_true", help="Include dark frames.")
    ft_group.add_argument("-F", "--flats",        action="store_true", help="Include flat frames.")
    ft_group.add_argument("-B", "--bias",         action="store_true", help="Include bias / zero frames.")

    # Options
    parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Show what would be written without modifying any FITS files.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help=(
            "After writing, re-read the header and confirm the value was stored "
            "correctly.  In --dry-run mode, performs a read-only check of "
            "whatever is currently in the header."
        ),
    )
    parser.add_argument(
        "--limit",
        metavar="N",
        type=int,
        default=0,
        help="Process at most N files (useful for testing; 0 = no limit).",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print each file path as it is processed.",
    )
    parser.add_argument(
        "--output-json",
        metavar="PATH",
        help=(
            "Write a JSON report of all processed files to PATH, grouped by "
            "frame type and including key metadata (object, filter, exposure, "
            "camera, gain, etc.) and stamp/verify status."
        ),
    )
    parser.add_argument(
        "--db",
        metavar="PATH",
        help=(
            "Path to the astro_cat SQLite database. "
            "Auto-detected from config.json if omitted."
        ),
    )
    parser.add_argument(
        "--fits-root",
        metavar="PATH",
        help=(
            "Root directory where FITS files live on this machine. "
            "Useful when the database paths refer to a different machine "
            "(e.g. after copying files to a processing workstation)."
        ),
    )
    parser.add_argument(
        "--keyword",
        metavar="KEY",
        default="IMGSESS",
        help="FITS header keyword to write (max 8 chars, default: IMGSESS).",
    )

    args = parser.parse_args()

    if len(args.keyword) > 8:
        print(
            f"ERROR: --keyword '{args.keyword}' is {len(args.keyword)} characters; "
            "FITS keywords must be 8 characters or fewer.",
            file=sys.stderr,
        )
        sys.exit(1)
    args.keyword = args.keyword.upper()

    run(args)


if __name__ == "__main__":
    main()
