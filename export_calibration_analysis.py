"""Export calibration analysis data for a processing session.

Produces a JSON file containing all LIGHT, DARK, FLAT, and BIAS frames in a
processing session, with the FITS metadata fields that are relevant to
calibration matching.  The JSON is intended to be consumed by an algorithm
(human or automated) that decides which calibration frames best match each
light frame.

Usage:
    python export_calibration_analysis.py <session_id> [--output <path>] [--config <path>]

The output JSON has the following top-level structure:
{
  "session": { ... session metadata ... },
  "lights": [ { ...per-file record... }, ... ],
  "darks":  [ { ... }, ... ],
  "flats":  [ { ... }, ... ],
  "bias":   [ { ... }, ... ],
  "light_calibration_keys": [
      {
          "key": { "camera": ..., "filter": ..., "exposure": ..., ... },
          "light_file_ids": [...],
          "needs": { "dark_key": {...}, "flat_key": {...}, "bias_key": {...} }
      },
      ...
  ],
  "calibration_inventory": {
      "darks":  [ { "key": {...}, "file_ids": [...], "count": N }, ... ],
      "flats":  [ { "key": {...}, "file_ids": [...], "count": N }, ... ],
      "bias":   [ { "key": {...}, "file_ids": [...], "count": N }, ... ]
  }
}

Key design decisions
--------------------
* Every FITS field that PixInsight's ImageCalibration process uses to group
  frames is included.  The primary grouping keys are extracted separately so
  they are easy to compare programmatically.
* "needs" entries under each light group describe the calibration key that
  would perfectly match that group of lights (same camera/gain/binning/etc.).
  The algorithm can then look for the closest available calibration set in
  time.
* Sensor temperature is included for darks/bias but treated as informational
  (not a hard-match key) because temperature tolerance varies by sensor.
* Imaging session IDs and observation dates are included so a downstream
  algorithm can rank calibration sets by temporal proximity.
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import FitsFile, ProcessingSession, ProcessingSessionFile
from config import load_config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe(value: Any) -> Any:
    """Make a value JSON-serialisable."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if value is None:
        return None
    return value


def _fits_record(f: FitsFile) -> dict:
    """Return a complete per-file dict with all calibration-relevant fields."""
    return {
        # Identity
        "id": f.id,
        "file": f.file,
        "folder": f.folder,
        "md5sum": f.md5sum,
        "imaging_session_id": f.imaging_session_id,
        "frame_type": f.frame_type,

        # Observation timing
        "obs_date": _safe(f.obs_date),
        "obs_timestamp": _safe(f.obs_timestamp),

        # Equipment
        "camera": f.camera,
        "telescope": f.telescope,
        "focal_length": f.focal_length,

        # Filter
        "filter": f.filter,

        # Exposure
        "exposure": f.exposure,

        # Sensor configuration  ← primary PixInsight grouping dimensions
        "gain": f.gain,
        "offset": f.offset,
        "binning_x": f.binning_x,
        "binning_y": f.binning_y,
        "readout_mode": f.readout_mode,
        "iso_speed": f.iso_speed,

        # Sensor temperature (informational for dark matching)
        "sensor_temp": f.sensor_temp,

        # Image geometry
        "width_pixels": f.width_pixels,
        "height_pixels": f.height_pixels,
        "bayerpat": f.bayerpat,

        # Quality / context (useful for deciding *which* set is best)
        "airmass": f.airmass,
        "star_count": f.star_count,
        "median_fwhm": f.median_fwhm,
        "eccentricity": f.eccentricity,
        "sky_quality_mpsas": f.sky_quality_mpsas,
        "ambient_temp": f.ambient_temp,
        "focuser_temp": f.focuser_temp,

        # Object (lights only, informational)
        "object": f.object,
    }


# ---------------------------------------------------------------------------
# Key extraction  –  what PixInsight groups on
# ---------------------------------------------------------------------------

def _dark_key(f: FitsFile) -> dict:
    """Fields that must match between a LIGHT and its DARK calibration."""
    return {
        "camera": f.camera,
        "exposure": f.exposure,
        "gain": f.gain,
        "offset": f.offset,
        "binning_x": f.binning_x,
        "binning_y": f.binning_y,
        "readout_mode": f.readout_mode,
    }


def _flat_key(f: FitsFile) -> dict:
    """Fields that must match between a LIGHT and its FLAT calibration."""
    return {
        "camera": f.camera,
        "telescope": f.telescope,
        "focal_length": f.focal_length,
        "filter": f.filter,
        "binning_x": f.binning_x,
        "binning_y": f.binning_y,
        "gain": f.gain,
        "offset": f.offset,
        "readout_mode": f.readout_mode,
    }


