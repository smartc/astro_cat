#!/usr/bin/env bash

################################################################################
# astro_cat Initial Setup Script
#
# This script automates the initial setup of astro_cat, including:
# - Python virtual environment creation
# - Dependency installation
# - Frontend library installation
# - Directory structure creation
# - Configuration file setup
# - Equipment configuration
# - Database initialization
# - Optional S3 backup setup
#
# Usage: ./setup.sh
################################################################################

set -e  # Exit on error
set -o pipefail  # Exit on pipe failure

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

################################################################################
# Helper Functions
################################################################################

print_header() {
    echo -e "\n${CYAN}===================================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}===================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ $1${NC}"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to prompt for yes/no
prompt_yes_no() {
    local prompt="$1"
    local default="${2:-n}"
    local response

    if [[ "$default" == "y" ]]; then
        prompt="${prompt} [Y/n]: "
    else
        prompt="${prompt} [y/N]: "
    fi

    read -r -p "$prompt" response
    response=${response:-$default}

    [[ "$response" =~ ^[Yy]$ ]]
}

# Function to validate directory path
validate_path() {
    local path="$1"
    # Expand ~ to home directory
    path="${path/#\~/$HOME}"
    # Remove trailing slashes
    path="${path%/}"
    echo "$path"
}

################################################################################
# Welcome
################################################################################

show_welcome() {
    clear
    echo -e "${CYAN}"
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║                                                                ║"
    echo "║              astro_cat Initial Setup Script                    ║"
    echo "║                                                                ║"
    echo "║    FITS Image Cataloging and Astrophotography Data Manager    ║"
    echo "║                                                                ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo "This script will guide you through setting up astro_cat."
    echo ""
    echo -e "${YELLOW}What this script does:${NC}"
    echo "  • Creates a Python virtual environment"
    echo "  • Installs all required dependencies"
    echo "  • Sets up your directory structure"
    echo "  • Configures paths and settings"
    echo "  • Optionally configures equipment (cameras, telescopes, filters)"
    echo "  • Initializes the database"
    echo "  • Optionally sets up S3 cloud backup"
    echo ""
    echo -e "${YELLOW}Prerequisites:${NC}"
    echo "  • Python 3.8 or higher"
    echo "  • ~500MB of free disk space for dependencies"
    echo "  • Space for your FITS file storage (varies by usage)"
    echo ""

    if ! prompt_yes_no "Ready to begin?" "y"; then
        print_info "Setup cancelled by user"
        exit 0
    fi
}

################################################################################
# Python Environment Check
################################################################################

check_python() {
    print_header "Step 1: Checking Python Installation"

    if ! command_exists python3; then
        print_error "Python 3 is not installed"
        print_info "Please install Python 3.8 or higher and run this script again"
        print_info "Download from: https://www.python.org/downloads/"
        exit 1
    fi

    local python_version
    python_version=$(python3 --version | cut -d' ' -f2)
    local major_version
    major_version=$(echo "$python_version" | cut -d'.' -f1)
    local minor_version
    minor_version=$(echo "$python_version" | cut -d'.' -f2)

    print_success "Found Python $python_version"

    if [[ $major_version -lt 3 ]] || [[ $major_version -eq 3 && $minor_version -lt 8 ]]; then
        print_error "Python 3.8 or higher is required"
        print_error "Current version: $python_version"
        exit 1
    fi

    print_success "Python version is compatible"
}

################################################################################
# Virtual Environment
################################################################################

setup_virtual_environment() {
    print_header "Step 2: Setting Up Virtual Environment"

    cd "$SCRIPT_DIR"

    if [[ -d "venv" ]]; then
        print_warning "Virtual environment already exists"
        if prompt_yes_no "Do you want to recreate it?" "n"; then
            print_info "Removing existing virtual environment..."
            rm -rf venv
        else
            print_info "Using existing virtual environment"
            return 0
        fi
    fi

    print_info "Creating virtual environment..."
    if python3 -m venv venv; then
        print_success "Virtual environment created"
    else
        print_error "Failed to create virtual environment"
        exit 1
    fi
}

################################################################################
# Dependencies
################################################################################

install_dependencies() {
    print_header "Step 3: Installing Python Dependencies"

    cd "$SCRIPT_DIR"

    # Activate virtual environment
    print_info "Activating virtual environment..."
    source venv/bin/activate

    # Upgrade pip
    print_info "Upgrading pip..."
    pip install --upgrade pip --quiet

    # Install requirements
    print_info "Installing dependencies from requirements.txt..."
    print_warning "This may take a few minutes..."

    if pip install -r requirements.txt --quiet; then
        print_success "Dependencies installed successfully"
    else
        print_error "Failed to install dependencies"
        exit 1
    fi
}

################################################################################
# Frontend Libraries
################################################################################

install_frontend_libraries() {
    print_header "Step 4: Installing Frontend Libraries"

    cd "$SCRIPT_DIR"
    source venv/bin/activate

    print_info "Installing Vue.js, Axios, Toast UI Editor, and Tailwind CSS..."

    if python install_frontend_libs.py; then
        print_success "Frontend libraries installed"
    else
        print_error "Failed to install frontend libraries"
        print_warning "You can try running 'python install_frontend_libs.py' manually later"
    fi
}

################################################################################
# Path Configuration
################################################################################

configure_paths() {
    print_header "Step 5: Configuring Directory Paths"

    echo "astro_cat needs to know where to store your files."
    echo ""
    echo -e "${CYAN}Directory Structure:${NC}"
    echo "  • Quarantine:  Incoming raw FITS files from your camera/acquisition software"
    echo "  • Images:      Organized library (files moved from Quarantine after cataloging)"
    echo "  • Processing:  Processing sessions with calibration and final outputs"
    echo "  • Database:    SQLite database file storing metadata"
    echo "  • Notes:       Markdown session notes (Obsidian-compatible)"
    echo ""

    # Get base path
    while true; do
        echo -e "${CYAN}Enter the base path for your astro_cat data:${NC}"
        echo -e "${CYAN}(This directory will contain all subdirectories)${NC}"
        read -r -p "Base path: " BASE_PATH

        BASE_PATH=$(validate_path "$BASE_PATH")

        if [[ -z "$BASE_PATH" ]]; then
            print_error "Base path cannot be empty"
            continue
        fi

        # Show what will be created
        echo ""
        echo -e "${CYAN}The following structure will be created:${NC}"
        echo "  $BASE_PATH/"
        echo "  ├── Quarantine/        (incoming raw FITS files)"
        echo "  ├── Images/            (organized library)"
        echo "  ├── Processing/        (processing sessions)"
        echo "  ├── Session_Notes/     (markdown notes)"
        echo "  └── fits_catalog.db    (database file)"
        echo ""

        if prompt_yes_no "Is this correct?" "y"; then
            break
        fi
    done

    # Set default subdirectories
    QUARANTINE_DIR="$BASE_PATH/Quarantine"
    IMAGE_DIR="$BASE_PATH/Images"
    PROCESSING_DIR="$BASE_PATH/Processing"
    NOTES_DIR="$BASE_PATH/Session_Notes"
    DATABASE_PATH="$BASE_PATH/fits_catalog.db"
    RESTORE_FOLDER="$BASE_PATH/.tmp/restore"

    echo ""
    if prompt_yes_no "Would you like to customize the subdirectory names?" "n"; then
        echo ""
        read -r -p "Quarantine directory [$QUARANTINE_DIR]: " custom_quarantine
        [[ -n "$custom_quarantine" ]] && QUARANTINE_DIR=$(validate_path "$custom_quarantine")

        read -r -p "Image library directory [$IMAGE_DIR]: " custom_image
        [[ -n "$custom_image" ]] && IMAGE_DIR=$(validate_path "$custom_image")

        read -r -p "Processing directory [$PROCESSING_DIR]: " custom_processing
        [[ -n "$custom_processing" ]] && PROCESSING_DIR=$(validate_path "$custom_processing")

        read -r -p "Notes directory [$NOTES_DIR]: " custom_notes
        [[ -n "$custom_notes" ]] && NOTES_DIR=$(validate_path "$custom_notes")

        read -r -p "Database file path [$DATABASE_PATH]: " custom_db
        [[ -n "$custom_db" ]] && DATABASE_PATH=$(validate_path "$custom_db")

        read -r -p "Restore folder [$RESTORE_FOLDER]: " custom_restore
        [[ -n "$custom_restore" ]] && RESTORE_FOLDER=$(validate_path "$custom_restore")
    fi

    # Create directories
    print_info "Creating directory structure..."
    mkdir -p "$QUARANTINE_DIR"
    mkdir -p "$IMAGE_DIR"
    mkdir -p "$PROCESSING_DIR"
    mkdir -p "$NOTES_DIR"
    mkdir -p "$(dirname "$DATABASE_PATH")"
    mkdir -p "$RESTORE_FOLDER"

    print_success "Directories created"

    # Generate config.json
    print_info "Generating config.json..."

    cat > "$SCRIPT_DIR/config.json" << EOF
{
  "_comment": "Generated by setup.sh - customize as needed",
  "_comment_paths": "All paths configured during initial setup",

  "paths": {
    "quarantine_dir": "$QUARANTINE_DIR",
    "image_dir": "$IMAGE_DIR",
    "processing_dir": "$PROCESSING_DIR",
    "database_path": "$DATABASE_PATH",
    "restore_folder": "$RESTORE_FOLDER",
    "notes_dir": "$NOTES_DIR"
  },
  "database": {
    "type": "sqlite",
    "connection_string": "sqlite:///{{database_path}}",
    "tables": {
      "fits_files": "fits_files",
      "process_log": "process_log",
      "cameras": "cameras",
      "telescopes": "telescopes"
    }
  },
  "file_monitoring": {
    "scan_interval_minutes": 30,
    "ignore_newer_than_minutes": 30
  },
  "equipment": {
    "cameras_file": "cameras.json",
    "telescopes_file": "telescopes.json",
    "filters_file": "filters.json"
  },
  "logging": {
    "level": "INFO",
    "file": "fits_cataloger.log",
    "max_bytes": 10485760,
    "backup_count": 5
  },
  "timezone_offset": 0
}
EOF

    print_success "Configuration file created: $SCRIPT_DIR/config.json"
}

################################################################################
# Equipment Configuration
################################################################################

configure_equipment() {
    print_header "Step 6: Equipment Configuration"

    echo "astro_cat can track your cameras, telescopes, and filters."
    echo ""

    # Check if equipment files already exist with data
    local has_cameras=false
    local has_telescopes=false
    local has_filters=false

    if [[ -f "$SCRIPT_DIR/cameras.json" ]]; then
        local camera_count
        camera_count=$(python3 -c "import json; print(len(json.load(open('$SCRIPT_DIR/cameras.json'))))" 2>/dev/null || echo 0)
        if [[ $camera_count -gt 0 ]]; then
            has_cameras=true
            print_info "Found existing cameras.json with $camera_count camera(s)"
        fi
    fi

    if [[ -f "$SCRIPT_DIR/telescopes.json" ]]; then
        local telescope_count
        telescope_count=$(python3 -c "import json; print(len(json.load(open('$SCRIPT_DIR/telescopes.json'))))" 2>/dev/null || echo 0)
        if [[ $telescope_count -gt 0 ]]; then
            has_telescopes=true
            print_info "Found existing telescopes.json with $telescope_count telescope(s)"
        fi
    fi

    if [[ -f "$SCRIPT_DIR/filters.json" ]]; then
        local filter_count
        filter_count=$(python3 -c "import json; print(len(json.load(open('$SCRIPT_DIR/filters.json'))))" 2>/dev/null || echo 0)
        if [[ $filter_count -gt 0 ]]; then
            has_filters=true
            print_info "Found existing filters.json with $filter_count filter(s)"
        fi
    fi

    if [[ "$has_cameras" == true && "$has_telescopes" == true && "$has_filters" == true ]]; then
        echo ""
        print_success "Equipment files already configured!"
        if prompt_yes_no "Would you like to keep your existing equipment configuration?" "y"; then
            print_info "Using existing equipment configuration"
            return 0
        fi
    fi

    echo ""
    echo "Choose an option:"
    echo "  1) Add equipment now (interactive)"
    echo "  2) Use existing equipment files (if you've already edited them)"
    echo "  3) Skip equipment setup (you can configure it later)"
    echo ""

    read -r -p "Enter choice [1-3]: " equipment_choice

    case "$equipment_choice" in
        1)
            configure_equipment_interactive
            ;;
        2)
            print_info "Using existing equipment files"
            if [[ ! -f "$SCRIPT_DIR/cameras.json" ]]; then
                echo "[]" > "$SCRIPT_DIR/cameras.json"
            fi
            if [[ ! -f "$SCRIPT_DIR/telescopes.json" ]]; then
                echo "[]" > "$SCRIPT_DIR/telescopes.json"
            fi
            if [[ ! -f "$SCRIPT_DIR/filters.json" ]]; then
                echo "[]" > "$SCRIPT_DIR/filters.json"
            fi
            ;;
        3)
            print_info "Skipping equipment setup"
            # Create empty equipment files if they don't exist
            [[ ! -f "$SCRIPT_DIR/cameras.json" ]] && echo "[]" > "$SCRIPT_DIR/cameras.json"
            [[ ! -f "$SCRIPT_DIR/telescopes.json" ]] && echo "[]" > "$SCRIPT_DIR/telescopes.json"
            [[ ! -f "$SCRIPT_DIR/filters.json" ]] && echo "[]" > "$SCRIPT_DIR/filters.json"
            ;;
        *)
            print_warning "Invalid choice, skipping equipment setup"
            ;;
    esac
}

