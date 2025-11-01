"""
File browsing and filtering routes.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc

from models import FitsFile
from web.dependencies import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/filter-options")
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


@router.get("/files")
async def get_files(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=1000),
    frame_types: Optional[str] = Query(None, description="Comma-separated frame types"),
    cameras: Optional[str] = Query(None, description="Comma-separated cameras"),
    telescopes: Optional[str] = Query(None, description="Comma-separated telescopes"),
    objects: Optional[str] = Query(None, description="Comma-separated objects"),
    filters: Optional[str] = Query(None, description="Comma-separated filters"),
    filename: Optional[str] = None,
    imaging_session_id: Optional[str] = None,
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
        # Base query
        query = session.query(FitsFile)
        
        # Apply filters
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
        
        if filename:
            query = query.filter(FitsFile.file.like(f'%{filename}%'))

        if imaging_session_id:
            query = query.filter(FitsFile.imaging_session_id == imaging_session_id)
        
        if exposure_min is not None:
            query = query.filter(FitsFile.exposure >= exposure_min)
        
        if exposure_max is not None:
            query = query.filter(FitsFile.exposure <= exposure_max)
        
        if date_start:
            query = query.filter(FitsFile.obs_date >= date_start)
        
        if date_end:
            query = query.filter(FitsFile.obs_date <= date_end)
        
        # Get total count before pagination
        total = query.count()
        
        # Apply sorting
        sort_column = getattr(FitsFile, sort_by, FitsFile.obs_date)
        if sort_order == 'asc':
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))
        
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
                    "obs_date": f.obs_date,
                    "frame_type": f.frame_type,
                    "filter": f.filter,
                    "exposure": f.exposure,
                    "camera": f.camera,
                    "telescope": f.telescope,
                    "obs_timestamp": f.obs_timestamp.isoformat() if f.obs_timestamp else None,
                    "ra": f.ra,
                    "dec": f.dec,
                    "imaging_session_id": f.imaging_session_id,
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


@router.get("/files/ids")
async def get_file_ids(
    frame_types: Optional[str] = Query(None),
    cameras: Optional[str] = Query(None),
    telescopes: Optional[str] = Query(None),
    objects: Optional[str] = Query(None),
    filters: Optional[str] = Query(None),
    filename: Optional[str] = None,
    imaging_session_id: Optional[str] = Query(None),
    exposure_min: Optional[float] = None,
    exposure_max: Optional[float] = None,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    session: Session = Depends(get_db_session)
):
    """Get file IDs matching filters (for bulk selection)."""
    try:
        # Base query - only select IDs
        query = session.query(FitsFile.id)
        
        # Apply same filters as get_files
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
        
        if filename:
            query = query.filter(FitsFile.file.like(f'%{filename}%'))

        if imaging_session_id:
            query = query.filter(FitsFile.imaging_session_id == imaging_session_id)
        
        if exposure_min is not None:
            query = query.filter(FitsFile.exposure >= exposure_min)
        
        if exposure_max is not None:
            query = query.filter(FitsFile.exposure <= exposure_max)
        
        if date_start:
            query = query.filter(FitsFile.obs_date >= date_start)
        
        if date_end:
            query = query.filter(FitsFile.obs_date <= date_end)
        
        # Get all IDs
        file_ids = [row[0] for row in query.all()]
        
        return {
            "file_ids": file_ids,
            "count": len(file_ids)
        }
    except Exception as e:
        logger.error(f"Error fetching file IDs: {e}")
        raise HTTPException(status_code=500, detail=str(e))