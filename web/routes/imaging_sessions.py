"""
Imaging session routes.
"""

import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import desc

from models import ImagingSession as SessionModel, FitsFile
from web.dependencies import get_db_session, get_config
from web.utils import generate_imaging_session_default_content

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/imaging-sessions")


@router.get("")
async def get_imaging_sessions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    cameras: Optional[str] = Query(None, description="Comma-separated cameras"),
    telescopes: Optional[str] = Query(None, description="Comma-separated telescopes"),
    session: Session = Depends(get_db_session)
):
    """Get imaging sessions with pagination and filtering."""
    try:
        query = session.query(SessionModel).order_by(desc(SessionModel.date))
        
        # Apply filters
        if date_start:
            query = query.filter(SessionModel.date >= date_start)
        if date_end:
            query = query.filter(SessionModel.date <= date_end)
        if cameras:
            camera_list = [c.strip() for c in cameras.split(',') if c.strip()]
            if camera_list:
                query = query.filter(SessionModel.camera.in_(camera_list))
        if telescopes:
            telescope_list = [t.strip() for t in telescopes.split(',') if t.strip()]
            if telescope_list:
                query = query.filter(SessionModel.telescope.in_(telescope_list))
        
        total = query.count()
        offset = (page - 1) * limit
        sessions = query.offset(offset).limit(limit).all()
        
        # Get file counts for each session
        session_data = []
        for s in sessions:
            file_count = session.query(FitsFile).filter(FitsFile.imaging_session_id == s.id).count()
            session_data.append({
                "session_id": s.id,
                "session_date": s.date,
                "telescope": s.telescope,
                "camera": s.camera,
                "site_name": s.site_name,
                "observer": s.observer,
                "notes": s.notes,
                "file_count": file_count,
                "created_at": s.created_at.isoformat() if s.created_at else None
            })
        
        return {
            "sessions": session_data,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit if total > 0 else 0
            }
        }
    except Exception as e:
        logger.error(f"Error fetching imaging sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{session_id}/details")
