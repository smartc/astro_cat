"""
WebDAV Server Module for FITS Cataloger
Provides file access to processing sessions via WebDAV protocol.
"""

import logging
import threading
from pathlib import Path
from typing import Optional

from wsgidav.wsgidav_app import WsgiDAVApp
from wsgidav.fs_dav_provider import FilesystemProvider
from cheroot import wsgi

logger = logging.getLogger(__name__)


class WebDAVServer:
    """WebDAV server for serving processing session files."""
    
    def __init__(self, processing_dir: Path, host: str = "0.0.0.0", port: int = 8082):
        """
        Initialize WebDAV server.
        
        Args:
            processing_dir: Root directory containing processing sessions
            host: Host address to bind to
            port: Port to listen on
        """
        self.processing_dir = Path(processing_dir)
        self.host = host
        self.port = port
        self.server = None
        self.thread = None
        
        if not self.processing_dir.exists():
            raise ValueError(f"Processing directory does not exist: {processing_dir}")
    
    def start(self) -> bool:
        """
        Start the WebDAV server in a background thread.
        
        Returns:
            True if server started successfully, False otherwise
        """
        try:
            # Create provider with symlink support
            provider = FilesystemProvider(
                str(self.processing_dir),
                fs_opts={'follow_symlinks': True}
            )
            
            # Configure WebDAV
            config = {
                "host": self.host,
                "port": self.port,
                "provider_mapping": {
                    "/": provider
                },
                "verbose": 1,
                "logging": {
                    "enable_loggers": [],  # Disable verbose logging in production
                },
                "property_manager": True,
                "lock_storage": True,
                
                # Directory browser configuration
                "dir_browser": {
                    "enable": True,
                    "icon": False,  # Hide WsgiDAV icon
                    "ms_sharepoint_support": False,
                    "response_trailer": False,  # Remove WsgiDAV footer
                },
                
                # No authentication - relies on network security
                # TODO: Add authentication if exposing to internet
                "simple_dc": {"user_mapping": {"*": True}},
            }
            
            # Create WSGI app and server
            app = WsgiDAVApp(config)
            self.server = wsgi.Server((self.host, self.port), app)
            
            # Start in background thread
            self.thread = threading.Thread(
                target=self.server.start,
                daemon=True,
                name="WebDAV-Server"
            )
            self.thread.start()
            
            logger.info(f"✓ WebDAV server started: http://{self.host}:{self.port}")
            logger.info(f"  Serving: {self.processing_dir}")
            logger.info(f"  Windows: Map network drive to \\\\{self.host}@{self.port}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start WebDAV server: {e}")
            return False
    
    def stop(self):
        """Stop the WebDAV server."""
        if self.server:
            try:
                logger.info("Stopping WebDAV server...")
                self.server.stop()
                if self.thread:
                    self.thread.join(timeout=5)
                logger.info("✓ WebDAV server stopped")
            except Exception as e:
                logger.error(f"Error stopping WebDAV server: {e}")
    
    def get_url(self, path: str = "") -> str:
        """
        Get the full WebDAV URL for a given path.
        
        Args:
            path: Optional path within the processing directory
            
        Returns:
            Full HTTP URL
        """
        base_url = f"http://{self.host}:{self.port}"
        if path:
            return f"{base_url}/{path.lstrip('/')}"
        return base_url
    
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self.server is not None and self.thread is not None and self.thread.is_alive()


# Global instance
_webdav_server: Optional[WebDAVServer] = None


def start_webdav_server(processing_dir: Path, host: str = "0.0.0.0", port: int = 8082) -> Optional[WebDAVServer]:
    """
    Start the global WebDAV server instance.
    
    Args:
        processing_dir: Root directory for processing sessions
        host: Host to bind to
        port: Port to listen on
        
    Returns:
        WebDAVServer instance if successful, None otherwise
    """
    global _webdav_server
    
    if _webdav_server and _webdav_server.is_running():
        logger.warning("WebDAV server already running")
        return _webdav_server
    
    try:
        _webdav_server = WebDAVServer(processing_dir, host, port)
        if _webdav_server.start():
            return _webdav_server
        else:
            _webdav_server = None
            return None
    except Exception as e:
        logger.error(f"Failed to initialize WebDAV server: {e}")
        _webdav_server = None
        return None


def stop_webdav_server():
    """Stop the global WebDAV server instance."""
    global _webdav_server
    
    if _webdav_server:
        _webdav_server.stop()
        _webdav_server = None


def get_webdav_server() -> Optional[WebDAVServer]:
    """Get the global WebDAV server instance."""
    return _webdav_server