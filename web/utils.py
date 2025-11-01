"""
Utility functions for web interface.
"""

from datetime import datetime
from sqlalchemy.orm import Session
from models import ImagingSession as SessionModel, FitsFile


def generate_imaging_session_default_content(session_id: str, session: Session) -> str:
    """Generate default markdown content for an imaging session."""
    
    # Get session info
    imaging_session = session.query(SessionModel).filter(
        SessionModel.id == session_id
    ).first()

    if not imaging_session:
        return "# Session Not Found\n\nThe requested session could not be found in the database."

    # Get files for this session
    files = session.query(FitsFile).filter(
        FitsFile.imaging_session_id == session_id
    ).all()

    # Build markdown content
    content = f"# Imaging Session: {session_id}\n\n"
    content += f"**Date:** {imaging_session.date}\n\n"
    
    if imaging_session.site_name:
        content += f"**Site:** {imaging_session.site_name}\n\n"
    
    if imaging_session.observer:
        content += f"**Observer:** {imaging_session.observer}\n\n"
    
    if imaging_session.telescope:
        content += f"**Telescope:** {imaging_session.telescope}\n\n"
    
    if imaging_session.camera:
        content += f"**Camera:** {imaging_session.camera}\n\n"
    
    # Location info
    if imaging_session.latitude and imaging_session.longitude:
        content += f"**Location:** {imaging_session.latitude:.4f}, {imaging_session.longitude:.4f}"
        if imaging_session.elevation:
            content += f" (elevation: {imaging_session.elevation}m)"
        content += "\n\n"
    
    content += "## Summary\n\n"
    content += f"**Total Files:** {len(files)}\n\n"
    
    # Frame types summary
    frame_types = {}
    for f in files:
        frame_type = f.frame_type or 'UNKNOWN'
        frame_types[frame_type] = frame_types.get(frame_type, 0) + 1
    
    if frame_types:
        content += "**Frame Types:**\n\n"
        for ft, count in sorted(frame_types.items()):
            content += f"- {ft}: {count}\n"
        content += "\n"
    
    # Objects imaged
    objects = set()
    for f in files:
        if f.object and f.object != 'CALIBRATION':
            objects.add(f.object)
    
    if objects:
        content += "**Objects:**\n\n"
        for obj in sorted(objects):
            obj_files = [f for f in files if f.object == obj]
            content += f"- {obj}: {len(obj_files)} frames\n"
        content += "\n"
    
    content += "## Session Notes\n\n"
    content += "_Add your notes about this imaging session here..._\n\n"
    content += "### Weather Conditions\n\n"
    content += "- Temperature: \n"
    content += "- Humidity: \n"
    content += "- Wind: \n"
    content += "- Seeing: \n"
    content += "- Transparency: \n\n"
    
    content += "### Equipment Notes\n\n"
    content += "_Any issues or observations about equipment performance..._\n\n"
    
    content += "### Targets & Observations\n\n"
    content += "_Notes about individual targets, framing, focus, etc..._\n\n"
    
    return content