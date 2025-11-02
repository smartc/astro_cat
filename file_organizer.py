"""File organization and migration system for FITS Cataloger - Validation Score Based."""

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
    
    def _safe_float_to_int(self, value: Optional[float], default: int = 0) -> int:
        """Safely convert float to int, handling None values."""
        if value is None:
            return default
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return default
    
    def _safe_get_exposure(self, file_data: Dict) -> int:
        """Safely get exposure value as integer, handling None."""
        exposure = file_data.get('exposure')
        return self._safe_float_to_int(exposure, 0)
    
    def _safe_get_string(self, file_data: Dict, key: str, default: str = "UNKNOWN") -> str:
        """Safely get string value, handling None and empty strings."""
        value = file_data.get(key)
        if value is None or value == "" or str(value).lower() in ['none', 'null', 'nan']:
            return default
        return str(value)
    
    def generate_standardized_filename(self, file_data: Dict, sequence: int) -> str:
        """Generate standardized filename based on frame type and metadata."""
        frame_type = self._safe_get_string(file_data, 'frame_type', 'UNKNOWN')
        camera = self._safe_get_string(file_data, 'camera', 'UNKNOWN')
        
        # Format sequence number as 4-digit zero-padded
        seq_str = f"{sequence:04d}"
        
        if frame_type == 'LIGHT':
            obj = self._safe_get_string(file_data, 'object', 'UNKNOWN')
            filter_name = self._safe_get_string(file_data, 'filter', 'NONE')
            exposure = self._safe_get_exposure(file_data)
            mosaic = file_data.get('mosaic')
            
            # Clean object name for filename (remove invalid chars)
            obj_clean = re.sub(r'[^\w\-]', '_', str(obj))
            
            if mosaic:
                return f"{obj_clean}_{frame_type}_{filter_name}_{exposure}s_{mosaic}_{seq_str}.fits"
            else:
                return f"{obj_clean}_{frame_type}_{filter_name}_{exposure}s_{seq_str}.fits"
                
        elif frame_type == 'FLAT':
            telescope = self._safe_get_string(file_data, 'telescope', 'UNKNOWN')
            filter_name = self._safe_get_string(file_data, 'filter', 'NONE')
            exposure = self._safe_get_exposure(file_data)
            return f"{camera}_{frame_type}_{telescope}_{filter_name}_{exposure}s_{seq_str}.fits"
            
        elif frame_type == 'DARK':
            exposure = self._safe_get_exposure(file_data)
            # Check if this should be classified as FLAT_DARK
            if exposure <= 29:
                filter_name = self._safe_get_string(file_data, 'filter', 'NONE')
                return f"{camera}_FLAT_DARK_{filter_name}_{seq_str}.fits"
            else:
                return f"{camera}_{frame_type}_{exposure}s_{seq_str}.fits"
            
        elif frame_type == 'BIAS':
            return f"{camera}_{frame_type}_{seq_str}.fits"
        
        # Fallback for unknown frame types
        return f"{camera}_{frame_type}_{seq_str}.fits"
    
    def determine_destination_path(self, file_data: Dict) -> str:
        """Determine destination folder path based on file metadata."""
        frame_type = self._safe_get_string(file_data, 'frame_type', 'UNKNOWN')
        camera = self._safe_get_string(file_data, 'camera', 'UNKNOWN')
        obs_date = self._safe_get_string(file_data, 'obs_date', 'UNKNOWN')
        
        base_path = Path(self.config.paths.image_dir)
        
        if frame_type == 'LIGHT':
            obj = self._safe_get_string(file_data, 'object', 'UNKNOWN')
            telescope = self._safe_get_string(file_data, 'telescope', 'UNKNOWN')
            filter_name = self._safe_get_string(file_data, 'filter', 'NONE')
            mosaic = file_data.get('mosaic')
            
            path = base_path / obj / camera / telescope / filter_name / obs_date
            if mosaic:
                path = path / str(mosaic)
                
        elif frame_type == 'FLAT':
            telescope = self._safe_get_string(file_data, 'telescope', 'UNKNOWN')
            filter_name = self._safe_get_string(file_data, 'filter', 'NONE')
            path = base_path / "CALIBRATION" / camera / "FLAT" / telescope / filter_name / obs_date
            
        elif frame_type == 'DARK':
            exposure = self._safe_get_exposure(file_data)
            
            # Check if this is a flat dark (≤29 seconds)
            if exposure <= 29:
                filter_name = self._safe_get_string(file_data, 'filter', 'NONE')
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
    
    def migrate_files(self, limit: Optional[int] = None, auto_cleanup: bool = False, 
                         progress_callback=None, web_mode: bool = False) -> Dict[str, int]:
            """
            Migrate files from quarantine to organized structure - only files with validation scores > 95.
            
            Args:
                limit: Maximum number of files to process (None for all)
                auto_cleanup: Automatically delete duplicates and bad files without prompting
                progress_callback: Optional callback function(progress_pct, stats_dict) for progress updates
                web_mode: If True, skip interactive prompts (for web interface use)
                
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
                'bad_files_moved': 0,
                'left_for_review': 0,
                'duplicates_found': 0,
                'bad_files_found': 0
            }
            
            # Create special folders for duplicates and bad files only
            duplicates_folder = Path(self.config.paths.quarantine_dir) / "Duplicates"
            bad_files_folder = Path(self.config.paths.quarantine_dir) / "Bad"
            duplicates_folder.mkdir(exist_ok=True)
            bad_files_folder.mkdir(exist_ok=True)
            
            quarantine_path = Path(self.config.paths.quarantine_dir)
            session = self.db_service.db_manager.get_session()
            
            # Calculate total work for progress tracking
            # We'll weight the stages: file migration (70%), categorization (20%), cleanup (10%)
            total_progress_units = 100
            current_progress = 0
            
            def update_progress(stage_progress, stage_weight):
                """Update overall progress based on stage completion."""
                nonlocal current_progress
                progress_pct = int(current_progress + (stage_progress * stage_weight))
                if progress_callback:
                    progress_callback(progress_pct, stats)
            
            try:
                # STEP 1: Migrate files with scores > 95 (70% of total progress)
                stage_weight = 0.70
                click.echo("Getting files from database...")
                update_progress(0, stage_weight)
                
                # Get database records for files still in quarantine
                db_files = session.query(FitsFile).filter(
                    FitsFile.folder.like(f"%{self.config.paths.quarantine_dir}%")
                ).all()
                
                # Only migrate files with scores > 95, leave everything else in place
                auto_migrate_files = []
                skipped_for_review = 0
                
                for db_file in db_files:
                    file_path = Path(db_file.folder) / db_file.file
                    if ("Duplicates" not in str(file_path) and 
                        "Bad" not in str(file_path) and 
                        file_path.exists()):
                        
                        validation_score = getattr(db_file, 'validation_score', None)
                        
                        if validation_score is not None and validation_score > 95.0:
                            auto_migrate_files.append(db_file)
                        else:
                            skipped_for_review += 1
                
                files_to_migrate = auto_migrate_files
                
                if auto_migrate_files:
                    click.echo(f"Found {len(auto_migrate_files)} files with scores >95 ready for migration")
                
                if skipped_for_review > 0:
                    click.echo(f"Leaving {skipped_for_review} files in quarantine for review (scores ≤95, NULL scores, or data issues)")
                
                stats['left_for_review'] = skipped_for_review
                
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
                    
                    total_files = len(migration_records)
                    files_processed = 0
                    
                    with tqdm(total=total_files, desc="Migrating files") as pbar:
                        for dest_path, group_files in file_groups.items():
                            os.makedirs(dest_path, exist_ok=True)
                            
                            for seq_num, file_record in enumerate(group_files, 1):
                                try:
                                    stats['processed'] += 1
                                    files_processed += 1
                                    
                                    old_filepath = Path(file_record['folder']) / file_record['file']
                                    
                                    if not old_filepath.exists():
                                        logger.warning(f"Source file not found: {old_filepath}")
                                        stats['skipped'] += 1
                                        pbar.update(1)
                                        continue
                                    
                                    new_filename = self.generate_standardized_filename(file_record, seq_num)
                                    new_filepath = Path(dest_path) / new_filename
                                    orig_filename = self.strip_catalog_prefix(file_record['file'])
                                    
                                    shutil.move(str(old_filepath), str(new_filepath))
                                    
                                    db_record = session.query(FitsFile).filter_by(id=file_record['id']).first()
                                    if db_record:
                                        db_record.id = current_catalog_id
                                        db_record.file = new_filename
                                        db_record.folder = dest_path
                                        db_record.orig_file = orig_filename
                                        db_record.orig_folder = file_record['folder']
                                        current_catalog_id += 1
                                    
                                    stats['moved'] += 1
                                    
                                    # Update progress every 10 files or at completion
                                    if files_processed % 10 == 0 or files_processed == total_files:
                                        file_progress = (files_processed / total_files) * 100
                                        update_progress(file_progress, stage_weight)
                                    
                                except Exception as e:
                                    logger.error(f"Error processing file {file_record['file']}: {e}")
                                    stats['errors'] += 1
                                
                                pbar.update(1)
                    
                    session.commit()
                    click.echo(f"Database migration complete: {stats['moved']} files moved")
                
                current_progress += 70  # Stage 1 complete
                
                # STEP 2: Categorize remaining files (20% of total progress)
                stage_weight = 0.20
                click.echo("Scanning for remaining files to categorize...")
                update_progress(0, stage_weight)
                
                remaining_files = []
                for ext in ['.fits', '.fit', '.fts']:
                    files = list(quarantine_path.rglob(f"*{ext}"))
                    files = [f for f in files if not any(folder in str(f) for folder in ["Duplicates", "Bad"])]
                    remaining_files.extend(files)
                
                if remaining_files:
                    click.echo(f"Found {len(remaining_files)} remaining files to categorize...")
                    
                    duplicates_to_move = []
                    bad_files_to_move = []
                    total_remaining = len(remaining_files)
                    
                    with tqdm(total=total_remaining, desc="Categorizing files") as pbar:
                        for idx, physical_file in enumerate(remaining_files):
                            
                            if "BAD_" in physical_file.name:
                                bad_files_to_move.append(physical_file)
                                pbar.update(1)
                                continue
                            
                            md5_hash = self._get_file_md5(str(physical_file))
                            if md5_hash:
                                existing_record = session.query(FitsFile).filter_by(md5sum=md5_hash).first()
                                if existing_record:
                                    original_path = Path(existing_record.folder) / existing_record.file
                                    if original_path.exists():
                                        duplicates_to_move.append(physical_file)
                                    else:
                                        logger.warning(f"Found file with database record but missing original: {physical_file}")
                            
                            # Update progress every 10 files
                            if (idx + 1) % 10 == 0 or (idx + 1) == total_remaining:
                                cat_progress = ((idx + 1) / total_remaining) * 100
                                update_progress(cat_progress, stage_weight)
                            
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
                                except Exception as e:
                                    logger.error(f"Error moving duplicate {duplicate_file}: {e}")
                                    stats['errors'] += 1
                                pbar.update(1)
                
                current_progress += 20  # Stage 2 complete
                
            except Exception as e:
                logger.error(f"Error during migration: {e}")
                session.rollback()
                raise
            finally:
                session.close()
            
            # STEP 3: Cleanup empty folders (5% of progress)
            update_progress(0, 0.05)
            try:
                click.echo("Cleaning up empty folders...")
                removed_count = self._cleanup_empty_folders()
                if removed_count > 0:
                    click.echo(f"Removed {removed_count} empty folders")
            except Exception as e:
                logger.error(f"Error during folder cleanup: {e}")
            
            current_progress += 5
            
            # STEP 4: Handle cleanup prompts (5% of progress)
            remaining_duplicates = list(duplicates_folder.glob("*.fit*")) if duplicates_folder.exists() else []
            remaining_bad_files = list(bad_files_folder.glob("*.fit*")) if bad_files_folder.exists() else []
            
            stats['duplicates_found'] = len(remaining_duplicates)
            stats['bad_files_found'] = len(remaining_bad_files)

            if remaining_duplicates:
                click.echo(f"Found {len(remaining_duplicates)} files in duplicates folder")
                if auto_cleanup:
                    self._delete_duplicates_folder()
                    click.echo("Duplicate files deleted automatically")
                elif not web_mode:
                    # Only prompt in terminal mode
                    try:
                        response = input(f"\nDelete {len(remaining_duplicates)} duplicate files? (y/N): ").lower().strip()
                        if response == 'y':
                            self._delete_duplicates_folder()
                            click.echo("Duplicate files deleted")
                        else:
                            click.echo("Duplicate files kept for manual review")
                    except KeyboardInterrupt:
                        click.echo("User interrupted. Duplicate files kept for manual review")
                # In web_mode, just report the count - no deletion

            if remaining_bad_files:
                click.echo(f"Found {len(remaining_bad_files)} files in bad files folder")
                if auto_cleanup:
                    self._delete_bad_files_folder()
                    click.echo("Bad files deleted automatically")
                elif not web_mode:
                    # Only prompt in terminal mode
                    try:
                        response = input(f"\nDelete {len(remaining_bad_files)} bad files? (y/N): ").lower().strip()
                        if response == 'y':
                            self._delete_bad_files_folder()
                            click.echo("Bad files deleted")
                        else:
                            click.echo("Bad files kept for manual review")
                    except KeyboardInterrupt:
                        click.echo("User interrupted. Bad files kept for manual review")
                # In web_mode, just report the count - no deletion
            
            # Final progress update
            if progress_callback:
                progress_callback(100, stats)
            
            return stats


    def create_folder_structure_preview(self, limit: int = 10) -> List[str]:
        """Preview the folder structure that would be created without moving files."""
        session = self.db_service.db_manager.get_session()
        try:
            # Get database records for files ready to migrate (validation score > 95)
            db_files = session.query(FitsFile).filter(
                FitsFile.folder.like(f"%{self.config.paths.quarantine_dir}%"),
                FitsFile.validation_score > 95.0
            ).limit(limit).all()

            if not db_files:
                return []

            # Convert to migration format and generate paths
            preview_paths = []
            for db_file in db_files:
                try:
                    # Convert database record to dictionary format
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
                        'mosaic': getattr(db_file, 'mosaic', None)
                    }

                    # Generate the actual destination path using real metadata
                    dest_path = self.determine_destination_path(record)

                    # Generate the actual standardized filename
                    filename = self.generate_standardized_filename(record, 1)

                    # Combine into full path
                    full_path = str(Path(dest_path) / filename)
                    preview_paths.append(full_path)

                except Exception as e:
                    logger.warning(f"Error generating preview for {db_file.file}: {e}")
                    continue

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