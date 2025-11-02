# astro_cat

**astro_cat** is a comprehensive toolkit for managing, cataloging, and archiving astrophotography data. It streamlines raw FITS image intake, session organization, processing workflows, and cloud backups—with an intuitive web interface and powerful CLI tools.

**NO WARRANTY** Please use with caution! I can take no responsibility for data loss, corruption or other issues.  I strongly recommend you back up your data before using this!  Test with a small dataset first!

---

## 🚀 Features

### Core Functionality
- 🔭 **FITS Image Cataloging** — Automatically scan directories for new FITS files, extract metadata (object, filter, exposure, etc.), and organize into a searchable SQLite database
- 📁 **Session Management** — Organize images into imaging sessions with automatic detection and manual override capabilities
- 🎯 **Processing Workflows** — Create processing sessions, select appropriate calibration frames, track processed outputs
- 📝 **Obsidian-Compatible Notes** — Maintain Markdown session notes that integrate seamlessly with Obsidian vaults
- 🔍 **Advanced Search** — Query by object, filter, date, telescope, camera, exposure time, and more

### Web Interface
- 📊 **Dashboard** — Real-time statistics, storage usage, recent activity
- 🌐 **Session Browser** — Browse and manage imaging sessions with detailed file listings
- 🖼️ **File Explorer** — Search and filter FITS files across your entire library
- 📈 **Statistics & Charts** — Visualize collection growth, equipment usage, integration times
- ⚙️ **Processing Sessions** — Create and manage processing workflows through the UI

### Command Line Tools
- 🧰 **Comprehensive CLI** — Full control over all features via command line
- 🔄 **Batch Operations** — Scan, catalog, validate, and migrate files in bulk
- 📋 **List & Query** — Generate reports on files, sessions, equipment, and statistics
- ✅ **Validation** — Check file integrity, verify metadata consistency

### Cloud Backup (Optional)
- ☁️ **S3 Integration** — Automated backups to AWS S3 with compression
- 🔐 **Integrity Verification** — MD5 checksum validation for all uploads
- 📦 **Lifecycle Management** — Automatic transitions to Glacier and Deep Archive
- 💾 **Incremental Backups** — Only backup new or changed sessions
- 📊 **Backup Dashboard** — Monitor backup status, storage costs, and coverage

---

## 📋 Requirements

- **Python 3.8+**
- **Operating System**: Linux, macOS, or Windows
- **Storage**: Local or network-attached storage for FITS files
- **Optional**: AWS account for S3 backup features

---

## ⚙️ Installation

### 1. Clone the Repository

