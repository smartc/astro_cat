"""
API routes for processed files.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from models import ProcessingSession
from processed_catalog.models import ProcessedFile
from web.dependencies import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/processed-files")


@router.get("/session/{session_id}/stats")
async def get_session_processed_stats(
    session_id: str,
    session: Session = Depends(get_db_session)
):
    """Get processed file statistics for a processing session."""
    try:
        # Verify session exists
        ps = session.query(ProcessingSession).filter(
            ProcessingSession.id == session_id
        ).first()
        
        if not ps:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get stats by subfolder and file type
        stats = session.query(
            ProcessedFile.subfolder,
            ProcessedFile.file_type,
            func.count(ProcessedFile.id).label('count'),
            func.sum(ProcessedFile.file_size).label('total_size')
        ).filter(
            ProcessedFile.processing_session_id == session_id
        ).group_by(
            ProcessedFile.subfolder,
            ProcessedFile.file_type
        ).all()
        
        # Organize by subfolder
        final_files = []
        intermediate_files = []
        
        for subfolder, file_type, count, total_size in stats:
            file_stat = {
                'file_type': file_type.upper(),
                'count': count,
                'total_size': total_size or 0,
                'total_size_mb': round((total_size or 0) / 1024 / 1024, 2)
            }
            
            if subfolder == 'final':
                final_files.append(file_stat)
            elif subfolder == 'intermediate':
                intermediate_files.append(file_stat)
        
        # Calculate totals
        total_final = sum(f['count'] for f in final_files)
        total_final_size = sum(f['total_size'] for f in final_files)
        total_intermediate = sum(f['count'] for f in intermediate_files)
        total_intermediate_size = sum(f['total_size'] for f in intermediate_files)
        
        return {
            'session_id': session_id,
            'final': {
                'files': final_files,
                'total_count': total_final,
                'total_size': total_final_size,
                'total_size_mb': round(total_final_size / 1024 / 1024, 2)
            },
            'intermediate': {
                'files': intermediate_files,
                'total_count': total_intermediate,
                'total_size': total_intermediate_size,
                'total_size_mb': round(total_intermediate_size / 1024 / 1024, 2)
            },
            'has_files': len(final_files) > 0 or len(intermediate_files) > 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting processed file stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))