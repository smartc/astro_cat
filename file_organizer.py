"""File organization and migration system for FITS Cataloger."""

import os
import re
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

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
    
    def migrate_files(self, limit: Optional[int] = None) -> Dict[str, int]:
        """
        Migrate files from quarantine to organized structure.
        
        Args:
            limit: Maximum number of files to process (None for all)
            
        Returns:
            Dict with migration statistics
        """
        logger.info("Starting file migration...")
        
        stats = {
            'processed': 0,
            'moved': 0,
            'errors': 0,
            'skipped': 0
        }
        
        # Get files from database that are still in quarantine
        session = self.db_service.db_manager.get_session()
        try:
            query = session.query(FitsFile).filter(
                FitsFile.folder.like(f"%{self.config.paths.quarantine_dir}%")
            )
            
            if limit:
                query = query.limit(limit)
            
            files_to_process = query.all()
            
            if not files_to_process:
                logger.info("No files found in quarantine to migrate")
                return stats
            
            logger.info(f"Found {len(files_to_process)} files to migrate")
            
            # Convert to dict format for processing
            file_records = []
            for file_obj in files_to_process:
                record = {
                    'id': file_obj.id,
                    'file': file_obj.file,
                    'folder': file_obj.folder,
                    'object': file_obj.object,
                    'frame_type': file_obj.frame_type,
                    'camera': file_obj.camera,
                    'telescope': file_obj.telescope,
                    'filter': file_obj.filter,
                    'exposure': file_obj.exposure,
                    'obs_date': file_obj.obs_date,
                    'obs_timestamp': file_obj.obs_timestamp,
                    'mosaic': getattr(file_obj, 'mosaic', None)  # May not exist in all schemas
                }
                file_records.append(record)
            
            # Group files by destination for sequential numbering
            file_groups = self.group_files_by_destination(file_records)
            
            # Get starting catalog ID
            next_catalog_id = self.get_next_catalog_id()
            current_catalog_id = next_catalog_id
            
            # Process each group
            for dest_path, group_files in file_groups.items():
                logger.info(f"Processing {len(group_files)} files for {dest_path}")
                
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
                            continue
                        
                        # Generate new filename
                        new_filename = self.generate_standardized_filename(file_record, seq_num)
                        new_filepath = Path(dest_path) / new_filename
                        
                        # Store original filename (stripped of catalog prefix)
                        orig_filename = self.strip_catalog_prefix(file_record['file'])
                        
                        # Move file
                        logger.debug(f"Moving {old_filepath} -> {new_filepath}")
                        shutil.move(str(old_filepath), str(new_filepath))
                        
                        # Update database record
                        file_obj = session.query(FitsFile).filter_by(id=file_record['id']).first()
                        if file_obj:
                            file_obj.id = current_catalog_id
                            file_obj.file = new_filename
                            file_obj.folder = dest_path
                            file_obj.orig_file = orig_filename
                            file_obj.orig_folder = file_record['folder']
                            
                            current_catalog_id += 1
                            
                        stats['moved'] += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing file {file_record['file']}: {e}")
                        stats['errors'] += 1
                        continue
            
            # Commit all database changes
            session.commit()
            
        except Exception as e:
            logger.error(f"Error during migration: {e}")
            session.rollback()
            raise
        finally:
            session.close()
        
        logger.info(f"Migration complete: {stats['moved']} moved, {stats['errors']} errors, {stats['skipped']} skipped")
        
        # Clean up empty folders in quarantine after successful migration
        try:
            logger.info("Cleaning up empty folders in quarantine...")
            removed_count = self._cleanup_empty_folders()
            if removed_count > 0:
                logger.info(f"Removed {removed_count} empty folders from quarantine")
            else:
                logger.info("No empty folders found to remove")
        except Exception as e:
            logger.error(f"Error during folder cleanup: {e}")
        
        return stats
    
    def create_folder_structure_preview(self, limit: int = 10) -> List[str]:
        """Preview the folder structure that would be created without moving files."""
        session = self.db_service.db_manager.get_session()
        try:
            files_to_process = session.query(FitsFile).filter(
                FitsFile.folder.like(f"%{self.config.paths.quarantine_dir}%")
            ).limit(limit).all()
            
            preview_paths = []
            for file_obj in files_to_process:
                record = {
                    'object': file_obj.object,
                    'frame_type': file_obj.frame_type,
                    'camera': file_obj.camera,
                    'telescope': file_obj.telescope,
                    'filter': file_obj.filter,
                    'exposure': file_obj.exposure,
                    'obs_date': file_obj.obs_date
                }
                
                dest_path = self.determine_destination_path(record)
                new_filename = self.generate_standardized_filename(record, 1)
                full_path = str(Path(dest_path) / new_filename)
                preview_paths.append(full_path)
            
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
                all_dirs.append(dir_path)
        
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