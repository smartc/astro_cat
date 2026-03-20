"""Match calibration frames to light frame groups.

Reads the JSON produced by export_calibration_analysis.py and scores every
available calibration set (dark/flat/bias) against every light group, then
recommends the best available match for each.

The scoring model recognises three classes of field:

  HARD   – camera, binning_x, binning_y
           A mismatch here disqualifies the calibration set entirely.

  EXACT  – gain, offset, readout_mode, exposure (darks), filter/telescope
           /focal_length (flats).  Matching earns full points; a mismatch
           costs a heavy penalty.  A null on either side means the field was
           not recorded and costs a smaller "unknown" penalty.

  SOFT   – sensor_temp
           Treated as informational; small bonus for closeness.

After field scoring a temporal proximity bonus is added: calibration sets
taken closer in time to the light frames score higher.

Usage:
    python match_calibrations.py <analysis_json> [--output <path>] [--verbose]

Output JSON structure:
{
  "matched_at": "...",
  "session": { ... },
  "light_group_matches": [
    {
      "light_key": { ... },
      "light_file_ids": [...],
      "light_count": N,
      "obs_dates": [...],
      "best_dark":  { "key": {...}, "score": N, "flags": [...], "file_ids": [...], "count": N },
      "best_flat":  { ... },
      "best_bias":  { ... },
      "dark_candidates":  [ { "key": {...}, "score": N, "flags": [...] }, ... ],
      "flat_candidates":  [ ... ],
      "bias_candidates":  [ ... ],
    },
    ...
  ],
  "diagnosis": [ "...human-readable warning strings..." ]
}
"""

import argparse
import json
import sys
from datetime import date
from typing import Any


# ---------------------------------------------------------------------------
# Scoring constants
# ---------------------------------------------------------------------------

POINTS_EXACT_MATCH   = 50   # per field that matches exactly
PENALTY_EXACT_MISS   = -40  # per field that should match but doesn't
PENALTY_UNKNOWN      = -5   # per field where one or both sides is null
BONUS_TEMPORAL_MAX   = 30   # maximum temporal proximity bonus
TEMPORAL_HALF_LIFE   = 180  # days – bonus halves every N days of separation


# ---------------------------------------------------------------------------
# Field definitions per calibration type
# ---------------------------------------------------------------------------

# Fields that must match or the set is disqualified
DARK_HARD   = ["camera", "binning_x", "binning_y"]
FLAT_HARD   = ["camera", "binning_x", "binning_y"]
BIAS_HARD   = ["camera", "binning_x", "binning_y"]

# Fields that should match (penalty if they don't)
DARK_EXACT  = ["gain", "offset", "readout_mode", "exposure"]
FLAT_EXACT  = ["gain", "offset", "readout_mode", "telescope", "focal_length", "filter"]
BIAS_EXACT  = ["gain", "offset", "readout_mode"]


# ---------------------------------------------------------------------------
# Temporal scoring
# ---------------------------------------------------------------------------

