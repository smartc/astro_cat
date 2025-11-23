#!/usr/bin/env python3
"""
Startup script for S3 Backup web interface.
Run: python -m s3_backup.run_web
"""

import os
import sys
import logging
from pathlib import Path


# Ensure templates directory exists
templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)

if __name__ == "__main__":
    import uvicorn
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Check environment variables for bind host and port
    bind_host = os.environ.get('ASTROCAT_BIND_HOST', '127.0.0.1')
    port = int(os.environ.get('ASTROCAT_S3_BACKUP_PORT', '8083'))

    print("=" * 70)
    print("Starting S3 Backup Manager Web Interface")
    print("=" * 70)
    print(f"Server: http://{bind_host}:{port}")
    print(f"Access via main app: http://localhost:8000/s3-backup-viewer")
    print("=" * 70)

    uvicorn.run(
        "s3_backup.web_app:app",
        host=bind_host,
        port=port,
        reload=False,
        log_level="info"
    )