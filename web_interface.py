"""
FITS Cataloger Web Interface - Updated with Processing Sessions
FastAPI application for browsing database and managing operations
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import traceback

from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc
import uvicorn
from concurrent.futures import ThreadPoolExecutor
from functools import partial

# Import your existing modules
from models import DatabaseManager, DatabaseService, FitsFile, Session as SessionModel, ProcessingSession
from config import load_config
from validation import FitsValidator
from file_organizer import FileOrganizer
from fits_processor import OptimizedFitsProcessor
from processing_session_manager import ProcessingSessionManager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables for managing background tasks
background_tasks_status: Dict[str, Dict] = {}

# Initialize FastAPI
app = FastAPI(
    title="FITS Cataloger", 
    description="Astrophotography Image Management System",
    version="1.0.0"
)

# Enhanced CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global configuration and services
config = None
db_manager = None
db_service = None
cameras = []
telescopes = []
filter_mappings = {}
processing_manager = None
executor = ThreadPoolExecutor(max_workers=2)

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    global config, db_manager, db_service, cameras, telescopes, filter_mappings, processing_manager
    
    try:
        # Load configuration
        config, cameras, telescopes, filter_mappings = load_config()
        
        # Initialize database
        db_manager = DatabaseManager(config.database.connection_string)
        db_service = DatabaseService(db_manager)
        
        # Initialize processing session manager
        processing_manager = ProcessingSessionManager(config, db_service)
        
        # Create directories for static files if they don't exist
        Path("static").mkdir(exist_ok=True)
        
        logger.info("FITS Cataloger web interface started successfully")
        logger.info(f"Loaded {len(cameras)} cameras, {len(telescopes)} telescopes")
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    global db_manager
    if db_manager:
        db_manager.close()

# Dependency to get database session
def get_db_session():
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()

# ============================================================================
# EXISTING API ROUTES (unchanged)
# ============================================================================

@app.get("/api/filter-options")
async def get_filter_options(session: Session = Depends(get_db_session)):
    """Get unique values for filter dropdowns."""
    try:
        # Get unique values for each filterable column
        frame_types = [row[0] for row in session.query(FitsFile.frame_type).distinct().all() if row[0]]
        cameras_db = [row[0] for row in session.query(FitsFile.camera).distinct().all() if row[0]]
        telescopes_db = [row[0] for row in session.query(FitsFile.telescope).distinct().all() if row[0]]
        objects = [row[0] for row in session.query(FitsFile.object).distinct().all() if row[0] and row[0] != 'CALIBRATION']
        filters = [row[0] for row in session.query(FitsFile.filter).distinct().all() if row[0]]
        dates = [row[0] for row in session.query(FitsFile.obs_date).distinct().all() if row[0]]
        
        return {
            "frame_types": sorted(frame_types),
            "cameras": sorted(cameras_db),
            "telescopes": sorted(telescopes_db),
            "objects": sorted(objects)[:100],  # Limit to prevent huge lists
            "filters": sorted(filters),
            "dates": sorted(dates, reverse=True)[:50]  # Recent dates first, limited
        }
    except Exception as e:
        logger.error(f"Error fetching filter options: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files")
async def get_files(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=1000),
    frame_types: Optional[str] = Query(None, description="Comma-separated frame types"),
    cameras: Optional[str] = Query(None, description="Comma-separated cameras"),
    telescopes: Optional[str] = Query(None, description="Comma-separated telescopes"),
    objects: Optional[str] = Query(None, description="Comma-separated objects"),
    filters: Optional[str] = Query(None, description="Comma-separated filters"),
    filename: Optional[str] = None,
    session_id: Optional[str] = None,
    exposure_min: Optional[float] = None,
    exposure_max: Optional[float] = None,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    sort_by: str = Query("obs_date"),
    sort_order: str = Query("desc"),
    session: Session = Depends(get_db_session)
):
    """Get paginated list of FITS files with filtering and sorting."""
    try:
        query = session.query(FitsFile)
        
        # Apply multi-select filters
        if frame_types:
            frame_type_list = [ft.strip() for ft in frame_types.split(',') if ft.strip()]
            if frame_type_list:
                query = query.filter(FitsFile.frame_type.in_(frame_type_list))
        
        if cameras:
            camera_list = [c.strip() for c in cameras.split(',') if c.strip()]
            if camera_list:
                query = query.filter(FitsFile.camera.in_(camera_list))
        
        if telescopes:
            telescope_list = [t.strip() for t in telescopes.split(',') if t.strip()]
            if telescope_list:
                query = query.filter(FitsFile.telescope.in_(telescope_list))
        
        if objects:
            object_list = [o.strip() for o in objects.split(',') if o.strip()]
            if object_list:
                query = query.filter(FitsFile.object.in_(object_list))
        
        if filters:
            filter_list = [f.strip() for f in filters.split(',') if f.strip()]
            if filter_list:
                query = query.filter(FitsFile.filter.in_(filter_list))
        
        # Apply search filters
        if filename:
            query = query.filter(FitsFile.file.ilike(f"%{filename}%"))
        if session_id:
            query = query.filter(FitsFile.session_id.ilike(f"%{session_id}%"))
        if exposure_min is not None:
            query = query.filter(FitsFile.exposure >= exposure_min)
        if exposure_max is not None:
            query = query.filter(FitsFile.exposure <= exposure_max)
        
        # Apply date range filters
        if date_start:
            query = query.filter(FitsFile.obs_date >= date_start)
        if date_end:
            query = query.filter(FitsFile.obs_date <= date_end)
        
        # Apply sorting
        sort_column = getattr(FitsFile, sort_by, FitsFile.obs_date)
        if sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))
        
        # Get total count for pagination
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * limit
        files = query.offset(offset).limit(limit).all()
        
        return {
            "files": [
                {
                    "id": f.id,
                    "file": f.file,
                    "folder": f.folder,
                    "object": f.object,
                    "frame_type": f.frame_type,
                    "camera": f.camera,
                    "telescope": f.telescope,
                    "filter": f.filter,
                    "exposure": f.exposure,
                    "obs_date": f.obs_date,
                    "obs_timestamp": f.obs_timestamp.isoformat() if f.obs_timestamp else None,
                    "ra": f.ra,
                    "dec": f.dec,
                    "session_id": f.session_id,
                    "bad": f.bad,
                    "file_not_found": f.file_not_found,
                    "validation_score": f.validation_score
                }
                for f in files
            ],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit if total > 0 else 0
            }
        }
    except Exception as e:
        logger.error(f"Error fetching files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def get_stats(session: Session = Depends(get_db_session)):
    """Get comprehensive database statistics."""
    try:
        logger.info("Getting database stats...")
        
        # Get basic stats
        total_files = session.query(FitsFile).count()
        logger.info(f"Total files: {total_files}")
        
        if total_files == 0:
            return {
                "total_files": 0,
                "validation": {
                    "total_files": 0,
                    "auto_migrate": 0,
                    "needs_review": 0,
                    "manual_only": 0,
                    "no_score": 0
                },
                "recent_files": 0,
                "by_frame_type": {},
                "by_camera": {},
                "by_telescope": {}
            }
        
        # Add validation statistics
        auto_migrate = session.query(FitsFile).filter(
            FitsFile.validation_score.isnot(None),
            FitsFile.validation_score >= 95.0
        ).count()
        
        needs_review = session.query(FitsFile).filter(
            FitsFile.validation_score.isnot(None),
            FitsFile.validation_score >= 80.0,
            FitsFile.validation_score < 95.0
        ).count()
        
        manual_only = session.query(FitsFile).filter(
            FitsFile.validation_score.isnot(None),
            FitsFile.validation_score < 80.0
        ).count()
        
        no_score = session.query(FitsFile).filter(
            FitsFile.validation_score.is_(None)
        ).count()
        
        # Add recent files count
        recent_cutoff = datetime.now() - timedelta(days=7)
        recent_files = session.query(FitsFile).filter(
            FitsFile.created_at >= recent_cutoff
        ).count()
        
        # Get frame type counts
        frame_type_counts = session.query(
            FitsFile.frame_type, 
            func.count(FitsFile.id)
        ).group_by(FitsFile.frame_type).all()
        
        # Get camera counts
        camera_counts = session.query(
            FitsFile.camera, 
            func.count(FitsFile.id)
        ).group_by(FitsFile.camera).all()
        
        # Get telescope counts
        telescope_counts = session.query(
            FitsFile.telescope, 
            func.count(FitsFile.id)
        ).group_by(FitsFile.telescope).all()
        
        stats = {
            "total_files": total_files,
            "validation": {
                "total_files": total_files,
                "auto_migrate": auto_migrate,
                "needs_review": needs_review,
                "manual_only": manual_only,
                "no_score": no_score
            },
            "recent_files": recent_files,
            "by_frame_type": {ft: count for ft, count in frame_type_counts if ft},
            "by_camera": {cam: count for cam, count in camera_counts if cam},
            "by_telescope": {tel: count for tel, count in telescope_counts if tel}
        }
        
        logger.info(f"Stats compiled: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/imaging-sessions")
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

@app.get("/api/imaging-sessions/{session_id}/details")
async def get_imaging_session_details(
    session_id: str,
    session: Session = Depends(get_db_session)
):
    """Get detailed information about a specific imaging session including object-level summaries."""
    try:
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
            
            # Object-level data
            obj_name = file.object or 'UNKNOWN'
            
            if obj_name not in objects_data:
                objects_data[obj_name] = {
                    'name': obj_name,
                    'total_files': 0,
                    'frame_types': {},
                    'filters': {},
                    'total_imaging_time': {}  # by filter for LIGHT frames only
                }
            
            objects_data[obj_name]['total_files'] += 1
            
            # Frame type counts by object
            objects_data[obj_name]['frame_types'][frame_type] = \
                objects_data[obj_name]['frame_types'].get(frame_type, 0) + 1
            
            # Track filters used
            if file.filter:
                objects_data[obj_name]['filters'][file.filter] = \
                    objects_data[obj_name]['filters'].get(file.filter, 0) + 1
            
            # Calculate imaging time for LIGHT frames only
            if frame_type == 'LIGHT' and file.exposure:
                filter_name = file.filter or 'No Filter'
                if filter_name not in objects_data[obj_name]['total_imaging_time']:
                    objects_data[obj_name]['total_imaging_time'][filter_name] = 0
                objects_data[obj_name]['total_imaging_time'][filter_name] += file.exposure
        
        # Convert imaging times to hours:minutes:seconds format
        for obj_data in objects_data.values():
            formatted_times = {}
            for filter_name, total_seconds in obj_data['total_imaging_time'].items():
                hours = int(total_seconds // 3600)
                minutes = int((total_seconds % 3600) // 60)
                seconds = int(total_seconds % 60)
                formatted_times[filter_name] = {
                    'seconds': total_seconds,
                    'formatted': f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                }
            obj_data['total_imaging_time'] = formatted_times
        
        # Sort objects by total files (descending)
        objects_list = sorted(
            objects_data.values(), 
            key=lambda x: x['total_files'], 
            reverse=True
        )
        
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
                "total_files": total_files,
                "frame_types": frame_type_counts,
                "objects": objects_list
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching imaging session details: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/equipment")
async def get_equipment():
    """Get equipment lists and filter mappings."""
    try:
        # Get unique values from database for additional context
        session = db_manager.get_session()
        try:
            camera_usage = session.query(
                FitsFile.camera, func.count(FitsFile.id)
            ).group_by(FitsFile.camera).all()
            
            telescope_usage = session.query(
                FitsFile.telescope, func.count(FitsFile.id)
            ).group_by(FitsFile.telescope).all()
            
            filter_usage = session.query(
                FitsFile.filter, func.count(FitsFile.id)
            ).group_by(FitsFile.filter).all()
            
        finally:
            session.close()
        
        return {
            "cameras": [
                {
                    "name": cam.camera,
                    "x": cam.x,
                    "y": cam.y,
                    "pixel": cam.pixel,
                    "brand": cam.brand,
                    "type": cam.type,
                    "rgb": getattr(cam, 'rgb', True)
                }
                for cam in cameras
            ],
            "telescopes": [
                {
                    "name": tel.scope,
                    "focal": tel.focal,
                    "aperture": getattr(tel, 'aperture', None),
                    "make": getattr(tel, 'make', None),
                    "type": getattr(tel, 'type', None)
                }
                for tel in telescopes
            ],
            "filters": filter_mappings,
            "usage": {
                "cameras": {name: count for name, count in camera_usage},
                "telescopes": {name: count for name, count in telescope_usage},
                "filters": {name: count for name, count in filter_usage}
            }
        }
    except Exception as e:
        logger.error(f"Error fetching equipment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# NEW PROCESSING SESSION API ROUTES
# ============================================================================

@app.get("/api/processing-sessions")
async def get_processing_sessions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="Filter by status"),
    session: Session = Depends(get_db_session)
):
    """Get processing sessions with pagination and filtering."""
    try:
        query = session.query(ProcessingSession).order_by(desc(ProcessingSession.created_at))
        
        # Apply status filter
        if status:
            query = query.filter(ProcessingSession.status == status)
        
        total = query.count()
        offset = (page - 1) * limit
        sessions = query.offset(offset).limit(limit).all()
        
        # Get detailed info for each session using ProcessingSessionManager
        session_data = []
        for ps in sessions:
            session_info = processing_manager.get_processing_session(ps.id)
            if session_info:
                session_data.append({
                    "id": session_info.id,
                    "name": session_info.name,
                    "status": session_info.status,
                    "objects": session_info.objects,
                    "total_files": session_info.total_files,
                    "lights": session_info.lights,
                    "darks": session_info.darks,
                    "flats": session_info.flats,
                    "bias": session_info.bias,
                    "folder_path": session_info.folder_path,
                    "created_at": session_info.created_at.isoformat(),
                    "notes": session_info.notes
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

@app.get("/api/processing-sessions/{session_id}")
async def get_processing_session(session_id: str):
    """Get detailed information about a specific processing session."""
    try:
        session_info = processing_manager.get_processing_session(session_id)
        if not session_info:
            raise HTTPException(status_code=404, detail="Processing session not found")
        
        return {
            "id": session_info.id,
            "name": session_info.name,
            "status": session_info.status,
            "objects": session_info.objects,
            "total_files": session_info.total_files,
            "lights": session_info.lights,
            "darks": session_info.darks,
            "flats": session_info.flats,
            "bias": session_info.bias,
            "folder_path": session_info.folder_path,
            "created_at": session_info.created_at.isoformat(),
            "notes": session_info.notes
        }
    except Exception as e:
        logger.error(f"Error fetching processing session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/processing-sessions")
async def create_processing_session(
    name: str = Body(...),
    file_ids: List[int] = Body(...),
    notes: Optional[str] = Body(None)
):
    """Create a new processing session."""
    try:
        session_info = processing_manager.create_processing_session(name, file_ids, notes)
        
        return {
            "id": session_info.id,
            "name": session_info.name,
            "status": session_info.status,
            "objects": session_info.objects,
            "total_files": session_info.total_files,
            "lights": session_info.lights,
            "darks": session_info.darks,
            "flats": session_info.flats,
            "bias": session_info.bias,
            "folder_path": session_info.folder_path,
            "created_at": session_info.created_at.isoformat(),
            "notes": session_info.notes
        }
    except Exception as e:
        logger.error(f"Error creating processing session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/processing-sessions/{session_id}/status")
async def update_processing_session_status(
    session_id: str,
    status: str = Body(...),
    notes: Optional[str] = Body(None)
):
    """Update processing session status."""
    try:
        valid_statuses = ['not_started', 'in_progress', 'complete']
        if status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
        
        success = processing_manager.update_session_status(session_id, status, notes)
        if not success:
            raise HTTPException(status_code=404, detail="Processing session not found")
        
        return {"message": f"Processing session {session_id} updated successfully"}
    except Exception as e:
        logger.error(f"Error updating processing session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/processing-sessions/{session_id}")
async def delete_processing_session(
    session_id: str,
    remove_files: bool = Query(True, description="Remove staged files")
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

@app.get("/api/processing-sessions/{session_id}/calibration-matches")
async def get_calibration_matches(session_id: str):
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

@app.post("/api/processing-sessions/{session_id}/add-files")
async def add_files_to_processing_session(
    session_id: str,
    file_ids: List[int] = Body(...)
):
    """Add files to an existing processing session."""
    try:
        success = processing_manager.add_files_to_session(session_id, file_ids)
        if not success:
            raise HTTPException(status_code=404, detail="Processing session not found")
        
        return {"message": f"Added {len(file_ids)} files to processing session {session_id}"}
    except ValueError as e:
        # User input validation errors (duplicates, missing files, etc)
        logger.warning(f"Validation error adding files to session {session_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Unexpected server errors
        logger.error(f"Error adding files to processing session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# EXISTING OPERATION ROUTES (unchanged)
# ============================================================================

_processing_tasks = set()

def _run_scan_sync(task_id: str):
    """Synchronous scan wrapper."""
    if task_id in _processing_tasks:
        return
    
    _processing_tasks.add(task_id)
    
    try:
        background_tasks_status[task_id]["status"] = "running"
        background_tasks_status[task_id]["message"] = "Scanning quarantine..."
        
        logger.info(f"Starting scan operation {task_id}")
        
        fits_processor = OptimizedFitsProcessor(
            config, cameras, telescopes, filter_mappings, db_service
        )
        
        df, session_data = fits_processor.scan_quarantine()
        
        # Process results
        added_count = 0
        duplicate_count = 0
        error_count = 0
        
        for row in df.iter_rows(named=True):
            try:
                success, is_duplicate = db_service.add_fits_file(row)
                if success:
                    if is_duplicate:
                        duplicate_count += 1
                    else:
                        added_count += 1
                else:
                    error_count += 1
            except Exception as e:
                error_count += 1
                logger.error(f"Error adding file to database: {e}")
        
        # Add sessions
        session_count = 0
        for session in session_data:
            try:
                db_service.add_session(session)
                session_count += 1
            except Exception as e:
                logger.error(f"Error adding session: {e}")
        
        background_tasks_status[task_id] = {
            "status": "completed",
            "message": f"Scan completed: {added_count} new files, {duplicate_count} duplicates",
            "progress": 100,
            "started_at": background_tasks_status[task_id]["started_at"],
            "completed_at": datetime.now(),
            "results": {
                "added": added_count,
                "duplicates": duplicate_count,
                "errors": error_count,
                "sessions": session_count
            }
        }
        
        logger.info(f"Scan operation {task_id} completed: {added_count} added, {duplicate_count} duplicates")
        
    except Exception as e:
        background_tasks_status[task_id] = {
            "status": "error",
            "message": f"Scan failed: {str(e)}",
            "completed_at": datetime.now()
        }
        logger.error(f"Background scan failed: {e}")

async def run_scan_operation(task_id: str):
    """Async wrapper."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, _run_scan_sync, task_id)


