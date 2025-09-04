# FITS Cataloger - Phase 1 Project Structure

## Directory Layout

```
fits_cataloger/
├── config.json                 # Configuration file
├── requirements.txt            # Python dependencies
├── main.py                     # CLI entry point
├── config.py                   # Configuration management
├── models.py                   # Database models
├── fits_processor.py           # FITS file processing
├── file_monitor.py             # File monitoring
├── tests/                      # Unit tests
│   ├── __init__.py
│   ├── test_config.py
│   ├── test_fits_processor.py
│   └── test_models.py
├── logs/                       # Application logs
├── alembic/                    # Database migrations (future)
└── README.md                   # Project documentation
```

## Setup Instructions

### 1. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Linux/Mac
# or
venv\Scripts\activate     # On Windows
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Initialize Configuration

```bash
python main.py init-config
```

Edit `config.json` with your specific paths and equipment details.

### 4. Test Database Setup

```bash
python main.py test-db
```

### 5. Perform Initial Scan

```bash
python main.py scan
```

### 6. Start Continuous Monitoring

```bash
python main.py monitor
```

## Key Features Implemented

### Phase 1 Functionality

- ✅ **Configuration Management**: JSON-based configuration with validation
- ✅ **Database Models**: Modern SQLAlchemy models with proper relationships
- ✅ **FITS Processing**: Metadata extraction using astropy
- ✅ **File Monitoring**: Real-time quarantine directory monitoring
- ✅ **Equipment Identification**: Camera and telescope detection
- ✅ **Filter Normalization**: Configurable filter name mappings
- ✅ **Session Grouping**: Automatic session ID generation
- ✅ **Duplicate Detection**: MD5-based duplicate identification
- ✅ **CLI Interface**: Click-based command line interface

### Architecture Benefits

- **Modern Python**: Type hints, async/await, context managers
- **Configurable**: All settings in external JSON file
- **Extensible**: Easy to add new equipment, filters, or processing rules
- **Robust**: Proper error handling and logging
- **Cross-platform**: Works on Linux ARM64, Windows, macOS
- **Database Agnostic**: Easy migration from SQLite to PostgreSQL/MySQL

## Usage Examples

### Basic Operations

```bash
# Create configuration
python main.py init-config

# One-time scan of quarantine directory
python main.py scan

# Start continuous monitoring
python main.py monitor

# View database statistics
python main.py stats

# Test database connection
python main.py test-db
```

### Configuration Customization

Edit `config.json` to:
- Set your quarantine and image directories
- Add your cameras with pixel dimensions
- Add your telescopes with focal lengths
- Configure filter name mappings
- Adjust monitoring intervals

## Next Steps (Future Phases)

- **Phase 2**: File organization and structured folder creation
- **Phase 3**: Web interface for review and management
- **Phase 4**: Advanced session management and notes

## Dependencies Explained

- **astropy**: Essential for FITS file handling and astronomical calculations
- **polars**: Fast data manipulation (modern pandas alternative)
- **sqlalchemy**: Database ORM with migration support
- **watchdog**: Cross-platform file system monitoring
- **pydantic**: Configuration validation and type safety
- **click**: Modern CLI framework
- **tqdm**: Progress bars for long operations
