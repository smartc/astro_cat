#!/usr/bin/env python3
"""
Helper script to find and select FITS files for processing sessions.
This makes it easier to query the database and get file IDs for processing.
"""

import sys
from pathlib import Path
from typing import List, Optional

import click
from sqlalchemy import func
from tabulate import tabulate

# Add your project path
sys.path.append(str(Path(__file__).parent))

from config import load_config
from models import DatabaseManager, DatabaseService, FitsFile


def format_file_table(files: List[FitsFile], show_ids: bool = True) -> str:
    """Format files as a table for display."""
    headers = []
    rows = []
    
    if show_ids:
        headers.append("ID")
    
    headers.extend(["File", "Object", "Type", "Camera", "Telescope", "Filter", "Exp", "Date"])
    
    for file_obj in files:
        row = []
        
        if show_ids:
            row.append(file_obj.id)
        
        row.extend([
            file_obj.file[:30] + "..." if len(file_obj.file) > 30 else file_obj.file,
            file_obj.object or "N/A",
            file_obj.frame_type or "N/A",
            file_obj.camera or "N/A",
            file_obj.telescope or "N/A",
            file_obj.filter or "N/A",
            f"{file_obj.exposure}s" if file_obj.exposure else "N/A",
            file_obj.obs_date or "N/A"
        ])
        
        rows.append(row)
    
    return tabulate(rows, headers=headers, tablefmt="grid")


@click.group()
@click.option('--config', '-c', default='config.json', help='Configuration file path')
@click.pass_context
def cli(ctx, config):
    """FITS File Selection Helper - Find files for processing sessions."""
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = config


@cli.command()
@click.option('--object', '-o', help='Filter by object name')
@click.option('--session-id', '-s', help='Filter by capture session ID')
@click.option('--camera', '-c', help='Filter by camera')
@click.option('--telescope', '-t', help='Filter by telescope')
@click.option('--filter', '-f', help='Filter by filter name')
@click.option('--frame-type', type=click.Choice(['LIGHT', 'DARK', 'FLAT', 'BIAS']), help='Filter by frame type')
@click.option('--date', '-d', help='Filter by observation date (YYYY-MM-DD)')
@click.option('--limit', '-l', default=50, help='Limit number of results')
@click.option('--ids-only', is_flag=True, help='Show only file IDs (for copying)')
@click.pass_context
def find(ctx, object, session_id, camera, telescope, filter, frame_type, date, limit, ids_only):
    """Find FITS files matching criteria."""
    config_path = ctx.obj['config_path']
    
    try:
        config, cameras, telescopes, filter_mappings = load_config(config_path)
        
        db_manager = DatabaseManager(config.database.connection_string)
        db_service = DatabaseService(db_manager)
        session = db_service.db_manager.get_session()
        
        try:
            query = session.query(FitsFile)
            
            # Apply filters
            if object:
                if '*' in object or '%' in object:
                    # User wants wildcard matching
                    search_pattern = object.replace('*', '%')
                    query = query.filter(FitsFile.object.ilike(search_pattern))
                else:
                    # Exact match
                    query = query.filter(FitsFile.object == object)
            
            if session_id:
                query = query.filter(FitsFile.imaging_session_id.ilike(f"%{session_id}%"))
            
            if camera:
                query = query.filter(FitsFile.camera.ilike(f"%{camera}%"))
            
            if telescope:
                query = query.filter(FitsFile.telescope.ilike(f"%{telescope}%"))
            
            if filter:
                query = query.filter(FitsFile.filter.ilike(f"%{filter}%"))
            
            if frame_type:
                query = query.filter(FitsFile.frame_type == frame_type)
            
            if date:
                query = query.filter(FitsFile.obs_date == date)
            
            # Order by date and limit
            query = query.order_by(FitsFile.obs_date.desc(), FitsFile.obs_timestamp.desc())
            
            if limit:
                query = query.limit(limit)
            
            files = query.all()
            
            if not files:
                click.echo("No files found matching criteria.")
                return
            
            click.echo(f"Found {len(files)} file(s):")
            click.echo()
            
            if ids_only:
                # Just show IDs for easy copying
                ids = [str(f.id) for f in files]
                click.echo(" ".join(ids))
            else:
                # Show detailed table
                table = format_file_table(files)
                click.echo(table)
                
                # Show summary for easy copy-paste
                click.echo()
                ids = [str(f.id) for f in files]
                click.echo(f"File IDs: {' '.join(ids)}")
        
        finally:
            session.close()
            db_manager.close()
        
    except Exception as e:
        click.echo(f"Error finding files: {e}")
        sys.exit(1)