async def get_imaging_session_details(
    session_id: str,
    session: Session = Depends(get_db_session)):
    """Get detailed information about a specific imaging session including object-level summaries."""
    try:
        logger.info(f"Getting imaging session details for: {session_id}")
        
        # Get session metadata
        imaging_session = session.query(SessionModel).filter(
            SessionModel.id == session_id
        ).first()
        
        if not imaging_session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get all files for this session
        files = session.query(FitsFile).filter(
            FitsFile.imaging_session_id == session_id
        ).all()
        
        logger.info(f"Found {len(files)} files for session {session_id}")
        
        if not files:
            return {
                "session": {
                    "session_id": imaging_session.id,
                    "session_date": imaging_session.date,
                    "telescope": imaging_session.telescope,
                    "camera": imaging_session.camera,
                    "site_name": imaging_session.site_name,
                    "observer": imaging_session.observer,
                    "latitude": imaging_session.latitude,
                    "longitude": imaging_session.longitude,
                    "elevation": imaging_session.elevation,
                    "notes": imaging_session.notes,
                    "created_at": imaging_session.created_at.isoformat() if imaging_session.created_at else None
                },
                "summary": {
                    "total_files": 0,
                    "frame_types": {},
                    "total_exposure": 0,
                    "objects": []
                }
            }
        
        # Calculate session-level statistics
        total_files = len(files)
        frame_type_counts = {}
        session_total_exposure = 0
        
        # Group files by object
        objects_data = {}
        
        for file in files:
            # Session-level frame type counts
            frame_type = file.frame_type or 'UNKNOWN'
            frame_type_counts[frame_type] = frame_type_counts.get(frame_type, 0) + 1
            
            # Session-level total exposure (LIGHT frames only)
            if frame_type == 'LIGHT' and file.exposure:
                session_total_exposure += file.exposure
            
            # Object-level data (only for LIGHT frames)
            if frame_type == 'LIGHT':
                obj_name = file.object or 'UNKNOWN'
                
                if obj_name not in objects_data:
                    objects_data[obj_name] = {
                        'name': obj_name,
                        'total_files': 0,
                        'frame_types': {},
                        'filter_data': {}  # Track detailed filter info
                    }
                
                objects_data[obj_name]['total_files'] += 1
                objects_data[obj_name]['frame_types'][frame_type] = \
                    objects_data[obj_name]['frame_types'].get(frame_type, 0) + 1
                
                # Track filter-level data with exposure breakdown
                if file.exposure:
                    filter_name = file.filter or 'No Filter'
                    
                    if filter_name not in objects_data[obj_name]['filter_data']:
                        objects_data[obj_name]['filter_data'][filter_name] = {
                            'total_exposure': 0,
                            'exposures': {}  # {exposure_time: [file_ids]}
                        }
                    
                    # Add to total exposure for this filter
                    objects_data[obj_name]['filter_data'][filter_name]['total_exposure'] += file.exposure
                    
                    # Track individual exposures
                    exp_time = file.exposure
                    if exp_time not in objects_data[obj_name]['filter_data'][filter_name]['exposures']:
                        objects_data[obj_name]['filter_data'][filter_name]['exposures'][exp_time] = []
                    objects_data[obj_name]['filter_data'][filter_name]['exposures'][exp_time].append(file.id)
        
        # Convert objects_data to the format expected by frontend
        objects_list = []
        for obj_name, obj_data in objects_data.items():
            # Build filters array with exposure breakdown
            filters_list = []
            for filter_name, filter_info in obj_data['filter_data'].items():
                exposure_breakdown = []
                for exp_time, file_ids in sorted(filter_info['exposures'].items()):
                    exposure_breakdown.append({
                        'exposure': exp_time,
                        'count': len(file_ids),
                        'total': exp_time * len(file_ids),
                        'file_ids': file_ids
                    })
                
                filters_list.append({
                    'filter': filter_name,
                    'total_exposure': filter_info['total_exposure'],
                    'exposure_breakdown': exposure_breakdown
                })
            
            # Sort filters by name
            filters_list.sort(key=lambda x: x['filter'])
            
            objects_list.append({
                'name': obj_name,
                'total_files': obj_data['total_files'],
                'frame_types': obj_data['frame_types'],
                'filters': filters_list
            })
        
        # Sort objects by total files (descending)
        objects_list.sort(key=lambda x: x['total_files'], reverse=True)
        
        result = {
            "session": {
                "session_id": imaging_session.id,
                "session_date": imaging_session.date,
                "telescope": imaging_session.telescope,
                "camera": imaging_session.camera,
                "site_name": imaging_session.site_name,
                "observer": imaging_session.observer,
                "latitude": imaging_session.latitude,
                "longitude": imaging_session.longitude,
                "elevation": imaging_session.elevation,
                "notes": imaging_session.notes,
                "created_at": imaging_session.created_at.isoformat() if imaging_session.created_at else None
            },
            "summary": {
                "total_files": total_files,
                "frame_types": frame_type_counts,
                "total_exposure": session_total_exposure,
                "objects": objects_list
            }
        }
        
        logger.info(f"Returning session details with {len(objects_list)} objects")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching imaging session details: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
        

@router.get("/{session_id}/session-info")
async def get_imaging_session_info(
    session_id: str,
    session: Session = Depends(get_db_session),
    config = Depends(get_config)
):
    """Get session_info.md file for imaging session, creating default content if none exists."""
    try:
        # Verify session exists in database
        imaging_session = session.query(SessionModel).filter(
            SessionModel.id == session_id
        ).first()

        if not imaging_session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Use centralized Session_Notes folder from config
        session_date = datetime.strptime(imaging_session.date, '%Y-%m-%d')
        year = session_date.year
        session_notes_dir = Path(config.paths.notes_dir) / "Imaging_Sessions" / str(year)
        session_notes_dir.mkdir(parents=True, exist_ok=True)
        
        # Session info file path - no _session_notes suffix
        info_file = session_notes_dir / f"{session_id}.md"
        
        if info_file.exists():
            return {"content": info_file.read_text(encoding='utf-8')}
        else:
            # Generate default content from database
            default_content = generate_imaging_session_default_content(session_id, session)
            return {"content": default_content}
            
    except Exception as e:
        logger.error(f"Error reading imaging session info: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{session_id}/session-info")
