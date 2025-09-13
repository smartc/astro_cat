"""
FITS Cataloger Web Interface - Column Header Filters
FastAPI application for browsing database and managing operations
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import traceback

from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, asc
import uvicorn

# Import your existing modules
from models import DatabaseManager, DatabaseService, FitsFile, Session as SessionModel
from config import load_config
from validation import FitsValidator
from file_organizer import FileOrganizer
from fits_processor import OptimizedFitsProcessor

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

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global configuration and services
config = None
db_manager = None
db_service = None
cameras = []
telescopes = []
filter_mappings = {}

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    global config, db_manager, db_service, cameras, telescopes, filter_mappings
    
    try:
        # Load configuration
        config, cameras, telescopes, filter_mappings = load_config()
        
        # Initialize database
        db_manager = DatabaseManager(config.database.connection_string)
        db_service = DatabaseService(db_manager)
        
        logger.info("FITS Cataloger web interface started successfully")
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
# API ROUTES
# ============================================================================

@app.get("/api/filter-options")
async def get_filter_options(session: Session = Depends(get_db_session)):
    """Get unique values for filter dropdowns."""
    try:
        # Get unique values for each filterable column
        frame_types = [row[0] for row in session.query(FitsFile.frame_type).distinct().all() if row[0]]
        cameras = [row[0] for row in session.query(FitsFile.camera).distinct().all() if row[0]]
        telescopes = [row[0] for row in session.query(FitsFile.telescope).distinct().all() if row[0]]
        objects = [row[0] for row in session.query(FitsFile.object).distinct().all() if row[0] and row[0] != 'CALIBRATION']
        filters = [row[0] for row in session.query(FitsFile.filter).distinct().all() if row[0]]
        dates = [row[0] for row in session.query(FitsFile.obs_date).distinct().all() if row[0]]
        
        return {
            "frame_types": sorted(frame_types),
            "cameras": sorted(cameras),
            "telescopes": sorted(telescopes),
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
    dates: Optional[str] = Query(None, description="Comma-separated dates"),
    filename: Optional[str] = None,
    session_id: Optional[str] = None,
    exposure_min: Optional[float] = None,
    exposure_max: Optional[float] = None,
    validation_score_min: Optional[float] = None,
    validation_score_max: Optional[float] = None,
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
        
        if dates:
            date_list = [d.strip() for d in dates.split(',') if d.strip()]
            if date_list:
                query = query.filter(FitsFile.obs_date.in_(date_list))
        
        # Apply search filters
        if filename:
            query = query.filter(FitsFile.file.ilike(f"%{filename}%"))
        if session_id:
            query = query.filter(FitsFile.session_id.ilike(f"%{session_id}%"))
        if exposure_min is not None:
            query = query.filter(FitsFile.exposure >= exposure_min)
        if exposure_max is not None:
            query = query.filter(FitsFile.exposure <= exposure_max)
        if validation_score_min is not None:
            query = query.filter(FitsFile.validation_score >= validation_score_min)
        if validation_score_max is not None:
            query = query.filter(FitsFile.validation_score <= validation_score_max)
        
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
                    "validation_score": f.validation_score,
                    "migration_ready": f.migration_ready,
                    "session_id": f.session_id,
                    "bad": f.bad,
                    "file_not_found": f.file_not_found
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
        stats = db_service.get_database_stats()
        
        # Add validation statistics
        total_files = session.query(FitsFile).count()
        auto_migrate = session.query(FitsFile).filter(FitsFile.validation_score >= 95.0).count()
        needs_review = session.query(FitsFile).filter(
            FitsFile.validation_score >= 80.0,
            FitsFile.validation_score < 95.0
        ).count()
        manual_only = session.query(FitsFile).filter(FitsFile.validation_score < 80.0).count()
        no_score = session.query(FitsFile).filter(FitsFile.validation_score.is_(None)).count()
        
        # Add recent files count
        from datetime import datetime, timedelta
        recent_cutoff = datetime.now() - timedelta(days=7)
        recent_files = session.query(FitsFile).filter(
            FitsFile.created_at >= recent_cutoff
        ).count()
        
        stats.update({
            "validation": {
                "total_files": total_files,
                "auto_migrate": auto_migrate,
                "needs_review": needs_review,
                "manual_only": manual_only,
                "no_score": no_score
            },
            "recent_files": recent_files
        })
        
        return stats
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions")
async def get_sessions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_db_session)
):
    """Get imaging sessions with pagination."""
    try:
        query = session.query(SessionModel).order_by(desc(SessionModel.session_date))
        
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
        logger.error(f"Error fetching sessions: {e}")
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
# OPERATION ROUTES (abbreviated for space)
# ============================================================================

async def run_scan_operation(task_id: str):
    # Implementation same as before
    pass

@app.post("/api/operations/scan")
async def start_scan(background_tasks: BackgroundTasks):
    """Start a quarantine scan operation."""
    task_id = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    background_tasks.add_task(run_scan_operation, task_id)
    return {"task_id": task_id, "message": "Scan started"}

# ============================================================================
# WEB INTERFACE ROUTES
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Main dashboard page."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>FITS Cataloger</title>
        <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
        <script src="https://unpkg.com/axios/dist/axios.min.js"></script>
        <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
        <style>
            .filter-dropdown {
                position: absolute;
                top: 100%;
                left: 0;
                right: 0;
                z-index: 50;
                background: white;
                border: 1px solid #d1d5db;
                border-radius: 0.375rem;
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
                max-height: 200px;
                overflow-y: auto;
            }
            .filter-button {
                width: 100%;
                text-align: left;
                padding: 0.25rem 0.5rem;
                font-size: 0.75rem;
                border: 1px solid #d1d5db;
                border-radius: 0.25rem;
                background: white;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }
            .filter-button:hover {
                background-color: #f9fafb;
            }
            .header-cell {
                position: relative;
                padding: 0.5rem;
                vertical-align: top;
            }
            .sort-header {
                cursor: pointer;
                padding: 0.25rem 0;
                border-bottom: 1px solid #e5e7eb;
                margin-bottom: 0.25rem;
            }
            .sort-header:hover {
                background-color: #f3f4f6;
            }
        </style>
    </head>
    <body class="bg-gray-100">
        <div id="app">
            <!-- Header -->
            <header class="bg-blue-600 text-white p-4 shadow-lg">
                <div class="container mx-auto flex justify-between items-center">
                    <h1 class="text-2xl font-bold">FITS Cataloger</h1>
                    <div class="flex space-x-4">
                        <button @click="activeTab = 'dashboard'" 
                                :class="activeTab === 'dashboard' ? 'bg-blue-700' : 'bg-blue-500'"
                                class="px-4 py-2 rounded hover:bg-blue-700 transition">
                            Dashboard
                        </button>
                        <button @click="activeTab = 'files'" 
                                :class="activeTab === 'files' ? 'bg-blue-700' : 'bg-blue-500'"
                                class="px-4 py-2 rounded hover:bg-blue-700 transition">
                            Files
                        </button>
                        <button @click="activeTab = 'sessions'" 
                                :class="activeTab === 'sessions' ? 'bg-blue-700' : 'bg-blue-500'"
                                class="px-4 py-2 rounded hover:bg-blue-700 transition">
                            Sessions
                        </button>
                        <button @click="activeTab = 'operations'" 
                                :class="activeTab === 'operations' ? 'bg-blue-700' : 'bg-blue-500'"
                                class="px-4 py-2 rounded hover:bg-blue-700 transition">
                            Operations
                        </button>
                    </div>
                </div>
            </header>

            <!-- Main Content -->
            <main class="container mx-auto p-6">
                <!-- Dashboard Tab -->
                <div v-show="activeTab === 'dashboard'" class="space-y-6">
                    <!-- Stats Cards -->
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                        <div class="bg-white p-6 rounded-lg shadow">
                            <h3 class="text-lg font-semibold text-gray-700 mb-2">Total Files</h3>
                            <p class="text-3xl font-bold text-blue-600">{{ stats.total_files || 0 }}</p>
                        </div>
                        <div class="bg-white p-6 rounded-lg shadow">
                            <h3 class="text-lg font-semibold text-gray-700 mb-2">Auto-Migrate Ready</h3>
                            <p class="text-3xl font-bold text-green-600">{{ stats.validation?.auto_migrate || 0 }}</p>
                            <p class="text-sm text-gray-500">≥95 points</p>
                        </div>
                        <div class="bg-white p-6 rounded-lg shadow">
                            <h3 class="text-lg font-semibold text-gray-700 mb-2">Needs Review</h3>
                            <p class="text-3xl font-bold text-yellow-600">{{ stats.validation?.needs_review || 0 }}</p>
                            <p class="text-sm text-gray-500">80-94 points</p>
                        </div>
                        <div class="bg-white p-6 rounded-lg shadow">
                            <h3 class="text-lg font-semibold text-gray-700 mb-2">Manual Only</h3>
                            <p class="text-3xl font-bold text-red-600">{{ stats.validation?.manual_only || 0 }}</p>
                            <p class="text-sm text-gray-500">&lt;80 points</p>
                        </div>
                    </div>
                </div>

                <!-- Files Tab -->
                <div v-show="activeTab === 'files'" class="space-y-6">
                    <!-- Controls -->
                    <div class="bg-white rounded-lg shadow p-4">
                        <div class="flex justify-between items-center mb-4">
                            <h2 class="text-xl font-bold">File Browser</h2>
                            <div class="flex space-x-4 items-center">
                                <div class="flex items-center space-x-2 text-sm text-gray-600">
                                    <span>Sort:</span>
                                    <select v-model="fileSorting.sort_by" @change="loadFiles" class="border border-gray-300 rounded px-2 py-1">
                                        <option value="obs_date">Date</option>
                                        <option value="file">Filename</option>
                                        <option value="object">Object</option>
                                        <option value="frame_type">Frame Type</option>
                                        <option value="camera">Camera</option>
                                        <option value="telescope">Telescope</option>
                                        <option value="filter">Filter</option>
                                        <option value="exposure">Exposure</option>
                                        <option value="validation_score">Score</option>
                                    </select>
                                    <select v-model="fileSorting.sort_order" @change="loadFiles" class="border border-gray-300 rounded px-2 py-1">
                                        <option value="desc">↓</option>
                                        <option value="asc">↑</option>
                                    </select>
                                </div>
                                <button @click="resetAllFilters" class="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded transition">
                                    Reset Filters
                                </button>
                                <button @click="loadFiles" class="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded transition">
                                    Refresh
                                </button>
                            </div>
                        </div>
                        
                        <!-- Active Filters Summary -->
                        <div v-if="hasActiveFilters" class="text-sm text-gray-600 mb-2">
                            <span class="font-medium">Active filters:</span>
                            <span v-for="filter in getActiveFilterSummary()" :key="filter" 
                                  class="ml-2 bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs">
                                {{ filter }}
                            </span>
                        </div>
                    </div>

                    <!-- Files Table -->
                    <div class="bg-white rounded-lg shadow overflow-hidden">
                        <div class="overflow-x-auto">
                            <table class="w-full">
                                <thead class="bg-gray-50">
                                    <tr>
                                        <!-- File Column -->
                                        <th class="header-cell border-r border-gray-200">
                                            <div @click="sortBy('file')" class="sort-header">
                                                <div class="flex items-center justify-between text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    <span>File</span>
                                                    <span v-if="fileSorting.sort_by === 'file'">
                                                        {{ fileSorting.sort_order === 'asc' ? '↑' : '↓' }}
                                                    </span>
                                                </div>
                                            </div>
                                            <input v-model="searchFilters.filename" 
                                                   placeholder="Search filename..." 
                                                   class="w-full text-xs border border-gray-300 rounded px-2 py-1">
                                        </th>

                                        <!-- Object Column -->
                                        <th class="header-cell border-r border-gray-200">
                                            <div @click="sortBy('object')" class="sort-header">
                                                <div class="flex items-center justify-between text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    <span>Object</span>
                                                    <span v-if="fileSorting.sort_by === 'object'">
                                                        {{ fileSorting.sort_order === 'asc' ? '↑' : '↓' }}
                                                    </span>
                                                </div>
                                            </div>
                                            <div class="relative">
                                                <button @click="toggleFilter('objects')" class="filter-button">
                                                    <span>{{ getFilterText('objects') }}</span>
                                                    <span class="text-gray-400">▼</span>
                                                </button>
                                                <div v-show="activeFilter === 'objects'" class="filter-dropdown">
                                                    <div class="p-2">
                                                        <label v-for="option in filterOptions.objects" :key="option" 
                                                               class="flex items-center text-xs hover:bg-gray-50 px-2 py-1 cursor-pointer">
                                                            <input type="checkbox" 
                                                                   :checked="fileFilters.objects.includes(option)"
                                                                   @change="toggleFilterOption('objects', option)"
                                                                   class="mr-2">
                                                            <span class="truncate">{{ option }}</span>
                                                        </label>
                                                    </div>
                                                </div>
                                            </div>
                                        </th>

                                        <!-- Frame Type Column -->
                                        <th class="header-cell border-r border-gray-200">
                                            <div @click="sortBy('frame_type')" class="sort-header">
                                                <div class="flex items-center justify-between text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    <span>Type</span>
                                                    <span v-if="fileSorting.sort_by === 'frame_type'">
                                                        {{ fileSorting.sort_order === 'asc' ? '↑' : '↓' }}
                                                    </span>
                                                </div>
                                            </div>
                                            <div class="relative">
                                                <button @click="toggleFilter('frame_types')" class="filter-button">
                                                    <span>{{ getFilterText('frame_types') }}</span>
                                                    <span class="text-gray-400">▼</span>
                                                </button>
                                                <div v-show="activeFilter === 'frame_types'" class="filter-dropdown">
                                                    <div class="p-2">
                                                        <label v-for="option in filterOptions.frame_types" :key="option" 
                                                               class="flex items-center text-xs hover:bg-gray-50 px-2 py-1 cursor-pointer">
                                                            <input type="checkbox" 
                                                                   :checked="fileFilters.frame_types.includes(option)"
                                                                   @change="toggleFilterOption('frame_types', option)"
                                                                   class="mr-2">
                                                            <span>{{ option }}</span>
                                                        </label>
                                                    </div>
                                                </div>
                                            </div>
                                        </th>

                                        <!-- Camera Column -->
                                        <th class="header-cell border-r border-gray-200">
                                            <div @click="sortBy('camera')" class="sort-header">
                                                <div class="flex items-center justify-between text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    <span>Camera</span>
                                                    <span v-if="fileSorting.sort_by === 'camera'">
                                                        {{ fileSorting.sort_order === 'asc' ? '↑' : '↓' }}
                                                    </span>
                                                </div>
                                            </div>
                                            <div class="relative">
                                                <button @click="toggleFilter('cameras')" class="filter-button">
                                                    <span>{{ getFilterText('cameras') }}</span>
                                                    <span class="text-gray-400">▼</span>
                                                </button>
                                                <div v-show="activeFilter === 'cameras'" class="filter-dropdown">
                                                    <div class="p-2">
                                                        <label v-for="option in filterOptions.cameras" :key="option" 
                                                               class="flex items-center text-xs hover:bg-gray-50 px-2 py-1 cursor-pointer">
                                                            <input type="checkbox" 
                                                                   :checked="fileFilters.cameras.includes(option)"
                                                                   @change="toggleFilterOption('cameras', option)"
                                                                   class="mr-2">
                                                            <span>{{ option }}</span>
                                                        </label>
                                                    </div>
                                                </div>
                                            </div>
                                        </th>

                                        <!-- Telescope Column -->
                                        <th class="header-cell border-r border-gray-200">
                                            <div @click="sortBy('telescope')" class="sort-header">
                                                <div class="flex items-center justify-between text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    <span>Telescope</span>
                                                    <span v-if="fileSorting.sort_by === 'telescope'">
                                                        {{ fileSorting.sort_order === 'asc' ? '↑' : '↓' }}
                                                    </span>
                                                </div>
                                            </div>
                                            <div class="relative">
                                                <button @click="toggleFilter('telescopes')" class="filter-button">
                                                    <span>{{ getFilterText('telescopes') }}</span>
                                                    <span class="text-gray-400">▼</span>
                                                </button>
                                                <div v-show="activeFilter === 'telescopes'" class="filter-dropdown">
                                                    <div class="p-2">
                                                        <label v-for="option in filterOptions.telescopes" :key="option" 
                                                               class="flex items-center text-xs hover:bg-gray-50 px-2 py-1 cursor-pointer">
                                                            <input type="checkbox" 
                                                                   :checked="fileFilters.telescopes.includes(option)"
                                                                   @change="toggleFilterOption('telescopes', option)"
                                                                   class="mr-2">
                                                            <span>{{ option }}</span>
                                                        </label>
                                                    </div>
                                                </div>
                                            </div>
                                        </th>

                                        <!-- Filter Column -->
                                        <th class="header-cell border-r border-gray-200">
                                            <div @click="sortBy('filter')" class="sort-header">
                                                <div class="flex items-center justify-between text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    <span>Filter</span>
                                                    <span v-if="fileSorting.sort_by === 'filter'">
                                                        {{ fileSorting.sort_order === 'asc' ? '↑' : '↓' }}
                                                    </span>
                                                </div>
                                            </div>
                                            <div class="relative">
                                                <button @click="toggleFilter('filters')" class="filter-button">
                                                    <span>{{ getFilterText('filters') }}</span>
                                                    <span class="text-gray-400">▼</span>
                                                </button>
                                                <div v-show="activeFilter === 'filters'" class="filter-dropdown">
                                                    <div class="p-2">
                                                        <label v-for="option in filterOptions.filters" :key="option" 
                                                               class="flex items-center text-xs hover:bg-gray-50 px-2 py-1 cursor-pointer">
                                                            <input type="checkbox" 
                                                                   :checked="fileFilters.filters.includes(option)"
                                                                   @change="toggleFilterOption('filters', option)"
                                                                   class="mr-2">
                                                            <span>{{ option }}</span>
                                                        </label>
                                                    </div>
                                                </div>
                                            </div>
                                        </th>

                                        <!-- Exposure Column -->
                                        <th class="header-cell border-r border-gray-200">
                                            <div @click="sortBy('exposure')" class="sort-header">
                                                <div class="flex items-center justify-between text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    <span>Exposure</span>
                                                    <span v-if="fileSorting.sort_by === 'exposure'">
                                                        {{ fileSorting.sort_order === 'asc' ? '↑' : '↓' }}
                                                    </span>
                                                </div>
                                            </div>
                                            <div class="flex space-x-1">
                                                <input v-model="searchFilters.exposure_min" 
                                                       placeholder="Min" 
                                                       type="number" 
                                                       class="w-full text-xs border border-gray-300 rounded px-1 py-1">
                                                <input v-model="searchFilters.exposure_max" 
                                                       placeholder="Max" 
                                                       type="number" 
                                                       class="w-full text-xs border border-gray-300 rounded px-1 py-1">
                                            </div>
                                        </th>

                                        <!-- Date Column -->
                                        <th class="header-cell border-r border-gray-200">
                                            <div @click="sortBy('obs_date')" class="sort-header">
                                                <div class="flex items-center justify-between text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    <span>Date</span>
                                                    <span v-if="fileSorting.sort_by === 'obs_date'">
                                                        {{ fileSorting.sort_order === 'asc' ? '↑' : '↓' }}
                                                    </span>
                                                </div>
                                            </div>
                                            <div class="relative">
                                                <button @click="toggleFilter('dates')" class="filter-button">
                                                    <span>{{ getFilterText('dates') }}</span>
                                                    <span class="text-gray-400">▼</span>
                                                </button>
                                                <div v-show="activeFilter === 'dates'" class="filter-dropdown">
                                                    <div class="p-2">
                                                        <label v-for="option in filterOptions.dates" :key="option" 
                                                               class="flex items-center text-xs hover:bg-gray-50 px-2 py-1 cursor-pointer">
                                                            <input type="checkbox" 
                                                                   :checked="fileFilters.dates.includes(option)"
                                                                   @change="toggleFilterOption('dates', option)"
                                                                   class="mr-2">
                                                            <span>{{ option }}</span>
                                                        </label>
                                                    </div>
                                                </div>
                                            </div>
                                        </th>

                                        <!-- Session ID Column -->
                                        <th class="header-cell border-r border-gray-200">
                                            <div @click="sortBy('session_id')" class="sort-header">
                                                <div class="flex items-center justify-between text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    <span>Session</span>
                                                    <span v-if="fileSorting.sort_by === 'session_id'">
                                                        {{ fileSorting.sort_order === 'asc' ? '↑' : '↓' }}
                                                    </span>
                                                </div>
                                            </div>
                                            <input v-model="searchFilters.session_id" 
                                                   placeholder="Session..." 
                                                   class="w-full text-xs border border-gray-300 rounded px-2 py-1">
                                        </th>

                                        <!-- Score Column -->
                                        <th class="header-cell">
                                            <div @click="sortBy('validation_score')" class="sort-header">
                                                <div class="flex items-center justify-between text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    <span>Score</span>
                                                    <span v-if="fileSorting.sort_by === 'validation_score'">
                                                        {{ fileSorting.sort_order === 'asc' ? '↑' : '↓' }}
                                                    </span>
                                                </div>
                                            </div>
                                            <select v-model="searchFilters.score_range" class="w-full text-xs border border-gray-300 rounded px-1 py-1">
                                                <option value="">All</option>
                                                <option value="auto">≥95</option>
                                                <option value="review">80-94</option>
                                                <option value="manual">&lt;80</option>
                                                <option value="none">None</option>
                                            </select>
                                        </th>
                                    </tr>
                                </thead>
                                <tbody class="bg-white divide-y divide-gray-200">
                                    <tr v-for="file in files" :key="file.id" class="hover:bg-gray-50">
                                        <td class="px-4 py-4 whitespace-nowrap text-sm font-mono text-gray-900">{{ file.file }}</td>
                                        <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-900">{{ file.object || 'N/A' }}</td>
                                        <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                                            <span :class="getFrameTypeClass(file.frame_type)" class="px-2 py-1 text-xs rounded-full">
                                                {{ file.frame_type }}
                                            </span>
                                        </td>
                                        <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-900">{{ file.camera || 'Unknown' }}</td>
                                        <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-900">{{ file.telescope || 'Unknown' }}</td>
                                        <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-900">{{ file.filter || 'None' }}</td>
                                        <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-900">{{ file.exposure ? file.exposure + 's' : 'N/A' }}</td>
                                        <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-900">{{ file.obs_date || 'N/A' }}</td>
                                        <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                                            <span @click="navigateToSession(file.session_id)" 
                                                  class="text-blue-600 hover:text-blue-800 cursor-pointer underline font-mono text-xs">
                                                {{ file.session_id || 'N/A' }}
                                            </span>
                                        </td>
                                        <td class="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                                            <span :class="getScoreClass(file.validation_score)" class="font-semibold">
                                                {{ file.validation_score?.toFixed(1) || 'N/A' }}
                                            </span>
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                        
                        <!-- Pagination -->
                        <div class="bg-gray-50 px-4 py-3 border-t border-gray-200 sm:px-6">
                            <div class="flex items-center justify-between">
                                <div>
                                    <p class="text-sm text-gray-700">
                                        Showing {{ (filePagination.page - 1) * filePagination.limit + 1 }} to 
                                        {{ Math.min(filePagination.page * filePagination.limit, filePagination.total) }} 
                                        of {{ filePagination.total }} files
                                    </p>
                                </div>
                                <div class="flex space-x-2">
                                    <button @click="prevPage" :disabled="filePagination.page <= 1" 
                                            class="px-3 py-1 border border-gray-300 rounded text-sm disabled:bg-gray-100 disabled:text-gray-400">
                                        Previous
                                    </button>
                                    <span class="px-3 py-1 text-sm text-gray-700">
                                        Page {{ filePagination.page }} of {{ filePagination.pages }}
                                    </span>
                                    <button @click="nextPage" :disabled="filePagination.page >= filePagination.pages" 
                                            class="px-3 py-1 border border-gray-300 rounded text-sm disabled:bg-gray-100 disabled:text-gray-400">
                                        Next
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Sessions Tab -->
                <div v-show="activeTab === 'sessions'" class="space-y-6">
                    <div class="bg-white rounded-lg shadow p-6">
                        <h2 class="text-xl font-bold mb-4">Imaging Sessions</h2>
                        <div class="space-y-4">
                            <div v-for="session in sessions" :key="session.session_id" 
                                 class="border border-gray-200 rounded-lg p-4 hover:bg-gray-50">
                                <div class="flex justify-between items-start">
                                    <div>
                                        <h3 class="font-semibold text-lg">{{ session.session_date }}</h3>
                                        <p class="text-gray-600">{{ session.camera }} + {{ session.telescope }}</p>
                                        <p class="text-sm text-gray-500">{{ session.file_count }} files</p>
                                        <p class="text-sm text-gray-500" v-if="session.site_name">{{ session.site_name }}</p>
                                    </div>
                                    <div class="text-right">
                                        <p class="text-sm text-gray-500">{{ session.session_id }}</p>
                                        <p class="text-sm text-gray-500" v-if="session.observer">{{ session.observer }}</p>
                                    </div>
                                </div>
                                <div v-if="session.notes" class="mt-2 text-sm text-gray-700">
                                    {{ session.notes }}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Operations Tab -->
                <div v-show="activeTab === 'operations'" class="space-y-6">
                    <div class="bg-white rounded-lg shadow p-6">
                        <h2 class="text-xl font-bold mb-4">Operations Status</h2>
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <button @click="startOperation('scan')" 
                                    class="bg-blue-500 hover:bg-blue-600 text-white py-3 px-6 rounded-lg transition">
                                Scan Quarantine
                            </button>
                            <button @click="startOperation('validate')" 
                                    class="bg-green-500 hover:bg-green-600 text-white py-3 px-6 rounded-lg transition">
                                Run Validation
                            </button>
                            <button @click="startOperation('migrate')" 
                                    class="bg-purple-500 hover:bg-purple-600 text-white py-3 px-6 rounded-lg transition">
                                Migrate Files
                            </button>
                        </div>
                    </div>
                </div>
            </main>
        </div>

        <script>
        const { createApp } = Vue;
        
        createApp({
            data() {
                return {
                    activeTab: 'dashboard',
                    stats: {},
                    files: [],
                    sessions: [],
                    filePagination: { page: 1, limit: 50, total: 0, pages: 0 },
                    fileFilters: {
                        frame_types: [],
                        cameras: [],
                        telescopes: [],
                        objects: [],
                        filters: [],
                        dates: []
                    },
                    searchFilters: {
                        filename: '',
                        session_id: '',
                        exposure_min: '',
                        exposure_max: '',
                        score_range: ''
                    },
                    filterOptions: {
                        frame_types: [],
                        cameras: [],
                        telescopes: [],
                        objects: [],
                        filters: [],
                        dates: []
                    },
                    activeFilter: null,
                    fileSorting: {
                        sort_by: 'obs_date',
                        sort_order: 'desc'
                    }
                }
            },
            computed: {
                hasActiveFilters() {
                    return Object.values(this.fileFilters).some(arr => arr.length > 0) ||
                           Object.values(this.searchFilters).some(val => val !== '');
                }
            },
            methods: {
                async loadStats() {
                    try {
                        const response = await axios.get('/api/stats');
                        this.stats = response.data;
                    } catch (error) {
                        console.error('Error loading stats:', error);
                    }
                },
                
                async loadFilterOptions() {
                    try {
                        const response = await axios.get('/api/filter-options');
                        this.filterOptions = response.data;
                    } catch (error) {
                        console.error('Error loading filter options:', error);
                    }
                },
                
                async loadFiles() {
                    try {
                        const params = {
                            page: this.filePagination.page,
                            limit: this.filePagination.limit,
                            sort_by: this.fileSorting.sort_by,
                            sort_order: this.fileSorting.sort_order
                        };
                        
                        // Add multi-select filters
                        for (const [key, values] of Object.entries(this.fileFilters)) {
                            if (values.length > 0) {
                                params[key] = values.join(',');
                            }
                        }
                        
                        // Add search filters
                        for (const [key, value] of Object.entries(this.searchFilters)) {
                            if (value) {
                                if (key === 'score_range') {
                                    switch (value) {
                                        case 'auto':
                                            params.validation_score_min = 95;
                                            break;
                                        case 'review':
                                            params.validation_score_min = 80;
                                            params.validation_score_max = 94.9;
                                            break;
                                        case 'manual':
                                            params.validation_score_max = 79.9;
                                            break;
                                    }
                                } else {
                                    params[key] = value;
                                }
                            }
                        }
                        
                        const response = await axios.get('/api/files', { params });
                        this.files = response.data.files;
                        this.filePagination = response.data.pagination;
                    } catch (error) {
                        console.error('Error loading files:', error);
                    }
                },
                
                async loadSessions() {
                    try {
                        const response = await axios.get('/api/sessions');
                        this.sessions = response.data.sessions;
                    } catch (error) {
                        console.error('Error loading sessions:', error);
                    }
                },
                
                toggleFilter(filterName) {
                    this.activeFilter = this.activeFilter === filterName ? null : filterName;
                },
                
                toggleFilterOption(filterName, option) {
                    const index = this.fileFilters[filterName].indexOf(option);
                    if (index > -1) {
                        this.fileFilters[filterName].splice(index, 1);
                    } else {
                        this.fileFilters[filterName].push(option);
                    }
                },
                
                getFilterText(filterName) {
                    const count = this.fileFilters[filterName].length;
                    if (count === 0) return `All ${filterName}`;
                    if (count === 1) return this.fileFilters[filterName][0];
                    return `${count} selected`;
                },
                
                getActiveFilterSummary() {
                    const summary = [];
                    for (const [key, values] of Object.entries(this.fileFilters)) {
                        if (values.length > 0) {
                            summary.push(`${key}: ${values.length}`);
                        }
                    }
                    for (const [key, value] of Object.entries(this.searchFilters)) {
                        if (value) {
                            summary.push(`${key}: ${value}`);
                        }
                    }
                    return summary;
                },
                
                resetAllFilters() {
                    // Reset all filters
                    for (const key of Object.keys(this.fileFilters)) {
                        this.fileFilters[key] = [];
                    }
                    for (const key of Object.keys(this.searchFilters)) {
                        this.searchFilters[key] = '';
                    }
                    this.activeFilter = null;
                    this.filePagination.page = 1;
                    this.loadFiles();
                },
                
                sortBy(column) {
                    if (this.fileSorting.sort_by === column) {
                        this.fileSorting.sort_order = this.fileSorting.sort_order === 'asc' ? 'desc' : 'asc';
                    } else {
                        this.fileSorting.sort_by = column;
                        this.fileSorting.sort_order = 'desc';
                    }
                    this.filePagination.page = 1;
                    this.loadFiles();
                },
                
                navigateToSession(sessionId) {
                    if (sessionId && sessionId !== 'N/A') {
                        this.activeTab = 'sessions';
                    }
                },
                
                prevPage() {
                    if (this.filePagination.page > 1) {
                        this.filePagination.page--;
                        this.loadFiles();
                    }
                },
                
                nextPage() {
                    if (this.filePagination.page < this.filePagination.pages) {
                        this.filePagination.page++;
                        this.loadFiles();
                    }
                },
                
                getScoreClass(score) {
                    if (!score) return 'text-gray-500';
                    if (score >= 95) return 'text-green-600';
                    if (score >= 80) return 'text-yellow-600';
                    return 'text-red-600';
                },
                
                getFrameTypeClass(frameType) {
                    const classes = {
                        'LIGHT': 'bg-blue-100 text-blue-800',
                        'DARK': 'bg-gray-100 text-gray-800',
                        'FLAT': 'bg-yellow-100 text-yellow-800',
                        'BIAS': 'bg-purple-100 text-purple-800'
                    };
                    return classes[frameType] || 'bg-gray-100 text-gray-800';
                },
                
                async startOperation(type) {
                    try {
                        await axios.post(`/api/operations/${type}`);
                        alert(`${type} operation started`);
                    } catch (error) {
                        alert(`Failed to start ${type}: ${error.message}`);
                    }
                }
            },
            
            watch: {
                activeTab(newTab) {
                    if (newTab === 'files') {
                        this.loadFiles();
                    } else if (newTab === 'sessions') {
                        this.loadSessions();
                    }
                },
                
                fileFilters: {
                    handler() {
                        this.filePagination.page = 1;
                        this.loadFiles();
                    },
                    deep: true
                },
                
                searchFilters: {
                    handler() {
                        this.filePagination.page = 1;
                        this.loadFiles();
                    },
                    deep: true
                }
            },
            
            async mounted() {
                await this.loadStats();
                await this.loadFilterOptions();
                
                // Close dropdowns when clicking outside
                document.addEventListener('click', (e) => {
                    if (!e.target.closest('.relative')) {
                        this.activeFilter = null;
                    }
                });
            }
        }).mount('#app');
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)