@cli.command()
@click.argument('object_name')
@click.option('--date', '-d', help='Filter by specific date (YYYY-MM-DD)')
@click.option('--session-id', '-s', help='Filter by specific session ID')
@click.option('--include-calibration', is_flag=True, help='Include calibration frames')
@click.pass_context
def by_object(ctx, object_name, date, session_id, include_calibration):
    """Find all files for a specific object (target)."""
    config_path = ctx.obj['config_path']
    
    try:
        config, cameras, telescopes, filter_mappings = load_config(config_path)
        
        db_manager = DatabaseManager(config.database.connection_string)
        db_service = DatabaseService(db_manager)
        session = db_service.db_manager.get_session()
        
        try:
            if '*' in object_name or '%' in object_name:
                search_pattern = object_name.replace('*', '%')
                query = session.query(FitsFile).filter(FitsFile.object.ilike(search_pattern))
            else:
                query = session.query(FitsFile).filter(FitsFile.object == object_name)

            
            
            if not include_calibration:
                query = query.filter(FitsFile.frame_type == 'LIGHT')
            
            if date:
                query = query.filter(FitsFile.obs_date == date)
            
            if session_id:
                query = query.filter(FitsFile.imaging_session_id.ilike(f"%{session_id}%"))
            
            query = query.order_by(FitsFile.obs_date.desc(), FitsFile.frame_type, FitsFile.filter)
            files = query.all()
            
            if not files:
                click.echo(f"No files found for object '{object_name}'.")
                return
            
            # Group by session and frame type
            sessions = {}
            for file_obj in files:
                session_key = file_obj.imaging_session_id or "Unknown"
                if session_key not in sessions:
                    sessions[session_key] = {'LIGHT': [], 'DARK': [], 'FLAT': [], 'BIAS': []}
                
                frame_type = file_obj.frame_type or 'UNKNOWN'
                if frame_type in sessions[session_key]:
                    sessions[session_key][frame_type].append(file_obj)
            
            click.echo(f"Files for object '{object_name}':")
            click.echo()
            
            total_ids = []
            
            for session_id, frame_types in sessions.items():
                click.echo(f"Session: {session_id}")
                
                for frame_type, files_list in frame_types.items():
                    if files_list:
                        click.echo(f"  {frame_type}: {len(files_list)} files")
                        
                        # Group by filter for lights
                        if frame_type == 'LIGHT':
                            filters = {}
                            for f in files_list:
                                filter_name = f.filter or 'None'
                                if filter_name not in filters:
                                    filters[filter_name] = []
                                filters[filter_name].append(f)
                            
                            for filter_name, filter_files in filters.items():
                                exposures = [f.exposure for f in filter_files if f.exposure]
                                exp_summary = f"{min(exposures)}-{max(exposures)}s" if exposures and min(exposures) != max(exposures) else f"{exposures[0]}s" if exposures else "Unknown"
                                
                                click.echo(f"    {filter_name}: {len(filter_files)} ({exp_summary})")
                                filter_ids = [str(f.id) for f in filter_files]
                                click.echo(f"      IDs: {' '.join(filter_ids)}")
                        
                        total_ids.extend([str(f.id) for f in files_list])
                
                click.echo()
            
            click.echo(f"All file IDs ({len(total_ids)} total):")
            click.echo(" ".join(total_ids))
        
        finally:
            session.close()
            db_manager.close()
        
    except Exception as e:
        click.echo(f"Error finding files by object: {e}")
        sys.exit(1)


@cli.command()
@click.option('--limit', '-l', default=20, help='Number of recent sessions to show')
@click.pass_context
def recent_sessions(ctx, limit):
    """Show recent capture sessions with file counts."""
    config_path = ctx.obj['config_path']
    
    try:
        config, cameras, telescopes, filter_mappings = load_config(config_path)
        
        db_manager = DatabaseManager(config.database.connection_string)
        db_service = DatabaseService(db_manager)
        session = db_service.db_manager.get_session()
        
        try:
            # Get session summaries
            sessions = session.query(
                FitsFile.imaging_session_id,
                FitsFile.obs_date,
                FitsFile.camera,
                FitsFile.telescope,
                func.count(FitsFile.id).label('file_count'),
                func.group_concat(func.distinct(FitsFile.object)).label('objects')
            ).filter(
                FitsFile.imaging_session_id.isnot(None)
            ).group_by(
                FitsFile.imaging_session_id
            ).order_by(
                FitsFile.obs_date.desc()
            ).limit(limit).all()
            
            if not sessions:
                click.echo("No sessions found.")
                return
            
            click.echo(f"Recent capture sessions (last {len(sessions)}):")
            click.echo()
            
            headers = ["Session ID", "Date", "Camera", "Telescope", "Files", "Objects"]
            rows = []
            
            for sess in sessions:
                objects = sess.objects.split(',') if sess.objects else []
                # Remove 'CALIBRATION' and clean up object list
                objects = [obj.strip() for obj in objects if obj.strip() and obj.strip() != 'CALIBRATION']
                objects_str = ', '.join(objects[:2])  # Show first 2 objects
                if len(objects) > 2:
                    objects_str += f" (+{len(objects)-2} more)"
                
                rows.append([
                    sess.imaging_session_id[:20] + "..." if len(sess.imaging_session_id) > 20 else sess.imaging_session_id,
                    sess.obs_date or "N/A",
                    sess.camera or "N/A",
                    sess.telescope or "N/A",
                    str(sess.file_count),
                    objects_str or "Calibration only"
                ])
            
            table = tabulate(rows, headers=headers, tablefmt="grid")
            click.echo(table)
        
        finally:
            session.close()
            db_manager.close()
        
    except Exception as e:
        click.echo(f"Error getting recent sessions: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli()