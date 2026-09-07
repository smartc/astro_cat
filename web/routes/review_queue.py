"""
Review Queue routes — surface quarantine files that need manual attention and
provide one-click fixes for common issues.
"""
import json
import os
import sys
import logging
import statistics
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from models import FitsFile
from validation import FitsValidator
from web.dependencies import get_config, get_db_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

VALID_FRAME_TYPES = {"LIGHT", "FLAT", "DARK", "BIAS"}
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


class ApplyFixRequest(BaseModel):
    fix_id: str
    params: dict
    file_ids: list[int]


# ── small helpers ─────────────────────────────────────────────────────────────

def _mode_or_none(values: list):
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return statistics.multimode(clean)[0]


def _suggest_proper_name(raw_name: str) -> str:
    """'SPECTRAL-PRO' → 'Spectral-Pro'"""
    return "-".join(part.capitalize() for part in raw_name.split("-"))


def _file_dict(f: FitsFile) -> dict:
    return {
        "id": f.id,
        "file": f.file,
        "folder": f.folder,
        "frame_type": f.frame_type,
        "filter": f.filter,
        "object": f.object,
        "camera": f.camera,
        "telescope": f.telescope,
        "obs_date": f.obs_date,
        "validation_score": f.validation_score,
        "validation_notes": f.validation_notes,
    }


# ── grouping logic ────────────────────────────────────────────────────────────

