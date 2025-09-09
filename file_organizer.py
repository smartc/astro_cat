"""File organization and migration system for FITS Cataloger."""

import os
import re
import shutil
import logging
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import click
from tqdm import tqdm

from models import DatabaseService, FitsFile
from config import Config

logger = logging.getLogger(__name__)


class FileOrganizer:
    """Handles file organization and migration from quarantine to structured library."""
    
    def __init__(self, config: Config, db_service: DatabaseService):
        self.config = config
        self.db_service = db_service
        
    def get_next_catalog_id(self) -> int:
        """Get the next available catalog ID from database."""
        session = self.db_service.db_manager.get_session()
        try:
            # Find the highest existing catalog ID
            max_id = session.query(FitsFile.id).order_by(FitsFile.id.desc()).first()
            if max_id and max_id[0]:
                return max_id[0] + 1
            return 1
        finally:
            session.close()
    
    def strip_catalog_prefix(self, filename: str) -> str:
        """Strip existing 6-digit catalog ID prefix from filename."""
        # Match pattern like "000123_" at start of filename
        pattern = r'^\d{6}_'
        if re.match(pattern, filename):
            return re.sub(pattern, '', filename)
        return filename
    
    def generate_standardized_filename(self, file_data: Dict, sequence: int) -> str:
        """Generate standardized filename based on frame type and metadata."""
        frame_type = file_data.get('frame_type', 'UNKNOWN')
        camera = file_data.get('camera', 'UNKNOWN')
        
        # Format sequence number as 4-digit zero-padded
        seq_str = f"{sequence:04d}"
        
        if frame_type == 'LIGHT':
            obj = file_data.get('object', 'UNKNOWN')
            filter_name = file_data.get('filter', 'NONE')
            exposure = file_data.get('exposure', 0)
            mosaic = file_data.get('mosaic')
            
            # Clean object name for filename (remove invalid chars)
            obj_clean = re.sub(r'[^\w\-]', '_', str(obj))
            
            if mosaic:
                return f"{obj_clean}_{frame_type}_{filter_name}_{exposure}s_{mosaic}_{seq_str}.fits"
            else:
                return f"{obj_clean}_{frame_type}_{filter_name}_{exposure}s_{seq_str}.fits"
                
        elif frame_type == 'FLAT':
            telescope = file_data.get('telescope', 'UNKNOWN')
            filter_name = file_data.get('filter', 'NONE')
            exposure = file_data.get('exposure', 0)
            return f"{camera}_{frame_type}_{telescope}_{filter_name}_{exposure}s_{seq_str}.fits"
            
        elif frame_type == 'DARK':
            exposure = file_data.get('exposure', 0)
            # Check if this should be classified as FLAT_DARK
            if exposure <= 29:
                filter_name = file_data.get('filter', 'NONE')
                return f"{camera}_FLAT_DARK_{filter_name}_{seq_str}.fits"
            else:
                return f"{camera}_{frame_type}_{exposure}s_{seq_str}.fits"
            
        elif frame_type == 'BIAS':
            return f"{camera}_{frame_type}_{seq_str}.fits"
        
        # Fallback for unknown frame types
        return f"{camera}_{frame_type}_{seq_str}.fits"
    
    def determine_destination_path(self, file_data: Dict) -> str:
        """Determine destination folder path based on file metadata."""
        frame_type = file_data.get('frame_type')
        camera = file_data.get('camera', 'UNKNOWN')
        obs_date = file_data.get('obs_date')
        
        base_path = Path(self.config.paths.image_dir)
        
        if frame_type == 'LIGHT':
            obj = file_data.get('object', 'UNKNOWN')
            telescope = file_data.get('telescope', 'UNKNOWN')
            filter_name = file_data.get('filter', 'NONE')
            mosaic = file_data.get('mosaic')
            
            path = base_path / obj / camera / telescope / filter_name / obs_date
            if mosaic:
                path = path / str(mosaic)
                
        elif frame_type == 'FLAT':
            telescope = file_data.get('telescope', 'UNKNOWN')
            filter_name = file_data.get('filter', 'NONE')
            path = base_path / "CALIBRATION" / camera / "FLAT" / telescope / filter_name / obs_date
            
        elif frame_type == 'DARK':
            exposure = file_data.get('exposure', 0)
            
            # Check if this is a flat dark (≤29 seconds)
            if exposure <= 29:
                filter_name = file_data.get('filter', 'NONE')
                path = base_path / "CALIBRATION" / camera / "FLAT_DARK" / filter_name / obs_date
            else:
                path = base_path / "CALIBRATION" / camera / "DARK" / f"{exposure}s" / obs_date
                
        elif frame_type == 'BIAS':
            path = base_path / "CALIBRATION" / camera / "BIAS" / obs_date
            
        else:
            # Unknown frame type - put in a generic location
            path = base_path / "UNKNOWN" / camera / obs_date
        
        return str(path)
    
    def group_files_by_destination(self, file_records: List[Dict]) -> Dict[str, List[Dict]]:
        """Group files by their destination directory for sequential numbering."""
        groups = {}
        
        for record in file_records:
            dest_path = self.determine_destination_path(record)
            if dest_path not in groups:
                groups[dest_path] = []
            groups[dest_path].append(record)
        
        # Sort each group by observation timestamp
        for dest_path in groups:
            groups[dest_path].sort(key=lambda x: x.get('obs_timestamp') or datetime.min)
        
        return groups
    
    def _get_file_md5(self, filepath: str) -> str:
        """Calculate MD5 hash of file."""
        hash_md5 = hashlib.md5()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating MD5 for {filepath}: {e}")
            return ""
    
    def _delete_duplicates_folder(self):
        """Delete the duplicates folder and all its contents."""
        duplicates_folder = Path(self.config.paths.quarantine_dir) / "Duplicates"
        if duplicates_folder.exists():
            shutil.rmtree(duplicates_folder)
            logger.debug(f"Deleted duplicates folder: {duplicates_folder}")

    def _delete_bad_files_folder(self):
        """Delete the bad files folder and all its contents."""
        bad_files_folder = Path(self.config.paths.quarantine_dir) / "Bad"
        if bad_files_folder.exists():
            shutil.rmtree(bad_files_folder)
            logger.debug(f"Deleted bad files folder: {bad_files_folder}")
    
    def migrate_files(self, limit: Optional[int] = None, auto_cleanup: bool = False) -> Dict[str, int]:
        """
        Migrate files from quarantine to organized structure with database-first approach.
        
        Args:
            limit: Maximum number of files to process (None for all)
            
        Returns:
            Dict with migration statistics
        """
        click.echo("Starting file migration...")
        logger.info("Starting file migration...")
        
        stats = {
            'processed': 0,
            'moved': 0,
            'errors': 0,
            'skipped': 0,
            'duplicates_moved': 0,
            'bad_files_moved': 0
        }
        
        # Create special folders
        duplicates_folder = Path(self.config.paths.quarantine_dir) / "Duplicates"
        bad_files_folder = Path(self.config.paths.quarantine_dir) / "Bad"
        duplicates_folder.mkdir(exist_ok=True)
        bad_files_folder.mkdir(exist_ok=True)
        
        quarantine_path = Path(self.config.paths.quarantine_dir)
        session = self.db_service.db_manager.get_session()
        
        try:
            # STEP 1: Migrate files that have database records first
            click.echo("Getting files from database...")
            
            # Get database records for files still in quarantine
            db_files = session.query(FitsFile).filter(
                FitsFile.folder.like(f"%{self.config.paths.quarantine_dir}%")
            ).all()
            
            # Filter out files already in special folders
            files_to_migrate = []
            for db_file in db_files:
                file_path = Path(db_file.folder) / db_file.file
                if ("Duplicates" not in str(file_path) and 
                    "Bad" not in str(file_path) and 
                    file_path.exists()):
                    files_to_migrate.append(db_file)
            
            if limit and len(files_to_migrate) > limit:
                click.echo(f"Limiting migration to {limit} files")
                files_to_migrate = files_to_migrate[:limit]
            
            if files_to_migrate:
                click.echo(f"Migrating {len(files_to_migrate)} database files to organized structure...")
                
                # Convert database records to migration format
                migration_records = []
                for db_file in files_to_migrate:
                    record = {
                        'id': db_file.id,
                        'file': db_file.file,
                        'folder': db_file.folder,
                        'object': db_file.object,
                        'frame_type': db_file.frame_type,
                        'camera': db_file.camera,
                        'telescope': db_file.telescope,
                        'filter': db_file.filter,
                        'exposure': db_file.exposure,
                        'obs_date': db_file.obs_date,
                        'obs_timestamp': db_file.obs_timestamp,
                        'md5sum': db_file.md5sum,
                        'mosaic': getattr(db_file, 'mosaic', None)
                    }
                    migration_records.append(record)
                
                # Group by destination and migrate
                file_groups = self.group_files_by_destination(migration_records)
                next_catalog_id = self.get_next_catalog_id()
                current_catalog_id = next_catalog_id
                
                click.echo(f"Organizing into {len(file_groups)} destination folders...")
                
                with tqdm(total=len(migration_records), desc="Migrating files") as pbar:
                    for dest_path, group_files in file_groups.items():
                        # Create destination directory
                        os.makedirs(dest_path, exist_ok=True)
                        
                        # Process files in sequence
                        for seq_num, file_record in enumerate(group_files, 1):
                            try:
                                stats['processed'] += 1
                                
                                # Current file paths
                                old_filepath = Path(file_record['folder']) / file_record['file']
                                
                                # Skip if source file doesn't exist
                                if not old_filepath.exists():
                                    logger.warning(f"Source file not found: {old_filepath}")
                                    stats['skipped'] += 1
                                    pbar.update(1)
                                    continue
                                
                                # Generate new filename
                                new_filename = self.generate_standardized_filename(file_record, seq_num)
                                new_filepath = Path(dest_path) / new_filename
                                
                                # Store original filename (stripped of catalog prefix)
                                orig_filename = self.strip_catalog_prefix(file_record['file'])
                                
                                # Move file
                                shutil.move(str(old_filepath), str(new_filepath))
                                
                                # Update database record
                                db_record = session.query(FitsFile).filter_by(id=file_record['id']).first()
                                if db_record:
                                    db_record.id = current_catalog_id
                                    db_record.file = new_filename
                                    db_record.folder = dest_path
                                    db_record.orig_file = orig_filename
                                    db_record.orig_folder = file_record['folder']
                                    
                                    current_catalog_id += 1
                                
                                stats['moved'] += 1
                                
                            except Exception as e:
                                logger.error(f"Error processing file {file_record['file']}: {e}")
                                stats['errors'] += 1
                            
                            pbar.update(1)
                
                # Commit database changes
                session.commit()
                click.echo(f"Database migration complete: {stats['moved']} files moved")
            
            # STEP 2: Handle remaining physical files in quarantine
            click.echo("Scanning for remaining files to categorize...")
            
            # Find all remaining physical files (excluding special folders)
            remaining_files = []
            for ext in ['.fits', '.fit', '.fts']:
                files = list(quarantine_path.rglob(f"*{ext}"))
                # Filter out special folders
                files = [f for f in files if not any(folder in str(f) for folder in ["Duplicates", "Bad"])]
                remaining_files.extend(files)
            
            if remaining_files:
                click.echo(f"Found {len(remaining_files)} remaining files to categorize...")
                
                duplicates_to_move = []
                bad_files_to_move = []
                
                with tqdm(total=len(remaining_files), desc="Categorizing files") as pbar:
                    for physical_file in remaining_files:
                        
                        # Check if it's a bad file
                        if "BAD_" in physical_file.name:
                            bad_files_to_move.append(physical_file)
                            pbar.update(1)
                            continue
                        
                        # Check if it's a duplicate by MD5
                        md5_hash = self._get_file_md5(str(physical_file))
                        if md5_hash:
                            existing_record = session.query(FitsFile).filter_by(md5sum=md5_hash).first()
                            if existing_record:
                                # Check if original exists in organized structure
                                original_path = Path(existing_record.folder) / existing_record.file
                                if original_path.exists():
                                    duplicates_to_move.append(physical_file)
                                else:
                                    logger.warning(f"Found file with database record but missing original: {physical_file}")
                        
                        pbar.update(1)
                
                # Move bad files
                if bad_files_to_move:
                    click.echo(f"Moving {len(bad_files_to_move)} bad files...")
                    with tqdm(total=len(bad_files_to_move), desc="Moving bad files") as pbar:
                        for bad_file in bad_files_to_move:
                            try:
                                bad_dest = bad_files_folder / bad_file.name
                                shutil.move(str(bad_file), str(bad_dest))
                                stats['bad_files_moved'] += 1
                                logger.debug(f"Moved bad file: {bad_file} -> {bad_dest}")
                            except Exception as e:
                                logger.error(f"Error moving bad file {bad_file}: {e}")
                                stats['errors'] += 1
                            pbar.update(1)
                
                # Move duplicates
                if duplicates_to_move:
                    click.echo(f"Moving {len(duplicates_to_move)} duplicate files...")
                    with tqdm(total=len(duplicates_to_move), desc="Moving duplicates") as pbar:
                        for duplicate_file in duplicates_to_move:
                            try:
                                duplicate_dest = duplicates_folder / duplicate_file.name
                                shutil.move(str(duplicate_file), str(duplicate_dest))
                                stats['duplicates_moved'] += 1
                                logger.debug(f"Moved duplicate: {duplicate_file} -> {duplicate_dest}")
                            except Exception as e:
                                logger.error(f"Error moving duplicate {duplicate_file}: {e}")
                                stats['errors'] += 1
                            pbar.update(1)
            
        except Exception as e:
            logger.error(f"Error during migration: {e}")
            session.rollback()
            raise
        finally:
            session.close()
        
        # STEP 3: Cleanup empty folders
        try:
            click.echo("Cleaning up empty folders...")
            removed_count = self._cleanup_empty_folders()
            if removed_count > 0:
                click.echo(f"Removed {removed_count} empty folders")
        except Exception as e:
            logger.error(f"Error during folder cleanup: {e}")
        
        # STEP 4: Handle duplicates folder cleanup prompt
        remaining_duplicates = list(duplicates_folder.glob("*.fit*")) if duplicates_folder.exists() else []
        remaining_bad_files = list(bad_files_folder.glob("*.fit*")) if bad_files_folder.exists() else []

        if remaining_duplicates:
            click.echo(f"Found {len(remaining_duplicates)} files in duplicates folder")
            if auto_cleanup:
                self._delete_duplicates_folder()
                click.echo("Duplicate files deleted automatically")
            else:
                try:
                    response = input(f"\nDelete {len(remaining_duplicates)} duplicate files? (y/N): ").lower().strip()
                    if response == 'y':
                        self._delete_duplicates_folder()
                        click.echo("Duplicate files deleted")
                    else:
                        click.echo("Duplicate files kept for manual review")
                except KeyboardInterrupt:
                    click.echo("User interrupted. Duplicate files kept for manual review")

        if remaining_bad_files:
            click.echo(f"Found {len(remaining_bad_files)} files in bad files folder")
            if auto_cleanup:
                self._delete_bad_files_folder()
                click.echo("Bad files deleted automatically")
            else:
                try:
                    response = input(f"\nDelete {len(remaining_bad_files)} bad files? (y/N): ").lower().strip()
                    if response == 'y':
                        self._delete_bad_files_folder()
                        click.echo("Bad files deleted")
                    else:
                        click.echo("Bad files kept for manual review")
                except KeyboardInterrupt:
                    click.echo("User interrupted. Bad files kept for manual review")
        
        return stats
    
    def create_folder_structure_preview(self, limit: int = 10) -> List[str]:
        """Preview the folder structure that would be created without moving files."""
        session = self.db_service.db_manager.get_session()
        try:
            # Get physical files instead of database records to avoid path issues
            quarantine_path = Path(self.config.paths.quarantine_dir)
            physical_files = []
            for ext in ['.fits', '.fit', '.fts']:
                files = list(quarantine_path.rglob(f"*{ext}"))
                # Filter out duplicates folder for preview
                files = [f for f in files if "Duplicates" not in str(f)]
                physical_files.extend(files)
            
            if not physical_files:
                return []
            
            # Limit files for preview
            preview_files = physical_files[:limit]
            
            # Extract basic metadata for preview
            preview_paths = []
            for file_path in preview_files:
                try:
                    # Simple preview - use filename patterns to estimate structure
                    filename = file_path.name
                    folder_parts = file_path.parent.parts
                    
                    # Try to extract basic info from path/filename
                    if "Light" in str(file_path) or "_LIGHT_" in filename:
                        frame_type = "LIGHT"
                    elif "Flat" in str(file_path) or "_FLAT_" in filename:
                        frame_type = "FLAT"
                    elif "Dark" in str(file_path) or "_DARK_" in filename:
                        frame_type = "DARK"
                    elif "Bias" in str(file_path) or "_BIAS_" in filename:
                        frame_type = "BIAS"
                    else:
                        frame_type = "UNKNOWN"
                    
                    # Create sample destination path
                    base_path = Path(self.config.paths.image_dir)
                    if frame_type == "LIGHT":
                        dest = base_path / "TARGET" / "CAMERA" / "TELESCOPE" / "FILTER" / "DATE"
                    else:
                        dest = base_path / "CALIBRATION" / "CAMERA" / frame_type / "DATE"
                    
                    sample_filename = f"standardized_{frame_type.lower()}_0001.fits"
                    full_path = str(dest / sample_filename)
                    preview_paths.append(full_path)
                    
                except Exception:
                    # Fallback for problematic files
                    dest = Path(self.config.paths.image_dir) / "UNKNOWN" / "preview_file.fits"
                    preview_paths.append(str(dest))
            
            return preview_paths
            
        finally:
            session.close()
    
    def _cleanup_empty_folders(self) -> int:
        """Remove empty folders from quarantine directory, working from deepest levels up."""
        quarantine_path = Path(self.config.paths.quarantine_dir)
        
        if not quarantine_path.exists():
            logger.warning(f"Quarantine directory does not exist: {quarantine_path}")
            return 0
        
        removed_count = 0
        
        # Get all subdirectories and sort by depth (deepest first)
        all_dirs = []
        for root, dirs, files in os.walk(str(quarantine_path)):
            for dir_name in dirs:
                dir_path = Path(root) / dir_name
                all_dirs.append(dir_path)  # Include all directories, including special ones
        
        # Sort by depth (deepest first) to remove nested empty folders first
        all_dirs.sort(key=lambda p: len(p.parts), reverse=True)
        
        for dir_path in all_dirs:
            try:
                # Check if directory is empty
                if not any(dir_path.iterdir()):
                    logger.debug(f"Removing empty folder: {dir_path}")
                    dir_path.rmdir()
                    removed_count += 1
                else:
                    # Log what's preventing removal
                    contents = list(dir_path.iterdir())
                    logger.debug(f"Folder not empty: {dir_path} contains {len(contents)} items")
                    
            except OSError as e:
                logger.warning(f"Could not remove folder {dir_path}: {e}")
                continue
        
        return removed_count