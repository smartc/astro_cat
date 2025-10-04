"""
Equipment management API routes - Using Database.
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models import Camera, Telescope, FilterMapping
from web.dependencies import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/equipment")


# Pydantic models for request/response
class CameraModel(BaseModel):
    camera: str
    brand: str = ""
    type: str = "CMOS"
    x: int
    y: int
    pixel: float
    bin: int = 1
    rgb: bool = False
    comments: str = ""


class TelescopeModel(BaseModel):
    scope: str
    make: str = ""
    type: str = ""
    focal: int
    aperture: int
    subtype: str = ""
    comments: str = ""


class FilterMappingModel(BaseModel):
    raw_name: str
    proper_name: str


# ============================================================================
# GET ALL EQUIPMENT
# ============================================================================

@router.get("/all")
async def get_all_equipment(db: Session = Depends(get_db_session)):
    """Get all equipment data from database."""
    try:
        cameras = db.query(Camera).filter_by(active=True).all()
        telescopes = db.query(Telescope).filter_by(active=True).all()
        filters = db.query(FilterMapping).all()
        
        # Convert to dict format expected by frontend
        cameras_data = [
            {
                "camera": cam.name,
                "brand": getattr(cam, 'notes', '') or '',
                "type": "CMOS",  # Default type
                "x": cam.x_pixels,
                "y": cam.y_pixels,
                "pixel": cam.pixel_size,
                "bin": 1,
                "rgb": False,
                "comments": cam.notes or ''
            }
            for cam in cameras
        ]
        
        telescopes_data = [
            {
                "scope": tel.name,
                "make": '',
                "type": tel.telescope_type or '',
                "focal": int(tel.focal_length),
                "aperture": int(tel.aperture) if tel.aperture else 0,
                "subtype": '',
                "comments": tel.notes or ''
            }
            for tel in telescopes
        ]
        
        filters_data = [
            {
                "raw_name": f.raw_name,
                "proper_name": f.standard_name
            }
            for f in filters
        ]
        
        return {
            "cameras": cameras_data,
            "telescopes": telescopes_data,
            "filters": filters_data
        }
    except Exception as e:
        logger.error(f"Error loading equipment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CAMERA ROUTES
# ============================================================================

@router.get("/cameras")
async def get_cameras(db: Session = Depends(get_db_session)):
    """Get all cameras from database."""
    cameras = db.query(Camera).filter_by(active=True).all()
    return [
        {
            "camera": cam.name,
            "brand": '',
            "type": "CMOS",
            "x": cam.x_pixels,
            "y": cam.y_pixels,
            "pixel": cam.pixel_size,
            "bin": 1,
            "rgb": False,
            "comments": cam.notes or ''
        }
        for cam in cameras
    ]


@router.post("/cameras")
async def add_camera(camera: CameraModel, db: Session = Depends(get_db_session)):
    """Add a new camera to database."""
    # Check if camera already exists
    existing = db.query(Camera).filter_by(name=camera.camera).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Camera '{camera.camera}' already exists")
    
    new_camera = Camera(
        name=camera.camera,
        x_pixels=camera.x,
        y_pixels=camera.y,
        pixel_size=camera.pixel,
        notes=camera.comments,
        active=True
    )
    
    db.add(new_camera)
    db.commit()
    db.refresh(new_camera)
    
    return {"message": "Camera added successfully", "camera": camera.dict()}


@router.put("/cameras")
async def update_camera(camera: CameraModel, db: Session = Depends(get_db_session)):
    """Update an existing camera."""
    existing = db.query(Camera).filter_by(name=camera.camera).first()
    if not existing:
        raise HTTPException(status_code=404, detail=f"Camera '{camera.camera}' not found")
    
    existing.x_pixels = camera.x
    existing.y_pixels = camera.y
    existing.pixel_size = camera.pixel
    existing.notes = camera.comments
    
    db.commit()
    
    return {"message": "Camera updated successfully", "camera": camera.dict()}


@router.delete("/cameras/{camera_name}")
async def delete_camera(camera_name: str, db: Session = Depends(get_db_session)):
    """Delete a camera (soft delete by setting active=False)."""
    camera = db.query(Camera).filter_by(name=camera_name).first()
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_name}' not found")
    
    camera.active = False
    db.commit()
    
    return {"message": f"Camera '{camera_name}' deleted successfully"}


# ============================================================================
# TELESCOPE ROUTES
# ============================================================================

@router.get("/telescopes")
async def get_telescopes(db: Session = Depends(get_db_session)):
    """Get all telescopes from database."""
    telescopes = db.query(Telescope).filter_by(active=True).all()
    return [
        {
            "scope": tel.name,
            "make": '',
            "type": tel.telescope_type or '',
            "focal": int(tel.focal_length),
            "aperture": int(tel.aperture) if tel.aperture else 0,
            "subtype": '',
            "comments": tel.notes or ''
        }
        for tel in telescopes
    ]


@router.post("/telescopes")
async def add_telescope(telescope: TelescopeModel, db: Session = Depends(get_db_session)):
    """Add a new telescope to database."""
    existing = db.query(Telescope).filter_by(name=telescope.scope).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Telescope '{telescope.scope}' already exists")
    
    new_telescope = Telescope(
        name=telescope.scope,
        focal_length=telescope.focal,
        aperture=telescope.aperture,
        telescope_type=telescope.type,
        notes=telescope.comments,
        active=True
    )
    
    db.add(new_telescope)
    db.commit()
    db.refresh(new_telescope)
    
    return {"message": "Telescope added successfully", "telescope": telescope.dict()}


@router.put("/telescopes")
async def update_telescope(telescope: TelescopeModel, db: Session = Depends(get_db_session)):
    """Update an existing telescope."""
    existing = db.query(Telescope).filter_by(name=telescope.scope).first()
    if not existing:
        raise HTTPException(status_code=404, detail=f"Telescope '{telescope.scope}' not found")
    
    existing.focal_length = telescope.focal
    existing.aperture = telescope.aperture
    existing.telescope_type = telescope.type
    existing.notes = telescope.comments
    
    db.commit()
    
    return {"message": "Telescope updated successfully", "telescope": telescope.dict()}


@router.delete("/telescopes/{telescope_name}")
async def delete_telescope(telescope_name: str, db: Session = Depends(get_db_session)):
    """Delete a telescope (soft delete)."""
    telescope = db.query(Telescope).filter_by(name=telescope_name).first()
    if not telescope:
        raise HTTPException(status_code=404, detail=f"Telescope '{telescope_name}' not found")
    
    telescope.active = False
    db.commit()
    
    return {"message": f"Telescope '{telescope_name}' deleted successfully"}


# ============================================================================
# FILTER ROUTES
# ============================================================================

@router.get("/filters")
async def get_filters(db: Session = Depends(get_db_session)):
    """Get all filter mappings from database."""
    filters = db.query(FilterMapping).all()
    return [
        {
            "raw_name": f.raw_name,
            "proper_name": f.standard_name
        }
        for f in filters
    ]


@router.post("/filters")
async def add_filter(filter_mapping: FilterMappingModel, db: Session = Depends(get_db_session)):
    """Add a new filter mapping to database."""
    existing = db.query(FilterMapping).filter_by(raw_name=filter_mapping.raw_name).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Filter mapping for '{filter_mapping.raw_name}' already exists"
        )
    
    new_filter = FilterMapping(
        raw_name=filter_mapping.raw_name,
        standard_name=filter_mapping.proper_name
    )
    
    db.add(new_filter)
    db.commit()
    db.refresh(new_filter)
    
    return {"message": "Filter mapping added successfully", "filter": filter_mapping.dict()}


@router.put("/filters")
async def update_filter(filter_mapping: FilterMappingModel, db: Session = Depends(get_db_session)):
    """Update an existing filter mapping."""
    existing = db.query(FilterMapping).filter_by(raw_name=filter_mapping.raw_name).first()
    if not existing:
        raise HTTPException(
            status_code=404,
            detail=f"Filter mapping '{filter_mapping.raw_name}' not found"
        )
    
    existing.standard_name = filter_mapping.proper_name
    db.commit()
    
    return {"message": "Filter mapping updated successfully", "filter": filter_mapping.dict()}


@router.delete("/filters/{raw_name}")
async def delete_filter(raw_name: str, db: Session = Depends(get_db_session)):
    """Delete a filter mapping."""
    filter_mapping = db.query(FilterMapping).filter_by(raw_name=raw_name).first()
    if not filter_mapping:
        raise HTTPException(status_code=404, detail=f"Filter mapping '{raw_name}' not found")
    
    db.delete(filter_mapping)
    db.commit()
    
    return {"message": f"Filter mapping '{raw_name}' deleted successfully"}