"""FITS File Validation Module - Scores files for migration readiness."""

import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session
from tqdm import tqdm

from models import DatabaseService, FitsFile, Camera, Telescope, FilterMapping

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Validation result for a single FITS file."""
    score: float
    max_possible: int
    migration_ready: bool
    notes: List[str]
    breakdown: Dict[str, float]
    file_exists: bool = True


class FitsValidator:
    """Validates FITS files and calculates migration readiness scores."""
    
    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service
        
        # Cache equipment tables for performance
        self._cameras = None
        self._telescopes = None 
        self._filter_mappings = None
        self._camera_types = None  # rgb field lookup
        
        # Migration thresholds
        self.AUTO_MIGRATE_THRESHOLD = 95.0
        self.REVIEW_THRESHOLD = 80.0
    
    def _load_equipment_data(self):
        """Load and cache equipment data."""
        if self._cameras is None:
            cameras = self.db_service.get_cameras()
            self._cameras = {cam.name for cam in cameras}
            self._camera_types = {cam.name: getattr(cam, 'rgb', True) for cam in cameras}
            
        if self._telescopes is None:
            telescopes = self.db_service.get_telescopes()
            self._telescopes = {tel.name for tel in telescopes}
            
        if self._filter_mappings is None:
            mappings = self.db_service.get_filter_mappings()
            self._filter_mappings = set(mappings.keys()) | set(mappings.values())
    
    def _check_file_exists(self, db_record: FitsFile) -> bool:
        """Check if the physical file exists on disk."""
        file_path = Path(db_record.folder) / db_record.file
        return file_path.exists()
    
    def _score_equipment(self, equipment_name: str, equipment_set: set, full_points: float) -> Tuple[float, str]:
        """Score equipment field based on standardization."""
        if not equipment_name or equipment_name.upper() in ['UNKNOWN', 'NULL', 'NONE']:
            return 0.0, "missing/unknown"
        
        if equipment_name in equipment_set:
            return full_points, "standard"
        else:
            return full_points * 0.25, "non-standard"
    
    def _score_filter(self, filter_name: str, camera_name: str, full_points: float = 10.0) -> Tuple[float, str]:
        """Score filter field based on camera type and standardization."""
        if not filter_name:
            return 0.0, "NULL filter"
        
        # Get camera type (True = OSC/color, False = mono)
        is_osc = self._camera_types.get(camera_name, True)  # Default to OSC if unknown camera
        filter_upper = filter_name.upper()
        
        # Check if it's a standard filter
        is_standard = filter_name in self._filter_mappings
        
        if is_osc:
            # OSC cameras: any valid filter including "NONE" gets full points
            if is_standard or filter_upper in ['NONE', 'CLEAR']:
                return full_points, "OSC + valid filter"
            else:
                return full_points * 0.25, "OSC + non-standard filter"
        else:
            # Mono cameras
            if filter_upper in ['NONE', 'CLEAR']:
                return 2.5, "mono + no filter (unusual)"
            elif is_standard:
                return full_points, "mono + standard filter"
            else:
                return full_points * 0.25, "mono + non-standard filter"
    
    def _validate_light_frame(self, record: Dict) -> ValidationResult:
        """Validate LIGHT frame (100 points max)."""
        score = 0.0
        notes = []
        breakdown = {}
        
        # Critical Fields
        # object (20 points)
        obj = record.get('object')
        if obj and str(obj).upper() not in ['UNKNOWN', 'CALIBRATION', 'NULL', 'NONE']:
            obj_score = 20.0
            notes.append("Valid object name")
        else:
            obj_score = 0.0
            notes.append("Missing/invalid object name")
        score += obj_score
        breakdown['object'] = obj_score
        
        # obs_date (20 points)
        obs_date = record.get('obs_date')
        if obs_date:
            date_score = 20.0
            notes.append("Observation date present")
        else:
            date_score = 0.0
            notes.append("Missing observation date")
        score += date_score
        breakdown['obs_date'] = date_score
        
        # camera (15 points)
        camera = record.get('camera')
        cam_score, cam_note = self._score_equipment(camera, self._cameras, 15.0)
        score += cam_score
        breakdown['camera'] = cam_score
        notes.append(f"Camera: {cam_note}")
        
        # telescope (15 points)
        telescope = record.get('telescope')
        tel_score, tel_note = self._score_equipment(telescope, self._telescopes, 15.0)
        score += tel_score
        breakdown['telescope'] = tel_score
        notes.append(f"Telescope: {tel_note}")
        
        # filter (10 points)
        filter_name = record.get('filter')
        filt_score, filt_note = self._score_filter(filter_name, camera, 10.0)
        score += filt_score
        breakdown['filter'] = filt_score
        notes.append(f"Filter: {filt_note}")
        
        # Important Fields
        # exposure (10 points)
        exposure = record.get('exposure', 0)
        if exposure and exposure > 0:
            exp_score = 10.0
            notes.append("Valid exposure time")
        else:
            exp_score = 0.0
            notes.append("Missing/invalid exposure")
        score += exp_score
        breakdown['exposure'] = exp_score
        
        # focal_length (5 points)
        focal_length = record.get('focal_length')
        if focal_length:
            fl_score = 5.0
            notes.append("Focal length present")
        else:
            fl_score = 0.0
            notes.append("Missing focal length")
        score += fl_score
        breakdown['focal_length'] = fl_score
        
        # ra/dec coordinates (5 points)
        ra = record.get('ra')
        dec = record.get('dec')
        if ra and dec:
            coord_score = 5.0
            notes.append("Coordinates present")
        else:
            coord_score = 0.0
            notes.append("Missing coordinates")
        score += coord_score
        breakdown['coordinates'] = coord_score
        
        migration_ready = score >= self.AUTO_MIGRATE_THRESHOLD
        
        return ValidationResult(
            score=score,
            max_possible=100,
            migration_ready=migration_ready,
            notes=notes,
            breakdown=breakdown
        )
    
    def _validate_flat_frame(self, record: Dict) -> ValidationResult:
        """Validate FLAT frame (100 points max)."""
        score = 0.0
        notes = []
        breakdown = {}
        
        # obs_date (25 points)
        obs_date = record.get('obs_date')
        if obs_date:
            date_score = 25.0
            notes.append("Observation date present")
        else:
            date_score = 0.0
            notes.append("Missing observation date")
        score += date_score
        breakdown['obs_date'] = date_score
        
        # camera (20 points)
        camera = record.get('camera')
        cam_score, cam_note = self._score_equipment(camera, self._cameras, 20.0)
        score += cam_score
        breakdown['camera'] = cam_score
        notes.append(f"Camera: {cam_note}")
        
        # telescope (20 points)
        telescope = record.get('telescope')
        tel_score, tel_note = self._score_equipment(telescope, self._telescopes, 20.0)
        score += tel_score
        breakdown['telescope'] = tel_score
        notes.append(f"Telescope: {tel_note}")
        
        # filter (25 points) - critical for flats
        filter_name = record.get('filter')
        filt_score, filt_note = self._score_filter(filter_name, camera, 25.0)
        score += filt_score
        breakdown['filter'] = filt_score
        notes.append(f"Filter: {filt_note}")
        
        # exposure (10 points)
        exposure = record.get('exposure', 0)
        if exposure and exposure > 0:
            exp_score = 10.0
            notes.append("Valid exposure time")
        else:
            exp_score = 0.0
            notes.append("Missing/invalid exposure")
        score += exp_score
        breakdown['exposure'] = exp_score
        
        migration_ready = score >= self.AUTO_MIGRATE_THRESHOLD
        
        return ValidationResult(
            score=score,
            max_possible=100,
            migration_ready=migration_ready,
            notes=notes,
            breakdown=breakdown
        )
    
    def _validate_dark_frame(self, record: Dict) -> ValidationResult:
        """Validate DARK frame - only needs camera, exposure, date (no telescope/object)."""
        score = 0.0
        notes = []
        breakdown = {}
        
        # obs_date (30 points)
        obs_date = record.get('obs_date')
        if obs_date:
            date_score = 30.0
            notes.append("Observation date present")
        else:
            date_score = 0.0
            notes.append("Missing observation date")
        score += date_score
        breakdown['obs_date'] = date_score
        
        # camera (50 points) - most critical for darks
        camera = record.get('camera')
        cam_score, cam_note = self._score_equipment(camera, self._cameras, 50.0)
        score += cam_score
        breakdown['camera'] = cam_score
        notes.append(f"Camera: {cam_note}")
        
        # exposure (20 points) - critical for dark matching
        exposure = record.get('exposure')
        if exposure is not None and exposure >= 0:
            exp_score = 20.0
            notes.append("Valid exposure time")
        else:
            exp_score = 0.0
            notes.append("Missing/invalid exposure")
        score += exp_score
        breakdown['exposure'] = exp_score
        
        migration_ready = score >= self.AUTO_MIGRATE_THRESHOLD
        
        return ValidationResult(
            score=score,
            max_possible=100,
            migration_ready=migration_ready,
            notes=notes,
            breakdown=breakdown
        )
    
    def _validate_bias_frame(self, record: Dict) -> ValidationResult:
        """Validate BIAS frame (100 points max)."""
        score = 0.0
        notes = []
        breakdown = {}
        
        # obs_date (50 points)
        obs_date = record.get('obs_date')
        if obs_date:
            date_score = 50.0
            notes.append("Observation date present")
        else:
            date_score = 0.0
            notes.append("Missing observation date")
        score += date_score
        breakdown['obs_date'] = date_score
        
        # camera (50 points)
        camera = record.get('camera')
        cam_score, cam_note = self._score_equipment(camera, self._cameras, 50.0)
        score += cam_score
        breakdown['camera'] = cam_score
        notes.append(f"Camera: {cam_note}")
        
        migration_ready = score >= self.AUTO_MIGRATE_THRESHOLD
        
        return ValidationResult(
            score=score,
            max_possible=100,
            migration_ready=migration_ready,
            notes=notes,
            breakdown=breakdown
        )
    
    def validate_record(self, record: Dict) -> ValidationResult:
        """Validate a single FITS file record."""
        self._load_equipment_data()
        
        frame_type = record.get('frame_type', '').upper()
        
        if frame_type == 'LIGHT':
            return self._validate_light_frame(record)
        elif frame_type == 'FLAT':
            return self._validate_flat_frame(record)
        elif frame_type == 'DARK':
            return self._validate_dark_frame(record)
        elif frame_type == 'BIAS':
            return self._validate_bias_frame(record)
        else:
            return ValidationResult(
                score=0.0,
                max_possible=100,
                migration_ready=False,
                notes=[f"Unknown frame type: {frame_type}"],
                breakdown={'frame_type': 0.0}
            )
    
    def validate_all_files(self, limit: Optional[int] = None, 
                          check_files: bool = True,
                          progress_callback=None) -> Dict[str, int]:
        """
        Validate all FITS files in the database.
        
        Args:
            limit: Maximum number of files to validate
            check_files: If True, also check if physical files exist
            progress_callback: Optional callback for progress updates
        """
        import uuid
        run_id = str(uuid.uuid4())[:8]
        logger.info(f"VALIDATION START - Run ID: {run_id}, Check files: {check_files}")

        self._load_equipment_data()
        
        session = self.db_service.db_manager.get_session()
        stats = {
            'total': 0,
            'auto_migrate': 0,
            'needs_review': 0,
            'manual_only': 0,
            'missing_files': 0,
            'updated': 0,
            'errors': 0
        }
        
        try:
            query = session.query(FitsFile)
            if limit:
                query = query.limit(limit)
            
            records = query.all()
            stats['total'] = len(records)
            
            logger.info(f"Validating {len(records)} FITS files...")
            
            with tqdm(total=len(records), desc="Validating files") as pbar:
                for i, db_record in enumerate(records):
                    try:
                        # Check if file exists on disk
                        file_exists = True
                        if check_files:
                            file_exists = self._check_file_exists(db_record)
                            if not file_exists:
                                stats['missing_files'] += 1
                                db_record.file_not_found = True
                                logger.warning(f"File not found: {db_record.folder}/{db_record.file}")
                        
                        # Convert database record to dict
                        record_dict = {
                            'object': db_record.object,
                            'obs_date': db_record.obs_date,
                            'camera': db_record.camera,
                            'telescope': db_record.telescope,
                            'filter': db_record.filter,
                            'exposure': db_record.exposure,
                            'frame_type': db_record.frame_type,
                            'focal_length': db_record.focal_length,
                            'ra': db_record.ra,
                            'dec': db_record.dec
                        }
                        
                        # Validate metadata
                        result = self.validate_record(record_dict)
                        result.file_exists = file_exists
                        
                        # Update database record
                        db_record.validation_score = result.score
                        db_record.migration_ready = result.migration_ready and file_exists
                        db_record.validation_notes = "; ".join(result.notes) if result.notes else None
                        
                        # Update stats
                        if result.score >= self.AUTO_MIGRATE_THRESHOLD and file_exists:
                            stats['auto_migrate'] += 1
                        elif result.score >= self.REVIEW_THRESHOLD:
                            stats['needs_review'] += 1
                        else:
                            stats['manual_only'] += 1
                        
                        stats['updated'] += 1
                        
                        # Progress callback
                        if progress_callback and i % 100 == 0:
                            progress = int((i + 1) / len(records) * 100)
                            progress_callback(progress, stats)
                        
                    except Exception as e:
                        logger.error(f"Error validating file {db_record.file}: {e}")
                        stats['errors'] += 1
                    
                    pbar.update(1)
            
            # Commit all changes
            session.commit()
            
            logger.info(f"VALIDATION COMPLETE - Run ID: {run_id}")
            logger.info(f"Stats: {stats}")
            
        except Exception as e:
            session.rollback()
            logger.error(f"Validation failed: {e}")
            raise
        finally:
            session.close()
        
        return stats
    
    def remove_missing_files(self, dry_run: bool = True) -> Dict[str, int]:
        """
        Remove database records for files that don't exist on disk.
        
        Args:
            dry_run: If True, only report what would be deleted
        
        Returns:
            Statistics about removed files
        """
        session = self.db_service.db_manager.get_session()
        stats = {
            'checked': 0,
            'missing': 0,
            'removed': 0
        }
        
        try:
            # Get all files marked as not found
            missing_files = session.query(FitsFile).filter(
                FitsFile.file_not_found == True
            ).all()
            
            stats['missing'] = len(missing_files)
            
            if not dry_run:
                for db_record in missing_files:
                    logger.info(f"Removing missing file: {db_record.folder}/{db_record.file}")
                    session.delete(db_record)
                    stats['removed'] += 1
                
                session.commit()
                logger.info(f"Removed {stats['removed']} missing file records")
            else:
                logger.info(f"Dry run: Would remove {stats['missing']} missing file records")
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error removing missing files: {e}")
            raise
        finally:
            session.close()
        
        return stats
    
    def get_validation_summary(self) -> Dict:
        """Get validation summary statistics."""
        session = self.db_service.db_manager.get_session()

        try:
            from sqlalchemy import func

            # Get total files
            total_files = session.query(func.count(FitsFile.id)).scalar() or 0

            # Get counts by migration category
            auto_migrate = session.query(func.count(FitsFile.id)).filter(
                FitsFile.validation_score >= self.AUTO_MIGRATE_THRESHOLD
            ).scalar() or 0

            needs_review = session.query(func.count(FitsFile.id)).filter(
                FitsFile.validation_score >= self.REVIEW_THRESHOLD,
                FitsFile.validation_score < self.AUTO_MIGRATE_THRESHOLD
            ).scalar() or 0

            manual_only = session.query(func.count(FitsFile.id)).filter(
                FitsFile.validation_score < self.REVIEW_THRESHOLD
            ).scalar() or 0

            # Get average scores by frame type
            frame_type_stats = session.query(
                FitsFile.frame_type,
                func.avg(FitsFile.validation_score).label('avg_score'),
                func.count(FitsFile.id).label('count')
            ).group_by(FitsFile.frame_type).all()

            summary = {
                'total_files': total_files,
                'auto_migrate': auto_migrate,
                'needs_review': needs_review,
                'manual_only': manual_only,
                'frame_type_averages': {}
            }

            for frame_type, avg_score, count in frame_type_stats:
                summary['frame_type_averages'][frame_type or 'UNKNOWN'] = {
                    'avg_score': float(avg_score) if avg_score else 0.0,
                    'count': count
                }

            return summary

        finally:
            session.close()