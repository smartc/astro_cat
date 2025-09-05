"""Database models for FITS Cataloger."""

from datetime import datetime
from typing import Optional, List, Dict

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
    obs_date = Column(DateTime)
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
    duplicate = Column(Boolean, default=False)
    instances = Column(Integer, default=1)
    purged = Column(Boolean, default=False)
    bad = Column(Boolean, default=False)
    file_not_found = Column(Boolean, default=False)
    
    # Original location tracking
    orig_file = Column(String(255))
    orig_folder = Column(String(500))
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    session_id = Column(String(50))  # For grouping images from same session

    # Indexes
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
    
    def add_fits_file(self, fits_data: dict) -> Optional[FitsFile]:
        """Add a new FITS file record."""
        session = self.db_manager.get_session()
        try:
            # Check for existing file by MD5
            existing = session.query(FitsFile).filter_by(
                md5sum=fits_data.get('md5sum')
            ).first()
            
            if existing:
                existing.instances += 1
                existing.duplicate = True
                session.commit()
                return existing
            
            # Create new record
            fits_file = FitsFile(**fits_data)
            session.add(fits_file)
            session.commit()
            # Don't refresh - just return the object
            return fits_file
            
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_cameras(self) -> List[Camera]:
        """Get all cameras."""
        with self.db_manager.get_session() as session:
            return session.query(Camera).filter_by(active=True).all()
    
    def get_telescopes(self) -> List[Telescope]:
        """Get all telescopes."""
        with self.db_manager.get_session() as session:
            return session.query(Telescope).filter_by(active=True).all()
    
    def get_filter_mappings(self) -> Dict[str, str]:
        """Get filter name mappings."""
        with self.db_manager.get_session() as session:
            mappings = session.query(FilterMapping).all()
            return {m.raw_name: m.standard_name for m in mappings}
    
    def initialize_equipment(self, cameras: List[dict], telescopes: List[dict], 
                           filter_mappings: Dict[str, str]):
        """Initialize equipment tables from config."""
        with self.db_manager.get_session() as session:
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