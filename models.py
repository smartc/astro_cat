"""Database models for FITS Cataloger."""

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
    """Main table for FITS file metadata."""
    __tablename__ = 'fits_files'

    id = Column(Integer, primary_key=True, autoincrement=True)
    file = Column(String(255), nullable=False)
    folder = Column(String(500), nullable=False)
    object = Column(String(100))
    obs_date = Column(String(10))
    obs_timestamp = Column(DateTime)
    ra = Column(String(20))
    dec = Column(String(20))
    x = Column(Integer)
    y = Column(Integer)
    frame_type = Column(String(20))
    filter = Column(String(20))
    focal_length = Column(Float)
    exposure = Column(Float)
    camera = Column(String(50))
    telescope = Column(String(50))
    md5sum = Column(String(32), unique=True, index=True)
    
    # Location data
    latitude = Column(Float)  # Site latitude in degrees
    longitude = Column(Float)  # Site longitude in degrees
    elevation = Column(Float)  # Site elevation in meters
    
    # Field of view data
    fov_x = Column(Float)  # Field of view in arcminutes (X axis)
    fov_y = Column(Float)  # Field of view in arcminutes (Y axis)
    pixel_scale = Column(Float)  # Pixel scale in arcseconds per pixel
    
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
    )


class ProcessLog(Base):
    """Log of processing sessions."""
    __tablename__ = 'process_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_name = Column(String(100), nullable=False)
    object = Column(String(100))
    image_type = Column(String(20))
    create_date = Column(DateTime, default=datetime.utcnow)
    status = Column(Integer, default=0)  # 0=pending, 1=completed, -1=error
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
    pixel_size = Column(Float)  # in microns
    binning_support = Column(String(20), default="1,2,3,4")
    notes = Column(Text)
    active = Column(Boolean, default=True)


class Telescope(Base):
    """Telescope/lens specifications."""
    __tablename__ = 'telescopes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    focal_length = Column(Float, nullable=False)  # in mm
    aperture = Column(Float)  # in mm
    telescope_type = Column(String(20))  # refractor, reflector, lens, etc.
    notes = Column(Text)
    active = Column(Boolean, default=True)


class FilterMapping(Base):
    """Mapping table for filter name normalization."""
    __tablename__ = 'filter_mappings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_name = Column(String(50), unique=True, nullable=False)
    standard_name = Column(String(20), nullable=False)
    filter_type = Column(String(20))  # broadband, narrowband, etc.
    bandpass = Column(String(20))  # wavelength info
    notes = Column(Text)


class Session(Base):
    """Imaging sessions table."""
    __tablename__ = 'sessions'

    session_id = Column(String(50), primary_key=True)  # Hash-based ID from fits_processor
    session_date = Column(String(10), nullable=False)  # YYYY-MM-DD (observation night)
    telescope = Column(String(50))
    camera = Column(String(50))
    site_name = Column(String(100))
    latitude = Column(Float)
    longitude = Column(Float)
    elevation = Column(Float)  # in meters
    observer = Column(String(100))
    notes = Column(Text)  # Markdown-formatted notes
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('idx_session_date', 'session_date'),
        Index('idx_session_telescope_camera', 'telescope', 'camera'),
    )


class ProcessingSession(Base):
    """Processing session for selected FITS files."""
    __tablename__ = 'processing_sessions'

    id = Column(String(50), primary_key=True)  # Unique processing session ID
    name = Column(String(255), nullable=False)  # User-friendly name
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Metadata
    objects = Column(Text)  # JSON array of object names in the session
    notes = Column(Text)    # Markdown-formatted processing notes
    status = Column(String(20), default='not_started')  # not_started, in_progress, complete
    version = Column(Integer, default=1)  # Processing version (for reprocessing)
    
    # External references
    astrobin_url = Column(String(500))  # AstroBin posting URL
    social_urls = Column(Text)  # JSON array of social media URLs
    
    # Processing timeline
    processing_started = Column(DateTime)
    processing_completed = Column(DateTime)
    
    # File system
    folder_path = Column(String(500))  # Path to processing folder
    
    # Indexes
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
    original_path = Column(String(500), nullable=False)  # Full path to original file
    original_filename = Column(String(255), nullable=False)  # Original filename
    
    # Staged file information
    staged_path = Column(String(500), nullable=False)  # Full path to symbolic link
    staged_filename = Column(String(255), nullable=False)  # Filename in processing folder (with prefix)
    subfolder = Column(String(50), nullable=False)  # lights, darks, flats, bias
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    file_size = Column(Integer)  # Size of original file in bytes
    frame_type = Column(String(20))  # Cached frame type for easy querying
    
    # Indexes
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

        # Enable foreign keys for SQLite
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
        """
        Add a new FITS file record.
        
        Returns:
            Tuple[bool, bool]: (success, is_duplicate)
        """
        session = self.db_manager.get_session()
        try:
            # Check for existing file by MD5
            existing = session.query(FitsFile).filter_by(
                md5sum=fits_data.get('md5sum')
            ).first()
            
            if existing:
                # Skip duplicate - don't update database
                return True, True  # success=True, is_duplicate=True
            
            # Create new record
            fits_file = FitsFile(**fits_data)
            session.add(fits_file)
            session.commit()
            return True, False  # success=True, is_duplicate=False
            
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
            # Add cameras
            for cam_data in cameras:
                existing = session.query(Camera).filter_by(name=cam_data['name']).first()
                if not existing:
                    camera = Camera(**cam_data)
                    session.add(camera)
            
            # Add telescopes
            for tel_data in telescopes:
                existing = session.query(Telescope).filter_by(name=tel_data['name']).first()
                if not existing:
                    telescope = Telescope(**tel_data)
                    session.add(telescope)
            
            # Add filter mappings
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
            stats = {}
            
            # Total files
            total_files = session.query(FitsFile).count()
            stats['total_files'] = total_files
            
            # Files by frame type
            frame_type_counts = session.query(
                FitsFile.frame_type, 
                func.count(FitsFile.id)
            ).group_by(FitsFile.frame_type).all()
            stats['by_frame_type'] = {ft: count for ft, count in frame_type_counts}
            
            # Files by camera
            camera_counts = session.query(
                FitsFile.camera, 
                func.count(FitsFile.id)
            ).group_by(FitsFile.camera).all()
            stats['by_camera'] = {cam: count for cam, count in camera_counts}
            
            # Files by telescope
            telescope_counts = session.query(
                FitsFile.telescope, 
                func.count(FitsFile.id)
            ).group_by(FitsFile.telescope).all()
            stats['by_telescope'] = {tel: count for tel, count in telescope_counts}
            
            return stats
            
        finally:
            session.close()

    def add_session(self, session_data: dict) -> bool:
        """Add a new session record."""
        session = self.db_manager.get_session()
        try:
            # Check if session already exists
            existing = session.query(Session).filter_by(
                session_id=session_data['session_id']
            ).first()
            
            if existing:
                # Update existing session with any new data
                for key, value in session_data.items():
                    if hasattr(existing, key) and value is not None:
                        setattr(existing, key, value)
                existing.updated_at = datetime.utcnow()
            else:
                # Create new session
                new_session = Session(**session_data)
                session.add(new_session)
            
            session.commit()
            return True
            
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def log_object_processing_failure(self, filename: str, raw_name: str, 
                                     proposed_name: str = None, error: str = None):
        """Log object name processing failure."""
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
                # Try to convert to appropriate type
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