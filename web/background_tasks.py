"""
Background task management for FITS Cataloger operations.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Global variables for background task tracking
background_tasks_status: Dict[str, Dict] = {}
_processing_tasks = set()

# Operation lock to prevent concurrent operations
operation_lock = asyncio.Lock()
current_operation = None

# Thread pool executor for background tasks
executor = ThreadPoolExecutor(max_workers=2)


def get_task_status(task_id: str) -> Dict:
    """Get the status of a background task."""
    return background_tasks_status.get(task_id, {
        "status": "unknown",
        "message": "Task not found"
    })


def set_task_status(task_id: str, status: str, message: str, progress: int = None, **kwargs):
    """Update the status of a background task."""
    background_tasks_status[task_id] = {
        "status": status,
        "message": message,
        "progress": progress,
        "updated_at": datetime.now(),
        **kwargs
    }
    
    if status == "pending":
        background_tasks_status[task_id]["started_at"] = datetime.now()
    elif status in ["completed", "failed"]:
        background_tasks_status[task_id]["completed_at"] = datetime.now()


async def set_operation(operation_name: str):
    """Set the current operation (with lock)."""
    global current_operation
    async with operation_lock:
        current_operation = operation_name


async def clear_operation():
    """Clear the current operation (with lock)."""
    global current_operation
    async with operation_lock:
        current_operation = None


def get_current_operation() -> str:
    """Get the current operation name."""
    return current_operation


def is_operation_in_progress() -> bool:
    """Check if any operation is currently in progress."""
    return current_operation is not None


def add_processing_task(task_id: str):
    """Add a task to the processing tasks set."""
    _processing_tasks.add(task_id)


def remove_processing_task(task_id: str):
    """Remove a task from the processing tasks set."""
    _processing_tasks.discard(task_id)


def get_processing_tasks():
    """Get the set of currently processing tasks."""
    return list(_processing_tasks)


def get_all_tasks_summary() -> Dict:
    """Get summary of all background tasks."""
    return {
        "current_operation": current_operation,
        "processing_tasks": get_processing_tasks(),
        "total_tracked_tasks": len(background_tasks_status)
    }