```bash
git clone https://github.com/smartc/astro_cat.git
cd astro_cat
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv

# Activate on Linux/macOS:
source venv/bin/activate

# Or on Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Frontend Libraries

The web interface requires JavaScript and CSS libraries that are not included in the repository. Run the installer script to download them:

```bash
python install_frontend_libs.py
```

This will download:
- Vue.js 3.4.21
- Axios 1.6.7
- Toast UI Editor (latest)
- Tailwind CSS 2.2.19

**Note**: These libraries are downloaded to `static/js/lib/` and `static/css/lib/` directories, which are excluded from version control.

### 5. Verify Installation

```bash
python main.py --help
```

You should see the CLI help menu with available commands.

---

## 🛠️ Initial Configuration

### 1. Configure Paths

First, copy the template configuration file:

```bash
cp config.json.template config.json
```

Then edit `config.json` to set your file locations:

```json
{
  "paths": {
    "quarantine_dir": "/path/to/quarantine",     # Incoming raw FITS files
    "image_dir": "/path/to/images",              # Organized library
    "processing_dir": "/path/to/processing",     # Processing sessions
    "database_path": "/path/to/fits_catalog.db", # SQLite database
    "notes_dir": "/path/to/session_notes"        # Markdown notes
  },
  "database": {
    "type": "sqlite",
    "connection_string": "sqlite:///{{database_path}}"
  },
  "file_monitoring": {
    "scan_interval_minutes": 30,
    "ignore_newer_than_minutes": 30
  },
  "timezone_offset": -6
}
```

**Key Paths Explained:**
- **quarantine_dir**: Where new FITS files arrive (from camera/acquisition software)
- **image_dir**: Organized library structured by date and session
- **processing_dir**: Processing sessions with calibration, intermediate, and final outputs
- **database_path**: SQLite database storing all metadata
- **notes_dir**: Markdown notes for sessions (Obsidian-compatible)

### 2. Configure Equipment (Optional)

Edit the equipment definition files to match your gear:

**cameras.json:**
```json
{
  "ZWO ASI2600MM Pro": {
    "sensor_width": 23.5,
    "sensor_height": 15.7,
    "pixel_size": 3.76
  }
}
```

**telescopes.json:**
```json
{
  "WO Star71": {
    "aperture": 71,
    "focal_length": 350,
    "type": "Refractor"
  }
}
```

**filters.json:**
```json
[
  {
    "raw_name": "Lum",
    "proper_name": "L"
  },
  {
    "raw_name": "Red",
    "proper_name": "R"
  },
  {
    "raw_name": "Green",
    "proper_name": "G"
  },
  {
    "raw_name": "Blue",
    "proper_name": "B"
  }
]
```

### 3. Initialize Database

The database and required directories will be created automatically on first run. To verify:

```bash
python main.py list imaging-sessions
```

If the database doesn't exist, it will be created with the proper schema.

---

## 🌐 Web Interface Usage

### Starting the Web Server

**Important**: Before starting the web server for the first time, make sure you've installed the frontend libraries:

```bash
python install_frontend_libs.py
```

Then start the server:

```bash
python run_web.py
```

The server will start on `http://localhost:8000`. Open this URL in your browser.

### Dashboard

The main dashboard shows:
- **Collection Statistics**: Total files, sessions, integration time
- **Recent Activity**: Latest imaging sessions and processed files
- **Storage Overview**: Disk usage by session, camera, and telescope
- **Quick Actions**: Common tasks and shortcuts

### Imaging Sessions

**View Sessions:**
1. Click "Imaging Sessions" in the navigation
2. Browse sessions organized by date
3. Click a session to view details

**Session Details:**
- List of all files in the session
- Summary statistics (integration time, filter breakdown)
- Links to processing sessions using these files
- Option to edit session notes (Markdown)

**Create Processing Session:**
1. From session details, click "Create Processing Session"
2. Select files to include
3. Choose calibration frames
4. Name and save the processing session

### File Browser

**Search Files:**
1. Click "Files" in navigation
2. Use filters:
   - Object name
   - Filter (L, R, G, B, Ha, etc.)
   - Date range
   - Telescope/Camera
   - Frame type (Light, Dark, Flat, Bias)

**File Details:**
- Full FITS metadata
- Preview (if supported)
- Download options
- Associated session information

### Processing Sessions

**Create Processing Session:**
1. Click "Processing Sessions" → "New Session"
2. Enter session details:
   - Name (e.g., "M31 LRGB Stack")
   - Primary target
   - Target type (Galaxy, Nebula, etc.)
3. Select source files from imaging sessions
4. Save session

**Session Workflow:**
1. **Select Files**: Choose light, dark, flat, bias frames
2. **Process**: Use PixInsight or other software (external)
3. **Catalog Results**: Add processed files back to the session
4. **Track Progress**: Mark files as intermediate or final

### Statistics

View detailed analytics:
- **File Counts**: By object, filter, telescope, camera
- **Integration Time**: Total hours, by target, by filter
- **Collection Growth**: Charts showing acquisitions over time
- **Equipment Usage**: Which gear produces the most data

---

## 💻 Command Line Usage

### Basic Workflow

**1. Scan for New Files**

```bash
# Scan quarantine directory for new FITS files
python main.py scan
```

**2. Catalog Files**

```bash
# Extract metadata and add to database
python main.py catalog
```

**3. List Imaging Sessions**

```bash
# Show all imaging sessions
python main.py list imaging-sessions

# Show sessions from specific year
python main.py list imaging-sessions --year 2024
```

**4. View File Details**

```bash
# List files with filters
python main.py list files --object M31
python main.py list files --filter Ha
python main.py list files --date 2024-11-01
```

