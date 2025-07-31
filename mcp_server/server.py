import urllib.parse
from sqlalchemy import create_engine, text
from azure.identity import DefaultAzureCredential
import struct
import json
from mcp.server.fastmcp import FastMCP
import os
from dotenv import load_dotenv
from typing import Optional, List, Dict

load_dotenv("../.env")

mcp = FastMCP("azure-sql-server")

server_name = os.getenv("SERVER_NAME")
database = os.getenv("DATABASE")

engine = None

async def get_azure_engine():
    """Create or return existing Azure SQL engine"""
    global engine
    
    if engine is not None:
        return engine
        
    try:
        credential = DefaultAzureCredential()
        token = credential.get_token("https://database.windows.net/")
        access_token = token.token
        
        token_bytes = access_token.encode("utf-16-le")
        token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
        
        conn_params = {
            "DRIVER": "{ODBC Driver 17 for SQL Server}",
            "SERVER": server_name,
            "DATABASE": database,
            "Encrypt": "yes",
            "TrustServerCertificate": "no",
            "Connection Timeout": "100"
        }
        
        conn_str = urllib.parse.quote_plus(';'.join([f"{key}={value}" for key, value in conn_params.items()]))
        
        engine = create_engine(
            f"mssql+pyodbc:///?odbc_connect={conn_str}",
            connect_args={"attrs_before": {1256: token_struct}}
        )
        
        return engine
        
    except Exception as e:
        raise Exception(f"Failed to create Azure SQL engine: {e}")


@mcp.tool()
async def execute_query(query: str) -> str:
    """Execute a SQL query against the Azure SQL database.

    Args:
        query: SQL query to execute (e.g., "SELECT * FROM users LIMIT 10")
    """
    try:
        engine = await get_azure_engine()
        
        with engine.connect() as connection:
            result = connection.execute(text(query))
            columns = list(result.keys())
            rows = result.fetchall()
            
            data = [dict(zip(columns, row)) for row in rows]
            
            result_dict = {
                "rows": len(data),
                "columns": columns,
                "data": data
            }
        
        return json.dumps(result_dict, indent=2, default=str)
        
    except Exception as e:
        return f"Query failed: {str(e)}"

@mcp.tool()
async def get_tables() -> str:
    """Get list of all tables in the Azure SQL database."""
    try:
        engine = await get_azure_engine()
        
        query = text("""
            SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_SCHEMA, TABLE_NAME
        """)
        
        with engine.connect() as connection:
            result = connection.execute(query)
            rows = result.fetchall()
            
            tables = []
            for row in rows:
                tables.append({
                    "schema": row.TABLE_SCHEMA,
                    "name": row.TABLE_NAME,
                    "full_name": f"{row.TABLE_SCHEMA}.{row.TABLE_NAME}"
                })
        
        return json.dumps({"tables": tables}, indent=2)
        
    except Exception as e:
        return f"Failed to get tables: {str(e)}"

@mcp.tool()
async def get_table_schema(table_name: str) -> str:
    """Get schema information for a specific table.

    Args:
        table_name: Name of the table (e.g., "users" or "schema.table_name")
    """
    try:
        engine = await get_azure_engine()
        
        # Handle schema.table format
        if '.' in table_name:
            schema, table = table_name.split('.', 1)
            where_clause = f"TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{table}'"
        else:
            where_clause = f"TABLE_NAME = '{table_name}'"
        
        query = text(f"""
            SELECT 
                COLUMN_NAME,
                DATA_TYPE,
                IS_NULLABLE,
                COLUMN_DEFAULT,
                CHARACTER_MAXIMUM_LENGTH
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE {where_clause}
            ORDER BY ORDINAL_POSITION
        """)
        
        with engine.connect() as connection:
            result = connection.execute(query)
            columns = list(result.keys())
            rows = result.fetchall()
            
            if len(rows) == 0:
                return f"Table '{table_name}' not found"
            
            schema_info = [dict(zip(columns, row)) for row in rows]
        
        return json.dumps({
            "table": table_name,
            "columns": schema_info
        }, indent=2)
        
    except Exception as e:
        return f"Failed to get schema for '{table_name}': {str(e)}"