def _build_review_groups(files, filter_mappings: dict, cameras, telescopes) -> list:
    groups: dict[str, dict] = {}
    camera_raw: dict[str, list] = defaultdict(list)
    telescope_raw: dict[str, list] = defaultdict(list)

    def add_to_group(group_id: str, meta: dict, file_entry: dict):
        if group_id not in groups:
            groups[group_id] = {"meta": meta, "files": []}
        groups[group_id]["files"].append(file_entry)

    for f in files:
        notes = f.validation_notes or ""
        fe = _file_dict(f)
        frame_type = f.frame_type or ""
        obj_raw = f.object or ""
        obj_lower = obj_raw.lower()
        filter_val = f.filter or ""
        camera_val = f.camera or ""
        telescope_val = f.telescope or ""

        # non_standard_filter
        if "non-standard filter" in notes:
            gid = f"non_standard_filter__{filter_val}"
            meta = {
                "group_id": gid,
                "issue_type": "non_standard_filter",
                "severity": "warning",
                "issue_summary": f"Filter '{filter_val}' is not in the filter list",
                "detail": (
                    "This filter name is not recognised. Adding it will restore full "
                    "scoring and allow these files to auto-migrate."
                ),
                "available_fixes": [
                    {
                        "fix_id": "add_filter_to_list",
                        "label": f"Add '{filter_val}' to the filter list",
                        "description": (
                            "Registers this as a known filter. Files will be "
                            "re-validated and will reach 100/100."
                        ),
                        "params": {
                            "raw_name": filter_val,
                            "proper_name": _suggest_proper_name(filter_val),
                        },
                    },
                    {
                        "fix_id": "rename_value_in_db",
                        "label": "Rename to an existing filter",
                        "description": (
                            "Use if this is a typo or alias for a filter already in the list."
                        ),
                        "params": {
                            "field": "filter",
                            "current_value": filter_val,
                            "new_value": None,
                        },
                    },
                ],
            }
            add_to_group(gid, meta, fe)

        # non_standard_camera
        if "Camera: non-standard" in notes:
            gid = f"non_standard_camera__{camera_val}"
            meta = {
                "group_id": gid,
                "issue_type": "non_standard_camera",
                "severity": "warning",
                "issue_summary": f"Camera '{camera_val}' is not in the camera list",
                "detail": (
                    "This camera is not recognised. Adding it will improve scoring. "
                    "The OSC/mono setting determines how filter scores are calculated."
                ),
                "available_fixes": [
                    {
                        "fix_id": "add_camera_to_list",
                        "label": f"Add '{camera_val}' to the camera list",
                        "description": (
                            "Registers this camera. OSC = colour/one-shot; "
                            "mono = narrowband/broadband with separate filters."
                        ),
                        "params": {
                            "camera": camera_val,
                            "bin": 1,
                            "x": None,
                            "y": None,
                            "type": "CMOS",
                            "brand": "",
                            "pixel": None,
                            "rgb": True,
                            "comments": "",
                            "prefill": {},
                        },
                    },
                    {
                        "fix_id": "rename_value_in_db",
                        "label": "Rename to an existing camera",
                        "description": (
                            "Use if this is a typo or alias for a camera already in the list."
                        ),
                        "params": {
                            "field": "camera",
                            "current_value": camera_val,
                            "new_value": None,
                        },
                    },
                ],
            }
            add_to_group(gid, meta, fe)
            camera_raw[gid].append(
                {"x": f.width_pixels, "y": f.height_pixels, "focal": f.focal_length}
            )

        # camera_unresolved (pixel dims matched, but couldn't be confirmed against
        # any single camera's instrument/color signature -- see equipment_identifier.py)
        if "Camera: missing/unknown" in notes and camera_val.upper() == "UNKNOWN":
            instrument_val = f.instrument or ""
            gid = f"camera_unresolved__{f.width_pixels}x{f.height_pixels}__{instrument_val or 'NONE'}"
            meta = {
                "group_id": gid,
                "issue_type": "camera_unresolved",
                "severity": "error",
                "issue_summary": (
                    f"Unidentified camera ({f.width_pixels}×{f.height_pixels}px, "
                    f"INSTRUME='{instrument_val or '(none)'}')"
                ),
                "detail": (
                    "Pixel dimensions didn't uniquely confirm a known camera — either this "
                    "sensor is shared with another registered camera and the INSTRUME text "
                    "didn't confirm either one, or this exact INSTRUME string hasn't been "
                    "seen before. Assign it below; the pairing is remembered, so this exact "
                    "signature resolves automatically from now on."
                ),
                "available_fixes": [
                    {
                        "fix_id": "assign_camera_fingerprint",
                        "label": "Assign to existing camera",
                        "description": (
                            "Use if this is really one of your registered cameras — "
                            "just an INSTRUME string variant it hasn't seen before."
                        ),
                        "params": {"camera_name": None},
                    },
                    {
                        "fix_id": "add_camera_to_list",
                        "label": "This is a new camera",
                        "description": "Register a brand-new camera and remember its fingerprint.",
                        "params": {
                            "camera": instrument_val,
                            "bin": 1,
                            "x": f.width_pixels,
                            "y": f.height_pixels,
                            "type": "CMOS",
                            "brand": "",
                            "pixel": None,
                            "rgb": True,
                            "comments": "",
                            "prefill": {},
                        },
                    },
                ],
            }
            add_to_group(gid, meta, fe)

        # non_standard_telescope
        if "Telescope: non-standard" in notes:
            gid = f"non_standard_telescope__{telescope_val}"
            meta = {
                "group_id": gid,
                "issue_type": "non_standard_telescope",
                "severity": "warning",
                "issue_summary": f"Telescope '{telescope_val}' is not in the telescope list",
                "detail": "This telescope is not recognised. Adding it will improve scoring.",
                "available_fixes": [
                    {
                        "fix_id": "add_telescope_to_list",
                        "label": f"Add '{telescope_val}' to the telescope list",
                        "description": "Registers this telescope.",
                        "params": {
                            "scope": telescope_val,
                            "focal": None,
                            "aperture": None,
                            "make": "",
                            "type": "Refractor",
                            "subtype": "",
                            "comments": "",
                            "prefill": {},
                        },
                    },
                    {
                        "fix_id": "rename_value_in_db",
                        "label": "Rename to an existing telescope",
                        "description": (
                            "Use if this is a typo or alias for a telescope already in the list."
                        ),
                        "params": {
                            "field": "telescope",
                            "current_value": telescope_val,
                            "new_value": None,
                        },
                    },
                ],
            }
            add_to_group(gid, meta, fe)
            telescope_raw[gid].append({"focal": f.focal_length})

        # suspect_frame_type
        if frame_type == "LIGHT" and any(
            kw in obj_lower for kw in ("flat", "dark", "bias", "adhoc")
        ):
            gid = f"suspect_frame_type__LIGHT__{obj_raw}"
            meta = {
                "group_id": gid,
                "issue_type": "suspect_frame_type",
                "severity": "warning",
                "issue_summary": f"Suspect frame type: LIGHT / '{obj_raw}'",
                "detail": (
                    "Frame type is LIGHT but the object name suggests a calibration frame."
                ),
                "available_fixes": [
                    {
                        "fix_id": "change_frame_type",
                        "label": "Change frame type",
                        "description": "Correct the frame type to match the actual data.",
                        "params": {"new_frame_type": None},
                    }
                ],
            }
            add_to_group(gid, meta, fe)

        # unknown_frame_type (score = 0)
        if "Unknown frame type" in notes:
            gid = f"unknown_frame_type__{frame_type}"
            meta = {
                "group_id": gid,
                "issue_type": "unknown_frame_type",
                "severity": "error",
                "issue_summary": f"Unknown frame type: '{frame_type}'",
                "detail": (
                    "Frame type is not one of LIGHT / FLAT / DARK / BIAS. "
                    "These files score 0 until corrected."
                ),
                "available_fixes": [
                    {
                        "fix_id": "change_frame_type",
                        "label": "Change frame type",
                        "description": "Set the correct frame type to enable scoring.",
                        "params": {"new_frame_type": None},
                    }
                ],
            }
            add_to_group(gid, meta, fe)

        # missing_object (inform only)
        if "Missing/invalid object name" in notes:
            gid = "missing_object"
            meta = {
                "group_id": gid,
                "issue_type": "missing_object",
                "severity": "info",
                "issue_summary": "Missing or invalid object name",
                "detail": (
                    "These files have no recognised object name. This reduces the "
                    "validation score but cannot be fixed automatically."
                ),
                "available_fixes": [],
            }
            add_to_group(gid, meta, fe)

    # Populate camera prefill from accumulated raw values
    for gid, raw_list in camera_raw.items():
        xs = _mode_or_none([r["x"] for r in raw_list])
        ys = _mode_or_none([r["y"] for r in raw_list])
        focal_hint = _mode_or_none([r["focal"] for r in raw_list])
        for fix in groups[gid]["meta"]["available_fixes"]:
            if fix["fix_id"] == "add_camera_to_list":
                fix["params"]["x"] = xs
                fix["params"]["y"] = ys
                fix["params"]["prefill"] = {
                    "x": xs,
                    "y": ys,
                    "focal_length_hint": focal_hint,
                }

    # Populate telescope prefill
    for gid, raw_list in telescope_raw.items():
        focal = _mode_or_none([r["focal"] for r in raw_list])
        for fix in groups[gid]["meta"]["available_fixes"]:
            if fix["fix_id"] == "add_telescope_to_list":
                fix["params"]["focal"] = focal
                fix["params"]["prefill"] = {"focal": focal}

    # Assemble final list with file_count, sorted by severity then group_id
    result = []
    for g in groups.values():
        entry = dict(g["meta"])
        entry["file_count"] = len(g["files"])
        entry["files"] = g["files"]
        result.append(entry)

    result.sort(key=lambda g: (SEVERITY_ORDER.get(g["severity"], 99), g["group_id"]))
    return result


