#!/usr/bin/env python3
"""
Startup script for S3 Backup web interface.
Run: python -m s3_backup.run_web
"""

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
    
    print("=" * 70)
    print("Starting S3 Backup Manager Web Interface")
    print("=" * 70)
    print(f"Server: http://0.0.0.0:8083")
    print(f"Access via main app: http://localhost:8000/s3-backup-viewer.html")
    print("=" * 70)
    
    uvicorn.run(
        "s3_backup.web_app:app",
        host="0.0.0.0",
        port=8083,
        reload=False,
        log_level="info"
    )