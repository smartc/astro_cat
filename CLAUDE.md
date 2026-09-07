# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

**astro_cat** is a Python toolkit for managing astrophotography FITS files: scanning raw files from a quarantine directory, extracting metadata, organizing into a library, tracking imaging/processing sessions, and backing up to AWS S3. It has both a CLI (Click) and a web UI (FastAPI + Vue.js 3 SPA).

## Running the Application

```bash
# Activate venv first
source venv/bin/activate

# CLI entry point
python main.py --help

# Web server (http://localhost:8000)
python run_web.py

# Port overrides via environment
ASTROCAT_PORT=8001 python run_web.py
```

Secondary services started by the web server:
- `8081` — sqlite_web database browser
- `8082` — WebDAV server
- `8083` — S3 backup UI

## CLI Workflow

The typical intake pipeline runs in order:

```bash
python main.py scan raw              # detect new FITS files in quarantine
python main.py catalog raw           # extract FITS headers into DB
python main.py validate raw          # score file quality
python main.py migrate raw           # move files to library (add --dry-run first)
python main.py list imaging-sessions # query what was imported
python main.py stats summary         # collection-wide statistics
```

## Setup (first time)

```bash
pip install -r requirements.txt
cp config.json.template config.json  # then edit paths
python install_frontend_libs.py      # downloads Vue/Axios/Tailwind from CDN into static/lib/
```

## Testing

There is no automated test suite. Verification is done via:

```bash
python test_phase4_models.py         # model correctness after Phase 4 migration
python scripts/verify_phase3.py      # migration verification
python scripts/diagnose_db_size.py   # database analysis
python scripts/diagnose_performance.py
```

Linting/formatting:
```bash
black .
isort .
pylint <file>
ruff check .
```

## Architecture

### Layer Overview

```
CLI (cli/)          ──►  core modules  ──►  models.py (SQLAlchemy)  ──►  SQLite
Web (web/app.py)    ──►  core modules  ──/
Frontend (static/)  ──►  FastAPI routes (web/routes/)
```

### Core Modules

| Module | Purpose |
|--------|---------|
| `models.py` | SQLAlchemy ORM — `FitsFile`, `ImagingSession`, `ProcessingSession`, `ProcessingSessionFile`, `ObjectProcessingLog` |
| `config.py` | Pydantic-based config loaded from `config.json`; expands env vars and `~` in paths |
| `file_organizer.py` | Moves files from quarantine → library with standardized naming |
| `file_selector.py` | Selects calibration frames for a processing session |
| `file_monitor.py` | Watchdog-based directory monitoring for auto-intake |
| `validation.py` | Scores files for metadata completeness |
| `equipment_manager.py` | Loads camera/telescope/filter definitions from JSON files |
| `processing_session_manager.py` | Manages processing workflows end-to-end |

### Database Schema (key tables)

- **`fits_files`** — one row per FITS file; 100+ columns including all FITS header values, `imaging_session_id` FK, `frame_type`, `imgsess` (session stamp in FITS header)
- **`imaging_sessions`** — grouped capture sessions; primary key is a string ID (not integer)
- **`processing_sessions`** — processing workflows; linked to imaging sessions
- **`processing_session_files`** — M2M join between processing sessions and source files

### Web Routes (`web/routes/`)

Each file corresponds to a logical API group mounted in `web/app.py`. All routes return JSON. The frontend in `static/` is a Vue 3 SPA that calls these endpoints via `static/js/services/api-service.js`.

### Configuration

`config.json` (from template) is the sole config file. Key sections:
- `paths` — quarantine_dir, image_dir, database_path, processing_dir, notes_dir
- `database` — connection string, table name overrides
- `file_monitoring` — extensions, scan interval, auto_process flag
- `equipment` — paths to cameras.json, telescopes.json, filters.json
- `logging` — level, file, rotation

Equipment definitions are stored in separate JSON files (`cameras.json`, `telescopes.json`, `filters.json`).

## Important Naming Conventions (Phase 4)

The codebase went through four migration phases. Phase 4 (complete) removed all backward-compatibility aliases. Use only the **current** names:

| Old (removed) | Current |
|---------------|---------|
| `Session` | `ImagingSession` |
| `file.imaging_session_id` was `file.session_id` | `file.imaging_session_id` |
| `session.id` was `session.session_id` | `session.id` |
| `session.date` was `session.session_date` | `session.date` |
| `file.width_pixels` was `file.x` | `file.width_pixels` |
| `file.height_pixels` was `file.y` | `file.height_pixels` |
| FITS keyword `IMG_SESS` | `IMGSESS` |

Do not introduce `Session` aliases or old column names anywhere in new code.

## File Organization on Disk

The library organizes files under `image_dir` as:
- Light frames: `{object}/{camera}/{telescope}/{filter}/{date}/`
- Calibration: `CALIBRATION/{camera}/{type}/{filter_or_exposure}/{date}/`
- Processing outputs: `processing/{session_id}/{calibration,intermediate,final}/`

## Database Migrations

Ad-hoc migration scripts live in `migrations/` (Alembic is installed but migrations are mostly manual scripts). When adding columns, prefer adding a script to `migrations/` and updating both `models.py` and any affected route handlers.