# ── re-validation helper ──────────────────────────────────────────────────────

def _revalidate_files(db_session, file_ids: list[int], db_service) -> dict:
    """Re-run validation on given file IDs, update DB, return {str(id): new_score}."""
    validator = FitsValidator(db_service)
    results = {}
    for file_id in file_ids:
        fits_file = db_session.get(FitsFile, file_id)
        if not fits_file:
            continue
        record = {
            "object": fits_file.object,
            "obs_date": fits_file.obs_date,
            "camera": fits_file.camera,
            "telescope": fits_file.telescope,
            "filter": fits_file.filter,
            "exposure": fits_file.exposure,
            "frame_type": fits_file.frame_type,
            "focal_length": fits_file.focal_length,
            "ra": fits_file.ra,
            "dec": fits_file.dec,
        }
        result = validator.validate_record(record)
        fits_file.validation_score = result.score
        fits_file.validation_notes = "; ".join(result.notes) if result.notes else None
        fits_file.migration_ready = result.migration_ready
        results[str(file_id)] = result.score
    db_session.commit()
    return results


# ── camera fingerprint helper ─────────────────────────────────────────────────

def _assign_camera_and_learn_fingerprints(session, db_service, file_ids: list[int], camera_name: str):
    """Set `camera` on the given files and record their (dims, instrument) ->
    camera fingerprint so this exact signature auto-resolves next time."""
    files = session.query(FitsFile).filter(FitsFile.id.in_(file_ids)).all()
    for f in files:
        f.camera = camera_name
        if f.width_pixels and f.height_pixels:
            is_color = None
            if f.bayerpat:
                is_color = f.bayerpat.strip().upper() != "NONE"
            db_service.add_camera_fingerprint(
                x_pixels=f.width_pixels,
                y_pixels=f.height_pixels,
                instrument=(f.instrument or None),
                camera_name=camera_name,
                is_color=is_color,
                source="review",
            )
    session.commit()


