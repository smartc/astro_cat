"""Backfill the IMGSESS FITS header keyword for cataloged files that are missing it.

Queries the astro_cat database for every fits_file record that has an
imaging_session_id, then checks whether the corresponding file on disk
already carries the keyword.  Files that are missing the keyword are
stamped (or previewed in dry-run mode).

Safe by default
---------------
  -n / --dry-run   Preview what would be written without touching any files.
  --limit N        Cap the number of files processed (useful for spot checks).
  --verify         After writing, re-read the header to confirm the value was
                   stored correctly.  In dry-run mode this performs a
                   read-only check of whatever is currently in the header.
  --output-json P  Write a JSON report to path P.
  --all            Also re-stamp files that already have the keyword
                   (useful if you changed the keyword name or want to
                   force an update to the current imaging_session_id).

Usage
-----
    # Preview first 10 files that are missing the header
    python backfill_img_sess.py --dry-run --limit 10 -v

    # Stamp all files missing the keyword, with verification
    python backfill_img_sess.py --verify -v

    # Full run with JSON report
    python backfill_img_sess.py --verify --output-json backfill_report.json

Requirements
------------
    pip install astropy

The script is standalone — the only astro_cat dependency is the SQLite
database (located automatically via config.json, or supplied with --db).
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Database helpers  (shared pattern with stamp_imaging_session.py)
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


def _fetch_candidates(conn: sqlite3.Connection, include_calibrations: bool = False) -> list[sqlite3.Row]:
    """Return fits_file rows that have a non-null imaging_session_id.

    Dark and bias frames are excluded by default because they are reusable
    across sessions and don't need session matching in WBPP.
    Pass include_calibrations=True to override.
    """
    extra = "" if include_calibrations else "AND UPPER(ff.frame_type) NOT IN ('DARK', 'BIAS')"
    cur = conn.execute(
        f"""
        SELECT
            ff.id               AS fits_file_id,
            ff.file             AS filename,
            ff.folder           AS folder,
            ff.imaging_session_id AS imaging_session_id,
            ff.frame_type       AS frame_type,
            ff.object           AS object,
            ff.obs_date         AS obs_date,
            ff.filter           AS filter,
            ff.exposure         AS exposure,
            ff.camera           AS camera,
            ff.telescope        AS telescope
        FROM fits_files ff
        WHERE ff.imaging_session_id IS NOT NULL
          AND ff.imaging_session_id != ''
          {extra}
        ORDER BY ff.imaging_session_id, ff.id
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


def _header_has_keyword(fits_path: Path, keyword: str) -> tuple[bool, str | None]:
    """Return (has_keyword, current_value_or_None).  Returns (False, 'error') on failure."""
    astrofits = _get_astrofits()
    try:
        with astrofits.open(fits_path, mode="readonly") as hdul:
            hdr = hdul[0].header
            if keyword in hdr:
                return True, str(hdr[keyword]).strip()
            return False, None
    except Exception as exc:
        return False, f"error:{exc}"


def _write_header(
    fits_path: Path,
    imaging_session_id: str,
    keyword: str,
    dry_run: bool,
    verbose: bool,
) -> str:
    """Write keyword to FITS file.  Returns 'ok' | 'dry_run' | 'error'."""
    if dry_run:
        if verbose:
            print(f"  [dry-run] would write {keyword}={imaging_session_id!r}  {fits_path}")
        return "dry_run"

    astrofits = _get_astrofits()
    try:
        with astrofits.open(fits_path, mode="update") as hdul:
            hdr = hdul[0].header
            value = str(imaging_session_id)[:68]
            if keyword in hdr:
                hdr[keyword] = value
            else:
                hdr.append(
                    (keyword, value, "astro_cat imaging session identifier"),
                    end=True,
                )
            hdul.flush()
        if verbose:
            print(f"  OK  {fits_path}  [{keyword}={imaging_session_id!r}]")
        return "ok"
    except Exception as exc:
        print(f"  ERROR: {fits_path}: {exc}", file=sys.stderr)
        return "error"