@mcp.tool()
async def get_sample_data(table_name: str, limit: int = 5) -> str:
    """Get sample data from a table.

    Args:
        table_name: Name of the table (e.g., "users" or "schema.table_name")
        limit: Number of rows to return (default: 5, max: 100)
    """
    try:
        engine = await get_azure_engine()
        
        # Limit safety check
        limit = min(max(1, limit), 100)
        
        query = text(f"SELECT TOP {limit} * FROM {table_name}")
        
        with engine.connect() as connection:
            result = connection.execute(query)
            columns = list(result.keys())
            rows = result.fetchall()
            
            data = [dict(zip(columns, row)) for row in rows]
            
            result_dict = {
                "table": table_name,
                "sample_rows": limit,
                "total_columns": len(columns),
                "columns": columns,
                "data": data
            }
        
        return json.dumps(result_dict, indent=2, default=str)
        
    except Exception as e:
        return f"Failed to get sample data from '{table_name}': {str(e)}"


# ==================================== tools based on expedientes

@mcp.tool()
async def search_expedients(search_criteria: str, limit: int = 10) -> str:
    """Search for expedients based on various criteria.
    
    Args:
        search_criteria: Search term (can be expedient ID, client name, description, etc.)
        limit: Maximum number of results to return (default: 10, max: 100)
    """
    try:
        engine = await get_azure_engine()
        limit = min(max(1, limit), 100)
        
        # Adjust this query based on your actual expedient table structure
        query = text("""
            SELECT TOP :limit
                expedient_id,
                client_name,
                description,
                status,
                created_date,
                last_updated
            FROM expedients 
            WHERE 
                expedient_id LIKE :search_term
                OR client_name LIKE :search_term
                OR description LIKE :search_term
                OR status LIKE :search_term
            ORDER BY last_updated DESC
        """)
        
        search_term = f"%{search_criteria}%"
        
        with engine.connect() as connection:
            result = connection.execute(query, {"limit": limit, "search_term": search_term})
            columns = list(result.keys())
            rows = result.fetchall()
            
            expedients = [dict(zip(columns, row)) for row in rows]
            
            result_dict = {
                "search_criteria": search_criteria,
                "found": len(expedients),
                "expedients": expedients
            }
        
        return json.dumps(result_dict, indent=2, default=str)
        
    except Exception as e:
        return f"Expedient search failed: {str(e)}"

@mcp.tool()
async def get_expedient_details(expedient_id: str) -> str:
    """Get detailed information about a specific expedient.
    
    Args:
        expedient_id: The unique identifier of the expedient
    """
    try:
        engine = await get_azure_engine()
        
        query = text("""
            SELECT *
            FROM expedients 
            WHERE expedient_id = :expedient_id
        """)
        
        with engine.connect() as connection:
            result = connection.execute(query, {"expedient_id": expedient_id})
            columns = list(result.keys())
            rows = result.fetchall()
            
            if not rows:
                return f"Expedient '{expedient_id}' not found"
            
            expedient_data = dict(zip(columns, rows[0]))
            
            result_dict = {
                "expedient_id": expedient_id,
                "details": expedient_data
            }
        
        return json.dumps(result_dict, indent=2, default=str)
        
    except Exception as e:
        return f"Failed to get expedient details for '{expedient_id}': {str(e)}"

@mcp.tool()
async def get_expedient_tasks(expedient_id: str) -> str:
    """Get all tasks associated with an expedient.
    
    Args:
        expedient_id: The unique identifier of the expedient
    """
    try:
        engine = await get_azure_engine()
        
        query = text("""
            SELECT 
                task_id,
                task_name,
                task_description,
                status,
                assigned_to,
                due_date,
                created_date,
                completed_date
            FROM expedient_tasks 
            WHERE expedient_id = :expedient_id
            ORDER BY created_date DESC
        """)
        
        with engine.connect() as connection:
            result = connection.execute(query, {"expedient_id": expedient_id})
            columns = list(result.keys())
            rows = result.fetchall()
            
            tasks = [dict(zip(columns, row)) for row in rows]
            
            result_dict = {
                "expedient_id": expedient_id,
                "task_count": len(tasks),
                "tasks": tasks
            }
        
        return json.dumps(result_dict, indent=2, default=str)
        
    except Exception as e:
        return f"Failed to get tasks for expedient '{expedient_id}': {str(e)}"