async def save_imaging_session_info(
    session_id: str,
    content: str = Body(...),
    session: Session = Depends(get_db_session),
    config = Depends(get_config)
):
    """Save session_info.md file for imaging session."""
    try:
        # Verify session exists
        imaging_session = session.query(SessionModel).filter(
            SessionModel.id == session_id
        ).first()

        if not imaging_session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Use centralized Session_Notes folder from config
        session_date = datetime.strptime(imaging_session.date, '%Y-%m-%d')
        year = session_date.year
        session_notes_dir = Path(config.paths.notes_dir) / "Imaging_Sessions" / str(year)
        session_notes_dir.mkdir(parents=True, exist_ok=True)
        
        # Session info file path - no _session_notes suffix
        info_file = session_notes_dir / f"{session_id}.md"
        info_file.write_text(content, encoding='utf-8')
        
        logger.info(f"Saved imaging session info for {session_id}: {len(content)} characters")
        
        return {"message": "Session info saved successfully", "file_path": str(info_file)}
        
    except Exception as e:
        logger.error(f"Error saving imaging session info: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ids")
async def get_imaging_session_ids(
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    cameras: Optional[str] = Query(None, description="Comma-separated cameras"),
    telescopes: Optional[str] = Query(None, description="Comma-separated telescopes"),
    session: Session = Depends(get_db_session)
):
    """
    Get all imaging session IDs matching the filters.
    Used for navigation in the session detail modal.
    Returns sessions in descending date order.
    """
    try:
        query = session.query(SessionModel.id).order_by(desc(SessionModel.date))
        
        # Apply same filters as main list endpoint
        if date_start:
            query = query.filter(SessionModel.date >= date_start)
        if date_end:
            query = query.filter(SessionModel.date <= date_end)
        if cameras:
            camera_list = [c.strip() for c in cameras.split(',') if c.strip()]
            if camera_list:
                query = query.filter(SessionModel.camera.in_(camera_list))
        if telescopes:
            telescope_list = [t.strip() for t in telescopes.split(',') if t.strip()]
            if telescope_list:
                query = query.filter(SessionModel.telescope.in_(telescope_list))
        
        # Get just the session IDs
        session_ids = [row[0] for row in query.all()]
        
        return {
            "session_ids": session_ids,
            "total": len(session_ids)
        }
        
    except Exception as e:
        logger.error(f"Error fetching imaging session IDs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{session_id}")
async def delete_imaging_session(
    session_id: str,
    scope: str = Query(
        "all",
        description="Which files to act on: 'all', 'lights', 'calibration', or 'db_only'"
    ),
    target_objects: Optional[str] = Query(
        None,
        description="Comma-separated object names; limits light-frame deletion when scope='lights' or 'all'"
    ),
    session: Session = Depends(get_db_session),
    config = Depends(get_config)
):
    """
    Delete an imaging session and, optionally, its physical files.

    scope:
      - all         — delete all physical files (lights + calibration) then DB records
      - lights      — delete only LIGHT frame files (optionally filtered by target_objects)
      - calibration — delete only DARK / FLAT / BIAS frame files
      - db_only     — remove DB records only; leave files on disk

    If all files belonging to the session are removed from the database the
    ImagingSession record itself is also deleted.  If only a subset is removed
    (e.g. scope='lights') the session record stays and the remaining files keep
    their association.
    """
    import os
    from pathlib import Path as FilePath

    CALIBRATION_TYPES = {'DARK', 'FLAT', 'BIAS', 'FLAT_DARK', 'MASTER DARK', 'MASTER BIAS', 'MASTER FLAT'}

    # Validate scope
    if scope not in ('all', 'lights', 'calibration', 'db_only'):
        raise HTTPException(status_code=400, detail=f"Invalid scope '{scope}'")

    # Load session
    imaging_session = session.query(SessionModel).filter(
        SessionModel.id == session_id
    ).first()
    if not imaging_session:
        raise HTTPException(status_code=404, detail="Session not found")

    all_files = session.query(FitsFile).filter(
        FitsFile.imaging_session_id == session_id
    ).all()

    # Parse optional object filter
    object_filter: Optional[set] = None
    if target_objects:
        object_filter = {o.strip() for o in target_objects.split(',') if o.strip()}

    # -----------------------------------------------------------------------
    # Determine which records / files to act on
    # -----------------------------------------------------------------------
    def _matches_scope(f: FitsFile) -> bool:
        frame = (f.frame_type or '').upper()
        if scope == 'all':
            return True
        if scope == 'lights':
            if frame != 'LIGHT':
                return False
            if object_filter is not None:
                return bool(f.object and f.object in object_filter)
            return True
        if scope == 'calibration':
            return frame in CALIBRATION_TYPES
        return False  # db_only handled separately

    files_in_scope = [f for f in all_files if _matches_scope(f)] if scope != 'db_only' else all_files

    # -----------------------------------------------------------------------
    # Delete physical files (skip for db_only)
    # -----------------------------------------------------------------------
    deleted_from_disk = 0
    failed_deletes: list = []

    if scope != 'db_only':
        for f in files_in_scope:
            file_path = (
                FilePath(f.folder) / f.file if f.folder else FilePath(f.file)
            )
            try:
                if file_path.exists():
                    file_path.unlink()
                    deleted_from_disk += 1
                else:
                    logger.warning(f"File not found on disk (skipping): {file_path}")
            except OSError as e:
                logger.error(f"Could not delete {file_path}: {e}")
                failed_deletes.append(str(file_path))

    # -----------------------------------------------------------------------
    # Remove DB records
    # -----------------------------------------------------------------------
    for f in files_in_scope:
        session.delete(f)

    # Flush so the subsequent count reflects the deletions
    session.flush()

    remaining_count = session.query(FitsFile).filter(
        FitsFile.imaging_session_id == session_id
    ).count()

    session_deleted = remaining_count == 0
    if session_deleted:
        session.delete(imaging_session)

    session.commit()

    logger.info(
        f"Deleted session {session_id}: scope={scope}, "
        f"disk={deleted_from_disk}, db={len(files_in_scope)}, "
        f"session_record_removed={session_deleted}"
    )

    return {
        "session_id": session_id,
        "session_deleted": session_deleted,
        "files_removed_from_disk": deleted_from_disk,
        "files_removed_from_db": len(files_in_scope),
        "files_remaining_in_session": remaining_count,
        "failed_deletes": failed_deletes
    }