def _verify_header(
    fits_path: Path,
    keyword: str,
    expected: str,
) -> tuple[str, str | None]:
    """Re-read keyword after write.  Returns (result, actual_value)."""
    astrofits = _get_astrofits()
    try:
        with astrofits.open(fits_path, mode="readonly") as hdul:
            hdr = hdul[0].header
            if keyword not in hdr:
                return "missing", None
            actual = str(hdr[keyword]).strip()
            return ("pass" if actual == str(expected).strip() else "mismatch"), actual
    except Exception as exc:
        return "error", str(exc)


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def _row_to_dict(
    row: sqlite3.Row,
    fits_path: Path | None,
    status: str,
    skipped_reason: str | None,
    verify_result: str | None,
    verify_actual: str | None,
    keyword: str,
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
        "stamp_status":       status,
    }
    if skipped_reason:
        d["skipped_reason"] = skipped_reason
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

def run(args: argparse.Namespace) -> None:
    db_path = _find_db(args.db)
    conn = _connect(db_path)

    print(f"Database : {db_path}")
    print(f"Keyword  : {args.keyword}")

    mode_parts = []
    if args.dry_run:
        mode_parts.append("DRY RUN — no files will be modified")
    if args.verify:
        mode_parts.append("verify ON" + (" (read-only check)" if args.dry_run else ""))
    if args.all:
        mode_parts.append("--all: re-stamp files that already have the keyword")
    if args.include_calibrations:
        mode_parts.append("--include-calibrations: including DARK and BIAS frames")
    if mode_parts:
        print(f"Mode     : {', '.join(mode_parts)}")
    if args.limit:
        print(f"Limit    : {args.limit} files")
    if not args.include_calibrations:
        print("Skipping  : DARK and BIAS frames (use --include-calibrations to override)")
    print()

    rows = _fetch_candidates(conn, include_calibrations=args.include_calibrations)
    conn.close()

    total_in_db = len(rows)
    print(f"Files in database with imaging_session_id : {total_in_db}")

    if not rows:
        print("Nothing to do.")
        return

    counters = {
        "ok": 0,
        "dry_run": 0,
        "already_stamped": 0,
        "skip_not_found": 0,
        "skip_no_session": 0,
        "error": 0,
        "verify_pass": 0,
        "verify_mismatch": 0,
        "verify_missing": 0,
        "verify_error": 0,
    }

    json_records: list[dict] = []
    processed = 0

    for row in rows:
        img_sess = row["imaging_session_id"]
        if not img_sess:
            counters["skip_no_session"] += 1
            if args.output_json:
                json_records.append(
                    _row_to_dict(row, None, "skip", "no_imaging_session_id", None, None, args.keyword)
                )
            continue

        folder = row["folder"] or ""
        filename = row["filename"] or ""
        fits_path = Path(folder) / filename if folder and filename else None

        if fits_path is None or not fits_path.exists():
            counters["skip_not_found"] += 1
            if args.verbose:
                print(f"  SKIP (not on disk): {fits_path or filename}")
            if args.output_json:
                json_records.append(
                    _row_to_dict(row, fits_path, "skip", "file_not_found", None, None, args.keyword)
                )
            continue

        # Check current header state
        has_kw, current_val = _header_has_keyword(fits_path, args.keyword)

        if has_kw and not args.all:
            counters["already_stamped"] += 1
            if args.verbose:
                print(f"  SKIP (already has {args.keyword}={current_val!r}): {fits_path}")
            if args.output_json:
                json_records.append(
                    _row_to_dict(row, fits_path, "already_stamped", None, None, current_val, args.keyword)
                )
            continue

        # Apply the limit only to files we actually intend to stamp
        if args.limit and processed >= args.limit:
            break

        processed += 1

        write_status = _write_header(
            fits_path, img_sess, args.keyword, args.dry_run, args.verbose
        )
        counters[write_status] = counters.get(write_status, 0) + 1

        verify_result = verify_actual = None
        if args.verify and write_status in ("ok", "dry_run"):
            verify_result, verify_actual = _verify_header(fits_path, args.keyword, img_sess)
            counters[f"verify_{verify_result}"] = counters.get(f"verify_{verify_result}", 0) + 1

            if args.verbose or verify_result != "pass":
                icon = {"pass": "✓", "mismatch": "✗", "missing": "?", "error": "!"}.get(verify_result, "?")
                if args.dry_run:
                    if verify_result == "pass":
                        msg = f"already set to {verify_actual!r}"
                    elif verify_result == "missing":
                        msg = "keyword not yet present"
                    elif verify_result == "mismatch":
                        msg = f"currently {verify_actual!r} (expected {img_sess!r})"
                    else:
                        msg = verify_actual or "unknown error"
                    print(f"    [{icon}] current header: {msg}")
                else:
                    if verify_result == "pass":
                        print(f"    [{icon}] verified: {verify_actual!r}")
                    elif verify_result == "mismatch":
                        print(
                            f"    [{icon}] MISMATCH: header={verify_actual!r}, expected={img_sess!r}",
                            file=sys.stderr,
                        )
                    elif verify_result == "missing":
                        print(f"    [{icon}] MISSING: keyword not found after write", file=sys.stderr)
                    else:
                        print(f"    [{icon}] verify error: {verify_actual}", file=sys.stderr)

        if args.output_json:
            json_records.append(
                _row_to_dict(row, fits_path, write_status, None, verify_result, verify_actual, args.keyword)
            )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    action = "Would stamp" if args.dry_run else "Stamped"
    stamped = counters["ok"] + counters["dry_run"]
    print(f"{action}          : {stamped}")
    print(f"Already stamped  : {counters['already_stamped']} (skipped)")
    print(f"File not on disk : {counters['skip_not_found']} (skipped)")
    if counters["skip_no_session"]:
        print(f"No session ID    : {counters['skip_no_session']} (skipped)")
    print(f"Errors           : {counters['error']}")

    if args.verify and stamped:
        print()
        print("Verification:")
        print(f"  Pass     : {counters['verify_pass']}")
        if counters["verify_missing"]:
            print(f"  Missing  : {counters['verify_missing']}")
        if counters["verify_mismatch"]:
            print(f"  Mismatch : {counters['verify_mismatch']}")
        if counters["verify_error"]:
            print(f"  Error    : {counters['verify_error']}")

    # ------------------------------------------------------------------
    # JSON output
    # ------------------------------------------------------------------
    if args.output_json and json_records:
        groups: dict[str, list[dict]] = {}
        for rec in json_records:
            ft = rec["frame_type"]
            groups.setdefault(ft, []).append(rec)

        payload = {
            "generated_at":        datetime.now(timezone.utc).isoformat(),
            "keyword":             args.keyword,
            "dry_run":             args.dry_run,
            "summary": {
                "total_in_db":        total_in_db,
                "stamped":            stamped,
                "already_stamped":    counters["already_stamped"],
                "file_not_on_disk":   counters["skip_not_found"],
                "no_session_id":      counters["skip_no_session"],
                "errors":             counters["error"],
                "verify_pass":        counters["verify_pass"],
                "verify_missing":     counters["verify_missing"],
                "verify_mismatch":    counters["verify_mismatch"],
                "verify_error":       counters["verify_error"],
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
            "Backfill the IMGSESS FITS header keyword for cataloged files\n"
            "that are missing it.\n\n"
            "Queries the astro_cat database for all fits_file records that\n"
            "have an imaging_session_id, checks whether the keyword is already\n"
            "present in the FITS header on disk, and stamps any that are missing."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Dry run — preview first 10 files that need stamping\n"
            "  %(prog)s --dry-run --limit 10 -v\n\n"
            "  # Stamp first 10 for real, then verify\n"
            "  %(prog)s --limit 10 --verify -v\n\n"
            "  # Full backfill with JSON report\n"
            "  %(prog)s --verify --output-json backfill_report.json\n\n"
            "  # Re-stamp everything (even files that already have the keyword)\n"
            "  %(prog)s --all --verify -v\n"
        ),
    )

    parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Show what would be written without modifying any FITS files.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help=(
            "Re-stamp files that already carry the keyword "
            "(useful to force an update to the current imaging_session_id)."
        ),
    )
    parser.add_argument(
        "--include-calibrations",
        action="store_true",
        help=(
            "Also stamp DARK and BIAS frames "
            "(excluded by default since they are reused across sessions)."
        ),
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help=(
            "After writing, re-read the header and confirm the value was stored "
            "correctly.  In --dry-run mode, performs a read-only check of whatever "
            "is currently in the header."
        ),
    )
    parser.add_argument(
        "--limit",
        metavar="N",
        type=int,
        default=0,
        help=(
            "Process at most N files that need stamping "
            "(already-stamped and missing-on-disk files do not count toward the limit; "
            "0 = no limit)."
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
        help="Write a JSON report of all processed files to PATH, grouped by frame type.",
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
