"""
Processing session routes.
"""

import json
import logging
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List
from pydantic import BaseModel

from models import ProcessingSession, ProcessingSessionFile, FitsFile
from web.dependencies import get_db_session, get_processing_manager, get_config


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/processing-sessions")

class PreSelectFilesRequest(BaseModel):
    file_ids: List[int]
    suggested_name: str


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


@router.get("/ids")
async def get_processing_session_ids(
    status: Optional[str] = Query(None),
    processing_manager = Depends(get_processing_manager)
):
    """
    Get all processing session IDs matching the filters.
    Used for navigation in the session detail modal.
    Returns sessions in descending creation date order.
    """
    try:
        # Get all sessions matching the filter
        all_sessions = processing_manager.list_processing_sessions(status_filter=status)
        
        # Extract just the IDs in order
        session_ids = [s.id for s in all_sessions]
        
        return {
            "session_ids": session_ids,
            "total": len(session_ids)
        }
        
    except Exception as e:
        logger.error(f"Error fetching processing session IDs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}")
async def get_processing_session(
    session_id: str,
    session: Session = Depends(get_db_session)
):
    """Get details for a specific processing session with object-level summaries."""
    try:
        from models import ProcessingSessionFile
        
        ps = session.query(ProcessingSession).filter(
            ProcessingSession.id == session_id
        ).first()
        
        if not ps:
            raise HTTPException(status_code=404, detail="Processing session not found")
        
        # Get file counts by frame type
        file_counts = session.query(
            FitsFile.frame_type,
            func.count(FitsFile.id)
        ).join(ProcessingSessionFile).filter(
            ProcessingSessionFile.processing_session_id == session_id
        ).group_by(FitsFile.frame_type).all()
        
        frame_counts = {'LIGHT': 0, 'DARK': 0, 'FLAT': 0, 'BIAS': 0}
        for frame_type, count in file_counts:
            if frame_type in frame_counts:
                frame_counts[frame_type] = count
        
        # Build object-level summaries using SQL aggregation (LIGHT frames only)
        # This is MUCH faster than loading all files into memory
        from sqlalchemy import case

        light_frame_summary = session.query(
            func.coalesce(FitsFile.object, 'UNKNOWN').label('object_name'),
            func.coalesce(FitsFile.filter, 'No Filter').label('filter_name'),
            FitsFile.exposure,
            func.count(FitsFile.id).label('file_count'),
            func.sum(FitsFile.exposure).label('total_exposure'),
            func.group_concat(FitsFile.id).label('file_ids')
        ).join(ProcessingSessionFile).filter(
            ProcessingSessionFile.processing_session_id == session_id,
            FitsFile.frame_type == 'LIGHT',
            FitsFile.exposure.isnot(None)
        ).group_by(
            func.coalesce(FitsFile.object, 'UNKNOWN'),
            func.coalesce(FitsFile.filter, 'No Filter'),
            FitsFile.exposure
        ).all()

        # Build hierarchical structure from aggregated data
        objects_data = {}

        for row in light_frame_summary:
            obj_name = row.object_name
            filter_name = row.filter_name
            exp_time = row.exposure
            file_count = row.file_count
            total_exp = row.total_exposure
            file_ids = [int(fid) for fid in row.file_ids.split(',')]

            if obj_name not in objects_data:
                objects_data[obj_name] = {
                    'name': obj_name,
                    'total_files': 0,
                    'filter_data': {}
                }

            objects_data[obj_name]['total_files'] += file_count

            if filter_name not in objects_data[obj_name]['filter_data']:
                objects_data[obj_name]['filter_data'][filter_name] = {
                    'total_exposure': 0,
                    'exposures': {}
                }

            objects_data[obj_name]['filter_data'][filter_name]['total_exposure'] += total_exp
            objects_data[obj_name]['filter_data'][filter_name]['exposures'][exp_time] = file_ids
        
        # Convert to frontend format
        objects_list = []
        for obj_name, obj_data in objects_data.items():
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
            
            filters_list.sort(key=lambda x: x['filter'])
            
            objects_list.append({
                'name': obj_name,
                'total_files': obj_data['total_files'],
                'filters': filters_list
            })
        
        objects_list.sort(key=lambda x: x['total_files'], reverse=True)
        
        # Parse JSON fields
        objects = json.loads(ps.objects) if ps.objects else []
        social_urls = json.loads(ps.social_urls) if ps.social_urls else []
        
        return {
            "id": ps.id,
            "name": ps.name,
            "objects": objects,
            "objects_detail": objects_list,  # NEW: detailed breakdown
            "total_files": sum(frame_counts.values()),
            "lights": frame_counts['LIGHT'],
            "darks": frame_counts['DARK'],
            "flats": frame_counts['FLAT'],
            "bias": frame_counts['BIAS'],
            "folder_path": ps.folder_path,
            "status": ps.status,
            "created_at": ps.created_at.isoformat() if ps.created_at else None,
            "notes": ps.notes,
            "version": ps.version,
            "astrobin_url": ps.astrobin_url,
            "social_urls": social_urls,
            "processing_started": ps.processing_started.isoformat() if ps.processing_started else None,
            "processing_completed": ps.processing_completed.isoformat() if ps.processing_completed else None,
            "updated_at": ps.updated_at.isoformat() if ps.updated_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching processing session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("")
async def create_processing_session(
    name: str = Body(...),
    file_ids: Optional[List[int]] = Body(default=[]),  # Changed: now optional with empty list default
    notes: Optional[str] = Body(None),
    processing_manager = Depends(get_processing_manager)
):
    """Create a new processing session.
    
    Args:
        name: Name of the processing session
        file_ids: Optional list of file IDs to include. Can be empty to create an empty session.
        notes: Optional notes for the session
    """
    try:
        if processing_manager is None:
            logger.error("Processing manager is None")
            raise HTTPException(status_code=500, detail="Processing manager not initialized")
        
        file_count = len(file_ids) if file_ids else 0
        logger.info(f"Creating processing session: name={name}, file_ids count={file_count}")
        
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
        result = {
            'already_has': matches.get('already_has', {'darks': False, 'flats': False, 'bias': False})
        }
        
        # Only process the calibration frame types, not 'already_has'
        for frame_type in ['darks', 'flats', 'bias']:
            result[frame_type] = []
            match_list = matches.get(frame_type, [])
            for match in match_list:
                match_dict = {
                    "capture_session_id": match.capture_session_id,
                    "camera": match.camera,
                    "telescope": match.telescope,
                    "filters": match.filters,
                    "capture_date": match.capture_date,
                    "frame_type": match.frame_type,
                    "file_count": match.file_count,
                    "exposure_times": match.exposure_times,
                    "file_ids": [f.id for f in match.files]
                }
                
                # Add new temporal matching fields
                if match.matched_light_dates:
                    match_dict["matched_light_dates"] = match.matched_light_dates
                if match.days_from_lights is not None:
                    match_dict["days_from_lights"] = match.days_from_lights
                
                result[frame_type].append(match_dict)
        
        return result
    except Exception as e:
        logger.error(f"Error finding calibration matches for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        

@router.get("/{session_id}/session-info")
async def get_processing_session_info(
    session_id: str,
    processing_manager = Depends(get_processing_manager),
    config = Depends(get_config)
):
    """Get session_info.md file for processing session."""
    try:
        session_info = processing_manager.get_processing_session(session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Read from centralized Session_Notes folder
        # Extract year from session_id (format: YYYYMMDD_...)
        try:
            year = int(session_id[:4])
        except (ValueError, IndexError):
            # Fallback: try to get from created_at if available
            from models import ProcessingSession
            db_session = processing_manager.db_service.db_manager.get_session()
            try:
                ps = db_session.query(ProcessingSession).filter(
                    ProcessingSession.id == session_id
                ).first()
                year = ps.created_at.year if ps and ps.created_at else datetime.now().year
            finally:
                db_session.close()
        
        notes_dir = Path(config.paths.notes_dir) / "Processing_Sessions" / str(year)
        info_file = notes_dir / f"{session_id}.md"
        
        if info_file.exists():
            return {"content": info_file.read_text(encoding='utf-8')}
        else:
            # Fallback: check old location in session folder for backwards compatibility
            old_location = Path(session_info.folder_path) / "session_info.md"
            if old_location.exists():
                logger.warning(f"Found markdown at old location for {session_id}, consider migrating")
                return {"content": old_location.read_text(encoding='utf-8')}
            
            raise HTTPException(status_code=404, detail="Session info file not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading session info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{session_id}/session-info")
async def save_processing_session_info(
    session_id: str,
    content: str = Body(...),
    processing_manager = Depends(get_processing_manager),
    config = Depends(get_config)
):
    """Save session_info.md file for processing session."""
    try:
        session_info = processing_manager.get_processing_session(session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Save to centralized Session_Notes folder
        # Extract year from session_id (format: YYYYMMDD_...)
        try:
            year = int(session_id[:4])
        except (ValueError, IndexError):
            # Fallback: try to get from created_at if available
            from models import ProcessingSession
            db_session = processing_manager.db_service.db_manager.get_session()
            try:
                ps = db_session.query(ProcessingSession).filter(
                    ProcessingSession.id == session_id
                ).first()
                year = ps.created_at.year if ps and ps.created_at else datetime.now().year
            finally:
                db_session.close()
        
        notes_dir = Path(config.paths.notes_dir) / "Processing_Sessions" / str(year)
        notes_dir.mkdir(parents=True, exist_ok=True)
        
        info_file = notes_dir / f"{session_id}.md"
        info_file.write_text(content, encoding='utf-8')
        
        logger.info(f"Saved session info for {session_id}: {len(content)} characters")
        
        return {"message": "Session info saved successfully", "file_path": str(info_file)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving session info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/preselect-files")
async def preselect_files_for_session(
    session_id: str,
    request: PreSelectFilesRequest,
    session: Session = Depends(get_db_session)
):
    """
    Endpoint to pre-select files for adding to a processing session.
    Returns session details with pre-selected file information.
    """
    try:
        # This is primarily for the frontend state management
        # The actual file addition happens through the existing add-files endpoint
        return {
            "session_id": session_id,
            "preselected_file_ids": request.file_ids,
            "suggested_name": request.suggested_name,
            "file_count": len(request.file_ids)
        }
    except Exception as e:
        logger.error(f"Error preselecting files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_id}/objects/{object_name}")
async def remove_object_from_session(
    session_id: str,
    object_name: str,
    session: Session = Depends(get_db_session),
    config = Depends(get_config)
):
    """
    Remove an object from a processing session.
    Also removes calibration files that no longer match any remaining light frames.
    """
    try:
        from models import ProcessingSessionFile
        from pathlib import Path
        
        # Get the processing session
        ps = session.query(ProcessingSession).filter(
            ProcessingSession.id == session_id
        ).first()
        
        if not ps:
            raise HTTPException(status_code=404, detail="Processing session not found")
        
        # Get IDs of all LIGHT files for this object
        light_file_ids = session.query(FitsFile.id).join(ProcessingSessionFile).filter(
            ProcessingSessionFile.processing_session_id == session_id,
            FitsFile.frame_type == 'LIGHT',
            FitsFile.object == object_name
        ).all()

        if not light_file_ids:
            raise HTTPException(status_code=404, detail=f"No light frames found for object '{object_name}'")

        light_file_ids = [f[0] for f in light_file_ids]  # Extract IDs from tuples
        
        # Get remaining LIGHT files (after removal) - only load needed columns
        from sqlalchemy.orm import load_only

        remaining_lights = session.query(FitsFile).options(
            load_only(FitsFile.camera, FitsFile.exposure, FitsFile.telescope, FitsFile.filter, FitsFile.object)
        ).join(ProcessingSessionFile).filter(
            ProcessingSessionFile.processing_session_id == session_id,
            FitsFile.frame_type == 'LIGHT',
            FitsFile.object != object_name
        ).all()
        
        # Determine what calibration is still needed based on remaining lights
        if remaining_lights:
            # Build sets of what's still needed
            needed_cameras = set()
            needed_camera_exposures = set()
            needed_camera_telescope_filters = set()
            
            for f in remaining_lights:
                if f.camera and f.camera != 'UNKNOWN':
                    needed_cameras.add(f.camera)
                    if f.exposure:
                        needed_camera_exposures.add((f.camera, f.exposure))
                    if f.telescope and f.telescope != 'UNKNOWN' and f.filter and f.filter not in ['UNKNOWN', 'NONE']:
                        needed_camera_telescope_filters.add((f.camera, f.telescope, f.filter))
            
            # Get current calibration files - only load needed columns for orphan detection
            current_darks = session.query(FitsFile).options(
                load_only(FitsFile.id, FitsFile.camera, FitsFile.exposure)
            ).join(ProcessingSessionFile).filter(
                ProcessingSessionFile.processing_session_id == session_id,
                FitsFile.frame_type == 'DARK'
            ).all()

            current_flats = session.query(FitsFile).options(
                load_only(FitsFile.id, FitsFile.camera, FitsFile.telescope, FitsFile.filter)
            ).join(ProcessingSessionFile).filter(
                ProcessingSessionFile.processing_session_id == session_id,
                FitsFile.frame_type == 'FLAT'
            ).all()

            current_bias = session.query(FitsFile).options(
                load_only(FitsFile.id, FitsFile.camera)
            ).join(ProcessingSessionFile).filter(
                ProcessingSessionFile.processing_session_id == session_id,
                FitsFile.frame_type == 'BIAS'
            ).all()
            
            # Identify orphaned calibration files
            orphaned_cal_ids = []
            
            # Check darks
            for dark in current_darks:
                if dark.camera and dark.exposure is not None:
                    if (dark.camera, dark.exposure) not in needed_camera_exposures:
                        orphaned_cal_ids.append(dark.id)
            
            # Check flats
            for flat in current_flats:
                if flat.camera and flat.telescope and flat.filter:
                    if (flat.camera, flat.telescope, flat.filter) not in needed_camera_telescope_filters:
                        orphaned_cal_ids.append(flat.id)
            
            # Check bias
            for bias in current_bias:
                if bias.camera:
                    if bias.camera not in needed_cameras:
                        orphaned_cal_ids.append(bias.id)
            
            files_to_remove_ids = light_file_ids + orphaned_cal_ids
        else:
            # No remaining lights, remove all files - just get IDs
            all_file_ids = session.query(FitsFile.id).join(ProcessingSessionFile).filter(
                ProcessingSessionFile.processing_session_id == session_id
            ).all()
            files_to_remove_ids = [f[0] for f in all_file_ids]
        
        # Remove symlinks from staging folder
        if ps.folder_path:
            staging_path = Path(ps.folder_path)
            if staging_path.exists():
                for file_id in files_to_remove_ids:
                    # Only load the filename, not all 70+ columns
                    result = session.query(FitsFile.file).filter(FitsFile.id == file_id).first()
                    if result:
                        filename = result[0]
                        
                        # Check in raw/lights and raw/calibration subfolders
                        possible_paths = [
                            staging_path / "raw" / "lights" / filename,
                            staging_path / "raw" / "calibration" / "darks" / filename,
                            staging_path / "raw" / "calibration" / "flats" / filename,
                            staging_path / "raw" / "calibration" / "bias" / filename,
                        ]
                        
                        for link_path in possible_paths:
                            if link_path.exists() and link_path.is_symlink():
                                link_path.unlink()
                                logger.info(f"Removed symlink: {link_path}")
        
        # Remove from database
        session.query(ProcessingSessionFile).filter(
            ProcessingSessionFile.processing_session_id == session_id,
            ProcessingSessionFile.fits_file_id.in_(files_to_remove_ids)
        ).delete(synchronize_session=False)
        
        session.commit()
        
        # Check if any objects remain
        remaining_objects = session.query(FitsFile.object).join(ProcessingSessionFile).filter(
            ProcessingSessionFile.processing_session_id == session_id,
            FitsFile.frame_type == 'LIGHT',
            FitsFile.object.isnot(None)
        ).distinct().all()
        
        remaining_object_names = [obj[0] for obj in remaining_objects if obj[0] and obj[0] != 'CALIBRATION']
        
        return {
            "message": f"Removed object '{object_name}' from session",
            "removed_light_frames": len(light_file_ids),
            "removed_calibration_frames": len(files_to_remove_ids) - len(light_file_ids),
            "remaining_objects": remaining_object_names,
            "session_empty": len(remaining_object_names) == 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing object from session: {e}", exc_info=True)
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{session_id}/files")
async def get_processing_session_files(
    session_id: str,
    session: Session = Depends(get_db_session)
):
    """
    Get all files in a processing session with their metadata.
    
    Returns:
        List of files with id, session_id, frame_type, camera, telescope, obs_date, etc.
    """
    try:
        from sqlalchemy.orm import load_only

        # Query files with only needed columns (11 instead of 70+)
        # This is MUCH faster than loading all columns
        files = session.query(FitsFile).options(
            load_only(
                FitsFile.id,
                FitsFile.file,
                FitsFile.folder,
                FitsFile.imaging_session_id,
                FitsFile.frame_type,
                FitsFile.camera,
                FitsFile.telescope,
                FitsFile.filter,
                FitsFile.exposure,
                FitsFile.obs_date,
                FitsFile.object
            )
        ).join(ProcessingSessionFile).filter(
            ProcessingSessionFile.processing_session_id == session_id
        ).all()

        if not files:
            return []

        # Build response with relevant file metadata
        files_data = []
        for file in files:
            files_data.append({
                "id": file.id,
                "file": file.file,
                "folder": file.folder,
                "imaging_session_id": file.imaging_session_id,  # New name (Phase 3)
                "session_id": file.imaging_session_id,  # Backward compatibility
                "frame_type": file.frame_type,
                "camera": file.camera,
                "telescope": file.telescope,
                "filter": file.filter,
                "exposure": file.exposure,
                "obs_date": file.obs_date,
                "object": file.object
            })

        return files_data
        
    except Exception as e:
        logger.error(f"Error fetching files for processing session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))