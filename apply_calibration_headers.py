"""Apply calibration-match FITS header keywords to light frames.

Reads the JSON produced by the Calibration Scoring tool
(<session_id>_calibration_scoring.json) and writes custom FITS header
keywords to each light frame so that PixInsight WBPP can group frames
with the correct calibration set, even when the sensor metadata isn't
perfectly consistent across sessions.

Keywords written
----------------
CAL_DARK   – imaging_session_id of the best-matching dark set
CAL_FLAT   – imaging_session_id of the best-matching flat set
CAL_BIAS   – imaging_session_id of the best-matching bias set
CAL_SCORE  – composite match quality string (dark/flat/bias scores)
CAL_DSCOR  – dark match score (integer)
CAL_FSCOR  – flat match score (integer)
CAL_BSCOR  – bias match score (integer)

All keywords are written as FITS string cards.  Existing cards with the
same keyword are replaced; other existing cards are preserved.

Usage
-----
    python apply_calibration_headers.py <scoring_json> [options]

    -d / --dry-run      Show what would be written without modifying files
    -v / --verbose      Print each file path as it is processed
    --fits-root PATH    Root directory to prepend to staged_filename paths
                        when the files have been moved to a new location.
                        If omitted, the script looks for files at the paths
                        stored in staged_path.

Requirements
------------
    pip install astropy

The script intentionally has no dependency on the rest of the astro_cat
codebase so that it can be run on a standalone processing workstation.
"""

import argparse
import json
import sys
from pathlib import Path


def _get_imaging_session(match_entry: dict | None) -> str | None:
    """Extract the first imaging_session_id from a best-match entry."""
    if not match_entry:
        return None
    sessions = match_entry.get("imaging_session_ids", [])
    return sessions[0] if sessions else None


def _build_per_file_assignments(scoring_data: dict) -> dict[int, dict]:
    """
    Return a mapping of file_id -> {cal_dark, cal_flat, cal_bias, scores}.
    """
    assignments: dict[int, dict] = {}

    for lg in scoring_data.get("light_group_matches", []):
        best_dark = lg.get("best_dark")
        best_flat = lg.get("best_flat")
        best_bias = lg.get("best_bias")

        cal_dark = _get_imaging_session(best_dark)
        cal_flat = _get_imaging_session(best_flat)
        cal_bias = _get_imaging_session(best_bias)

        d_score = round(best_dark["score"]) if best_dark else None
        f_score = round(best_flat["score"]) if best_flat else None
        b_score = round(best_bias["score"]) if best_bias else None

        score_str = (
            f"D:{d_score if d_score is not None else 'N/A'} "
            f"F:{f_score if f_score is not None else 'N/A'} "
            f"B:{b_score if b_score is not None else 'N/A'}"
        )

        for file_id in lg.get("light_file_ids", []):
            assignments[file_id] = {
                "cal_dark":  cal_dark,
                "cal_flat":  cal_flat,
                "cal_bias":  cal_bias,
                "d_score":   d_score,
                "f_score":   f_score,
                "b_score":   b_score,
                "score_str": score_str,
            }

    return assignments


def _find_light_paths(scoring_data: dict, fits_root: Path | None) -> dict[int, Path]:
    """
    Build file_id -> Path mapping from the 'lights' array in the JSON.
    Falls back to staged_filename under fits_root if fits_root is given.
    """
    paths: dict[int, Path] = {}
    for light in scoring_data.get("lights", []):
        fid = light.get("id")
        if fid is None:
            continue

        if fits_root:
            staged_fn = light.get("staged_filename") or light.get("file")
            if staged_fn:
                paths[fid] = fits_root / staged_fn
        else:
            staged = light.get("staged_path")
            if staged:
                paths[fid] = Path(staged)

    return paths


