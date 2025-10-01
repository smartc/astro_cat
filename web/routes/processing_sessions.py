"""
Processing session routes.
"""

import json
import logging
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import desc

from models import ProcessingSession
from web.dependencies import get_db_session, get_processing_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/processing-sessions")


@router.get("")
async def get_processing_sessions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    processing_manager = Depends(get_processing_manager)
):
    """Get processing sessions with pagination and filtering."""
    try:
        # Get sessions using ProcessingSessionManager which returns ProcessingSessionInfo objects
        all_sessions = processing_manager.list_processing_sessions(status_filter=status)
        
        # Apply pagination
        total = len(all_sessions)
        offset = (page - 1) * limit
        sessions = all_sessions[offset:offset + limit]
        
        # Build response using ProcessingSessionInfo attributes
        session_data = []
        for s in sessions:
            session_data.append({
                "id": s.id,
                "name": s.name,
                "objects": s.objects,  # Already a list
                "notes": s.notes,
                "status": s.status,
                "version": s.version,
                "folder_path": s.folder_path,
                "astrobin_url": s.astrobin_url,
                "social_urls": s.social_urls,  # Already a list
                "total_files": s.total_files,
                "lights": s.lights,
                "darks": s.darks,
                "flats": s.flats,
                "bias": s.bias,
                "processing_started": s.processing_started.isoformat() if s.processing_started else None,
                "processing_completed": s.processing_completed.isoformat() if s.processing_completed else None,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None
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
        logger.error(f"Error fetching processing sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}")
async def get_processing_session(
    session_id: str,
    processing_manager = Depends(get_processing_manager)
):
    """Get detailed information about a processing session."""
    try:
        if processing_manager is None:
            logger.error("Processing manager is None")
            raise HTTPException(status_code=500, detail="Processing manager not initialized")
        
        logger.info(f"Getting processing session: {session_id}")
        session_info = processing_manager.get_processing_session(session_id)
        
        if not session_info:
            raise HTTPException(status_code=404, detail="Processing session not found")
        
        # Return flat structure matching the list endpoint
        return {
            "id": session_info.id,
            "name": session_info.name,
            "objects": session_info.objects,
            "notes": session_info.notes,
            "status": session_info.status,
            "version": session_info.version,
            "folder_path": session_info.folder_path,
            "astrobin_url": session_info.astrobin_url,
            "social_urls": session_info.social_urls,
            "total_files": session_info.total_files,
            "lights": session_info.lights,
            "darks": session_info.darks,
            "flats": session_info.flats,
            "bias": session_info.bias,
            "processing_started": session_info.processing_started.isoformat() if session_info.processing_started else None,
            "processing_completed": session_info.processing_completed.isoformat() if session_info.processing_completed else None,
            "created_at": session_info.created_at.isoformat() if session_info.created_at else None,
            "updated_at": session_info.updated_at.isoformat() if session_info.updated_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching processing session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_processing_session(
    name: str = Body(...),
    file_ids: List[int] = Body(...),
    notes: Optional[str] = Body(None),
    processing_manager = Depends(get_processing_manager)
):
    """Create a new processing session."""
    try:
        if processing_manager is None:
            logger.error("Processing manager is None")
            raise HTTPException(status_code=500, detail="Processing manager not initialized")
        
        logger.info(f"Creating processing session: name={name}, file_ids={file_ids[:5]}... ({len(file_ids)} total)")
        
        session_info = processing_manager.create_processing_session(name, file_ids, notes)
        
        logger.info(f"Created processing session: {session_info.id}")
        
        return {
            "message": "Processing session created successfully",
            "session_id": session_info.id,
            "name": session_info.name,
            "folder_path": session_info.folder_path,
            "total_files": session_info.total_files
        }
    except ValueError as e:
        logger.warning(f"Validation error creating processing session: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating processing session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{session_id}/status")
async def update_processing_session_status(
    session_id: str,
    status: str = Body(...),
    notes: Optional[str] = Body(None),
    processing_manager = Depends(get_processing_manager)
):
    """Update processing session status."""
    try:
        valid_statuses = ['not_started', 'in_progress', 'complete']
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid status. Must be one of: {valid_statuses}"
            )
        
        success = processing_manager.update_session_status(session_id, status, notes)
        if not success:
            raise HTTPException(status_code=404, detail="Processing session not found")
        
        return {"message": f"Processing session {session_id} updated successfully"}
    except Exception as e:
        logger.error(f"Error updating processing session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}")
async def delete_processing_session(
    session_id: str,
    remove_files: bool = Query(True, description="Remove staged files"),
    processing_manager = Depends(get_processing_manager)
):
    """Delete a processing session."""
    try:
        success = processing_manager.delete_processing_session(session_id, remove_files)
        if not success:
            raise HTTPException(status_code=404, detail="Processing session not found")
        
        return {"message": f"Processing session {session_id} deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting processing session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/add-files")
async def add_files_to_processing_session(
    session_id: str,
    file_ids: List[int] = Body(...),
    processing_manager = Depends(get_processing_manager)
):
    """Add files to an existing processing session."""
    try:
        if processing_manager is None:
            logger.error("Processing manager is None")
            raise HTTPException(status_code=500, detail="Processing manager not initialized")
        
        logger.info(f"Adding {len(file_ids)} files to processing session {session_id}")
        
        success = processing_manager.add_files_to_session(session_id, file_ids)
        if not success:
            raise HTTPException(status_code=404, detail="Processing session not found")
        
        return {"message": f"Added {len(file_ids)} files to processing session {session_id}"}
    except ValueError as e:
        logger.warning(f"Validation error adding files to session {session_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding files to processing session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/calibration-matches")
async def get_calibration_matches(
    session_id: str,
    processing_manager = Depends(get_processing_manager)
):
    """Find matching calibration files for a processing session."""
    try:
        matches = processing_manager.find_matching_calibration(session_id)
        
        # Convert matches to JSON-serializable format
        result = {}
        for frame_type, match_list in matches.items():
            result[frame_type] = []
            for match in match_list:
                result[frame_type].append({
                    "capture_session_id": match.capture_session_id,
                    "camera": match.camera,
                    "telescope": match.telescope,
                    "filters": match.filters,
                    "capture_date": match.capture_date,
                    "frame_type": match.frame_type,
                    "file_count": match.file_count,
                    "exposure_times": match.exposure_times,
                    "file_ids": [f.id for f in match.files]
                })
        
        return result
    except Exception as e:
        logger.error(f"Error finding calibration matches for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{session_id}/session-info")
async def get_processing_session_info(
    session_id: str,
    processing_manager = Depends(get_processing_manager)
):
    """Get session_info.md file for processing session."""
    try:
        session_info = processing_manager.get_processing_session(session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail="Session not found")
        
        info_file = Path(session_info.folder_path) / "session_info.md"
        
        if info_file.exists():
            return {"content": info_file.read_text(encoding='utf-8')}
        else:
            raise HTTPException(status_code=404, detail="Session info file not found")
            
    except Exception as e:
        logger.error(f"Error reading session info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{session_id}/session-info")
async def save_processing_session_info(
    session_id: str,
    content: str = Body(...),
    processing_manager = Depends(get_processing_manager)
):
    """Save session_info.md file for processing session."""
    try:
        session_info = processing_manager.get_processing_session(session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail="Session not found")
        
        info_file = Path(session_info.folder_path) / "session_info.md"
        info_file.parent.mkdir(parents=True, exist_ok=True)
        info_file.write_text(content, encoding='utf-8')
        
        logger.info(f"Saved session info for {session_id}: {len(content)} characters")
        
        return {"message": "Session info saved successfully", "file_path": str(info_file)}
        
    except Exception as e:
        logger.error(f"Error saving session info: {e}")
        raise HTTPException(status_code=500, detail=str(e))