# ── equipment reload helper ───────────────────────────────────────────────────

def _reload_equipment(config):
    """Reload equipment JSON into app globals and re-sync DB equipment tables."""
    from equipment_manager import EquipmentManager
    from cli.utils import convert_equipment_for_db

    app_module = sys.modules["web.app"]
    em = EquipmentManager(config.equipment)
    app_module.cameras, app_module.telescopes, app_module.filter_mappings = (
        em.load_equipment()
    )
    cameras_dict, telescopes_dict, fm_dict = convert_equipment_for_db(
        app_module.cameras, app_module.telescopes, app_module.filter_mappings
    )
    app_module.db_service.initialize_equipment(cameras_dict, telescopes_dict, fm_dict)


def _write_json_atomic(path: Path, data):
    """Write JSON atomically: write to .tmp then os.replace."""
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2))
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


# ── GET /api/review-queue ─────────────────────────────────────────────────────

@router.get("/review-queue")
async def get_review_queue(
    db_service=Depends(get_db_service),
    config=Depends(get_config),
):
    app_module = sys.modules["web.app"]
    session = db_service.db_manager.get_session()
    try:
        quarantine_files = (
            session.query(FitsFile)
            .filter(
                FitsFile.validation_score < 95,
                FitsFile.folder.like(f"%{config.paths.quarantine_dir}%"),
            )
            .all()
        )

        filter_mappings = app_module.filter_mappings
        cameras = app_module.cameras
        telescopes = app_module.telescopes

        groups = _build_review_groups(quarantine_files, filter_mappings, cameras, telescopes)

        # Count distinct file IDs across all groups (a file may appear in multiple groups)
        distinct_ids = {f["id"] for g in groups for f in g["files"]}

        return {
            "total_files": len(distinct_ids),
            "known_filters": sorted(filter_mappings.keys()),
            "known_cameras": [c.camera for c in cameras],
            "known_telescopes": [t.scope for t in telescopes],
            "groups": groups,
        }
    finally:
        session.close()


# ── POST /api/review-queue/apply-fix ─────────────────────────────────────────

@router.post("/review-queue/apply-fix")
async def apply_fix(
    body: ApplyFixRequest,
    db_service=Depends(get_db_service),
    config=Depends(get_config),
):
    if not body.file_ids:
        raise HTTPException(status_code=422, detail="file_ids must not be empty")

    session = db_service.db_manager.get_session()
    try:
        handlers = {
            "add_filter_to_list": _fix_add_filter,
            "add_camera_to_list": _fix_add_camera,
            "add_telescope_to_list": _fix_add_telescope,
            "rename_value_in_db": _fix_rename_value,
            "change_frame_type": _fix_change_frame_type,
            "assign_camera_fingerprint": _fix_assign_camera_fingerprint,
        }
        handler = handlers.get(body.fix_id)
        if handler is None:
            raise HTTPException(status_code=422, detail=f"Unknown fix_id: '{body.fix_id}'")

        if body.fix_id in ("add_filter_to_list", "add_camera_to_list", "add_telescope_to_list"):
            return handler(session, body.params, body.file_ids, db_service, config)
        else:
            return handler(session, body.params, body.file_ids, db_service)
    finally:
        session.close()


