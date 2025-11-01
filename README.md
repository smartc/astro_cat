# astro_cat

**astro_cat** is a toolkit for managing, cataloging, and archiving astrophotography data.  
It streamlines raw image intake (FITS), session organization, notes, and S3 backups—with a simple web dashboard for status and stats.

---

## 🚀 Features

- 🔭 **Image Cataloging** — Monitor designated folders for new FITS files, automatically extract metadata, and organize them into a catalog of raw images.  
- 🧩 **Processing Workflow** — Organize raw files into processing sessions, locate appropriate calibration data, and catalog final products when processing is complete.  
- 🧮 **Metadata Catalogs** — Build searchable **SQLite** catalogs with complete image metadata. Maintain Markdown‑style notes for imaging and processing sessions, compatible with **Obsidian**.  
- 🧰 **CLI Utilities** — Helper tools for safe deletions (`safe_unlink`), dry‑runs, and sync validation.  
- 📊 **Dashboard Support** — HTML/JS dashboard visualizing local vs. remote sync status, storage usage, and file distribution.  
- 🔌 **Integration Ready** — Works with PixInsight, Voyager, Node‑RED, and custom Python scripts.  
- ☁️ **S3 Backup & Lifecycle** — Automate incremental backups from local drives to AWS S3 with MD5 checksum verification, versioning, and lifecycle transitions (e.g., Glacier → Deep Archive).  

---

## ⚙️ Installation

```bash
git clone https://github.com/smartc/astro_cat.git
cd astro_cat
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
pip install -r requirements.txt
```

Editable install (optional for contributors):
```bash
pip install -e .
```

---

## 🧭 Quick Start

1) **Set your configuration** in `config.json` (paths, buckets, options).  
2) **Start the monitor** (detects new FITS and extracts metadata):  
```bash
python file_monitor.py
```
3) **Organize files** into processing sessions:  
```bash
python processing_session_manager.py
```
4) **Run the web dashboard** (optional):  
```bash
python run_web.py
# Then open the printed URL in your browser
```

> Tip: See `file_organizer.py`, `file_selector.py`, and `fits_processor.py` for focused utilities.


---

## 📂 Project Layout

```
astro_cat/
├─ processing/                     # Processing helpers / scripts
├─ static/                         # Web assets (CSS/JS/images)
├─ web/                            # Web UI / templates & frontend
├─ cameras.json                    # Equipment definitions
├─ filters.json
├─ telescopes.json
├─ config.json                     # Runtime configuration
├─ config.py                       # Python config helpers
├─ equipment_manager.py            # Equipment registry helpers
├─ file_monitor.py                 # Directory watcher & metadata extraction
├─ file_organizer.py               # Move/organize files by session
├─ file_selector.py                # Find files by criteria
├─ fits_processor.py               # FITS-specific processing helpers
├─ object_processor.py             # Object/target-based helpers
├─ processing_session_manager.py   # Create/manage processing sessions
├─ models.py                       # Data models (catalog, sessions, etc.)
├─ validation.py                   # Validators for inputs/paths/metadata
├─ main.py                         # Entrypoint for selected workflows
├─ run_web.py                      # Launch the dashboard
├─ requirements.txt
└─ LICENSE
```

---

## 📝 Notes & Best Practices

- Keep your **imaging** and **processing session** notes in Markdown so they remain Obsidian‑friendly.  
- Use **dry runs** before any large re‑organize or backup.  
- Favor **stable paths** (e.g., mounted NAS like `/mnt/ganymede/...`) to simplify monitors and backups.  

---

## 📜 License

MIT — see [LICENSE](LICENSE).

