# FITS Cataloger

**Version:** 0.7.3 
**Last Updated:** October 4, 2025

A cross-platform astrophotography image management system for cataloging and organizing FITS files with automated metadata extraction, session grouping, and web-based review interface.

## Features

- **Automated Quarantine Monitoring** - Real-time detection and cataloging of new FITS files
- **Metadata Extraction** - Comprehensive FITS header parsing with equipment identification
- **Session Grouping** - Automatic detection and organization of imaging sessions
- **Duplicate Detection** - MD5-based duplicate identification
- **Filter Normalization** - Configurable standardization of filter names
- **File Organization** - Structured folder system with consistent naming
- **Web Interface** - Browse and manage images, sessions, and equipment via web UI
- **Processing Sessions** - Create and track image processing projects
- **Equipment Management** - Maintain cameras, telescopes, and filter databases

## Quick Start

### Prerequisites
- Python 3.11+
- Virtual environment (recommended)

### Installation

```bash
# Clone repository and navigate to directory
cd fits_cataloger

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Initialize configuration
python main.py init-config

# Edit config.json with your paths
nano config.json
```

### Configuration

Update `config.json` with your directory paths:

```json
{
  "paths": {
    "quarantine_dir": "/path/to/quarantine",
    "image_dir": "/path/to/images",
    "processing_dir": "/path/to/processing",
    "database_path": "/path/to/fits_catalog.db",
    "restore_folder": "/path/to/restore"
  }
}
```

Add your equipment to `cameras.json`, `telescopes.json`, and `filters.json`.

## Usage

### Command Line Interface

```bash
# Test database connection
python main.py test-db

# Scan quarantine folder once
python main.py scan

# Start continuous monitoring
python main.py monitor

# View database statistics
python main.py stats

# Organize files into structure
python main.py organize
```

### Web Interface

```bash
# Start web server
python main.py web

# Access at: http://localhost:8000
```

**Web Features:**
- Browse and filter FITS files
- Review imaging sessions with metadata
- Create processing sessions
- Manage equipment database
- Configure application settings
- View real-time statistics

### Processing Session Management

```bash
# Create processing session
python main.py processing create "M31 Project" --file-ids 1,2,3,4

# List processing sessions
python main.py processing list

# View session details
python main.py processing show <session-id>
```

## Architecture

### Database Models
- **FitsFile** - Core FITS metadata and location tracking
- **Session** - Imaging session grouping and notes
- **ProcessingSession** - Project-based file organization
- **Camera/Telescope/FilterMapping** - Equipment specifications
- **SystemSettings** - Application configuration

### Key Components
- `main.py` - CLI entry point
- `fits_processor.py` - FITS metadata extraction
- `file_monitor.py` - Quarantine directory monitoring
- `file_organizer.py` - File migration and organization
- `web/app.py` - FastAPI web application
- `models.py` - SQLAlchemy database models
- `config.py` - Configuration management

### Folder Structure

Organized images follow this pattern:
```
images/
├── YYYY-MM/              # Year-Month
│   └── telescope/        # Telescope name
│       └── object/       # Target object
│           ├── Lights/
│           ├── Darks/
│           ├── Flats/
│           └── Bias/
```

## Dependencies

- **astropy** - FITS file handling
- **sqlalchemy** - Database ORM
- **fastapi** - Web API framework
- **watchdog** - File system monitoring
- **polars** - High-performance data manipulation
- **pydantic** - Configuration validation
- **click** - CLI framework
- **uvicorn** - ASGI server

## Platform Support

Tested on:
- Debian ARM64 (OrangePi 5B)
- Linux x86_64
- Windows 10/11
- macOS

## Development

The codebase uses modern Python practices with type hints, SQLAlchemy ORM, and FastAPI for the web interface.

## License

MIT License - Copyright (c) 2025 smartc

See [LICENSE](LICENSE) file for full details.

## Contributing

Contributions welcome! Please open issues or pull requests for bugs, features, or improvements.

## Support

For issues or questions, please open a GitHub issue.