# FITS Cataloger

A modern Python application for cataloging and managing astrophotography FITS images.

## Features

### Phase 1 (Current)
- **Automated Quarantine Monitoring**: Real-time detection of new FITS files
- **Metadata Extraction**: Comprehensive FITS header parsing using astropy
- **Equipment Identification**: Automatic camera and telescope detection
- **Duplicate Detection**: MD5-based duplicate file identification
- **Session Grouping**: Automatic grouping of images by observation session
- **Filter Normalization**: Configurable filter name standardization
- **Database Storage**: SQLite database with migration-ready design
- **CLI Interface**: Command-line tools for scanning and monitoring

### Planned Features
- **Phase 2**: Structured file organization and renaming
- **Phase 3**: Web interface for review and management
- **Phase 4**: Advanced session management and equipment notes

## Installation

### Prerequisites
- Python 3.11 or higher
- Virtual environment (recommended)

### Setup

1. **Clone or download the project files**

2. **Create and activate virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate     # Windows
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize configuration:**
   ```bash
   python main.py init-config
   ```

5. **Edit configuration file:**
   ```bash
   nano config.json  # or your preferred editor
   ```
   
   Update the paths section with your actual directories:
   ```json
   {
     "paths": {
       "quarantine_dir": "/path/to/your/quarantine",
       "image_dir": "/path/to/your/images", 
       "database_path": "/path/to/your/fits_catalog.db",
       "restore_folder": "/path/to/restore/temp"
     }
   }
   ```

6. **Test the setup:**
   ```bash
   python main.py test-db
   python test_basic.py
   ```

## Usage

### Basic Commands

```bash
# Perform one-time scan of quarantine directory
python main.py scan

# Start continuous monitoring
python main.py monitor

# View database statistics
python main.py stats

# Test database connection
python main.py test-db

# Create new config file
python main.py init-config
```

### Configuration

The `config.json` file contains all application settings:

- **Paths**: Directory locations for quarantine, images, database
- **Equipment**: Camera and telescope specifications
- **Monitoring**: File extensions and scan intervals
- **Filters**: Name normalization mappings
- **Database**: Connection settings and table names

### Adding Equipment

To add new cameras or telescopes, edit the `config.json` file:

```json
{
  "cameras": [
    {
      "name": "YOUR_CAMERA",
      "x_pixels": 4000,
      "y_pixels": 3000,
      "pixel_size": 4.5
    }
  ],
  "telescopes": [
    {
      "name": "YOUR_SCOPE",
      "focal_length": 1000,
      "aperture": 200
    }
  ]
}
```

### Filter Mappings

Normalize varying filter names in your FITS headers:

```json
{
  "filter_mappings": {
    "Red": "R",
    "Hydrogen Alpha": "HA",
    "H-Alpha": "HA", 
    "HA-3": "HA",
    "Ha 3nm": "HA"
  }
}
```

## Database Schema

### Main Tables

- **fits_files**: Primary table storing all FITS file metadata
- **cameras**: Camera specifications and settings
- **telescopes**: Telescope/lens specifications
- **filter_mappings**: Filter name normalization rules
- **process_log**: Processing session logs

### Key Fields

- **Session ID**: Automatically generated based on date, camera, and telescope
- **MD5 Hash**: For duplicate detection and file integrity
- **Equipment Detection**: Automatic identification based on image dimensions and focal length
- **Observation Date**: Parsed from various FITS header formats

## Logging

Application logs are written to:
- Console output (INFO level and above)
- Log file specified in config (default: `fits_cataloger.log`)

Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

## Platform Support

Tested on:
- ✅ Linux ARM64 (OrangePi 5B / Debian)
- ✅ Linux x86_64
- ✅ macOS (Intel/Apple Silicon)
- ✅ Windows 10/11

## Troubleshooting

### Common Issues

1. **"Quarantine directory not found"**
   - Verify the path in `config.json` exists
   - Check permissions on the directory

2. **"Database connection failed"** 
   - Ensure the database directory exists
   - Check file permissions
   - Verify SQLite is properly installed

3. **"No FITS files found"**
   - Check file extensions in config match your files
   - Verify files are not marked as "BAD_" in filename

### Debug Mode

Enable debug logging by setting log level in config:
```json
{
  "logging": {
    "level": "DEBUG"
  }
}
```

## Development

### Running Tests

```bash
python test_basic.py
```

### Code Style

The project uses:
- **Black**: Code formatting
- **Ruff**: Linting and code quality
- **Type hints**: For better code documentation

Format code:
```bash
black *.py
ruff check *.py
```

## Migration Path

The database design supports easy migration to:
- **PostgreSQL**: For better performance and concurrent access
- **MySQL**: For compatibility with existing infrastructure  
- **Cloud databases**: AWS RDS, Google Cloud SQL, etc.

Simply update the `connection_string` in the configuration.

## Support

For issues or questions:
1. Check the logs for error details
2. Verify configuration settings
3. Test with `python main.py test-db`
4. Run basic tests with `python test_basic.py`
