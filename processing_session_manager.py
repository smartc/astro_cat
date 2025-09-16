"""Processing session management for FITS Cataloger."""

import os
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

import click
from sqlalchemy.orm import Session

from models import DatabaseService, FitsFile, ProcessingSession, ProcessingSessionFile
from config import Config

logger = logging.getLogger(__name__)


@dataclass
class ProcessingSessionInfo:
    """Information about a processing session."""
    id: str
    name: str
    objects: List[str]
    total_files: int
    lights: int
    darks: int
    flats: int
    bias: int
    folder_path: str
    status: str
    created_at: datetime
    notes: Optional[str] = None


class ProcessingSessionManager:
    """Manages processing sessions and file staging."""
    
    def __init__(self, config: Config, db_service: DatabaseService):
        self.config = config
        self.db_service = db_service
        self.processing_base_path = Path(config.paths.processing_dir)
        
        # Ensure processing directory exists
        self.processing_base_path.mkdir(parents=True, exist_ok=True)
        
    def generate_session_id(self, name: str) -> str:
        """Generate a unique session ID from name and timestamp."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Clean name for filesystem use
        clean_name = "".join(c for c in name if c.isalnum() or c in (' ', '_', '-')).strip()
        clean_name = clean_name.replace(' ', '_')[:20]  # Limit length
        
        session_id = f"{timestamp}_{clean_name}"
        return session_id
    
    def validate_file_selection(self, file_ids: List[int]) -> Tuple[List[FitsFile], Dict[str, str]]:
        """Validate file selection and return files with any warnings."""
        session = self.db_service.db_manager.get_session()
        warnings = {}
        
        try:
            # Get all requested files
            files = session.query(FitsFile).filter(FitsFile.id.in_(file_ids)).all()
            
            if len(files) != len(file_ids):
                found_ids = {f.id for f in files}
                missing_ids = set(file_ids) - found_ids
                warnings['missing_files'] = f"Files not found: {missing_ids}"
            
            # Check for missing files on disk
            missing_on_disk = []
            for file_obj in files:
                file_path = Path(file_obj.folder) / file_obj.file
                if not file_path.exists():
                    missing_on_disk.append(str(file_path))
            
            if missing_on_disk:
                warnings['missing_on_disk'] = f"Files not found on disk: {missing_on_disk}"
            
            # Check for files already in processing sessions
            existing_staged = session.query(ProcessingSessionFile.fits_file_id).filter(
                ProcessingSessionFile.fits_file_id.in_(file_ids)
            ).all()
            
            if existing_staged:
                staged_ids = {row[0] for row in existing_staged}
                warnings['already_staged'] = f"Files already in processing sessions: {staged_ids}"
            
            return files, warnings
            
        finally:
            session.close()
    
    def create_processing_session(self, name: str, file_ids: List[int], 
                                notes: Optional[str] = None) -> ProcessingSessionInfo:
        """Create a new processing session with selected files."""
        
        # Validate files
        files, warnings = self.validate_file_selection(file_ids)
        
        if warnings:
            warning_msg = "; ".join(warnings.values())
            logger.warning(f"Processing session creation warnings: {warning_msg}")
            if 'missing_files' in warnings or 'missing_on_disk' in warnings:
                raise ValueError(f"Cannot create session: {warning_msg}")
        
        # Generate session ID and create folder structure
        session_id = self.generate_session_id(name)
        session_folder = self.processing_base_path / session_id
        
        # Create folder structure
        self._create_folder_structure(session_folder)
        
        # Determine objects in this session
        objects = list(set(f.object for f in files if f.object and f.object != 'CALIBRATION'))
        
        # Count frame types
        frame_counts = {'LIGHT': 0, 'DARK': 0, 'FLAT': 0, 'BIAS': 0}
        for file_obj in files:
            frame_type = file_obj.frame_type or 'UNKNOWN'
            if frame_type in frame_counts:
                frame_counts[frame_type] += 1
        
        session = self.db_service.db_manager.get_session()
        
        try:
            # Create processing session record
            processing_session = ProcessingSession(
                id=session_id,
                name=name,
                objects=json.dumps(objects),
                notes=notes,
                status='not_started',
                version=1,
                folder_path=str(session_folder)
            )
            session.add(processing_session)
            
            # Stage files and create symbolic links
            staged_files = self._stage_files(session_folder, files, session_id)
            
            # Create processing session file records
            for staged_file in staged_files:
                ps_file = ProcessingSessionFile(
                    processing_session_id=session_id,
                    fits_file_id=staged_file['fits_file_id'],
                    original_path=staged_file['original_path'],
                    original_filename=staged_file['original_filename'],
                    staged_path=staged_file['staged_path'],
                    staged_filename=staged_file['staged_filename'],
                    subfolder=staged_file['subfolder'],
                    file_size=staged_file['file_size'],
                    frame_type=staged_file['frame_type']
                )
                session.add(ps_file)
            
            # Create session info file
            self._create_session_info_file(session_folder, session_id, name, objects, 
                                         frame_counts, notes)
            
            session.commit()
            
            logger.info(f"Created processing session {session_id} with {len(files)} files")
            
            return ProcessingSessionInfo(
                id=session_id,
                name=name,
                objects=objects,
                total_files=len(files),
                lights=frame_counts['LIGHT'],
                darks=frame_counts['DARK'],
                flats=frame_counts['FLAT'],
                bias=frame_counts['BIAS'],
                folder_path=str(session_folder),
                status='not_started',
                created_at=datetime.now(),
                notes=notes
            )
            
        except Exception as e:
            session.rollback()
            # Clean up created folder if session creation failed
            if session_folder.exists():
                import shutil
                shutil.rmtree(session_folder)
            raise e
        finally:
            session.close()
    
    def _create_folder_structure(self, session_folder: Path):
        """Create the processing session folder structure."""
        folders = [
            session_folder / "raw" / "lights",
            session_folder / "raw" / "calibration" / "darks",
            session_folder / "raw" / "calibration" / "flats", 
            session_folder / "raw" / "calibration" / "bias",
            session_folder / "intermediate" / "stacked",
            session_folder / "intermediate" / "calibrated",
            session_folder / "intermediate" / "registered",
            session_folder / "intermediate" / "aligned",
            session_folder / "intermediate" / "mono_channels",
            session_folder / "final",
            session_folder / "final" / "drafts",
            session_folder / "final" / "published"
        ]
        
        for folder in folders:
            folder.mkdir(parents=True, exist_ok=True)
            
        logger.debug(f"Created folder structure for {session_folder}")
    
    def _generate_staged_filename(self, original_path: str, original_filename: str, 
                                session_id: str) -> str:
        """Generate a prefixed filename to avoid collisions."""
        # Create a short hash from the full original path to ensure uniqueness
        path_hash = hashlib.md5(original_path.encode()).hexdigest()[:8]
        
        # Extract base name and extension
        name_parts = original_filename.split('.')
        if len(name_parts) > 1:
            base_name = '.'.join(name_parts[:-1])
            extension = name_parts[-1]
        else:
            base_name = original_filename
            extension = ''
        
        # Create prefixed filename: {hash}_{base_name}.{extension}
        if extension:
            staged_filename = f"{path_hash}_{base_name}.{extension}"
        else:
            staged_filename = f"{path_hash}_{base_name}"
        
        return staged_filename
    
    def _stage_files(self, session_folder: Path, files: List[FitsFile], 
                    session_id: str) -> List[Dict]:
        """Create symbolic links for files in the processing session."""
        staged_files = []
        
        for file_obj in files:
            original_path = Path(file_obj.folder) / file_obj.file
            
            # Determine subfolder based on frame type
            frame_type = (file_obj.frame_type or 'UNKNOWN').upper()
            if frame_type == 'LIGHT':
                subfolder_name = 'lights'
                subfolder_path = session_folder / "raw" / "lights"
            elif frame_type in ['DARK', 'FLAT', 'BIAS']:
                subfolder_name = frame_type.lower() + 's'
                subfolder_path = session_folder / "raw" / "calibration" / subfolder_name
            else:
                # Unknown frame types go in lights folder with a warning
                logger.warning(f"Unknown frame type {frame_type} for file {file_obj.file}, placing in lights")
                subfolder_name = 'lights'
                subfolder_path = session_folder / "raw" / "lights"
            
            # Generate staged filename
            staged_filename = self._generate_staged_filename(
                str(original_path), file_obj.file, session_id
            )
            
            staged_path = subfolder_path / staged_filename
            
            # Create symbolic link
            try:
                staged_path.symlink_to(original_path)
                logger.debug(f"Created symlink: {staged_path} -> {original_path}")
            except OSError as e:
                logger.error(f"Failed to create symlink for {original_path}: {e}")
                raise
            
            # Get file size
            file_size = original_path.stat().st_size if original_path.exists() else 0
            
            staged_files.append({
                'fits_file_id': file_obj.id,
                'original_path': str(original_path),
                'original_filename': file_obj.file,
                'staged_path': str(staged_path),
                'staged_filename': staged_filename,
                'subfolder': subfolder_name,
                'file_size': file_size,
                'frame_type': frame_type
            })
        
        return staged_files
    
    def _create_session_info_file(self, session_folder: Path, session_id: str, 
                                name: str, objects: List[str], frame_counts: Dict[str, int],
                                notes: Optional[str]):
        """Create a markdown info file for the processing session."""
        info_file = session_folder / "session_info.md"
        
        content = f"""# Processing Session: {name}

