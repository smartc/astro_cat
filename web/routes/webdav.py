"""
WebDAV access API routes.
"""

import logging
from urllib.parse import quote
from fastapi import APIRouter, HTTPException, Request
from webdav_server import get_webdav_server

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webdav")


@router.get("/status")
async def get_webdav_status():
    """Check if WebDAV server is running."""
    server = get_webdav_server()
    return {
        "running": server is not None and server.is_running(),
        "port": server.port if server else None,
        "url": server.get_url() if server else None
    }


@router.get("/session/{session_id}")
async def get_session_webdav_info(session_id: str, request: Request):
    """Get WebDAV connection info for a processing session."""
    try:
        server = get_webdav_server()
        if not server or not server.is_running():
            raise HTTPException(status_code=503, detail="WebDAV server not available")
        
        # Get server hostname from request (for proper URL generation)
        host_header = request.headers.get("host", "").split(":")[0]
        if not host_header:
            host_header = server.host if server.host != "0.0.0.0" else "localhost"
        
        # Construct WebDAV URLs
        webdav_port = server.port
        base_url = f"http://{host_header}:{webdav_port}"
        session_path = quote(session_id)
        
        return {
            "session_id": session_id,
            "webdav_base": base_url,
            "webdav_root": f"{base_url}/{session_path}",
            "folders": {
                "raw": f"{base_url}/{session_path}/raw",
                "lights": f"{base_url}/{session_path}/raw/lights",
                "darks": f"{base_url}/{session_path}/raw/calibration/darks",
                "flats": f"{base_url}/{session_path}/raw/calibration/flats",
                "bias": f"{base_url}/{session_path}/raw/calibration/bias",
                "intermediate": f"{base_url}/{session_path}/intermediate",
                "stacked": f"{base_url}/{session_path}/intermediate/stacked",
                "final": f"{base_url}/{session_path}/final"
            },
            "instructions": {
                "windows_map": f"Map network drive: {base_url}",
                "windows_cmd": f'net use Z: "{base_url}" /persistent:yes',
                "windows_explorer": f"\\\\{host_header}@{webdav_port}\\{session_id}",
                "macos": f"Finder → Go → Connect to Server → {base_url}",
                "linux": f"Mount with davfs2 or access via file manager: dav://{host_header}:{webdav_port}"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting WebDAV info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/browse/{session_id}")
async def get_webdav_browse_url(session_id: str, subfolder: str = ""):
    """Get URL for browsing a session folder via WebDAV."""
    try:
        server = get_webdav_server()
        if not server or not server.is_running():
            raise HTTPException(status_code=503, detail="WebDAV server not available")
        
        path = f"{session_id}/{subfolder}" if subfolder else session_id
        return {
            "url": server.get_url(path),
            "session_id": session_id,
            "subfolder": subfolder
        }
        
    except Exception as e:
        logger.error(f"Error generating browse URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))