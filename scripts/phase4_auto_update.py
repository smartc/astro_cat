#!/usr/bin/env python3
"""
Automated update script for Phase 4 - Remove backward compatibility

This script updates all Python files to use Phase 3 naming convention:
- FitsFile.session_id → FitsFile.imaging_session_id
- FitsFile.x → FitsFile.width_pixels (if used)
- FitsFile.y → FitsFile.height_pixels (if used)
- ImagingSession.session_id → ImagingSession.id
- ImagingSession.session_date → ImagingSession.date

Note: This is a best-effort automated replacement. Manual review is required.
"""

import re
import sys
from pathlib import Path

# Files to update
PYTHON_FILES_TO_UPDATE = [
    'file_selector.py',
    'web/routes/imaging_sessions.py',
    'web/utils.py',
    'cli/list_commands.py',
    'cli/imaging_session_commands.py',
]

# S3 backup files (separate list as they're extensive)
S3_FILES = [
    's3_backup/manager.py',
    's3_backup/cli.py',
    's3_backup/web_app.py',
    's3_backup/cleanup_orphan_notes.py',
]

def update_fits_file_references(content):
    """Update FitsFile.session_id to FitsFile.imaging_session_id"""
    # Pattern: f.session_id, file.session_id, file_obj.session_id, etc.
    # But NOT imaging_session.session_id, session_model.session_id, etc.

    # Replace FitsFile attribute access
    # Patterns like: f.session_id, file.session_id, file_obj.session_id
    content = re.sub(
        r'\bf\.session_id\b',
        'f.imaging_session_id',
        content
    )
    content = re.sub(
        r'\bfile\.session_id\b',
        'file.imaging_session_id',
        content
    )
    content = re.sub(
        r'\bfile_obj\.session_id\b',
        'file_obj.imaging_session_id',
        content
    )

    # Replace FitsFile column references in queries
    content = re.sub(
        r'\bFitsFile\.session_id\b',
        'FitsFile.imaging_session_id',
        content
    )

    return content

def update_imaging_session_references(content):
    """Update ImagingSession.session_id to ImagingSession.id"""

    # This is trickier - we need to identify when session_id is on ImagingSession
    # Common patterns:
    # - s.session_id (where s is from query(SessionModel))
    # - session.session_id (where session is ImagingSession)
    # - imaging_session.session_id
    # - SessionModel.session_id (column reference)

    # Replace SessionModel column references
    content = re.sub(
        r'\bSessionModel\.session_id\b',
        'SessionModel.id',
        content
    )
    content = re.sub(
        r'\bImagingSession\.session_id\b',
        'ImagingSession.id',
        content
    )

    # Replace imaging_session.session_id
    content = re.sub(
        r'\bimaging_session\.session_id\b',
        'imaging_session.id',
        content
    )

    # Replace session.session_id (but only in imaging session contexts)
    # This is risky - might catch processing sessions too
    # Let's be conservative and skip this one for now

    # Replace s.session_id in query contexts
    # Also risky - let's skip

    return content

def update_imaging_session_date(content):
    """Update ImagingSession.session_date to ImagingSession.date"""

    # Replace SessionModel.session_date
    content = re.sub(
        r'\bSessionModel\.session_date\b',
        'SessionModel.date',
        content
    )
    content = re.sub(
        r'\bImagingSession\.session_date\b',
        'ImagingSession.date',
        content
    )

    # Replace s.session_date, session.session_date, imaging_session.session_date
    content = re.sub(
        r'\bs\.session_date\b',
        's.date',
        content
    )
    content = re.sub(
        r'\bsession\.session_date\b',
        'session.date',
        content
    )
    content = re.sub(
        r'\bimaging_session\.session_date\b',
        'imaging_session.date',
        content
    )
    content = re.sub(
        r'\bsession_model\.session_date\b',
        'session_model.date',
        content
    )

    return content

def process_file(file_path):
    """Process a single file."""
    print(f"Processing {file_path}...")

    try:
        with open(file_path, 'r') as f:
            content = f.read()

        original_content = content

        # Apply replacements
        content = update_fits_file_references(content)
        content = update_imaging_session_references(content)
        content = update_imaging_session_date(content)

        if content != original_content:
            # Backup original
            backup_path = file_path.parent / f"{file_path.name}.phase4_backup"
            with open(backup_path, 'w') as f:
                f.write(original_content)

            # Write updated content
            with open(file_path, 'w') as f:
                f.write(content)

            print(f"  ✓ Updated (backup saved to {backup_path.name})")
            return True
        else:
            print(f"  - No changes needed")
            return False

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False

def main():
    """Main entry point."""
    base_path = Path(__file__).parent.parent

    print("="*60)
    print("PHASE 4 AUTOMATED UPDATE")
    print("="*60)
    print()
    print("This script will update Python files to use Phase 3 naming.")
    print("Backups will be created with .phase4_backup extension.")
    print()

    # Get confirmation
    response = input("Continue? (yes/no): ")
    if response.lower() != 'yes':
        print("Cancelled.")
        return 0

    print()

    updated_count = 0

    # Process main files
    all_files = PYTHON_FILES_TO_UPDATE + S3_FILES

    for file_rel in all_files:
        file_path = base_path / file_rel
        if file_path.exists():
            if process_file(file_path):
                updated_count += 1
        else:
            print(f"  ⚠ File not found: {file_rel}")

    print()
    print("="*60)
    print(f"✓ Updated {updated_count} files")
    print("="*60)
    print()
    print("Next steps:")
    print("1. Review the changes with: git diff")
    print("2. Test the application")
    print("3. Remove synonyms from models.py")
    print("4. Run: python scripts/verify_phase3.py")
    print()
    print("To restore backups if needed:")
    print("  find . -name '*.phase4_backup' -exec bash -c 'mv \"$0\" \"${0%.phase4_backup}\"' {} \\;")

    return 0

if __name__ == '__main__':
    sys.exit(main())
