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

from models import Session as SessionModel, FitsFile
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
        query = session.query(SessionModel).order_by(desc(SessionModel.session_date))
        
        # Apply filters
        if date_start:
            query = query.filter(SessionModel.session_date >= date_start)
        if date_end:
            query = query.filter(SessionModel.session_date <= date_end)
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
            file_count = session.query(FitsFile).filter(FitsFile.session_id == s.session_id).count()
            session_data.append({
                "session_id": s.session_id,
                "session_date": s.session_date,
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
    session: Session = Depends(get_db_session)
):
    """Get detailed information about a specific imaging session including object-level summaries."""
    try:
        logger.info(f"Getting imaging session details for: {session_id}")
        
        # Get session metadata
        imaging_session = session.query(SessionModel).filter(
            SessionModel.session_id == session_id
        ).first()
        
        if not imaging_session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get all files for this session
        files = session.query(FitsFile).filter(
            FitsFile.session_id == session_id
        ).all()
        
        logger.info(f"Found {len(files)} files for session {session_id}")
        
        if not files:
            return {
                "session": {
                    "session_id": imaging_session.session_id,
                    "session_date": imaging_session.session_date,
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
                    "objects": []
                }
            }
        
        # Calculate session-level statistics
        total_files = len(files)
        frame_type_counts = {}
        
        # Group files by object
        objects_data = {}
        
        for file in files:
            # Session-level frame type counts
            frame_type = file.frame_type or 'UNKNOWN'
            frame_type_counts[frame_type] = frame_type_counts.get(frame_type, 0) + 1
            
            # Object-level grouping
            obj = file.object or 'CALIBRATION'
            if obj not in objects_data:
                objects_data[obj] = {
                    "object": obj,
                    "files": [],
                    "frame_types": {},
                    "filters": set(),
                    "total_exposure": 0.0
                }
            
            objects_data[obj]["files"].append({
                "id": file.id,
                "file": file.file,
                "frame_type": file.frame_type,
                "filter": file.filter,
                "exposure": file.exposure,
                "ra": file.ra,
                "dec": file.dec,
                "validation_score": file.validation_score
            })
            
            # Object-level frame type counts
            objects_data[obj]["frame_types"][frame_type] = \
                objects_data[obj]["frame_types"].get(frame_type, 0) + 1
            
            # Filters used
            if file.filter:
                objects_data[obj]["filters"].add(file.filter)
            
            # Total exposure
            if file.exposure and file.frame_type == 'LIGHT':
                objects_data[obj]["total_exposure"] += file.exposure
        
        # Convert objects_data to list and serialize sets
        objects_list = []
        for obj_data in objects_data.values():
            obj_data["filters"] = sorted(list(obj_data["filters"]))
            obj_data["file_count"] = len(obj_data["files"])
            objects_list.append(obj_data)
        
        result = {
            "session": {
                "session_id": imaging_session.session_id,
                "session_date": imaging_session.session_date,
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
            SessionModel.session_id == session_id
        ).first()
        
        if not imaging_session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get image directory from config
        base_dir = Path(config.paths.image_dir)
        
        # Create session_info folder structure
        session_date = datetime.strptime(imaging_session.session_date, '%Y-%m-%d')
        year = session_date.year
        session_info_dir = base_dir / ".session_info" / str(year)
        session_info_dir.mkdir(parents=True, exist_ok=True)
        
        # Session info file path
        info_file = session_info_dir / f"{session_id}_session_notes.md"
        
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
            SessionModel.session_id == session_id
        ).first()
        
        if not imaging_session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get image directory from config
        base_dir = Path(config.paths.image_dir)
        
        # Create session_info folder structure
        session_date = datetime.strptime(imaging_session.session_date, '%Y-%m-%d')
        year = session_date.year
        session_info_dir = base_dir / ".session_info" / str(year)
        session_info_dir.mkdir(parents=True, exist_ok=True)
        
        # Session info file path
        info_file = session_info_dir / f"{session_id}_session_notes.md"
        info_file.write_text(content, encoding='utf-8')
        
        logger.info(f"Saved imaging session info for {session_id}: {len(content)} characters")
        
        return {"message": "Session info saved successfully", "file_path": str(info_file)}
        
    except Exception as e:
        logger.error(f"Error saving imaging session info: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e)) 