def _run_validation_sync(task_id: str):
    if task_id in _processing_tasks:
        return
    
    _processing_tasks.add(task_id)
    
    # Update from pending to running
    background_tasks_status[task_id]["status"] = "running"
    background_tasks_status[task_id]["message"] = "Running validation..."

    try:
        background_tasks_status[task_id] = {
            "status": "running",
            "message": "Running validation...",
            "progress": 0,
            "started_at": datetime.now()
        }
        
        def update_progress(progress, stats):
            background_tasks_status[task_id]["progress"] = progress
            background_tasks_status[task_id]["message"] = f"Validating: {stats['auto_migrate']} auto"
        
        validator = FitsValidator(db_service)
        stats = validator.validate_all_files(progress_callback=update_progress)
        
        background_tasks_status[task_id].update({
            "status": "completed",
            "message": f"Completed: {stats['auto_migrate']} auto-migrate",
            "progress": 100,
            "completed_at": datetime.now(),
            "results": stats
        })
    except Exception as e:
        background_tasks_status[task_id] = {
            "status": "error",
            "message": str(e),
            "completed_at": datetime.now()
        }

async def run_validation_operation(task_id: str):
    """Async wrapper that runs sync validation in executor."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, _run_validation_sync, task_id)


def _run_migration_sync(task_id: str):
    """Synchronous migration wrapper."""
    if task_id in _processing_tasks:
        return
    
    _processing_tasks.add(task_id)
    
    try:
        background_tasks_status[task_id]["status"] = "running"
        background_tasks_status[task_id]["message"] = "Migrating files..."
        
        logger.info(f"Starting migration operation {task_id}")
        
        # Use FileOrganizer to migrate files
        file_organizer = FileOrganizer(config, db_service)
        stats = file_organizer.migrate_files(limit=None, auto_cleanup=True)
        
        background_tasks_status[task_id] = {
            "status": "completed",
            "message": f"Migration completed: {stats['moved']} files moved",
            "progress": 100,
            "started_at": background_tasks_status[task_id]["started_at"],
            "completed_at": datetime.now(),
            "results": {
                "moved": stats['moved'],
                "processed": stats['processed'],
                "errors": stats['errors'],
                "skipped": stats['skipped'],
                "duplicates_moved": stats['duplicates_moved'],
                "bad_files_moved": stats['bad_files_moved'],
                "left_for_review": stats['left_for_review']
            }
        }
        
        logger.info(f"Migration operation {task_id} completed: {stats['moved']} files moved")
        
    except Exception as e:
        background_tasks_status[task_id] = {
            "status": "error",
            "message": f"Migration failed: {str(e)}",
            "completed_at": datetime.now()
        }
        logger.error(f"Background migration failed: {e}")
    finally:
        _processing_tasks.discard(task_id)


async def run_migration_operation(task_id: str):
    """Async wrapper that runs sync migration in executor."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, _run_migration_sync, task_id)