### Advanced Commands

**Processing Sessions**

```bash
# Create a processing session
python main.py processing-session create "M31 LRGB" --target M31

# List processing sessions
python main.py list processing-sessions

# Add files to a processing session
python main.py processing-session add-files <session-id> --file-ids 1,2,3
```

**Statistics**

```bash
# Show collection statistics
python main.py stats summary

# Statistics by object
python main.py stats by-object

# Statistics by filter
python main.py stats by-filter
```

**Validation**

```bash
# Validate all files in database
python main.py validate all

# Check for missing files
python main.py verify files

# Check database integrity
python main.py verify database
```

**Equipment Management**

```bash
# List cameras
python main.py list cameras

# List telescopes
python main.py list telescopes

# Show equipment statistics
python main.py stats equipment
```

### CLI Help

Get help for any command:

```bash
python main.py --help                    # List all commands
python main.py scan --help               # Scan command options
python main.py processing-session --help # Processing session commands
```

---

## ☁️ S3 Backup Configuration (Optional)

The S3 backup system provides automated, cost-effective cloud storage for your entire FITS library. With lifecycle management, you can store hundreds of gigabytes for as little as $10/year using AWS Glacier Deep Archive.

### Quick Start

**For detailed setup instructions**, see:
- **[S3 Quick Start Guide](s3_backup/QUICK_START.md)** - Step-by-step setup in 5 steps
- **[S3 Backup README](s3_backup/README.md)** - Comprehensive documentation

### Basic Setup

#### 1. AWS Prerequisites

Create an S3 bucket and configure AWS credentials:

```bash
# Create S3 bucket
aws s3 mb s3://your-bucket-name --region us-east-1

# Configure credentials (choose one method)
aws configure  # Interactive setup

# OR set environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
```

#### 2. Install Dependencies

```bash
pip install boto3
```

#### 3. Configure S3 Settings

On first startup, `s3_config.json` is created automatically with S3 disabled. Edit this file to enable S3 backups:

```bash
nano s3_config.json  # Edit with your bucket name and region
```

**Required changes** in `s3_config.json`:

```json
{
  "enabled": true,              # Change from false to true
  "aws_region": "us-east-1",    # Your AWS region
  "buckets": {
    "primary": "your-bucket-name"  # Your S3 bucket name
  }
}
```

#### 4. Test Backup

```bash
# Upload a test session
python -m s3_backup.cli upload --session-id YOUR_SESSION_ID

# Check status
python -m s3_backup.cli status

# Verify upload
python -m s3_backup.cli verify --all
```

### Lifecycle Management (Cost Optimization)

Automatically transition backups to low-cost storage with one command:

```bash
# Configure lifecycle rules (moves files to Deep Archive after 1 day)
python -m s3_backup.cli configure-lifecycle

# View current lifecycle rules
python -m s3_backup.cli show-lifecycle

# Estimate storage costs
python -m s3_backup.cli estimate-costs
```

**Cost Savings Example:**
- 827 GB in STANDARD storage: ~$19/month
- 827 GB in DEEP_ARCHIVE: ~$0.82/month
- **Annual savings: ~$218/year**

### Common Backup Commands

```bash
# Upload all sessions from a specific year
python -m s3_backup.cli upload --year 2024

# Upload all un-backed-up sessions
python -m s3_backup.cli upload

# List backed-up sessions
python -m s3_backup.cli list-sessions

# Verify backup integrity
python -m s3_backup.cli verify --all

# Backup database
python -m s3_backup.cli backup-database
```

### S3 Backup Web Interface

Launch a dedicated web interface for backup management:

```bash
python -m s3_backup.web_app
```

Access at `http://localhost:8083` for:
- Backup dashboard and statistics
- One-click session backups
- Storage cost tracking
- Upload progress monitoring
- Verification and restore operations

### Full Documentation

For complete details on:
- Lifecycle policy customization
- Restore procedures
- Cost estimation
- Troubleshooting
- Advanced configuration

See the comprehensive guides in the `s3_backup/` directory.

---

## 📂 Directory Structure

### Organized Library Layout

