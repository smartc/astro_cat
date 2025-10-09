"""Database models for FITS Cataloger - EXTENDED VERSION."""

from datetime import datetime
from typing import Optional, List, Dict, Tuple

from sqlalchemy import (
    Boolean, DateTime, Float, Integer, String, Text, 
    create_engine, Column, Index, ForeignKey, event
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func

Base = declarative_base()

class ObjectProcessingLog(Base):
    """Log of object name processing failures."""
    __tablename__ = 'object_processing_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    raw_object_name = Column(String(255))
    proposed_object_name = Column(String(255))
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class FitsFile(Base):
    """Main table for FITS file metadata - EXTENDED VERSION."""
    __tablename__ = 'fits_files'

    # Primary identification
    id = Column(Integer, primary_key=True, autoincrement=True)
    file = Column(String(255), nullable=False)
    folder = Column(String(500), nullable=False)
    
    # Target and observation info
    object = Column(String(100))
    obs_date = Column(String(10))
    obs_timestamp = Column(DateTime)
    
    # Coordinates
    ra = Column(String(20))
    dec = Column(String(20))
    
    # Image dimensions
    x = Column(Integer)
    y = Column(Integer)
    
    # Frame classification
    frame_type = Column(String(20))
    filter = Column(String(20))
    
    # Optical parameters
    focal_length = Column(Float)
    exposure = Column(Float)
    
    # Equipment
    camera = Column(String(50))
    telescope = Column(String(50))
    
    # File hash
    md5sum = Column(String(32), unique=True, index=True)
    
    # Location data
    latitude = Column(Float)
    longitude = Column(Float)
    elevation = Column(Float)
    
    # Field of view data
    fov_x = Column(Float)
    fov_y = Column(Float)
    pixel_scale = Column(Float)
    
    # ========================================================================
    # EXTENDED METADATA FIELDS - ADDED IN SCHEMA V2
    # ========================================================================
    
    # Camera/Sensor settings
    gain = Column(Integer)
    offset = Column(Integer)
    egain = Column(Float)
    binning_x = Column(Integer, default=1)
    binning_y = Column(Integer, default=1)
    sensor_temp = Column(Float)
    readout_mode = Column(String(50))
    bayerpat = Column(String(10))
    iso_speed = Column(Integer)
    
    # Guiding information
    guide_rms = Column(Float)
    guide_fwhm = Column(Float)
    guide_rms_ra = Column(Float)
    guide_rms_dec = Column(Float)
    
    # Weather conditions
    ambient_temp = Column(Float)
    dewpoint = Column(Float)
    humidity = Column(Float)
    pressure = Column(Float)
    sky_temp = Column(Float)
    sky_quality_mpsas = Column(Float)
    sky_brightness = Column(Float)
    wind_speed = Column(Float)
    wind_direction = Column(Float)
    wind_gust = Column(Float)
    cloud_cover = Column(Float)
    seeing_fwhm = Column(Float)
    
    # Focus information
    focuser_position = Column(Integer)
    focuser_temp = Column(Float)
    
    # Software and observer
    software_creator = Column(String(100))
    software_modifier = Column(String(100))
    observer = Column(String(100))
    site_name = Column(String(100))
    
    # Airmass and timing
    airmass = Column(Float)
    exposure_start = Column(DateTime)
    exposure_end = Column(DateTime)
    
    # Additional quality metrics
    star_count = Column(Integer)
    median_fwhm = Column(Float)
    eccentricity = Column(Float)
    
    # Boltwood Cloud Sensor
    boltwood_cloud = Column(Float)
    boltwood_wind = Column(Float)
    boltwood_rain = Column(Float)
    boltwood_daylight = Column(Float)
    
    # ========================================================================
    # END EXTENDED FIELDS
    # ========================================================================
    
    # File management fields
    bad = Column(Boolean, default=False)
    file_not_found = Column(Boolean, default=False)
    
    # Original location tracking
    orig_file = Column(String(255))
    orig_folder = Column(String(500))
    
    # Validation fields
    validation_score = Column(Float)
    migration_ready = Column(Boolean, default=False)
    validation_notes = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    session_id = Column(String(50))

    __table_args__ = (
        Index('idx_object_date', 'object', 'obs_date'),
        Index('idx_camera_telescope', 'camera', 'telescope'),
        Index('idx_frame_type_filter', 'frame_type', 'filter'),
        Index('idx_session', 'session_id'),
        Index('idx_location', 'latitude', 'longitude'),
        Index('idx_validation_score', 'validation_score'),
        Index('idx_migration_ready', 'migration_ready'),
        Index('idx_software_creator', 'software_creator'),
        Index('idx_observer', 'observer'),
        Index('idx_sky_quality', 'sky_quality_mpsas'),
    )


class ProcessLog(Base):
    """Log of processing sessions."""
    __tablename__ = 'process_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_name = Column(String(100), nullable=False)
    object = Column(String(100))
    image_type = Column(String(20))
    create_date = Column(DateTime, default=datetime.utcnow)
    status = Column(Integer, default=0)
    notes = Column(Text)
    files_processed = Column(Integer, default=0)
    files_failed = Column(Integer, default=0)


class Camera(Base):
    """Camera specifications."""
    __tablename__ = 'cameras'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    x_pixels = Column(Integer, nullable=False)
    y_pixels = Column(Integer, nullable=False)
    pixel_size = Column(Float)
    binning_support = Column(String(20), default="1,2,3,4")
    notes = Column(Text)
    active = Column(Boolean, default=True)


class Telescope(Base):
    """Telescope/lens specifications."""
    __tablename__ = 'telescopes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    focal_length = Column(Float, nullable=False)
    aperture = Column(Float)
    telescope_type = Column(String(20))
    notes = Column(Text)
    active = Column(Boolean, default=True)


class FilterMapping(Base):
    """Mapping table for filter name normalization."""
    __tablename__ = 'filter_mappings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_name = Column(String(50), unique=True, nullable=False)
    standard_name = Column(String(20), nullable=False)
    filter_type = Column(String(20))
    bandpass = Column(String(20))
    notes = Column(Text)


class Session(Base):
    """Imaging sessions table."""
    __tablename__ = 'sessions'

    session_id = Column(String(50), primary_key=True)
    session_date = Column(String(10), nullable=False)
    telescope = Column(String(50))
    camera = Column(String(50))
    site_name = Column(String(100))
    latitude = Column(Float)
    longitude = Column(Float)
    elevation = Column(Float)
    observer = Column(String(100))
    notes = Column(Text)
    
    # Extended session metadata
    avg_seeing = Column(Float)
    avg_sky_quality = Column(Float)
    avg_cloud_cover = Column(Float)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_session_date', 'session_date'),
        Index('idx_session_telescope_camera', 'telescope', 'camera'),
    )