# ── fix implementations ───────────────────────────────────────────────────────

def _fix_add_filter(session, params, file_ids, db_service, config):
    raw_name = (params.get("raw_name") or "").strip()
    proper_name = (params.get("proper_name") or "").strip()
    if not raw_name:
        raise HTTPException(status_code=422, detail="raw_name is required")

    filters_path = Path(config.equipment.filters_file)
    with open(filters_path) as fh:
        filters = json.load(fh)

    if any(e["raw_name"].upper() == raw_name.upper() for e in filters):
        raise HTTPException(
            status_code=409, detail=f"Filter '{raw_name}' is already in the filter list"
        )

    filters.append({"raw_name": raw_name, "proper_name": proper_name or raw_name})
    _write_json_atomic(filters_path, filters)
    _reload_equipment(config)

    all_with_filter = session.query(FitsFile).filter(FitsFile.filter == raw_name).all()
    all_ids = [f.id for f in all_with_filter]
    new_scores = _revalidate_files(session, all_ids, db_service)

    return {
        "fixed_count": len(file_ids),
        "revalidated_count": len(all_ids),
        "new_scores": {str(fid): new_scores.get(str(fid)) for fid in file_ids},
        "warnings": [],
    }


def _fix_add_camera(session, params, file_ids, db_service, config):
    camera_name = (params.get("camera") or "").strip()
    brand = (params.get("brand") or "").strip()
    x = params.get("x")
    y = params.get("y")
    if not camera_name or not brand or x is None or y is None:
        raise HTTPException(
            status_code=422, detail="camera, brand, x, and y are required"
        )

    cameras_path = Path(config.equipment.cameras_file)
    with open(cameras_path) as fh:
        cameras = json.load(fh)

    if any(c["camera"] == camera_name for c in cameras):
        raise HTTPException(
            status_code=409, detail=f"Camera '{camera_name}' is already in the camera list"
        )

    cameras.append({
        "camera": camera_name,
        "bin": params.get("bin", 1),
        "x": x,
        "y": y,
        "type": params.get("type", "CMOS"),
        "brand": brand,
        "pixel": params.get("pixel"),
        "rgb": params.get("rgb", True),
        "comments": params.get("comments", ""),
    })
    _write_json_atomic(cameras_path, cameras)
    _reload_equipment(config)

    # Explicitly assign the selected files (they may currently be "UNKNOWN",
    # not the raw camera_val, if they came via the camera_unresolved group)
    # and remember their fingerprint so this signature auto-resolves next time.
    _assign_camera_and_learn_fingerprints(session, db_service, file_ids, camera_name)

    all_with_camera = session.query(FitsFile).filter(FitsFile.camera == camera_name).all()
    all_ids = [f.id for f in all_with_camera]
    new_scores = _revalidate_files(session, all_ids, db_service)

    return {
        "fixed_count": len(file_ids),
        "revalidated_count": len(all_ids),
        "new_scores": {str(fid): new_scores.get(str(fid)) for fid in file_ids},
        "warnings": [],
    }


def _fix_assign_camera_fingerprint(session, params, file_ids, db_service):
    camera_name = (params.get("camera_name") or "").strip()
    if not camera_name:
        raise HTTPException(status_code=422, detail="camera_name is required")

    app_module = sys.modules["web.app"]
    known = {c.camera for c in app_module.cameras}
    if camera_name not in known:
        raise HTTPException(
            status_code=422, detail=f"'{camera_name}' is not a known camera name"
        )

    _assign_camera_and_learn_fingerprints(session, db_service, file_ids, camera_name)
    new_scores = _revalidate_files(session, file_ids, db_service)

    return {
        "fixed_count": len(file_ids),
        "revalidated_count": len(file_ids),
        "new_scores": new_scores,
        "warnings": [],
    }