configure_equipment_interactive() {
    print_info "Interactive equipment configuration"
    echo ""

    # Configure cameras
    echo -e "${CYAN}Camera Configuration${NC}"
    echo "Add your camera(s) - press Enter with empty camera name when done"

    local cameras="[]"
    while true; do
        echo ""
        read -r -p "Camera name (or Enter to finish): " camera_name
        [[ -z "$camera_name" ]] && break

        read -r -p "  Brand (e.g., ZWO, Canon): " camera_brand
        read -r -p "  Type (CMOS, CCD, DSLR): " camera_type
        read -r -p "  Resolution X (pixels): " camera_x
        read -r -p "  Resolution Y (pixels): " camera_y
        read -r -p "  Pixel size (μm): " camera_pixel
        read -r -p "  Bin (default 1): " camera_bin
        camera_bin=${camera_bin:-1}
        read -r -p "  Color (RGB)? [y/N]: " camera_rgb
        [[ "$camera_rgb" =~ ^[Yy]$ ]] && camera_rgb="true" || camera_rgb="false"
        read -r -p "  Comments: " camera_comments

        # Add to cameras array
        cameras=$(echo "$cameras" | python3 -c "
import sys, json
cameras = json.load(sys.stdin)
cameras.append({
    'camera': '$camera_name',
    'brand': '$camera_brand',
    'type': '$camera_type',
    'x': int('$camera_x'),
    'y': int('$camera_y'),
    'pixel': float('$camera_pixel'),
    'bin': int('$camera_bin'),
    'rgb': $camera_rgb,
    'comments': '$camera_comments'
})
print(json.dumps(cameras, indent=2))
")

        print_success "Added camera: $camera_name"
    done

    echo "$cameras" > "$SCRIPT_DIR/cameras.json"

    # Configure telescopes
    echo ""
    echo -e "${CYAN}Telescope Configuration${NC}"
    echo "Add your telescope(s)/lens(es) - press Enter with empty scope name when done"

    local telescopes="[]"
    while true; do
        echo ""
        read -r -p "Telescope/Lens name (or Enter to finish): " scope_name
        [[ -z "$scope_name" ]] && break

        read -r -p "  Make/Brand: " scope_make
        read -r -p "  Type (Refractor, Reflector, Lens): " scope_type
        read -r -p "  Subtype (e.g., APO, Newtonian, SCT): " scope_subtype
        read -r -p "  Focal length (mm): " scope_focal
        read -r -p "  Aperture (mm, optional): " scope_aperture
        read -r -p "  Comments: " scope_comments

        # Add to telescopes array
        telescopes=$(echo "$telescopes" | python3 -c "
import sys, json
telescopes = json.load(sys.stdin)
telescopes.append({
    'scope': '$scope_name',
    'make': '$scope_make',
    'type': '$scope_type',
    'subtype': '$scope_subtype',
    'focal': int('$scope_focal') if '$scope_focal' else '',
    'aperture': int('$scope_aperture') if '$scope_aperture' else '',
    'comments': '$scope_comments'
})
print(json.dumps(telescopes, indent=2))
")

        print_success "Added telescope: $scope_name"
    done

    echo "$telescopes" > "$SCRIPT_DIR/telescopes.json"

    # Configure filters
    echo ""
    echo -e "${CYAN}Filter Configuration${NC}"
    echo "Add your filters - press Enter with empty filter name when done"
    echo "(Map raw filter names from FITS headers to proper names)"

    local filters="[]"
    while true; do
        echo ""
        read -r -p "Raw filter name from FITS (or Enter to finish): " filter_raw
        [[ -z "$filter_raw" ]] && break

        read -r -p "  Proper name (e.g., L, R, G, B, Ha-7nm): " filter_proper

        # Add to filters array
        filters=$(echo "$filters" | python3 -c "
import sys, json
filters = json.load(sys.stdin)
filters.append({
    'raw_name': '$filter_raw',
    'proper_name': '$filter_proper'
})
print(json.dumps(filters, indent=2))
")

        print_success "Added filter mapping: $filter_raw → $filter_proper"
    done

    echo "$filters" > "$SCRIPT_DIR/filters.json"

    print_success "Equipment configuration saved"
}

################################################################################
# Database Initialization
################################################################################

initialize_database() {
    print_header "Step 7: Initializing Database"

    cd "$SCRIPT_DIR"
    source venv/bin/activate

    print_info "Testing database initialization..."

    # Test by running a simple command that will create the database
    if python main.py list imaging-sessions &>/dev/null; then
        print_success "Database initialized successfully"
    else
        print_warning "Database initialization test completed (this is normal for first run)"
    fi

    if [[ -f "$DATABASE_PATH" ]]; then
        print_success "Database file created: $DATABASE_PATH"
    else
        print_info "Database will be created on first use"
    fi
}

################################################################################
# S3 Setup
################################################################################

setup_s3_backup() {
    print_header "Step 8: S3 Cloud Backup (Optional)"

    echo "astro_cat supports automated backups to AWS S3 with cost-effective"
    echo "lifecycle management (Glacier Deep Archive)."
    echo ""
    echo -e "${CYAN}Benefits:${NC}"
    echo "  • Automated cloud backups of all imaging sessions"
    echo "  • Cost-effective storage (~\$0.82/month for 827GB)"
    echo "  • Automatic transition to deep archive storage"
    echo "  • Integrity verification with MD5 checksums"
    echo ""

    if prompt_yes_no "Would you like to set up S3 backup now?" "n"; then
        if [[ -f "$SCRIPT_DIR/s3_backup/setup_s3_bucket.sh" ]]; then
            print_info "Launching S3 setup script..."
            echo ""
            bash "$SCRIPT_DIR/s3_backup/setup_s3_bucket.sh"
        else
            print_error "S3 setup script not found"
            print_info "You can set up S3 manually later using: ./s3_backup/setup_s3_bucket.sh"
        fi
    else
        print_info "Skipping S3 setup"
        print_info "You can run it later with: ./s3_backup/setup_s3_bucket.sh"
    fi
}

################################################################################
# Final Steps
################################################################################

show_completion() {
    print_header "Setup Complete!"

    echo -e "${GREEN}astro_cat has been successfully set up!${NC}"
    echo ""
    echo -e "${CYAN}What was configured:${NC}"
    echo "  ✓ Python virtual environment"
    echo "  ✓ All dependencies installed"
    echo "  ✓ Frontend libraries installed"
    echo "  ✓ Directory structure created"
    echo "  ✓ Configuration file: config.json"
    echo "  ✓ Equipment configuration"
    echo "  ✓ Database initialized"
    echo ""
    echo -e "${CYAN}Your directories:${NC}"
    echo "  • Quarantine:  $QUARANTINE_DIR"
    echo "  • Images:      $IMAGE_DIR"
    echo "  • Processing:  $PROCESSING_DIR"
    echo "  • Notes:       $NOTES_DIR"
    echo "  • Database:    $DATABASE_PATH"
    echo ""
    echo -e "${CYAN}Next steps:${NC}"
    echo ""
    echo "1. Activate the virtual environment:"
    echo "   $ cd $SCRIPT_DIR"
    echo "   $ source venv/bin/activate"
    echo ""
    echo "2. Test the CLI:"
    echo "   $ python main.py --help"
    echo ""
    echo "3. Start the web interface:"
    echo "   $ python run_web.py"
    echo "   Then visit: http://localhost:8000"
    echo ""
    echo "4. Copy some FITS files to the quarantine directory and scan:"
    echo "   $ cp /path/to/your/fits/*.fits $QUARANTINE_DIR/"
    echo "   $ python main.py scan"
    echo "   $ python main.py catalog"
    echo ""
    echo "5. View your imaging sessions:"
    echo "   $ python main.py list imaging-sessions"
    echo ""
    echo -e "${CYAN}Useful commands:${NC}"
    echo "  • Scan for new files:    python main.py scan"
    echo "  • Catalog files:         python main.py catalog"
    echo "  • List sessions:         python main.py list imaging-sessions"
    echo "  • View statistics:       python main.py stats summary"
    echo "  • Web interface:         python run_web.py"
    echo ""
    echo -e "${CYAN}Documentation:${NC}"
    echo "  • README:           $SCRIPT_DIR/README.md"
    echo "  • S3 Backup Guide:  $SCRIPT_DIR/s3_backup/QUICK_START.md"
    echo ""
    echo -e "${GREEN}Happy imaging! 🔭✨${NC}"
    echo ""
}

################################################################################
# Main Script
################################################################################

main() {
    show_welcome
    check_python
    setup_virtual_environment
    install_dependencies
    install_frontend_libraries
    configure_paths
    configure_equipment
    initialize_database
    setup_s3_backup
    show_completion
}

# Run main function
main "$@"