```
/path/to/images/
├── 2024/
│   ├── 2024-11-01_M31/
│   │   ├── Light/
│   │   │   ├── M31_L_180s_001.fits
│   │   │   └── M31_L_180s_002.fits
│   │   ├── Dark/
│   │   ├── Flat/
│   │   └── Bias/
│   └── 2024-11-02_M42/
└── 2023/
```

### Processing Directory Layout

```
/path/to/processing/
├── M31_LRGB_20241101/
│   ├── calibration/
│   │   ├── master_dark.fits
│   │   └── master_flat.fits
│   ├── intermediate/
│   │   ├── M31_L_stacked.xisf
│   │   └── M31_RGB_stacked.xisf
│   └── final/
│       ├── M31_LRGB.jpg
│       └── M31_LRGB.xisf
```

### Session Notes

```
/path/to/session_notes/
├── Imaging_Sessions/
│   ├── 2024/
│   │   ├── 20241101_M31.md
│   │   └── 20241102_M42.md
└── Processing_Sessions/
    └── M31_LRGB_20241101.md
```

---

## 🔧 Common Workflows

### New Imaging Session Workflow

1. **Acquire images** to quarantine directory
2. **Scan for new files**: `python main.py scan`
3. **Catalog metadata**: `python main.py catalog`
4. **Review in web UI**: Check session was created correctly
5. **Add notes**: Edit session notes in web UI or Obsidian
6. **Optional**: Backup to S3

### Processing Workflow

1. **Create processing session** in web UI
2. **Select source files** from imaging sessions
3. **Process externally** (PixInsight, etc.)
4. **Add processed files** to session directory
5. **Catalog results**: Files auto-detected in processing directory
6. **Track as final**: Mark final outputs in web UI

### Backup Workflow

1. **Review backup status** in S3 web UI (`localhost:8083`)
2. **Select sessions to backup**
3. **Monitor upload progress**
4. **Verify backups** with integrity checks
5. **Optional**: Set lifecycle policies for cost savings

---

## 🔍 Troubleshooting

### Database Issues

**Database locked error:**
```bash
# Close any open connections to the database
# Check for stale lock files
rm -f /path/to/fits_catalog.db-journal
```

**Rebuild statistics:**
```bash
python scripts/fix_performance_post_migration.py
```

**Check database integrity:**
```bash
python scripts/diagnose_db_size.py
```

### Performance Issues

**Slow queries:**
```bash
# Analyze database and rebuild indexes
python scripts/fix_performance_post_migration.py
```

**Large database size:**
```bash
# Check for duplicate indexes
python scripts/diagnose_db_size.py

# Remove duplicates
python scripts/remove_duplicate_indexes.py
```

### Web Interface Issues

**Port already in use:**
```bash
# Change port in run_web.py or specify via environment
PORT=8001 python run_web.py
```

**Can't connect to web interface:**
- Check firewall settings
- Verify server is running: `ps aux | grep run_web`
- Check logs in terminal output

---

## 📚 Additional Resources

### File Monitoring

For automatic file intake, set up a cron job or systemd service:

```bash
# Cron example (every 30 minutes)
*/30 * * * * cd /path/to/astro_cat && ./venv/bin/python main.py scan && ./venv/bin/python main.py catalog
```

### Obsidian Integration

Session notes are stored as Markdown files compatible with Obsidian:

1. Add notes directory to Obsidian vault
2. Use `[[links]]` to reference between sessions
3. Add tags for organization: `#M31 #LRGB #stacked`

### PixInsight Integration

The file structure supports PixInsight workflows:

1. Processing sessions organize files by type
2. Use File Selector to find calibration frames
3. Export processed files to `processing/<session>/final/`
4. Files are auto-cataloged when placed in session directories

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## 📜 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- Built for the astrophotography community
- Optimized for large FITS file collections
- Designed to integrate with popular processing tools (PixInsight, etc.)
- Inspired by the need for better data management in amateur astrophotography

---

## 📞 Support

- **Issues**: https://github.com/smartc/astro_cat/issues
- **Discussions**: https://github.com/smartc/astro_cat/discussions
- **Documentation**: See `docs/` directory (coming soon)

---

**Happy imaging! 🔭✨**