@router.get("/{session_id}/processing-sessions")
async def get_processing_sessions_for_imaging_session(
    session_id: str,
    session: Session = Depends(get_db_session)
):
    """
    Get all processing sessions that use files from this imaging session.
    Returns processing session details including frame counts.
    """
    try:
        from models import ProcessingSession, ProcessingSessionFile
        from sqlalchemy import func, distinct
        import json
        
        # Find all processing sessions that contain files from this imaging session
        # We need to join: ProcessingSession -> ProcessingSessionFile -> FitsFile
        # and filter where FitsFile.session_id matches our imaging session_id
        
        processing_sessions_query = session.query(ProcessingSession).join(
            ProcessingSessionFile, ProcessingSession.id == ProcessingSessionFile.processing_session_id
        ).join(
            FitsFile, ProcessingSessionFile.fits_file_id == FitsFile.id
        ).filter(
            FitsFile.imaging_session_id == session_id
        ).distinct()
        
        processing_sessions = processing_sessions_query.all()
        
        if not processing_sessions:
            return []
        
        # Build response with file counts for each processing session
        result = []
        for ps in processing_sessions:
            # Get file counts by frame type for files from THIS imaging session
            file_counts = session.query(
                FitsFile.frame_type,
                func.count(FitsFile.id)
            ).join(ProcessingSessionFile, ProcessingSessionFile.fits_file_id == FitsFile.id).filter(
                ProcessingSessionFile.processing_session_id == ps.id,
                FitsFile.imaging_session_id == session_id  # Only count files from this imaging session
            ).group_by(FitsFile.frame_type).all()
            
            frame_counts = {'LIGHT': 0, 'DARK': 0, 'FLAT': 0, 'BIAS': 0}
            for frame_type, count in file_counts:
                if frame_type in frame_counts:
                    frame_counts[frame_type] = count
            
            # Parse objects from JSON
            objects = json.loads(ps.objects) if ps.objects else []
            objects_str = ', '.join(objects) if objects else 'N/A'
            
            result.append({
                'session_id': ps.id,
                'name': ps.name,
                'status': ps.status,
                'objects': objects_str,
                'lights': frame_counts['LIGHT'],
                'darks': frame_counts['DARK'],
                'flats': frame_counts['FLAT'],
                'bias': frame_counts['BIAS'],
                'created_at': ps.created_at.isoformat() if ps.created_at else None
            })
        
        # Sort by creation date (newest first)
        result.sort(key=lambda x: x['created_at'] or '', reverse=True)
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching processing sessions for imaging session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))