def _date_from_str(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def _min_day_gap(light_dates: list[str], calib_dates: list[str]) -> float | None:
    """Return the minimum |days| between any light date and any calib date."""
    l_dates = [d for d in (_date_from_str(s) for s in light_dates) if d]
    c_dates = [d for d in (_date_from_str(s) for s in calib_dates) if d]
    if not l_dates or not c_dates:
        return None
    gaps = [abs((ld - cd).days) for ld in l_dates for cd in c_dates]
    return min(gaps)


def _temporal_bonus(light_dates: list[str], calib_dates: list[str]) -> float:
    """Exponential decay bonus based on minimum day gap."""
    gap = _min_day_gap(light_dates, calib_dates)
    if gap is None:
        return 0.0
    import math
    return BONUS_TEMPORAL_MAX * math.exp(-gap * math.log(2) / TEMPORAL_HALF_LIFE)


# ---------------------------------------------------------------------------
# Core scoring
# ---------------------------------------------------------------------------

def _score_set(
    light_key: dict,
    calib_key: dict,
    hard_fields: list[str],
    exact_fields: list[str],
    light_dates: list[str],
    calib_dates: list[str],
) -> tuple[float, list[str]]:
    """
    Score one calibration set against one light group.

    Returns (score, flags) where:
      - score < 0 means disqualified (hard mismatch)
      - flags is a list of human-readable notes
    """
    flags: list[str] = []
    score: float = 0.0

    # Hard fields – disqualify immediately on mismatch
    for field in hard_fields:
        l_val = light_key.get(field)
        c_val = calib_key.get(field)
        if l_val is None and c_val is None:
            flags.append(f"UNKNOWN[hard]: {field}")
        elif l_val != c_val:
            return -9999.0, [f"DISQUALIFIED: {field} mismatch (need {l_val!r}, have {c_val!r})"]
        else:
            score += POINTS_EXACT_MATCH

    # Exact fields – penalty on mismatch, smaller penalty on unknown
    for field in exact_fields:
        l_val = light_key.get(field)
        c_val = calib_key.get(field)
        if l_val is None and c_val is None:
            flags.append(f"UNKNOWN[both]: {field}")
            score += PENALTY_UNKNOWN
        elif l_val is None or c_val is None:
            flags.append(f"UNKNOWN[one]: {field} (light={l_val!r}, calib={c_val!r})")
            score += PENALTY_UNKNOWN
        elif l_val == c_val:
            score += POINTS_EXACT_MATCH
        else:
            flags.append(f"MISMATCH: {field} (need {l_val!r}, have {c_val!r})")
            score += PENALTY_EXACT_MISS

    # Temporal bonus
    tb = _temporal_bonus(light_dates, calib_dates)
    score += tb
    if tb > 0:
        flags.append(f"temporal_bonus: +{tb:.1f} pts")

    return score, flags


def _score_all(light_group: dict, inventory: list[dict], calib_type: str) -> list[dict]:
    """Score every calibration set against this light group, sorted best-first."""
    if calib_type == "dark":
        hard, exact = DARK_HARD, DARK_EXACT
    elif calib_type == "flat":
        hard, exact = FLAT_HARD, FLAT_EXACT
    else:  # bias
        hard, exact = BIAS_HARD, BIAS_EXACT

    light_key   = light_group["needs"][f"{calib_type}_key"]
    light_dates = light_group.get("obs_dates", [])

    results = []
    for inv_set in inventory:
        calib_key   = inv_set["key"]
        calib_dates = inv_set.get("obs_dates", [])
        score, flags = _score_set(
            light_key, calib_key, hard, exact, light_dates, calib_dates
        )
        results.append({
            "key":      calib_key,
            "score":    round(score, 2),
            "flags":    flags,
            "file_ids": inv_set["file_ids"],
            "count":    inv_set["count"],
            "obs_dates": calib_dates,
            "imaging_session_ids": inv_set.get("imaging_session_ids", []),
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Diagnosis
# ---------------------------------------------------------------------------

def _diagnose(light_groups: list[dict]) -> list[str]:
    """Return human-readable warnings about calibration quality."""
    diag: list[str] = []

    for lg in light_groups:
        label = (
            f"Light group [{lg['light_count']} frames, "
            f"filter={lg['light_key'].get('filter')}, "
            f"exp={lg['light_key'].get('exposure')}s]"
        )

        for calib_type in ("dark", "flat", "bias"):
            best_key = f"best_{calib_type}"
            best = lg.get(best_key)
            if best is None:
                diag.append(f"WARNING  {label}: NO {calib_type.upper()} candidates found.")
                continue
            if best["score"] < 0:
                diag.append(f"ERROR    {label}: Best {calib_type.upper()} is DISQUALIFIED (score={best['score']}).")
                continue

            mismatches = [f for f in best["flags"] if f.startswith("MISMATCH")]
            unknowns   = [f for f in best["flags"] if f.startswith("UNKNOWN")]

            if mismatches:
                detail = "; ".join(mismatches)
                diag.append(
                    f"WARNING  {label}: Best {calib_type.upper()} has field mismatches – {detail}"
                )
            if unknowns:
                detail = "; ".join(unknowns)
                diag.append(
                    f"INFO     {label}: Best {calib_type.upper()} has unknown/null fields – {detail}"
                )
            if not mismatches and not unknowns:
                diag.append(
                    f"OK       {label}: {calib_type.upper()} match is perfect "
                    f"(score={best['score']}, {best['count']} frames)."
                )

    return diag


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def match_calibrations(analysis: dict) -> dict:
    from datetime import datetime

    inventory = analysis["calibration_inventory"]
    dark_inv  = inventory["darks"]
    flat_inv  = inventory["flats"]
    bias_inv  = inventory["bias"]

    light_group_matches = []

    for lg in analysis["light_calibration_keys"]:
        dark_candidates = _score_all(lg, dark_inv, "dark")
        flat_candidates = _score_all(lg, flat_inv, "flat")
        bias_candidates = _score_all(lg, bias_inv, "bias")

        def _best(candidates: list[dict]) -> dict | None:
            # Best is first after sort; exclude disqualified (score < 0)
            for c in candidates:
                if c["score"] >= 0:
                    return c
            return candidates[0] if candidates else None  # return best-of-bad if nothing qualifies

        light_group_matches.append({
            "light_key":         lg["key"],
            "light_file_ids":    lg["light_file_ids"],
            "light_count":       lg["light_count"],
            "obs_dates":         lg.get("obs_dates", []),
            "imaging_session_ids": lg.get("imaging_session_ids", []),
            "needs":             lg["needs"],
            "best_dark":         _best(dark_candidates),
            "best_flat":         _best(flat_candidates),
            "best_bias":         _best(bias_candidates),
            "dark_candidates":   dark_candidates,
            "flat_candidates":   flat_candidates,
            "bias_candidates":   bias_candidates,
        })

    diagnosis = _diagnose(light_group_matches)

    return {
        "matched_at":          datetime.utcnow().isoformat() + "Z",
        "session":             analysis["session"],
        "summary":             analysis["summary"],
        "light_group_matches": light_group_matches,
        "diagnosis":           diagnosis,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Match calibration sets to light groups and score each match."
    )
    parser.add_argument(
        "analysis_json",
        help="JSON file produced by export_calibration_analysis.py"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output JSON file (default: <stem>_matches.json)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print diagnosis to stdout"
    )
    args = parser.parse_args()

    try:
        with open(args.analysis_json, "r", encoding="utf-8") as fh:
            analysis = json.load(fh)
    except FileNotFoundError:
        print(f"Error: file not found: {args.analysis_json}", file=sys.stderr)
        sys.exit(1)

    result = match_calibrations(analysis)

    from pathlib import Path
    stem        = Path(args.analysis_json).stem
    output_path = args.output or f"{stem}_matches.json"

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, default=str, ensure_ascii=False)

    print(f"Written: {output_path}")
    print()
    print("Diagnosis:")
    for line in result["diagnosis"]:
        print(f"  {line}")


if __name__ == "__main__":
    main()