@mcp.tool()
async def run_expedient_task(expedient_id: str, task_name: str) -> str:
    """Execute or mark a task as started for an expedient.
    
    Args:
        expedient_id: The unique identifier of the expedient
        task_name: The name of the task to run
    """
    try:
        engine = await get_azure_engine()
        
        # First, check if the task exists
        check_query = text("""
            SELECT task_id, status 
            FROM expedient_tasks 
            WHERE expedient_id = :expedient_id AND task_name = :task_name
        """)
        
        with engine.connect() as connection:
            result = connection.execute(check_query, {
                "expedient_id": expedient_id, 
                "task_name": task_name
            })
            task_row = result.fetchone()
            
            if not task_row:
                return f"Task '{task_name}' not found for expedient '{expedient_id}'"
            
            # Update task status to 'running' or 'in_progress'
            update_query = text("""
                UPDATE expedient_tasks 
                SET status = 'running', 
                    started_date = GETDATE()
                WHERE expedient_id = :expedient_id AND task_name = :task_name
            """)
            
            connection.execute(update_query, {
                "expedient_id": expedient_id,
                "task_name": task_name
            })
            connection.commit()
            
            return f"Task '{task_name}' has been started for expedient '{expedient_id}'"
        
    except Exception as e:
        return f"Failed to run task '{task_name}' for expedient '{expedient_id}': {str(e)}"

@mcp.tool()
async def query_expedient_task_status(expedient_id: str, task_name: str) -> str:
    """Check the status of a specific task for an expedient.
    
    Args:
        expedient_id: The unique identifier of the expedient
        task_name: The name of the task to check
    """
    try:
        engine = await get_azure_engine()
        
        query = text("""
            SELECT 
                task_id,
                task_name,
                status,
                assigned_to,
                created_date,
                started_date,
                due_date,
                completed_date,
                task_description
            FROM expedient_tasks 
            WHERE expedient_id = :expedient_id AND task_name = :task_name
        """)
        
        with engine.connect() as connection:
            result = connection.execute(query, {
                "expedient_id": expedient_id,
                "task_name": task_name
            })
            columns = list(result.keys())
            rows = result.fetchall()
            
            if not rows:
                return f"Task '{task_name}' not found for expedient '{expedient_id}'"
            
            task_data = dict(zip(columns, rows[0]))
            
            result_dict = {
                "expedient_id": expedient_id,
                "task_name": task_name,
                "status": task_data
            }
        
        return json.dumps(result_dict, indent=2, default=str)
        
    except Exception as e:
        return f"Failed to check status for task '{task_name}' in expedient '{expedient_id}': {str(e)}"

@mcp.tool()
async def update_expedient_status(expedient_id: str, new_status: str, notes: str = "") -> str:
    """Update the status of an expedient.
    
    Args:
        expedient_id: The unique identifier of the expedient
        new_status: The new status to set
        notes: Optional notes about the status change
    """
    try:
        engine = await get_azure_engine()
        
        query = text("""
            UPDATE expedients 
            SET status = :new_status,
                last_updated = GETDATE(),
                notes = CASE 
                    WHEN :notes = '' THEN notes 
                    ELSE :notes 
                END
            WHERE expedient_id = :expedient_id
        """)
        
        with engine.connect() as connection:
            result = connection.execute(query, {
                "expedient_id": expedient_id,
                "new_status": new_status,
                "notes": notes
            })
            
            if result.rowcount == 0:
                return f"Expedient '{expedient_id}' not found"
            
            connection.commit()
            
            return f"Expedient '{expedient_id}' status updated to '{new_status}'"
        
    except Exception as e:
        return f"Failed to update status for expedient '{expedient_id}': {str(e)}"

if __name__ == "__main__":
    mcp.run(transport='stdio')