def _fix_add_telescope(session, params, file_ids, db_service, config):
    scope_name = (params.get("scope") or "").strip()
    if not scope_name:
        raise HTTPException(status_code=422, detail="scope is required")

    telescopes_path = Path(config.equipment.telescopes_file)
    with open(telescopes_path) as fh:
        telescopes = json.load(fh)

    if any(t["scope"] == scope_name for t in telescopes):
        raise HTTPException(
            status_code=409, detail=f"Telescope '{scope_name}' is already in the telescope list"
        )

    focal = params.get("focal")
    if focal is not None:
        try:
            focal = int(focal)
        except (TypeError, ValueError):
            focal = None

    telescopes.append({
        "scope": scope_name,
        "focal": focal,
        "aperture": params.get("aperture"),
        "make": params.get("make", ""),
        "type": params.get("type", "Refractor"),
        "subtype": params.get("subtype", ""),
        "comments": params.get("comments", ""),
    })
    _write_json_atomic(telescopes_path, telescopes)
    _reload_equipment(config)

    all_with_scope = session.query(FitsFile).filter(FitsFile.telescope == scope_name).all()
    all_ids = [f.id for f in all_with_scope]
    new_scores = _revalidate_files(session, all_ids, db_service)

    return {
        "fixed_count": len(file_ids),
        "revalidated_count": len(all_ids),
        "new_scores": {str(fid): new_scores.get(str(fid)) for fid in file_ids},
        "warnings": [],
    }


def _fix_rename_value(session, params, file_ids, db_service):
    field = params.get("field", "")
    current_value = params.get("current_value", "")  # noqa: F841 — informational only
    new_value = params.get("new_value", "")

    if field not in ("filter", "camera", "telescope"):
        raise HTTPException(
            status_code=422, detail="field must be one of 'filter', 'camera', 'telescope'"
        )
    if not new_value:
        raise HTTPException(status_code=422, detail="new_value is required")

    app_module = sys.modules["web.app"]

    if field == "filter":
        valid = set(app_module.filter_mappings.keys()) | set(app_module.filter_mappings.values())
        if new_value not in valid:
            raise HTTPException(
                status_code=422, detail=f"'{new_value}' is not a known filter name"
            )
    elif field == "camera":
        known = {c.camera for c in app_module.cameras}
        if new_value not in known:
            raise HTTPException(
                status_code=422, detail=f"'{new_value}' is not a known camera name"
            )
    elif field == "telescope":
        known = {t.scope for t in app_module.telescopes}
        if new_value not in known:
            raise HTTPException(
                status_code=422, detail=f"'{new_value}' is not a known telescope name"
            )

    session.query(FitsFile).filter(FitsFile.id.in_(file_ids)).update(
        {field: new_value}, synchronize_session="fetch"
    )
    session.commit()

    new_scores = _revalidate_files(session, file_ids, db_service)

    return {
        "fixed_count": len(file_ids),
        "revalidated_count": len(file_ids),
        "new_scores": new_scores,
        "warnings": [],
    }


def _fix_change_frame_type(session, params, file_ids, db_service):
    new_frame_type = (params.get("new_frame_type") or "").upper()
    if new_frame_type not in VALID_FRAME_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"new_frame_type must be one of {sorted(VALID_FRAME_TYPES)}",
        )

    warnings = []
    for file_id in file_ids:
        fits_file = session.get(FitsFile, file_id)
        if not fits_file:
            continue
        if fits_file.frame_type == "LIGHT" and new_frame_type != "LIGHT":
            if fits_file.imaging_session_id:
                warnings.append(
                    f"File {file_id} ('{fits_file.file}') has an imaging session association "
                    f"(session_id={fits_file.imaging_session_id}). Consider clearing it manually."
                )
        fits_file.frame_type = new_frame_type
    session.commit()

    new_scores = _revalidate_files(session, file_ids, db_service)

    return {
        "fixed_count": len(file_ids),
        "revalidated_count": len(file_ids),
        "new_scores": new_scores,
        "warnings": warnings,
    }