class ProcessingSession(Base):
    """Processing session for selected FITS files."""
    __tablename__ = 'processing_sessions'
    
    id = Column(String(50), primary_key=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Metadata
    objects = Column(Text)  # JSON array of object names
    notes = Column(Text)
    status = Column(String(20), default='not_started')  # not_started, in_progress, complete
    version = Column(Integer, default=1)
    
    # External references
    astrobin_url = Column(String(500))
    social_urls = Column(Text)  # JSON array
    
    # Processing timeline
    processing_started = Column(DateTime)
    processing_completed = Column(DateTime)
    
    # File system
    folder_path = Column(String(500))
    
    __table_args__ = (
        Index('idx_processing_status', 'status'),
        Index('idx_processing_created', 'created_at'),
        Index('idx_processing_objects', 'objects'),
    )


class ProcessingSessionFile(Base):
    """Files included in a processing session."""
    __tablename__ = 'processing_session_files'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    processing_session_id = Column(String(50), ForeignKey('processing_sessions.id', ondelete='CASCADE'))
    fits_file_id = Column(Integer, ForeignKey('fits_files.id', ondelete='CASCADE'))
    
    # Original file information
    original_path = Column(String(500), nullable=False)
    original_filename = Column(String(255), nullable=False)
    
    # Staged file information
    staged_path = Column(String(500), nullable=False)
    staged_filename = Column(String(255), nullable=False)
    subfolder = Column(String(50), nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    file_size = Column(Integer)
    frame_type = Column(String(20))
    
    __table_args__ = (
        Index('idx_processing_file_session', 'processing_session_id'),
        Index('idx_processing_file_fits', 'fits_file_id'),
        Index('idx_processing_file_type', 'frame_type'),
    )


class SystemSettings(Base):
    """Runtime system settings that persist across restarts."""
    __tablename__ = 'system_settings'
    
    key = Column(String(50), primary_key=True)
    value = Column(String(255), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<SystemSettings(key='{self.key}', value='{self.value}')>"


class DatabaseManager:
    """Database connection and session management."""
    
    def __init__(self, connection_string: str):
        self.engine = create_engine(connection_string, echo=False)

        if 'sqlite' in connection_string:
            @event.listens_for(self.engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def create_tables(self):
        """Create all tables."""
        Base.metadata.create_all(bind=self.engine)
    
    def get_session(self):
        """Get a database session."""
        return self.SessionLocal()
    
    def close(self):
        """Close the database connection."""
        self.engine.dispose()


class DatabaseService:
    """High-level database operations."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    def add_fits_file(self, fits_data: dict) -> Tuple[bool, bool]:
        """Add a new FITS file record. Returns (success, is_duplicate)."""
        session = self.db_manager.get_session()
        try:
            existing = session.query(FitsFile).filter_by(
                md5sum=fits_data.get('md5sum')
            ).first()
            
            if existing:
                return True, True
            
            fits_file = FitsFile(**fits_data)
            session.add(fits_file)
            session.commit()
            return True, False
            
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
        
    def get_cameras(self) -> List[Camera]:
        """Get all cameras."""
        session = self.db_manager.get_session()
        try:
            return session.query(Camera).filter_by(active=True).all()
        finally:
            session.close()
    
    def get_telescopes(self) -> List[Telescope]:
        """Get all telescopes."""
        session = self.db_manager.get_session()
        try:
            return session.query(Telescope).filter_by(active=True).all()
        finally:
            session.close()
    
    def get_filter_mappings(self) -> Dict[str, str]:
        """Get filter name mappings."""
        session = self.db_manager.get_session()
        try:
            mappings = session.query(FilterMapping).all()
            return {m.raw_name: m.standard_name for m in mappings}
        finally:
            session.close()
    
    def initialize_equipment(self, cameras: List[dict], telescopes: List[dict], 
                           filter_mappings: Dict[str, str]):
        """Initialize equipment tables from config."""
        session = self.db_manager.get_session()
        try:
            for cam_data in cameras:
                existing = session.query(Camera).filter_by(name=cam_data['name']).first()
                if not existing:
                    camera = Camera(**cam_data)
                    session.add(camera)
            
            for tel_data in telescopes:
                existing = session.query(Telescope).filter_by(name=tel_data['name']).first()
                if not existing:
                    telescope = Telescope(**tel_data)
                    session.add(telescope)
            
            for raw_name, standard_name in filter_mappings.items():
                existing = session.query(FilterMapping).filter_by(raw_name=raw_name).first()
                if not existing:
                    mapping = FilterMapping(
                        raw_name=raw_name,
                        standard_name=standard_name
                    )
                    session.add(mapping)
            
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_database_stats(self) -> Dict:
        """Get database statistics."""
        session = self.db_manager.get_session()
        try:
            stats = {
                'total_files': session.query(FitsFile).count(),
                'light_frames': session.query(FitsFile).filter_by(frame_type='LIGHT').count(),
                'dark_frames': session.query(FitsFile).filter_by(frame_type='DARK').count(),
                'flat_frames': session.query(FitsFile).filter_by(frame_type='FLAT').count(),
                'bias_frames': session.query(FitsFile).filter_by(frame_type='BIAS').count(),
                'cameras': session.query(Camera).filter_by(active=True).count(),
                'telescopes': session.query(Telescope).filter_by(active=True).count(),
                'sessions': session.query(Session).count(),
            }
            return stats
        finally:
            session.close()
    
    def log_object_processing_error(self, filename: str, raw_name: str, 
                                    proposed_name: str, error: str):
        """Log object name processing errors."""
        session = self.db_manager.get_session()
        try:
            log_entry = ObjectProcessingLog(
                filename=filename,
                raw_object_name=raw_name,
                proposed_object_name=proposed_name,
                error_message=error
            )
            session.add(log_entry)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_sessions(self) -> List[Session]:
        """Get all sessions."""
        session = self.db_manager.get_session()
        try:
            return session.query(Session).order_by(Session.session_date.desc()).all()
        finally:
            session.close()

    def get_setting(self, key: str, default=None):
        """Get a system setting value."""
        session = self.db_manager.get_session()
        try:
            setting = session.query(SystemSettings).filter_by(key=key).first()
            if setting:
                value = setting.value
                if value.lower() in ('true', 'false'):
                    return value.lower() == 'true'
                try:
                    return int(value)
                except ValueError:
                    try:
                        return float(value)
                    except ValueError:
                        return value
            return default
        finally:
            session.close()

    def set_setting(self, key: str, value):
        """Set a system setting value."""
        session = self.db_manager.get_session()
        try:
            setting = session.query(SystemSettings).filter_by(key=key).first()
            if setting:
                setting.value = str(value)
                setting.updated_at = datetime.utcnow()
            else:
                setting = SystemSettings(key=key, value=str(value))
                session.add(setting)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_all_settings(self) -> Dict[str, str]:
        """Get all system settings."""
        session = self.db_manager.get_session()
        try:
            settings = session.query(SystemSettings).all()
            return {s.key: s.value for s in settings}
        finally:
            session.close()

    def get_orphaned_records(self) -> Dict[str, int]:
        """Get counts of orphaned records across all tables."""
        session = self.db_manager.get_session()
        
        try:
            orphaned_imaging_sessions = session.query(Session).filter(
                ~Session.session_id.in_(
                    session.query(FitsFile.session_id).distinct()
                )
            ).count()
            
            orphaned_processing_sessions = session.query(ProcessingSession).filter(
                ~ProcessingSession.id.in_(
                    session.query(ProcessingSessionFile.processing_session_id).distinct()
                )
            ).count()
            
            orphaned_ps_files = session.query(ProcessingSessionFile).filter(
                ~ProcessingSessionFile.fits_file_id.in_(
                    session.query(FitsFile.id).distinct()
                )
            ).count()
            
            return {
                'imaging_sessions': orphaned_imaging_sessions,
                'processing_sessions': orphaned_processing_sessions,
                'processing_session_files': orphaned_ps_files,
                'total': (orphaned_imaging_sessions + orphaned_processing_sessions + 
                         orphaned_ps_files)
            }
            
        finally:
            session.close()
    
    def cleanup_orphaned_imaging_sessions(self) -> int:
        """Remove imaging sessions with no associated files."""
        session = self.db_manager.get_session()
        
        try:
            deleted = session.query(Session).filter(
                ~Session.session_id.in_(
                    session.query(FitsFile.session_id).distinct()
                )
            ).delete(synchronize_session=False)
            
            session.commit()
            return deleted
            
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def cleanup_orphaned_processing_sessions(self) -> int:
        """Remove processing sessions with no staged files."""
        session = self.db_manager.get_session()
        
        try:
            deleted = session.query(ProcessingSession).filter(
                ~ProcessingSession.id.in_(
                    session.query(ProcessingSessionFile.processing_session_id).distinct()
                )
            ).delete(synchronize_session=False)
            
            session.commit()
            return deleted
            
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def cleanup_orphaned_ps_files(self) -> int:
        """Remove processing_session_files referencing deleted fits_files."""
        session = self.db_manager.get_session()
        
        try:
            deleted = session.query(ProcessingSessionFile).filter(
                ~ProcessingSessionFile.fits_file_id.in_(
                    session.query(FitsFile.id).distinct()
                )
            ).delete(synchronize_session=False)
            
            session.commit()
            return deleted
            
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
    
    def cleanup_all_orphans(self) -> Dict[str, int]:
        """Clean up all orphaned records. Returns counts of deleted records."""
        return {
            'imaging_sessions': self.cleanup_orphaned_imaging_sessions(),
            'processing_sessions': self.cleanup_orphaned_processing_sessions(),
            'processing_session_files': self.cleanup_orphaned_ps_files()
        }