@app.post("/api/operations/scan")
async def start_scan(background_tasks: BackgroundTasks):
    task_id = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Initialize status first
    background_tasks_status[task_id] = {
        "status": "pending",
        "message": "Scan queued...",
        "progress": 0,
        "started_at": datetime.now()
    }
    
    background_tasks.add_task(run_scan_operation, task_id)
    return {"task_id": task_id, "message": "Scan started"}


@app.post("/api/operations/validate")
async def start_validation(background_tasks: BackgroundTasks):
    task_id = f"validate_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Initialize status BEFORE background task starts
    background_tasks_status[task_id] = {
        "status": "pending",
        "message": "Validation queued...",
        "progress": 0,
        "started_at": datetime.now()
    }
    
    background_tasks.add_task(run_validation_operation, task_id)
    return {"task_id": task_id, "message": "Validation started"}


@app.post("/api/operations/migrate")
async def start_migration(background_tasks: BackgroundTasks):
    """Start a file migration operation."""
    task_id = f"migrate_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Initialize status BEFORE background task starts
    background_tasks_status[task_id] = {
        "status": "pending",
        "message": "Migration queued...",
        "progress": 0,
        "started_at": datetime.now()
    }
    
    background_tasks.add_task(run_migration_operation, task_id)
    return {"task_id": task_id, "message": "Migration started"}


@app.get("/api/operations/status/{task_id}")
async def get_operation_status(task_id: str):
    """Get status of a background operation."""
    if task_id not in background_tasks_status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Include task_id in the response
    status_data = background_tasks_status[task_id].copy()
    status_data["task_id"] = task_id
    return status_data

# ============================================================================
# WEB INTERFACE ROUTES (unchanged)
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Main dashboard page."""
    dashboard_file = Path("static/dashboard.html")
    if not dashboard_file.exists():
        raise HTTPException(status_code=404, detail="Dashboard file not found")
    return FileResponse("static/dashboard.html")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Test database connection
        session = db_manager.get_session()
        try:
            total_files = session.query(FitsFile).count()
        finally:
            session.close()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "total_files": total_files
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)