def _write_headers(fits_path: Path, assignment: dict, dry_run: bool, verbose: bool) -> bool:
    """Write calibration assignment keywords to a FITS file. Returns True on success."""
    try:
        from astropy.io import fits as astrofits
    except ImportError:
        print("ERROR: astropy is required.  Install it with:  pip install astropy", file=sys.stderr)
        sys.exit(1)

    if not fits_path.exists():
        print(f"  SKIP (not found): {fits_path}", file=sys.stderr)
        return False

    if dry_run:
        if verbose:
            print(f"  [dry-run] would write to {fits_path}")
            print(f"    CAL_DARK={assignment['cal_dark']!r}")
            print(f"    CAL_FLAT={assignment['cal_flat']!r}")
            print(f"    CAL_BIAS={assignment['cal_bias']!r}")
            print(f"    CAL_SCORE={assignment['score_str']!r}")
        return True

    try:
        with astrofits.open(fits_path, mode="update") as hdul:
            hdr = hdul[0].header

            def _set(keyword: str, value, comment: str):
                if value is None:
                    value = "NONE"
                # FITS string values max 68 chars
                value = str(value)[:68]
                if keyword in hdr:
                    hdr[keyword] = value
                else:
                    hdr.append((keyword, value, comment), end=True)

            _set("CAL_DARK",  assignment["cal_dark"],  "Best-match dark calibration imaging session")
            _set("CAL_FLAT",  assignment["cal_flat"],  "Best-match flat calibration imaging session")
            _set("CAL_BIAS",  assignment["cal_bias"],  "Best-match bias calibration imaging session")
            _set("CAL_SCORE", assignment["score_str"], "Calibration match scores D/F/B")
            if assignment["d_score"] is not None:
                _set("CAL_DSCOR", str(assignment["d_score"]), "Dark calibration match score")
            if assignment["f_score"] is not None:
                _set("CAL_FSCOR", str(assignment["f_score"]), "Flat calibration match score")
            if assignment["b_score"] is not None:
                _set("CAL_BSCOR", str(assignment["b_score"]), "Bias calibration match score")

            hdul.flush()

        if verbose:
            print(f"  OK: {fits_path}")
        return True

    except Exception as exc:
        print(f"  ERROR writing {fits_path}: {exc}", file=sys.stderr)
        return False


def apply_headers(scoring_json: Path, fits_root: Path | None, dry_run: bool, verbose: bool):
    """Main logic: load scoring JSON and apply headers to all light files."""
    with open(scoring_json, encoding="utf-8") as fh:
        scoring_data = json.load(fh)

    assignments = _build_per_file_assignments(scoring_data)
    file_paths  = _find_light_paths(scoring_data, fits_root)

    session_name = scoring_data.get("session", {}).get("name", str(scoring_json))
    print(f"Session: {session_name}")
    print(f"Light groups: {len(scoring_data.get('light_group_matches', []))}")
    print(f"Files with assignments: {len(assignments)}")
    print(f"Files with paths: {len(file_paths)}")
    if dry_run:
        print("DRY RUN — no files will be modified.\n")

    ok = skipped = errors = 0

    for file_id, assignment in assignments.items():
        fits_path = file_paths.get(file_id)
        if fits_path is None:
            if verbose:
                print(f"  SKIP (no path for file_id={file_id})")
            skipped += 1
            continue

        success = _write_headers(fits_path, assignment, dry_run, verbose)
        if success:
            ok += 1
        else:
            errors += 1

    print(f"\nDone: {ok} written, {skipped} skipped (no path), {errors} errors.")

    # Print summary of assignments
    print("\nCalibration assignment summary:")
    for lg in scoring_data.get("light_group_matches", []):
        key = lg["light_key"]
        filt = key.get("filter") or "NoFilter"
        exp  = key.get("exposure")
        cnt  = lg.get("light_count", 0)
        bd   = lg.get("best_dark")
        bf   = lg.get("best_flat")
        bb   = lg.get("best_bias")
        print(f"  {filt} {exp}s × {cnt}:")
        print(f"    DARK  → {_get_imaging_session(bd) or 'NONE'} (score={round(bd['score']) if bd else 'N/A'})")
        print(f"    FLAT  → {_get_imaging_session(bf) or 'NONE'} (score={round(bf['score']) if bf else 'N/A'})")
        print(f"    BIAS  → {_get_imaging_session(bb) or 'NONE'} (score={round(bb['score']) if bb else 'N/A'})")


def main():
    parser = argparse.ArgumentParser(
        description="Write calibration-match FITS header keywords to light frames."
    )
    parser.add_argument(
        "scoring_json",
        help="JSON file produced by the Calibration Scoring tool "
             "(<session_id>_calibration_scoring.json)"
    )
    parser.add_argument(
        "--fits-root", "-r",
        help="Root directory where FITS files live on this workstation. "
             "The staged_filename from the JSON is appended to this path. "
             "If omitted, staged_path is used directly."
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Show what would be written without touching any files."
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print each file path as it is processed."
    )

    args = parser.parse_args()

    scoring_json = Path(args.scoring_json)
    if not scoring_json.exists():
        print(f"Error: JSON file not found: {scoring_json}", file=sys.stderr)
        sys.exit(1)

    fits_root = Path(args.fits_root) if args.fits_root else None

    apply_headers(scoring_json, fits_root, args.dry_run, args.verbose)


if __name__ == "__main__":
    main()
