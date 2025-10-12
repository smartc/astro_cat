"""
Dashboard and static page routes.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, FileResponse

from models import FitsFile
from web.background_tasks import is_operation_in_progress

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard():
    """Main dashboard page."""
    dashboard_file = Path("static/dashboard.html")
    if not dashboard_file.exists():
        raise HTTPException(status_code=404, detail="Dashboard file not found")
    return FileResponse("static/dashboard.html")


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Get module globals using sys.modules
        app_module = sys.modules['web.app']
        db_manager = app_module.db_manager
        
        session = db_manager.get_session()
        try:
            total_files = session.query(FitsFile).count()
        finally:
            session.close()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "total_files": total_files,
            "operation_in_progress": is_operation_in_progress()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/editor", response_class=HTMLResponse)
async def markdown_editor():
    """Markdown editor for processing sessions."""
    return FileResponse("static/editor.html")


@router.get("/imaging-editor", response_class=HTMLResponse)
async def imaging_session_markdown_editor():
    """Markdown editor for imaging sessions."""
    return FileResponse("static/editor.html")


@router.get("/database-viewer", response_class=HTMLResponse)
async def database_viewer():
    """Database browser with header."""
    return FileResponse("static/database-viewer.html")

@router.get("/file-browser", response_class=HTMLResponse)
async def file_browser():
    """File browser with WebDAV iframe."""
    return FileResponse("static/file-browser.html")