**Session ID:** `{session_id}`  
**Created:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Status:** Not Started  

## Objects
{', '.join(objects) if objects else 'No objects specified'}

## File Summary
- **Light frames:** {frame_counts['LIGHT']}
- **Dark frames:** {frame_counts['DARK']}
- **Flat frames:** {frame_counts['FLAT']}
- **Bias frames:** {frame_counts['BIAS']}
- **Total files:** {sum(frame_counts.values())}

## Processing Notes
{notes or '_No notes provided_'}

## Processing Timeline
- **Started:** _TBD_
- **Completed:** _TBD_

## External References
- **AstroBin URL:** _TBD_
- **Social Media:** _TBD_

## Folder Structure
```
{session_id}/
├── raw/
│   ├── lights/           # Light frames (symbolic links)
│   └── calibration/      # Calibration frames (symbolic links)
│       ├── darks/
│       ├── flats/
│       └── bias/
├── intermediate/         # Intermediate processing files
│   ├── stacked/         # Stacked images
│   ├── calibrated/      # Calibrated frames
│   ├── registered/      # Registered/aligned frames
│   ├── aligned/         # Additional alignment work
│   └── mono_channels/   # Individual channel images
└── final/               # Final processed images
    ├── drafts/          # Draft versions
    └── published/       # Published versions
```

