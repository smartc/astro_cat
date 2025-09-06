"""Database models for FITS Cataloger."""

from datetime import datetime
from typing import Optional, List, Dict, Tuple

from sqlalchemy import (
    Boolean, DateTime, Float, Integer, String, Text, 
    create_engine, Column, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func

Base = declarative_base()


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
    
    # File management fields
    purged = Column(Boolean, default=False)
    bad = Column(Boolean, default=False)
    file_not_found = Column(Boolean, default=False)
    
    # Original location tracking
    orig_file = Column(String(255))
    orig_folder = Column(String(500))
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    session_id = Column(String(50))

    __table_args__ = (
        Index('idx_object_date', 'object', 'obs_date'),
        Index('idx_camera_telescope', 'camera', 'telescope'),
        Index('idx_frame_type_filter', 'frame_type', 'filter'),
        Index('idx_session', 'session_id'),
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


class DatabaseManager:
    """Database connection and session management."""
    
    def __init__(self, connection_string: str):
        self.engine = create_engine(connection_string, echo=False)
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

    def get_sessions(self) -> List[Session]:
        """Get all sessions."""
        session = self.db_manager.get_session()
        try:
            return session.query(Session).order_by(Session.session_date.desc()).all()
        finally:
            session.close()

    def extract_session_data(self, fits_files_df) -> List[dict]:
        """Extract unique sessions from processed FITS files."""
        sessions = {}
        
        for row in fits_files_df.iter_rows(named=True):
            session_id = row.get('session_id')
            if not session_id or session_id == 'UNKNOWN':
                continue
                
            if session_id not in sessions:
                sessions[session_id] = {
                    'session_id': session_id,
                    'session_date': row.get('obs_date'),
                    'telescope': row.get('telescope'),
                    'camera': row.get('camera'),
                    'site_name': None,  # Will be extracted from headers if available
                    'latitude': None,
                    'longitude': None, 
                    'elevation': None,
                    'observer': None,  # Will be extracted from headers if available
                    'notes': None
                }
        
        return list(sessions.values())

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
