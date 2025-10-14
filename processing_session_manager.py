"""Processing session management for FITS Cataloger - Enhanced version."""

import os
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
from collections import defaultdict

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
    version: int = 1
    astrobin_url: Optional[str] = None
    social_urls: List[str] = None
    processing_started: Optional[datetime] = None
    processing_completed: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        """Ensure social_urls is a list."""
        if self.social_urls is None:
            self.social_urls = []



@dataclass
class CalibrationMatch:
    """Information about matched calibration files."""
    capture_session_id: str
    camera: str
    telescope: Optional[str]
    filters: List[str]
    capture_date: str
    frame_type: str
    file_count: int
    exposure_times: List[float]  # For darks
    files: List[FitsFile]
    matched_light_dates: Optional[List[str]] = None
    days_from_lights: Optional[int] = None


class ProcessingSessionManager:
    """Manages processing sessions and file staging."""
    
    def __init__(self, config: Config, db_service: DatabaseService):
        self.config = config
        self.db_service = db_service
        self.processing_base_path = Path(config.paths.processing_dir)
        
        # Ensure processing directory exists
        self.processing_base_path.mkdir(parents=True, exist_ok=True)
        
    def generate_session_id(self, name: str) -> str:
        """Generate a unique session ID with date prefix and hash suffix."""
        date_prefix = datetime.now().strftime('%Y%m%d')
        
        # Create hash from name + timestamp for uniqueness
        hash_input = f"{name}_{datetime.now().isoformat()}"
        name_hash = hashlib.md5(hash_input.encode()).hexdigest()[:8].upper()
        
        session_id = f"{date_prefix}_{name_hash}"
        return session_id
    
    
    def validate_file_selection(self, file_ids: List[int], session_id: Optional[str] = None) -> Tuple[List[FitsFile], Dict[str, str]]:
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
            
            # NEW: Check for files already in THIS SPECIFIC session (if session_id provided)
            if session_id:
                existing_in_session = session.query(ProcessingSessionFile.fits_file_id).filter(
                    ProcessingSessionFile.fits_file_id.in_(file_ids),
                    ProcessingSessionFile.processing_session_id == session_id
                ).all()
                
                if existing_in_session:
                    duplicate_ids = {row[0] for row in existing_in_session}
                    warnings['already_in_session'] = f"Files already in this session: {duplicate_ids}"
            
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
        
        # Determine objects in this session - FIX: ensure all objects are captured
        objects = []
        for f in files:
            if f.object and f.object != 'CALIBRATION':
                if f.object not in objects:  # Avoid duplicates but preserve order
                    objects.append(f.object)
        
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
                                         frame_counts, notes, files)
            
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
    
    def add_files_to_session(self, session_id: str, file_ids: List[int]) -> bool:
        """Add additional files to an existing processing session."""
        # Validate files - NOW PASS THE SESSION_ID
        files, warnings = self.validate_file_selection(file_ids, session_id)
        
        if warnings:
            warning_msg = "; ".join(warnings.values())
            logger.warning(f"Add files warnings: {warning_msg}")
            # Check for critical errors including duplicates in same session
            if 'missing_files' in warnings or 'missing_on_disk' in warnings or 'already_in_session' in warnings:
                raise ValueError(f"Cannot add files: {warning_msg}")
        
        session = self.db_service.db_manager.get_session()
        
        try:
            # Get existing processing session
            ps = session.query(ProcessingSession).filter(
                ProcessingSession.id == session_id
            ).first()
            
            if not ps:
                return False
            
            session_folder = Path(ps.folder_path)
            
            # Update objects list
            existing_objects = json.loads(ps.objects) if ps.objects else []
            new_objects = []
            for f in files:
                if f.object and f.object != 'CALIBRATION':
                    if f.object not in existing_objects and f.object not in new_objects:
                        new_objects.append(f.object)
            
            if new_objects:
                all_objects = existing_objects + new_objects
                ps.objects = json.dumps(all_objects)
            
            # Stage new files
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
            
            ps.updated_at = datetime.now()
            session.commit()
            
            # Update session info file
            self._update_session_info_file(session_folder, ps)
            
            logger.info(f"Added {len(files)} files to processing session {session_id}")
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to add files to session {session_id}: {e}")
            raise
        finally:
            session.close()
    
    def find_matching_calibration(self, session_id: str) -> Dict[str, List]:
        """Find matching calibration files for combinations not already covered in the session."""
        session = self.db_service.db_manager.get_session()
        
        try:
            # Get ALL files in the processing session (both lights and existing calibration)
            existing_files = session.query(FitsFile).join(ProcessingSessionFile).filter(
                ProcessingSessionFile.processing_session_id == session_id
            ).all()
            
            # Build sets of what calibration combinations are ALREADY COVERED
            covered_darks = set()  # (camera, exposure) tuples
            covered_flats = set()  # (camera, telescope, filter) tuples
            covered_bias = set()   # camera names
            
            light_files = []
            
            for f in existing_files:
                if f.frame_type == 'LIGHT':
                    light_files.append(f)
                elif f.frame_type == 'DARK':
                    if f.camera and f.camera != 'UNKNOWN' and f.exposure is not None:
                        covered_darks.add((f.camera, f.exposure))
                elif f.frame_type == 'FLAT':
                    if (f.camera and f.camera != 'UNKNOWN' and 
                        f.telescope and f.telescope != 'UNKNOWN' and 
                        f.filter and f.filter not in ['UNKNOWN', 'NONE']):
                        covered_flats.add((f.camera, f.telescope, f.filter))
                elif f.frame_type == 'BIAS':
                    if f.camera and f.camera != 'UNKNOWN':
                        covered_bias.add(f.camera)
            
            if not light_files:
                return {
                    'darks': [], 
                    'flats': [], 
                    'bias': [],
                    'already_has': {
                        'darks': len(covered_darks) > 0,
                        'flats': len(covered_flats) > 0,
                        'bias': len(covered_bias) > 0
                    }
                }
            
            # Build sets of what calibration combinations are NEEDED based on lights
            needed_darks = set()
            needed_flats = set()
            needed_bias = set()
            
            light_sessions = set()
            light_dates = set()
            
            for f in light_files:
                if f.session_id:
                    light_sessions.add(f.session_id)
                if f.obs_date:
                    light_dates.add(f.obs_date)
                    
                if f.camera and f.camera != 'UNKNOWN':
                    needed_bias.add(f.camera)
                    
                    if f.exposure is not None:
                        needed_darks.add((f.camera, f.exposure))
                        
                    if (f.telescope and f.telescope != 'UNKNOWN' and 
                        f.filter and f.filter not in ['UNKNOWN', 'NONE']):
                        needed_flats.add((f.camera, f.telescope, f.filter))
            
            # Calculate GAPS - what's needed but not covered
            gap_darks = needed_darks - covered_darks
            gap_flats = needed_flats - covered_flats
            gap_bias = needed_bias - covered_bias
            
            logger.info(f"Calibration analysis for session {session_id}:")
            logger.info(f"  Already covered - Darks: {covered_darks}, Flats: {covered_flats}, Bias: {covered_bias}")
            logger.info(f"  Needed - Darks: {needed_darks}, Flats: {needed_flats}, Bias: {needed_bias}")
            logger.info(f"  Gaps to fill - Darks: {gap_darks}, Flats: {gap_flats}, Bias: {gap_bias}")
            
            # Only search for calibration that fills the gaps
            matches = {
                'darks': self._find_matching_darks(session, light_sessions, gap_darks, light_dates),
                'flats': self._find_matching_flats(session, light_sessions, gap_flats, light_dates),
                'bias': self._find_matching_bias(session, light_sessions, gap_bias, light_dates),
                'already_has': {
                    'darks': len(covered_darks) > 0,
                    'flats': len(covered_flats) > 0,
                    'bias': len(covered_bias) > 0
                }
            }
            
            return matches
            
        finally:
            session.close()


    def _cluster_light_dates(self, light_dates: Set[str], max_gap_days: int = 7) -> List[List[str]]:
        """
        Cluster light frame dates into groups based on temporal proximity.
        
        Dates within max_gap_days of each other are grouped together.
        This helps identify when a session has frames from multiple distinct time periods.
        
        Args:
            light_dates: Set of observation dates (YYYY-MM-DD format)
            max_gap_days: Maximum days between dates to consider them in the same cluster
            
        Returns:
            List of date clusters, each cluster is a list of dates
        """
        if not light_dates:
            return []
        
        # Convert to datetime objects and sort
        dates_list = []
        for date_str in light_dates:
            try:
                dates_list.append(datetime.strptime(date_str, '%Y-%m-%d'))
            except:
                logger.warning(f"Could not parse date: {date_str}")
                continue
        
        if not dates_list:
            return []
        
        dates_list.sort()
        
        # Cluster dates
        clusters = []
        current_cluster = [dates_list[0]]
        
        for date in dates_list[1:]:
            days_diff = (date - current_cluster[-1]).days
            
            if days_diff <= max_gap_days:
                current_cluster.append(date)
            else:
                # Start a new cluster
                clusters.append([d.strftime('%Y-%m-%d') for d in current_cluster])
                current_cluster = [date]
        
        # Don't forget the last cluster
        clusters.append([d.strftime('%Y-%m-%d') for d in current_cluster])
        
        return clusters
    
    def _find_closest_calibration_for_dates(self, calibration_files: List[FitsFile], 
                                           target_dates: List[str],
                                           max_days: Optional[int] = None) -> Optional[Tuple[List[FitsFile], int]]:
        """
        Find the calibration files closest in time to the target dates.
        
        Args:
            calibration_files: List of potential calibration files
            target_dates: List of target observation dates (YYYY-MM-DD)
            max_days: Maximum allowed days difference (None = no limit)
            
        Returns:
            Tuple of (matching files, days_difference) or None if no match within range
        """
        if not calibration_files or not target_dates:
            return None
        
        # Calculate the median date of the target light frames
        target_datetimes = []
        for date_str in target_dates:
            try:
                target_datetimes.append(datetime.strptime(date_str, '%Y-%m-%d'))
            except:
                continue
        
        if not target_datetimes:
            return None
        
        target_datetimes.sort()
        median_target = target_datetimes[len(target_datetimes) // 2]
        
        # Group calibration files by session and find closest
        by_session = defaultdict(list)
        for f in calibration_files:
            if f.obs_date:
                sid = f.session_id or 'UNKNOWN'
                by_session[sid].append(f)
        
        closest_match = None
        closest_days = None
        
        for sid, session_files in by_session.items():
            # Get median date of this calibration session
            cal_dates = []
            for f in session_files:
                if f.obs_date:
                    try:
                        cal_dates.append(datetime.strptime(f.obs_date, '%Y-%m-%d'))
                    except:
                        continue
            
            if not cal_dates:
                continue
            
            cal_dates.sort()
            median_cal = cal_dates[len(cal_dates) // 2]
            
            days_diff = abs((median_cal - median_target).days)
            
            # Check if within max_days limit (if specified)
            if max_days is not None and days_diff > max_days:
                continue
            
            # Track closest match
            if closest_days is None or days_diff < closest_days:
                closest_days = days_diff
                closest_match = session_files
        
        if closest_match is None:
            return None
        
        return (closest_match, closest_days)
    

    def _find_matching_darks(self, session, light_sessions: set, gap_combinations: set,
                            light_dates: set) -> List[CalibrationMatch]:
        """
        Find dark frames only for camera+exposure combinations that aren't already covered.
        Returns only ONE set of darks per (camera, exposure) - the closest to ALL light frames.
        No time limit - will find the closest match regardless of age.
        """
        matches = []
        
        # Convert set to list for matching (use ALL dates, not clusters)
        all_light_dates = list(light_dates) if light_dates else []
        
        for camera, exposure in gap_combinations:
            # Query for ALL matching darks
            query = session.query(FitsFile).filter(
                FitsFile.frame_type == 'DARK',
                FitsFile.camera == camera,
                FitsFile.exposure == exposure,
                FitsFile.migration_ready == True
            )
            
            all_darks = query.all()
            
            if not all_darks:
                continue
            
            # Find the single closest match to ALL light dates
            result = self._find_closest_calibration_for_dates(
                all_darks, 
                all_light_dates,
                max_days=None  # No time limit for darks
            )
            
            if result:
                matched_files, days_diff = result
                
                # Get the session ID and date from the matched files
                sid = matched_files[0].session_id or 'UNKNOWN'
                obs_date = matched_files[0].obs_date if matched_files[0].obs_date else 'Unknown'
                
                matches.append(CalibrationMatch(
                    capture_session_id=sid,
                    camera=camera,
                    telescope=None,
                    filters=[],
                    capture_date=obs_date,
                    frame_type='DARK',
                    file_count=len(matched_files),
                    exposure_times=[exposure],
                    files=matched_files,
                    matched_light_dates=all_light_dates,
                    days_from_lights=days_diff
                ))
        
        return matches


    def _find_matching_flats(self, session, light_sessions: set, gap_combinations: set,
                            light_dates: set) -> List[CalibrationMatch]:
        """
        Find flat frames only for camera+telescope+filter combinations that aren't already covered.
        Returns the CLOSEST match for each date cluster, with cascading time windows:
        - First try: ±30 days (green - ideal)
        - Second try: ±60 days (yellow - acceptable)
        - Third try: ±90 days (red - old but usable)
        """
        matches = []
        
        # Cluster light dates to handle multi-date sessions
        date_clusters = self._cluster_light_dates(light_dates)
        
        for camera, telescope, filter_name in gap_combinations:
            # Query for ALL matching flats
            query = session.query(FitsFile).filter(
                FitsFile.frame_type == 'FLAT',
                FitsFile.camera == camera,
                FitsFile.telescope == telescope,
                FitsFile.filter == filter_name,
                FitsFile.migration_ready == True
            )
            
            all_flats = query.all()
            
            if not all_flats:
                continue
            
            # For each date cluster, try cascading time windows
            for cluster_dates in date_clusters:
                matched_files = None
                days_diff = None
                
                # Try 30 days first (green - ideal)
                result = self._find_closest_calibration_for_dates(
                    all_flats, 
                    cluster_dates,
                    max_days=30
                )
                
                if result:
                    matched_files, days_diff = result
                else:
                    # Try 60 days (yellow - acceptable)
                    result = self._find_closest_calibration_for_dates(
                        all_flats, 
                        cluster_dates,
                        max_days=60
                    )
                    
                    if result:
                        matched_files, days_diff = result
                    else:
                        # Try 90 days (red - old but usable)
                        result = self._find_closest_calibration_for_dates(
                            all_flats, 
                            cluster_dates,
                            max_days=90
                        )
                        
                        if result:
                            matched_files, days_diff = result
                
                # If we found a match at any tier, add it
                if matched_files:
                    # Get the session ID and date from the matched files
                    sid = matched_files[0].session_id or 'UNKNOWN'
                    obs_date = matched_files[0].obs_date if matched_files[0].obs_date else 'Unknown'
                    
                    matches.append(CalibrationMatch(
                        capture_session_id=sid,
                        camera=camera,
                        telescope=telescope,
                        filters=[filter_name],
                        capture_date=obs_date,
                        frame_type='FLAT',
                        file_count=len(matched_files),
                        exposure_times=[],
                        files=matched_files,
                        matched_light_dates=cluster_dates,
                        days_from_lights=days_diff
                    ))
        
        return matches
        

    def _find_matching_bias(self, session, light_sessions: set, gap_cameras: set,
                           light_dates: set) -> List[CalibrationMatch]:
        """
        Find bias frames only for cameras that aren't already covered.
        Returns only ONE set of bias per camera - the closest to ALL light frames.
        No time limit - will find the closest match regardless of age.
        """
        matches = []
        
        # Convert set to list for matching (use ALL dates, not clusters)
        all_light_dates = list(light_dates) if light_dates else []
        
        for camera in gap_cameras:
            # Query for ALL matching bias
            query = session.query(FitsFile).filter(
                FitsFile.frame_type == 'BIAS',
                FitsFile.camera == camera,
                FitsFile.migration_ready == True
            )
            
            all_bias = query.all()
            
            if not all_bias:
                continue
            
            # Find the single closest match to ALL light dates
            result = self._find_closest_calibration_for_dates(
                all_bias, 
                all_light_dates,
                max_days=None  # No time limit for bias
            )
            
            if result:
                matched_files, days_diff = result
                
                # Get the session ID and date from the matched files
                sid = matched_files[0].session_id or 'UNKNOWN'
                obs_date = matched_files[0].obs_date if matched_files[0].obs_date else 'Unknown'
                
                matches.append(CalibrationMatch(
                    capture_session_id=sid,
                    camera=camera,
                    telescope=None,
                    filters=[],
                    capture_date=obs_date,
                    frame_type='BIAS',
                    file_count=len(matched_files),
                    exposure_times=[],
                    files=matched_files,
                    matched_light_dates=all_light_dates,
                    days_from_lights=days_diff
                ))
        
        return matches

    def add_calibration_to_session(self, session_id: str, 
                                 calibration_matches: Dict[str, List[CalibrationMatch]]) -> bool:
        """Add selected calibration files to processing session."""
        all_files = []
        
        # Collect all files from selected matches
        for frame_type, matches in calibration_matches.items():
            for match in matches:
                all_files.extend(match.files)
        
        if not all_files:
            return False
        
        # Extract file IDs and add to session
        file_ids = [f.id for f in all_files]
        return self.add_files_to_session(session_id, file_ids)
    
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
    
    def _generate_staged_filename(self, file_obj: FitsFile, original_filename: str) -> str:
        """Generate a prefixed filename using capture session ID."""
        # Use capture session ID as prefix instead of hash
        session_prefix = file_obj.session_id or "UNKNOWN"
        
        # Clean session ID for filesystem use
        session_prefix = "".join(c for c in session_prefix if c.isalnum() or c in ('_', '-'))
        session_prefix = session_prefix[:20]  # Limit length
        
        # Extract base name and extension
        name_parts = original_filename.split('.')
        if len(name_parts) > 1:
            base_name = '.'.join(name_parts[:-1])
            extension = name_parts[-1]
        else:
            base_name = original_filename
            extension = ''
        
        # Create prefixed filename: {session_id}_{base_name}.{extension}
        if extension:
            staged_filename = f"{session_prefix}_{base_name}.{extension}"
        else:
            staged_filename = f"{session_prefix}_{base_name}"
        
        return staged_filename
    
    def _stage_files(self, session_folder: Path, files: List[FitsFile], 
                    session_id: str) -> List[Dict]:
        """Create symbolic links for files in the processing session."""
        staged_files = []
        
        for file_obj in files:
            original_path = Path(file_obj.folder) / file_obj.file
            
            # Validate original file exists before attempting to stage
            if not original_path.exists():
                logger.error(f"Cannot stage file - original not found: {original_path}")
                raise FileNotFoundError(f"Original file not found: {original_path}")
            
            # Determine subfolder based on frame type
            frame_type = (file_obj.frame_type or 'UNKNOWN').upper()
            if frame_type == 'LIGHT':
                subfolder_name = 'lights'
                subfolder_path = session_folder / "raw" / "lights"
            elif frame_type in ['DARK', 'FLAT', 'BIAS']:
                if frame_type == 'BIAS':
                    subfolder_name = 'bias'
                else:
                    subfolder_name = frame_type.lower() + 's'
                subfolder_path = session_folder / "raw" / "calibration" / subfolder_name
            else:
                # Unknown frame types go in lights folder with a warning
                logger.warning(f"Unknown frame type {frame_type} for file {file_obj.file}, placing in lights")
                subfolder_name = 'lights'
                subfolder_path = session_folder / "raw" / "lights"
            
            # Generate staged filename using capture session ID
            staged_filename = self._generate_staged_filename(file_obj, file_obj.file)
            staged_path = subfolder_path / staged_filename
            
            # Handle filename collisions
            counter = 1
            original_staged_path = staged_path
            while staged_path.exists():
                name_parts = staged_filename.split('.')
                if len(name_parts) > 1:
                    base_name = '.'.join(name_parts[:-1])
                    extension = name_parts[-1]
                    staged_filename = f"{base_name}_{counter:03d}.{extension}"
                else:
                    staged_filename = f"{staged_filename}_{counter:03d}"
                staged_path = subfolder_path / staged_filename
                counter += 1
            
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
                                    notes: Optional[str], files: Optional[List[FitsFile]] = None):
            """Create a markdown info file for the processing session in centralized location."""
            
            # Store markdown in centralized Session_Notes folder from config
            # Extract year from session_id (format: YYYYMMDD_...)
            try:
                year = int(session_id[:4])
            except (ValueError, IndexError):
                # Fallback to current year if session_id doesn't start with year
                year = datetime.now().year
            
            # Get notes directory from config
            notes_dir = Path(self.config.paths.notes_dir) / "Processing_Sessions" / str(year)
            notes_dir.mkdir(parents=True, exist_ok=True)
            
            info_file = notes_dir / f"{session_id}.md"
            
            # Format objects list properly
            objects_str = ', '.join(objects) if objects else 'No objects specified'
            
            # Build acquisition details table for light frames
            acquisition_table = self._build_acquisition_table(session_id, files)
            
            content = f"""# Processing Session: {name}

**Session ID:** `{session_id}`  
**Created:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Status:** Not Started  

## Objects
{objects_str}

## File Summary
- **Light frames:** {frame_counts['LIGHT']}
- **Dark frames:** {frame_counts['DARK']}
- **Flat frames:** {frame_counts['FLAT']}
- **Bias frames:** {frame_counts['BIAS']}
- **Total files:** {sum(frame_counts.values())}

## Acquisition Details

{acquisition_table}

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

        
    def _build_acquisition_table(self, session_id: str, files: Optional[List[FitsFile]] = None) -> str:
        """Build acquisition details table for light frames in Astrobin format."""
        
        # If files not provided, query from database
        if files is None:
            session = self.db_service.db_manager.get_session()
            try:
                # Get all LIGHT frames for this session
                light_files = session.query(FitsFile).join(ProcessingSessionFile).filter(
                    ProcessingSessionFile.processing_session_id == session_id,
                    FitsFile.frame_type == 'LIGHT'
                ).all()
            finally:
                session.close()
        else:
            # Filter to only LIGHT frames from provided files
            light_files = [f for f in files if f.frame_type == 'LIGHT']
        
        if not light_files:
            return "_No light frames in this session_"
        
        # Group by date, filter, exposure, and binning
        from collections import defaultdict
        acquisition_data = defaultdict(int)
        
        for f in light_files:
            date = f.obs_date if f.obs_date else 'Unknown'
            filter_name = f.filter if f.filter and f.filter not in ['UNKNOWN', 'NONE'] else 'No Filter'
            exposure = int(f.exposure) if f.exposure else 0
            binning = f.binning_x if f.binning_x else 1
            
            # Create key tuple
            key = (date, filter_name, exposure, binning)
            acquisition_data[key] += 1
        
        # Sort by date, then filter
        sorted_data = sorted(acquisition_data.items(), key=lambda x: (x[0][0], x[0][1]))
        
        # Build markdown table with aligned columns
        table = "| Date       | Filter        | Number | Duration (s) | Binning |\n"
        table += "|------------|---------------|--------|--------------|---------|"
        
        for (date, filter_name, exposure, binning), count in sorted_data:
            table += f"\n| {date:<10} | {filter_name:<13} | {count:>6} | {exposure:>12} | {binning:>7} |"
        
        return table

    
    def _update_session_info_file(self, session_folder: Path, ps: ProcessingSession):
        """Update the session info file with current session data."""
        objects = json.loads(ps.objects) if ps.objects else []
        
        # Get current file counts
        session = self.db_service.db_manager.get_session()
        try:
            file_counts_query = session.query(ProcessingSessionFile.frame_type).filter(
                ProcessingSessionFile.processing_session_id == ps.id
            ).all()
            
            frame_counts = {'LIGHT': 0, 'DARK': 0, 'FLAT': 0, 'BIAS': 0}
            for (frame_type,) in file_counts_query:
                if frame_type in frame_counts:
                    frame_counts[frame_type] += 1
        finally:
            session.close()
        
        self._create_session_info_file(session_folder, ps.id, ps.name, objects, 
                                     frame_counts, ps.notes, None)
        
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
                
                # Parse JSON fields
                objects = json.loads(ps.objects) if ps.objects else []
                social_urls = json.loads(ps.social_urls) if ps.social_urls else []
                
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
                    notes=ps.notes,
                    version=ps.version,
                    astrobin_url=ps.astrobin_url,
                    social_urls=social_urls,
                    processing_started=ps.processing_started,
                    processing_completed=ps.processing_completed,
                    updated_at=ps.updated_at
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