def _bias_key(f: FitsFile) -> dict:
    """Fields that must match between a LIGHT and its BIAS calibration."""
    return {
        "camera": f.camera,
        "gain": f.gain,
        "offset": f.offset,
        "binning_x": f.binning_x,
        "binning_y": f.binning_y,
        "readout_mode": f.readout_mode,
    }


def _light_group_key(f: FitsFile) -> dict:
    """Full sensor configuration of a light frame (superset of calib keys)."""
    return {
        "camera": f.camera,
        "telescope": f.telescope,
        "focal_length": f.focal_length,
        "filter": f.filter,
        "exposure": f.exposure,
        "gain": f.gain,
        "offset": f.offset,
        "binning_x": f.binning_x,
        "binning_y": f.binning_y,
        "readout_mode": f.readout_mode,
        "width_pixels": f.width_pixels,
        "height_pixels": f.height_pixels,
    }


def _key_to_str(key: dict) -> str:
    """Stable string representation of a key dict for use as a dict key."""
    return json.dumps(key, sort_keys=True, default=str)


# ---------------------------------------------------------------------------
# Main export logic
# ---------------------------------------------------------------------------

def build_calibration_analysis(session_id: str, db_session) -> dict:
    """Query the session and return the full analysis dict."""

    # -- Fetch the processing session -------------------------------------------
    ps = db_session.query(ProcessingSession).filter_by(id=session_id).first()
    if ps is None:
        raise ValueError(f"Processing session '{session_id}' not found.")

    session_meta = {
        "id": ps.id,
        "name": ps.name,
        "objects": ps.objects if isinstance(ps.objects, list) else json.loads(ps.objects or "[]"),
        "status": ps.status,
        "primary_target": ps.primary_target,
        "target_type": ps.target_type,
        "image_type": ps.image_type,
        "date_range_start": _safe(ps.date_range_start),
        "date_range_end": _safe(ps.date_range_end),
        "notes": ps.notes,
        "folder_path": ps.folder_path,
        "created_at": _safe(ps.created_at),
    }

    # -- Fetch all files in the session -----------------------------------------
    psf_rows = (
        db_session.query(ProcessingSessionFile, FitsFile)
        .join(FitsFile, ProcessingSessionFile.fits_file_id == FitsFile.id)
        .filter(ProcessingSessionFile.processing_session_id == session_id)
        .all()
    )

    lights, darks, flats, bias = [], [], [], []

    for psf, f in psf_rows:
        record = _fits_record(f)
        record["subfolder"] = psf.subfolder  # how it was staged (lights/darks/…)
        record["staged_path"] = psf.staged_path
        record["staged_filename"] = psf.staged_filename

        ft = (f.frame_type or "").upper()
        if ft == "LIGHT":
            lights.append(record)
        elif ft == "DARK":
            darks.append(record)
        elif ft == "FLAT":
            flats.append(record)
        elif ft == "BIAS":
            bias.append(record)
        # Unknown frame types are omitted; add an else branch here if needed.

    # Sort chronologically within each group
    for group in (lights, darks, flats, bias):
        group.sort(key=lambda r: (r["obs_date"] or "", r["obs_timestamp"] or ""))

    # -- Build calibration inventory (what we have) ----------------------------
    def _inventory(frames: list, key_fn) -> list:
        """Group frames by their calibration key and return an inventory list."""
        buckets: dict[str, list] = defaultdict(list)
        for r in frames:
            # Re-query from DB to call key_fn; we stored all needed fields inline.
            k = key_fn_from_record(r, key_fn)
            buckets[_key_to_str(k)].append(r["id"])

        result = []
        for key_str, file_ids in buckets.items():
            result.append({
                "key": json.loads(key_str),
                "file_ids": file_ids,
                "count": len(file_ids),
                # Date range of this calibration group
                "obs_dates": sorted(set(
                    r["obs_date"] for r in frames
                    if r["id"] in file_ids and r["obs_date"]
                )),
                "imaging_session_ids": sorted(set(
                    r["imaging_session_id"] for r in frames
                    if r["id"] in file_ids and r["imaging_session_id"]
                )),
            })
        return result

    # We need a helper that reconstructs a FitsFile-like key from a plain dict
    def key_fn_from_record(r: dict, key_fn) -> dict:
        class _Proxy:
            pass
        p = _Proxy()
        for field in (
            "camera", "telescope", "focal_length", "filter", "exposure",
            "gain", "offset", "binning_x", "binning_y", "readout_mode",
            "iso_speed", "width_pixels", "height_pixels",
        ):
            setattr(p, field, r.get(field))
        return key_fn(p)

    dark_inventory = _inventory(darks, _dark_key)
    flat_inventory = _inventory(flats, _flat_key)
    bias_inventory = _inventory(bias, _bias_key)

    # -- Build light calibration groups (what each group of lights needs) ------
    light_buckets: dict[str, list] = defaultdict(list)
    for r in lights:
        k = key_fn_from_record(r, _light_group_key)
        light_buckets[_key_to_str(k)].append(r["id"])

    light_calibration_keys = []
    for key_str, file_ids in light_buckets.items():
        key = json.loads(key_str)
        # Derive the calibration keys this light group needs
        dark_need = {k: key[k] for k in ("camera", "exposure", "gain", "offset",
                                          "binning_x", "binning_y", "readout_mode")}
        flat_need = {k: key[k] for k in ("camera", "telescope", "focal_length", "filter",
                                          "binning_x", "binning_y", "gain", "offset",
                                          "readout_mode")}
        bias_need = {k: key[k] for k in ("camera", "gain", "offset",
                                          "binning_x", "binning_y", "readout_mode")}

        # Collect the obs_dates for this light group (for temporal scoring)
        group_records = [r for r in lights if r["id"] in file_ids]
        obs_dates = sorted(set(r["obs_date"] for r in group_records if r["obs_date"]))
        imaging_sessions = sorted(set(
            r["imaging_session_id"] for r in group_records if r["imaging_session_id"]
        ))

        light_calibration_keys.append({
            "key": key,
            "light_file_ids": file_ids,
            "light_count": len(file_ids),
            "obs_dates": obs_dates,
            "imaging_session_ids": imaging_sessions,
            "needs": {
                "dark_key": dark_need,
                "flat_key": flat_need,
                "bias_key": bias_need,
            },
        })

    # -- Summary stats ----------------------------------------------------------
    summary = {
        "total_files": len(lights) + len(darks) + len(flats) + len(bias),
        "lights": len(lights),
        "darks": len(darks),
        "flats": len(flats),
        "bias": len(bias),
        "unique_light_groups": len(light_calibration_keys),
        "unique_dark_sets": len(dark_inventory),
        "unique_flat_sets": len(flat_inventory),
        "unique_bias_sets": len(bias_inventory),
    }

    return {
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "session": session_meta,
        "summary": summary,
        "light_calibration_keys": light_calibration_keys,
        "calibration_inventory": {
            "darks": dark_inventory,
            "flats": flat_inventory,
            "bias": bias_inventory,
        },
        "lights": lights,
        "darks": darks,
        "flats": flats,
        "bias": bias,
    }


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Export calibration analysis JSON for a processing session."
    )
    parser.add_argument("session_id", help="Processing session ID to analyse")
    parser.add_argument(
        "--output", "-o",
        help="Output JSON file path (default: <session_id>_calibration_analysis.json)"
    )
    parser.add_argument(
        "--config", "-c",
        default="config.json",
        help="Path to config.json (default: config.json)"
    )
    parser.add_argument(
        "--pretty", action="store_true", default=True,
        help="Pretty-print JSON output (default: True)"
    )

    args = parser.parse_args()

    # -- Load config & connect --------------------------------------------------
    try:
        config, _cameras, _telescopes, _filter_mappings = load_config(args.config)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    engine = create_engine(config.database.connection_string)
    Session = sessionmaker(bind=engine)
    db_session = Session()

    try:
        data = build_calibration_analysis(args.session_id, db_session)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db_session.close()

    # -- Write output -----------------------------------------------------------
    output_path = args.output or f"{args.session_id}_calibration_analysis.json"
    indent = 2 if args.pretty else None
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=indent, default=str, ensure_ascii=False)

    s = data["summary"]
    print(f"Written: {output_path}")
    print(
        f"  {s['lights']} lights in {s['unique_light_groups']} groups  |  "
        f"{s['darks']} darks ({s['unique_dark_sets']} sets)  |  "
        f"{s['flats']} flats ({s['unique_flat_sets']} sets)  |  "
        f"{s['bias']} bias ({s['unique_bias_sets']} sets)"
    )


if __name__ == "__main__":
    main()
