"""
Processed file cataloger core functionality.

Handles scanning processing session folders for output files and
cataloging them with metadata extraction.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

from .models import Base, ProcessingSession, ProcessedFile
from .metadata_extractor import extract_processed_file_metadata

logger = logging.getLogger(__name__)


class ProcessedFileCataloger:
    """Catalogs processed output files from astrophotography sessions."""
    
    # Supported file extensions
    SUPPORTED_EXTENSIONS = {
        '.jpg': 'jpg',
        '.jpeg': 'jpeg',
        '.xisf': 'xisf',
        '.xosm': 'xosm',
    }
    
    # Project folder extension
    PROJECT_EXTENSION = '.pxiproject'
    
    # Subfolders to scan
    TARGET_SUBFOLDERS = ['final', 'intermediate']
    
    def __init__(self, database_path: str):
        """
        Initialize cataloger.
        
        Args:
            database_path: Path to SQLite database
        """
        self.db_path = database_path
        self.engine = create_engine(f'sqlite:///{database_path}')
        self.Session = sessionmaker(bind=self.engine)
        
        # Stats
        self.stats = {
            'sessions_scanned': 0,
            'files_found': 0,
            'files_cataloged': 0,
            'files_updated': 0,
            'files_skipped': 0,
            'errors': 0,
        }
    
    def init_database(self):
        """Create database tables if they don't exist."""
        Base.metadata.create_all(self.engine)
        logger.info("Database tables created/verified")
    
    def get_processing_sessions(self, processing_dir: Path, 
                               session_id: Optional[str] = None) -> List[Dict]:
        """
        Get processing sessions to scan.
        
        Args:
            processing_dir: Root processing directory
            session_id: Optional specific session ID to process
            
        Returns:
            List of session dictionaries with id and folder_path
        """
        session = self.Session()
        try:
            query = session.query(ProcessingSession)
            
            if session_id:
                query = query.filter(ProcessingSession.id == session_id)
            
            sessions = query.all()
            
            result = []
            for ps in sessions:
                # Verify folder exists
                folder_path = Path(ps.folder_path)
                if folder_path.exists():
                    result.append({
                        'id': ps.id,
                        'name': ps.name,
                        'folder_path': folder_path,
                        'objects': json.loads(ps.objects) if ps.objects else []
                    })
                else:
                    logger.warning(f"Session folder not found: {ps.folder_path}")
            
            return result
            
        finally:
            session.close()
    
    def discover_files(self, session_folder: Path) -> List[Tuple[Path, str, str]]:
        """
        Discover processable files in a session folder.
        
        Args:
            session_folder: Path to processing session folder
            
        Returns:
            List of tuples: (file_path, file_type, subfolder)
        """
        discovered = []
        
        # Scan target subfolders
        for subfolder in self.TARGET_SUBFOLDERS:
            subfolder_path = session_folder / subfolder
            
            if not subfolder_path.exists():
                continue
            
            # Find .pxiproject folders first (they appear as directories)
            pxiproject_folders = set()
            for item in subfolder_path.iterdir():
                if item.is_dir() and item.suffix == self.PROJECT_EXTENSION:
                    discovered.append((item, 'pxiproject', subfolder))
                    pxiproject_folders.add(item)
            
            # Find regular files with supported extensions
            # Skip any files that are inside a .pxiproject folder
            for ext, file_type in self.SUPPORTED_EXTENSIONS.items():
                for filepath in subfolder_path.rglob(f'*{ext}'):
                    if filepath.is_file():
                        # Check if this file is inside any .pxiproject folder
                        inside_pxiproject = any(
                            pxiproject in filepath.parents 
                            for pxiproject in pxiproject_folders
                        )
                        if not inside_pxiproject:
                            discovered.append((filepath, file_type, subfolder))
        
        return discovered
    
    def detect_associated_object(self, filename: str, 
                                session_objects: List[str]) -> Optional[str]:
        """
        Auto-detect which object a file is associated with.
        
        Looks for object names in the filename.
        
        Args:
            filename: Name of the processed file
            session_objects: List of objects in the session
            
        Returns:
            Associated object name or None
        """
        if not session_objects:
            return None
        
        filename_lower = filename.lower()
        
        # Look for object names in filename
        for obj in session_objects:
            if obj.lower() in filename_lower:
                return obj
        
        # If only one object in session, assume it's that one
        if len(session_objects) == 1:
            return session_objects[0]
        
        return None
    
    def catalog_file(self, filepath: Path, file_type: str, 
                    session_id: str, subfolder: str,
                    session_objects: List[str]) -> bool:
        """
        Catalog a single file.
        
        Args:
            filepath: Path to file
            file_type: Type of file
            session_id: Processing session ID
            subfolder: Subfolder (final/intermediate)
            session_objects: Objects in the session
            
        Returns:
            True if cataloged, False if skipped
        """
        session = self.Session()
        try:
            # Check if already cataloged
            existing = session.query(ProcessedFile).filter(
                ProcessedFile.file_path == str(filepath)
            ).first()
            
            if existing:
                # Check if modified since last catalog
                current_mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
                if existing.modified_date and current_mtime <= existing.modified_date:
                    self.stats['files_skipped'] += 1
                    return False
                
                # File modified, update it
                logger.info(f"Updating modified file: {filepath.name}")
                self._update_file_record(session, existing, filepath, file_type, 
                                       subfolder, session_objects)
                self.stats['files_updated'] += 1
                return True
            
            # New file, catalog it
            logger.info(f"Cataloging: {filepath.name}")
            
            # Extract metadata
            metadata = extract_processed_file_metadata(filepath, file_type)
            
            # Detect associated object
            associated_object = self.detect_associated_object(
                filepath.name, session_objects
            )
            
            # Create database record
            processed_file = ProcessedFile(
                processing_session_id=session_id,
                file_path=metadata['file_path'],
                filename=metadata['filename'],
                file_type=metadata['file_type'],
                subfolder=subfolder,
                file_size=metadata['file_size'],
                created_date=metadata['created_date'],
                modified_date=metadata['modified_date'],
                md5sum=metadata['md5sum'],
                has_companion=metadata['has_companion'],
                companion_path=metadata['companion_path'],
                companion_size=metadata['companion_size'],
                image_width=metadata['image_width'],
                image_height=metadata['image_height'],
                bit_depth=metadata['bit_depth'],
                color_space=metadata['color_space'],
                associated_object=associated_object,
                processing_stage=subfolder,  # final or intermediate
                metadata_json=metadata['metadata_json'],
            )
            
            session.add(processed_file)
            session.commit()
            
            self.stats['files_cataloged'] += 1
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error cataloging {filepath}: {e}")
            self.stats['errors'] += 1
            return False
            
        finally:
            session.close()
    
    def _update_file_record(self, session, existing: ProcessedFile, 
                          filepath: Path, file_type: str,
                          subfolder: str, session_objects: List[str]):
        """Update an existing file record."""
        metadata = extract_processed_file_metadata(filepath, file_type)
        
        # Update fields
        existing.file_size = metadata['file_size']
        existing.modified_date = metadata['modified_date']
        existing.md5sum = metadata['md5sum']
        existing.has_companion = metadata['has_companion']
        existing.companion_path = metadata['companion_path']
        existing.companion_size = metadata['companion_size']
        existing.image_width = metadata['image_width']
        existing.image_height = metadata['image_height']
        existing.bit_depth = metadata['bit_depth']
        existing.color_space = metadata['color_space']
        existing.metadata_json = metadata['metadata_json']
        existing.updated_at = datetime.utcnow()
        
        # Re-detect associated object in case it changed
        associated_object = self.detect_associated_object(
            filepath.name, session_objects
        )
        if associated_object:
            existing.associated_object = associated_object
        
        session.commit()
    
    def catalog_session(self, session_info: Dict) -> int:
        """
        Catalog all files in a processing session.
        
        Args:
            session_info: Session information dictionary
            
        Returns:
            Number of files cataloged
        """
        logger.info(f"Scanning session: {session_info['name']} ({session_info['id']})")
        
        folder_path = session_info['folder_path']
        session_objects = session_info['objects']
        
        # Discover files
        discovered_files = self.discover_files(folder_path)
        
        if not discovered_files:
            logger.info(f"  No processable files found")
            return 0
        
        logger.info(f"  Found {len(discovered_files)} file(s)")
        self.stats['files_found'] += len(discovered_files)
        
        # Catalog each file with progress bar
        cataloged = 0
        with tqdm(total=len(discovered_files), desc="Cataloging files", unit="file") as pbar:
            for filepath, file_type, subfolder in discovered_files:
                if self.catalog_file(filepath, file_type, session_info['id'], 
                                   subfolder, session_objects):
                    cataloged += 1
                pbar.update(1)
        
        return cataloged
    
    def run(self, processing_dir: Path, session_id: Optional[str] = None):
        """
        Run the cataloger.
        
        Args:
            processing_dir: Root processing directory
            session_id: Optional specific session to process
        """
        logger.info("=" * 70)
        logger.info("PROCESSED FILE CATALOGER")
        logger.info("=" * 70)
        
        # Get sessions to process
        sessions = self.get_processing_sessions(processing_dir, session_id)
        
        if not sessions:
            logger.warning("No processing sessions found to scan")
            return
        
        logger.info(f"Found {len(sessions)} session(s) to scan")
        logger.info("")
        
        # Process each session
        if len(sessions) > 1:
            # Multiple sessions - show session progress bar
            with tqdm(total=len(sessions), desc="Processing sessions", unit="session") as session_pbar:
                for session_info in sessions:
                    self.catalog_session(session_info)
                    self.stats['sessions_scanned'] += 1
                    session_pbar.update(1)
        else:
            # Single session - no session-level progress bar needed
            for session_info in sessions:
                self.catalog_session(session_info)
                self.stats['sessions_scanned'] += 1
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print cataloging summary."""
        logger.info("")
        logger.info("=" * 70)
        logger.info("CATALOGING SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Sessions scanned:     {self.stats['sessions_scanned']}")
        logger.info(f"Files found:          {self.stats['files_found']}")
        logger.info(f"Files cataloged:      {self.stats['files_cataloged']}")
        logger.info(f"Files updated:        {self.stats['files_updated']}")
        logger.info(f"Files skipped:        {self.stats['files_skipped']}")
        logger.info(f"Errors:               {self.stats['errors']}")
        logger.info("=" * 70)