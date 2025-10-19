"""
Database models for processed file cataloging.

These models extend the existing FITS cataloger database to track
processed output files from astrophotography sessions.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, Text, ForeignKey, Index, Boolean
from sqlalchemy.ext.declarative import declarative_base

# Import Base from existing models when integrating
# For POC, using separate base
Base = declarative_base()


class ProcessingSession(Base):
    """
    UPDATED ProcessingSession model with target metadata.
    
    This extends the existing ProcessingSession with additional fields
    for target information and integration time tracking.
    """
    __tablename__ = 'processing_sessions'
    
    id = Column(String(50), primary_key=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Metadata
    objects = Column(Text)  # JSON array of object names
    notes = Column(Text)
    status = Column(String(20), default='not_started')
    version = Column(Integer, default=1)
    
    # External references
    astrobin_url = Column(String(500))
    social_urls = Column(Text)  # JSON array
    
    # Processing timeline
    processing_started = Column(DateTime)
    processing_completed = Column(DateTime)
    
    # File system
    folder_path = Column(String(500))
    
    # ===== NEW FIELDS FOR TARGET METADATA =====
    # Primary target information
    primary_target = Column(String(255))
    target_type = Column(String(50))  # Galaxy, Nebula, Star Cluster, Planetary, etc.
    image_type = Column(String(50))   # RGB, SHO, HOO, LRGB, Ha, OIII, etc.
    
    # Coordinates (from light frames)
    ra = Column(String(50))   # RA in HMS format or decimal degrees
    dec = Column(String(50))  # Dec in DMS format or decimal degrees
    
    # Integration metadata
    total_integration_seconds = Column(Integer)  # Total exposure time of light frames
    date_range_start = Column(DateTime)  # First capture date
    date_range_end = Column(DateTime)    # Last capture date
    
    __table_args__ = (
        Index('idx_processing_status', 'status'),
        Index('idx_processing_created', 'created_at'),
        Index('idx_processing_objects', 'objects'),
        Index('idx_processing_target', 'primary_target'),
        Index('idx_processing_target_type', 'target_type'),
    )


class ProcessedFile(Base):
    """
    Catalog of processed/output files from processing sessions.
    
    Tracks JPG, XISF, XOSM (with .data), and PXIPROJECT files
    that are outputs of astrophotography processing.
    """
    __tablename__ = 'processed_files'
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Link to processing session
    processing_session_id = Column(String(50), ForeignKey('processing_sessions.id', ondelete='CASCADE'))
    
    # File identification
    file_path = Column(String(500), nullable=False, unique=True)  # Full path - enforces no duplicates
    filename = Column(String(255), nullable=False)
    file_type = Column(String(20), nullable=False)  # jpg, jpeg, xisf, xosm, pxiproject
    subfolder = Column(String(50))  # final, intermediate, etc.
    
    # File metrics
    file_size = Column(Integer)  # bytes (aggregate for folders/paired files)
    created_date = Column(DateTime)
    modified_date = Column(DateTime)
    md5sum = Column(String(32))  # For integrity checking
    
    # Companion handling (for .xosm + .data)
    has_companion = Column(Boolean, default=False)
    companion_path = Column(String(500))  # Path to .data folder
    companion_size = Column(Integer)  # Size of companion in bytes
    
    # Image-specific metadata (null for project files)
    image_width = Column(Integer)
    image_height = Column(Integer)
    bit_depth = Column(Integer)
    color_space = Column(String(50))  # RGB, Grayscale, etc.
    
    # Processing context
    associated_object = Column(String(255))  # Auto-detected from session objects
    processing_stage = Column(String(50))  # final, intermediate, test
    
    # Flexible metadata storage
    metadata_json = Column(Text)  # Store format-specific metadata as JSON
    
    # User annotations
    notes = Column(Text)
    
    # Timestamps
    cataloged_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_processed_session', 'processing_session_id'),
        Index('idx_processed_type', 'file_type'),
        Index('idx_processed_subfolder', 'subfolder'),
        Index('idx_processed_object', 'associated_object'),
        Index('idx_processed_stage', 'processing_stage'),
    )

    def __repr__(self):
        return f"<ProcessedFile(id={self.id}, filename='{self.filename}', type='{self.file_type}')>"