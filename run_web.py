#!/usr/bin/env python3
"""
Startup script for FITS Cataloger Web Interface.
Replaces the old web_interface.py.
"""

import sys
from pathlib import Path

def check_requirements():
    """Check if required packages are installed."""
    try:
        import fastapi
        import uvicorn
        import sqlalchemy
        import astropy
        import polars
    except ImportError as e:
        print(f"Missing required package: {e.name}")
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
    
    # Import and run
    try:
        from web import app
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
    except ImportError as e:
        print(f"Error: Could not import web modules: {e}")
        print("Make sure the 'web' package is in the current directory")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nWeb interface stopped by user")
    except Exception as e:
        print(f"Error starting web interface: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()