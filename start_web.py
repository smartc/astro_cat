#!/usr/bin/env python3
"""
Simple startup script for FITS Cataloger Web Interface
"""

import sys
import subprocess
from pathlib import Path

def check_requirements():
    """Check if required packages are installed."""
    required_packages = [
        'fastapi',
        'uvicorn',
        'sqlalchemy',
        'astropy',
        'polars'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"Missing required packages: {', '.join(missing_packages)}")
        print("Please install with: pip install -r requirements.txt")
        return False
    
    return True

def check_config():
    """Check if configuration exists."""
    config_file = Path("config.json")
    if not config_file.exists():
        print("Configuration file not found!")
        print("Please run: python main.py init-config")
        return False
    
    return True

def main():
    """Start the web interface."""
    print("FITS Cataloger Web Interface")
    print("=" * 40)
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Check configuration
    if not check_config():
        sys.exit(1)
    
    print("✓ Requirements satisfied")
    print("✓ Configuration found")
    print()
    print("Starting web interface...")
    print("Open your browser to: http://localhost:8000")
    print("Press Ctrl+C to stop")
    print()
    
    # Start the web interface
    try:
        from web_interface import app
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
    except ImportError:
        print("Error: Could not import web interface modules")
        print("Make sure web_interface.py is in the current directory")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nWeb interface stopped by user")
    except Exception as e:
        print(f"Error starting web interface: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()