## Processing History
_No processing steps completed yet_

---
*Generated by FITS Cataloger Processing Session Manager*
"""
        
        with open(info_file, 'w') as f:
            f.write(content)
        
        logger.debug(f"Created session info file: {info_file}")
    
    def list_processing_sessions(self, status_filter: Optional[str] = None) -> List[ProcessingSessionInfo]:
        """List all processing sessions with optional status filter."""
        session = self.db_service.db_manager.get_session()
        
        try:
            query = session.query(ProcessingSession)
            
            if status_filter:
                query = query.filter(ProcessingSession.status == status_filter)
            
            query = query.order_by(ProcessingSession.created_at.desc())
            sessions = query.all()
            
            result = []
            for ps in sessions:
                # Get file counts
                file_counts = session.query(ProcessingSessionFile.frame_type).filter(
                    ProcessingSessionFile.processing_session_id == ps.id
                ).all()
                
                frame_counts = {'LIGHT': 0, 'DARK': 0, 'FLAT': 0, 'BIAS': 0}
                for (frame_type,) in file_counts:
                    if frame_type in frame_counts:
                        frame_counts[frame_type] += 1
                
                objects = json.loads(ps.objects) if ps.objects else []
                
                result.append(ProcessingSessionInfo(
                    id=ps.id,
                    name=ps.name,
                    objects=objects,
                    total_files=sum(frame_counts.values()),
                    lights=frame_counts['LIGHT'],
                    darks=frame_counts['DARK'],
                    flats=frame_counts['FLAT'],
                    bias=frame_counts['BIAS'],
                    folder_path=ps.folder_path,
                    status=ps.status,
                    created_at=ps.created_at,
                    notes=ps.notes
                ))
            
            return result
            
        finally:
            session.close()
    
    def get_processing_session(self, session_id: str) -> Optional[ProcessingSessionInfo]:
        """Get details for a specific processing session."""
        sessions = self.list_processing_sessions()
        for session in sessions:
            if session.id == session_id:
                return session
        return None
    
    def update_session_status(self, session_id: str, status: str, 
                            notes: Optional[str] = None) -> bool:
        """Update processing session status and optionally notes."""
        valid_statuses = ['not_started', 'in_progress', 'complete']
        if status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")
        
        session = self.db_service.db_manager.get_session()
        
        try:
            ps = session.query(ProcessingSession).filter(
                ProcessingSession.id == session_id
            ).first()
            
            if not ps:
                return False
            
            old_status = ps.status
            ps.status = status
            ps.updated_at = datetime.now()
            
            if notes is not None:
                ps.notes = notes
            
            # Update timeline fields
            if status == 'in_progress' and old_status == 'not_started':
                ps.processing_started = datetime.now()
            elif status == 'complete' and old_status != 'complete':
                ps.processing_completed = datetime.now()
            
            session.commit()
            logger.info(f"Updated processing session {session_id} status: {old_status} -> {status}")
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update session {session_id}: {e}")
            raise
        finally:
            session.close()
    
    def delete_processing_session(self, session_id: str, remove_files: bool = True) -> bool:
        """Delete a processing session and optionally remove staged files."""
        session = self.db_service.db_manager.get_session()
        
        try:
            ps = session.query(ProcessingSession).filter(
                ProcessingSession.id == session_id
            ).first()
            
            if not ps:
                return False
            
            folder_path = Path(ps.folder_path)
            
            # Delete database records (cascade will handle ProcessingSessionFile)
            session.delete(ps)
            session.commit()
            
            # Remove folder and files if requested
            if remove_files and folder_path.exists():
                import shutil
                shutil.rmtree(folder_path)
                logger.info(f"Removed processing session folder: {folder_path}")
            
            logger.info(f"Deleted processing session {session_id}")
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to delete session {session_id}: {e}")
            raise
        finally:
            session.close()