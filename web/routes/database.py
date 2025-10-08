"""
Database query API routes.
"""

import logging
import re
import time
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import text

from web.dependencies import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/database")


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    execution_time: float


def is_safe_query(query: str) -> bool:
    """
    Check if query is safe (read-only SELECT statement).
    Only allows SELECT queries to prevent accidental data modification.
    """
    # Remove comments
    query_clean = re.sub(r'--.*$', '', query, flags=re.MULTILINE)
    query_clean = re.sub(r'/\*.*?\*/', '', query_clean, flags=re.DOTALL)
    
    # Remove extra whitespace
    query_clean = ' '.join(query_clean.split()).strip().upper()
    
    # Check if it's a SELECT query
    if not query_clean.startswith('SELECT'):
        return False
    
    # Disallowed keywords that could modify data
    dangerous_keywords = [
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER',
        'TRUNCATE', 'REPLACE', 'MERGE', 'EXEC', 'EXECUTE'
    ]
    
    for keyword in dangerous_keywords:
        if keyword in query_clean:
            return False
    
    return True


@router.post("/query", response_model=QueryResponse)
async def execute_query(
    request: QueryRequest,
    session=Depends(get_db_session)
):
    """
    Execute a read-only SQL query.
    Only SELECT statements are allowed for safety.
    """
    query = request.query.strip()
    
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    # Safety check
    if not is_safe_query(query):
        raise HTTPException(
            status_code=400,
            detail="Only SELECT queries are allowed. INSERT, UPDATE, DELETE, and DDL statements are not permitted."
        )
    
    try:
        start_time = time.time()
        
        # Execute query
        result = session.execute(text(query))
        
        # Fetch results
        columns = list(result.keys()) if result.returns_rows else []
        rows = []
        
        if result.returns_rows:
            for row in result:
                # Convert row to dict
                row_dict = {}
                for i, column in enumerate(columns):
                    value = row[i]
                    # Convert datetime and other non-JSON-serializable types to strings
                    if value is not None and not isinstance(value, (int, float, str, bool)):
                        value = str(value)
                    row_dict[column] = value
                rows.append(row_dict)
        
        execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        logger.info(f"Query executed successfully: {len(rows)} rows, {execution_time:.2f}ms")
        
        return QueryResponse(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time=round(execution_time, 2)
        )
        
    except Exception as e:
        logger.error(f"Query execution error: {e}")
        error_message = str(e)
        
        # Make error message more user-friendly
        if "no such table" in error_message.lower():
            error_message = f"Table not found. {error_message}"
        elif "no such column" in error_message.lower():
            error_message = f"Column not found. {error_message}"
        elif "syntax error" in error_message.lower():
            error_message = f"SQL syntax error. {error_message}"
        
        raise HTTPException(status_code=400, detail=error_message)


@router.get("/schema")
async def get_schema(session=Depends(get_db_session)):
    """Get database schema information."""
    try:
        # Get all tables
        result = session.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
        """))
        
        tables = [row[0] for row in result]
        
        # Get columns for each table
        schema = {}
        for table in tables:
            result = session.execute(text(f"PRAGMA table_info({table})"))
            columns = []
            for row in result:
                columns.append({
                    "name": row[1],
                    "type": row[2],
                    "not_null": bool(row[3]),
                    "default": row[4],
                    "pk": bool(row[5])
                })
            schema[table] = columns
        
        return {"tables": schema}
        
    except Exception as e:
        logger.error(f"Error getting schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables")
async def get_tables(session=Depends(get_db_session)):
    """Get list of all tables in the database."""
    try:
        result = session.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
        """))
        
        tables = [row[0] for row in result]
        return {"tables": tables}
        
    except Exception as e:
        logger.error(f"Error getting tables: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/table/{table_name}/info")
async def get_table_info(table_name: str, session=Depends(get_db_session)):
    """Get information about a specific table."""
    try:
        # Validate table name (prevent SQL injection)
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table_name):
            raise HTTPException(status_code=400, detail="Invalid table name")
        
        # Get column info
        result = session.execute(text(f"PRAGMA table_info({table_name})"))
        columns = []
        for row in result:
            columns.append({
                "cid": row[0],
                "name": row[1],
                "type": row[2],
                "not_null": bool(row[3]),
                "default": row[4],
                "pk": bool(row[5])
            })
        
        if not columns:
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
        
        # Get row count
        result = session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        row_count = result.scalar()
        
        return {
            "table": table_name,
            "columns": columns,
            "row_count": row_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting table info: {e}")
        raise HTTPException(status_code=500, detail=str(e))