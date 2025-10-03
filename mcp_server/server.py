import urllib.parse
from sqlalchemy import create_engine, text
from azure.identity import DefaultAzureCredential
import struct
import json
from mcp.server.fastmcp import FastMCP
import os
from dotenv import load_dotenv

load_dotenv("../.env")

mcp = FastMCP("azure-sql-server")
local_db = os.getenv("LOCAL_DB", "true").lower() == "true"
server_name = os.getenv("SERVER_NAME")
database = os.getenv("DATABASE")

engine = None

async def get_azure_engine():
    """Create or return existing Azure SQL engine"""
    global engine
    
    if engine is not None:
        return engine
        
    try:
        if local_db:
            # Local SQL Server connection
            conn_params = {
                "DRIVER": "{ODBC Driver 17 for SQL Server}",
                "SERVER": server_name,
                "DATABASE": database,
                "Trusted_Connection": "yes",
                "Encrypt": "no",
                "Connection Timeout": "30"
            }
            
            conn_str = urllib.parse.quote_plus(';'.join([f"{key}={value}" for key, value in conn_params.items()]))
            
            engine = create_engine(
                f"mssql+pyodbc:///?odbc_connect={conn_str}"
            )
            
            print(f"Connected to local SQL Server: {server_name}")
            
        else:
            # Azure SQL Database connection
            from azure.identity import DefaultAzureCredential
            
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
                "TrustServerCertificate": "yes",
                "Connection Timeout": "100"
            }
            
            conn_str = urllib.parse.quote_plus(';'.join([f"{key}={value}" for key, value in conn_params.items()]))
            
            engine = create_engine(
                f"mssql+pyodbc:///?odbc_connect={conn_str}",
                connect_args={"attrs_before": {1256: token_struct}}
            )
            
            print(f"Connected to Azure SQL Database: {server_name}")
        
        return engine
        
    except Exception as e:
        connection_type = "local SQL Server" if local_db else "Azure SQL Database"
        raise Exception(f"Failed to create {connection_type} engine: {e}")


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

# ==================================== Northwind-specific tools

@mcp.tool()
async def search_customers(search_criteria: str, limit: int = 10) -> str:
    """Search customers by CompanyName, ContactName, City, or Country.

    Args:
        search_criteria: term to search for
        limit: maximum results (default 10, max 100)
    """
    try:
        engine = await get_azure_engine()
        limit = min(max(1, limit), 100)

        query = text("""
            SELECT TOP :limit
                CustomerID,
                CompanyName,
                ContactName,
                ContactTitle,
                Address,
                City,
                Region,
                PostalCode,
                Country,
                Phone,
                Fax
            FROM Customers
            WHERE CompanyName LIKE :term
               OR ContactName LIKE :term
               OR City LIKE :term
               OR Country LIKE :term
            ORDER BY CompanyName
        """)

        term = f"%{search_criteria}%"

        with engine.connect() as connection:
            result = connection.execute(query, {"limit": limit, "term": term})
            columns = list(result.keys())
            rows = result.fetchall()

            customers = [dict(zip(columns, row)) for row in rows]

        return json.dumps({"search_criteria": search_criteria, "found": len(customers), "customers": customers}, indent=2, default=str)

    except Exception as e:
        return f"Customer search failed: {str(e)}"


@mcp.tool()
async def get_customer_orders(customer_id: str, limit: int = 20) -> str:
    """Get orders for a given customer (from Orders table).

    Args:
        customer_id: CustomerID (e.g., 'ALFKI')
        limit: max number of orders to return (default 20, max 200)
    """
    try:
        engine = await get_azure_engine()
        limit = min(max(1, limit), 200)

        query = text("""
            SELECT TOP :limit
                OrderID,
                CustomerID,
                EmployeeID,
                OrderDate,
                RequiredDate,
                ShippedDate,
                ShipVia,
                Freight,
                ShipName,
                ShipCity,
                ShipCountry
            FROM Orders
            WHERE CustomerID = :customer_id
            ORDER BY OrderDate DESC
        """)

        with engine.connect() as connection:
            result = connection.execute(query, {"limit": limit, "customer_id": customer_id})
            columns = list(result.keys())
            rows = result.fetchall()
            orders = [dict(zip(columns, row)) for row in rows]

        return json.dumps({"customer_id": customer_id, "order_count": len(orders), "orders": orders}, indent=2, default=str)

    except Exception as e:
        return f"Failed to get orders for customer '{customer_id}': {str(e)}"


@mcp.tool()
async def get_order_details(order_id: int) -> str:
    """Get order header and line items for a specific OrderID.

    Args:
        order_id: numeric OrderID
    """
    try:
        engine = await get_azure_engine()

        header_q = text("""
            SELECT OrderID, CustomerID, EmployeeID, OrderDate, RequiredDate, ShippedDate, ShipVia, Freight, ShipName, ShipAddress, ShipCity, ShipRegion, ShipPostalCode, ShipCountry
            FROM Orders
            WHERE OrderID = :order_id
        """)

        lines_q = text("""
            SELECT od.OrderID, od.ProductID, p.ProductName, od.UnitPrice, od.Quantity, od.Discount
            FROM [Order Details] od
            JOIN Products p ON od.ProductID = p.ProductID
            WHERE od.OrderID = :order_id
        """)

        with engine.connect() as connection:
            h_res = connection.execute(header_q, {"order_id": order_id})
            header = h_res.fetchone()
            if not header:
                return f"Order '{order_id}' not found"

            header_cols = list(h_res.keys())
            header_dict = dict(zip(header_cols, header))

            l_res = connection.execute(lines_q, {"order_id": order_id})
            line_cols = list(l_res.keys())
            line_rows = l_res.fetchall()
            lines = [dict(zip(line_cols, row)) for row in line_rows]

        return json.dumps({"order": header_dict, "lines": lines}, indent=2, default=str)

    except Exception as e:
        return f"Failed to get order details for '{order_id}': {str(e)}"


@mcp.tool()
async def search_products(search_criteria: str, limit: int = 10) -> str:
    """Search products by product name, category name or supplier name.

    Args:
        search_criteria: term to search
        limit: maximum results (default 10, max 100)
    """
    try:
        engine = await get_azure_engine()
        limit = min(max(1, limit), 100)

        query = text("""
            SELECT TOP :limit
                p.ProductID,
                p.ProductName,
                c.CategoryName,
                s.CompanyName AS Supplier,
                p.QuantityPerUnit,
                p.UnitPrice,
                p.UnitsInStock,
                p.UnitsOnOrder,
                p.ReorderLevel,
                p.Discontinued
            FROM Products p
            LEFT JOIN Categories c ON p.CategoryID = c.CategoryID
            LEFT JOIN Suppliers s ON p.SupplierID = s.SupplierID
            WHERE p.ProductName LIKE :term
               OR c.CategoryName LIKE :term
               OR s.CompanyName LIKE :term
            ORDER BY p.ProductName
        """)

        term = f"%{search_criteria}%"

        with engine.connect() as connection:
            result = connection.execute(query, {"limit": limit, "term": term})
            columns = list(result.keys())
            rows = result.fetchall()
            products = [dict(zip(columns, row)) for row in rows]

        return json.dumps({"search_criteria": search_criteria, "found": len(products), "products": products}, indent=2, default=str)

    except Exception as e:
        return f"Product search failed: {str(e)}"


@mcp.tool()
async def get_product_info(product_id: int) -> str:
    """Get detailed product information including supplier and category.

    Args:
        product_id: numeric ProductID
    """
    try:
        engine = await get_azure_engine()

        query = text("""
            SELECT p.ProductID, p.ProductName, p.SupplierID, s.CompanyName AS Supplier,
                   p.CategoryID, c.CategoryName,
                   p.QuantityPerUnit, p.UnitPrice, p.UnitsInStock, p.UnitsOnOrder, p.ReorderLevel, p.Discontinued
            FROM Products p
            LEFT JOIN Suppliers s ON p.SupplierID = s.SupplierID
            LEFT JOIN Categories c ON p.CategoryID = c.CategoryID
            WHERE p.ProductID = :product_id
        """)

        with engine.connect() as connection:
            result = connection.execute(query, {"product_id": product_id})
            row = result.fetchone()
            if not row:
                return f"Product '{product_id}' not found"
            cols = list(result.keys())
            prod = dict(zip(cols, row))

        return json.dumps(prod, indent=2, default=str)

    except Exception as e:
        return f"Failed to get product info for '{product_id}': {str(e)}"


# ==================================== Advanced Search Capabilities

@mcp.tool()
async def advanced_search(table_name: str, filters: str, sort_by: str = None, limit: int = 20) -> str:
    """Advanced search with multiple parameters and logical operators.
    
    Args:
        table_name: Name of the table to search (e.g., 'Customers', 'Products', 'Orders')
        filters: JSON string with filter conditions. Example: '{"CompanyName": {"like": "Alfreds"}, "Country": {"eq": "Germany"}}'
        sort_by: Column to sort by (optional). Can include DESC: 'OrderDate DESC'
        limit: Maximum results (default 20, max 200)
    """
    try:
        engine = await get_azure_engine()
        limit = min(max(1, limit), 200)
        
        # Parse filters
        filter_dict = json.loads(filters)
        where_clauses = []
        params = {}
        param_counter = 1
        
        for column, condition in filter_dict.items():
            if isinstance(condition, dict):
                for op, value in condition.items():
                    param_name = f"param{param_counter}"
                    if op == "like":
                        where_clauses.append(f"{column} LIKE :{param_name}")
                        params[param_name] = f"%{value}%"
                    elif op == "eq":
                        where_clauses.append(f"{column} = :{param_name}")
                        params[param_name] = value
                    elif op == "gt":
                        where_clauses.append(f"{column} > :{param_name}")
                        params[param_name] = value
                    elif op == "lt":
                        where_clauses.append(f"{column} < :{param_name}")
                        params[param_name] = value
                    elif op == "gte":
                        where_clauses.append(f"{column} >= :{param_name}")
                        params[param_name] = value
                    elif op == "lte":
                        where_clauses.append(f"{column} <= :{param_name}")
                        params[param_name] = value
                    elif op == "in":
                        placeholders = []
                        for i, val in enumerate(value):
                            placeholder = f"{param_name}_{i}"
                            placeholders.append(f":{placeholder}")
                            params[placeholder] = val
                        where_clauses.append(f"{column} IN ({','.join(placeholders)})")
                    param_counter += 1
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        order_sql = f"ORDER BY {sort_by}" if sort_by else ""
        
        query = text(f"SELECT TOP {limit} * FROM {table_name} WHERE {where_sql} {order_sql}")
        
        with engine.connect() as connection:
            result = connection.execute(query, params)
            columns = list(result.keys())
            rows = result.fetchall()
            data = [dict(zip(columns, row)) for row in rows]
        
        return json.dumps({
            "table": table_name,
            "filters_applied": filter_dict,
            "found": len(data),
            "data": data
        }, indent=2, default=str)
        
    except Exception as e:
        return f"Advanced search failed: {str(e)}"


@mcp.tool()
async def range_search(table_name: str, column: str, min_value, max_value, additional_filters: str = "{}", limit: int = 50) -> str:
    """Search records within a specific range for numeric or date columns.
    
    Args:
        table_name: Name of the table
        column: Column name for range search
        min_value: Minimum value (inclusive)
        max_value: Maximum value (inclusive)
        additional_filters: Additional filters as JSON string (optional)
        limit: Maximum results (default 50, max 200)
    """
    try:
        engine = await get_azure_engine()
        limit = min(max(1, limit), 200)
        
        where_clauses = [f"{column} BETWEEN :min_val AND :max_val"]
        params = {"min_val": min_value, "max_val": max_value}
        
        # Add additional filters if provided
        if additional_filters != "{}":
            additional = json.loads(additional_filters)
            param_counter = 1
            for col, condition in additional.items():
                if isinstance(condition, dict):
                    for op, value in condition.items():
                        param_name = f"add_param{param_counter}"
                        if op == "like":
                            where_clauses.append(f"{col} LIKE :{param_name}")
                            params[param_name] = f"%{value}%"
                        elif op == "eq":
                            where_clauses.append(f"{col} = :{param_name}")
                            params[param_name] = value
                        param_counter += 1
        
        where_sql = " AND ".join(where_clauses)
        query = text(f"SELECT TOP {limit} * FROM {table_name} WHERE {where_sql} ORDER BY {column}")
        
        with engine.connect() as connection:
            result = connection.execute(query, params)
            columns = list(result.keys())
            rows = result.fetchall()
            data = [dict(zip(columns, row)) for row in rows]
        
        return json.dumps({
            "table": table_name,
            "range_column": column,
            "range": f"{min_value} to {max_value}",
            "found": len(data),
            "data": data
        }, indent=2, default=str)
        
    except Exception as e:
        return f"Range search failed: {str(e)}"


# ==================================== Data Manipulation Operations

@mcp.tool()
async def safe_insert_record(table_name: str, record_data: str, validate_only: bool = False) -> str:
    """Safely insert a new record with validation.
    
    Args:
        table_name: Name of the table
        record_data: JSON string with column-value pairs
        validate_only: If true, only validate without inserting (default: false)
    """
    try:
        engine = await get_azure_engine()
        data = json.loads(record_data)
        
        # Get table schema for validation
        schema_query = text(f"""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = '{table_name}'
            ORDER BY ORDINAL_POSITION
        """)
        
        with engine.connect() as connection:
            schema_result = connection.execute(schema_query)
            schema_rows = schema_result.fetchall()
            
            if not schema_rows:
                return f"Table '{table_name}' not found"
            
            # Validate columns exist
            valid_columns = {row.COLUMN_NAME for row in schema_rows}
            invalid_columns = set(data.keys()) - valid_columns
            
            if invalid_columns:
                return f"Invalid columns: {list(invalid_columns)}"
            
            if validate_only:
                return json.dumps({
                    "validation": "passed",
                    "table": table_name,
                    "columns_to_insert": list(data.keys()),
                    "would_insert": data
                }, indent=2)
            
            # Build INSERT query
            columns = list(data.keys())
            placeholders = [f":{col}" for col in columns]
            
            insert_query = text(f"""
                INSERT INTO {table_name} ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
            """)
            
            result = connection.execute(insert_query, data)
            connection.commit()
            
            return json.dumps({
                "operation": "insert",
                "table": table_name,
                "rows_affected": result.rowcount,
                "inserted_data": data
            }, indent=2)
        
    except Exception as e:
        return f"Insert operation failed: {str(e)}"


@mcp.tool()
async def safe_update_record(table_name: str, where_conditions: str, update_data: str, validate_only: bool = False) -> str:
    """Safely update records with validation and preview.
    
    Args:
        table_name: Name of the table
        where_conditions: JSON string with WHERE conditions
        update_data: JSON string with columns to update
        validate_only: If true, show what would be updated without executing
    """
    try:
        engine = await get_azure_engine()
        where_dict = json.loads(where_conditions)
        update_dict = json.loads(update_data)
        
        # Build WHERE clause
        where_clauses = []
        where_params = {}
        for col, value in where_dict.items():
            where_clauses.append(f"{col} = :where_{col}")
            where_params[f"where_{col}"] = value
        
        where_sql = " AND ".join(where_clauses)
        
        # First, show what records would be affected
        preview_query = text(f"SELECT * FROM {table_name} WHERE {where_sql}")
        
        with engine.connect() as connection:
            preview = connection.execute(preview_query, where_params)
            preview_rows = preview.fetchall()
            preview_cols = list(preview.keys())
            affected_records = [dict(zip(preview_cols, row)) for row in preview_rows]
            
            if not affected_records:
                return f"No records found matching the WHERE conditions"
            
            if validate_only:
                return json.dumps({
                    "validation": "passed",
                    "records_that_would_be_updated": len(affected_records),
                    "current_records": affected_records,
                    "updates_to_apply": update_dict
                }, indent=2, default=str)
            
            # Build UPDATE query
            set_clauses = []
            update_params = {**where_params}
            for col, value in update_dict.items():
                set_clauses.append(f"{col} = :update_{col}")
                update_params[f"update_{col}"] = value
            
            set_sql = ", ".join(set_clauses)
            update_query = text(f"UPDATE {table_name} SET {set_sql} WHERE {where_sql}")
            
            result = connection.execute(update_query, update_params)
            connection.commit()
            
            return json.dumps({
                "operation": "update",
                "table": table_name,
                "rows_affected": result.rowcount,
                "where_conditions": where_dict,
                "updates_applied": update_dict
            }, indent=2)
        
    except Exception as e:
        return f"Update operation failed: {str(e)}"


# ==================================== Batch Processing Tools

@mcp.tool()
async def batch_insert_records(table_name: str, records_data: str, batch_size: int = 100) -> str:
    """Insert multiple records in batches for better performance.
    
    Args:
        table_name: Name of the table
        records_data: JSON array string with multiple records
        batch_size: Number of records per batch (default 100, max 1000)
    """
    try:
        engine = await get_azure_engine()
        records = json.loads(records_data)
        batch_size = min(max(1, batch_size), 1000)
        
        if not isinstance(records, list):
            return "records_data must be a JSON array"
        
        total_inserted = 0
        failed_batches = []
        
        # Process in batches
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            
            try:
                with engine.connect() as connection:
                    # Assume all records have the same structure as the first one
                    if batch:
                        columns = list(batch[0].keys())
                        placeholders = [f":{col}" for col in columns]
                        
                        insert_query = text(f"""
                            INSERT INTO {table_name} ({', '.join(columns)})
                            VALUES ({', '.join(placeholders)})
                        """)
                        
                        for record in batch:
                            connection.execute(insert_query, record)
                        
                        connection.commit()
                        total_inserted += len(batch)
                        
            except Exception as batch_error:
                failed_batches.append({
                    "batch_start": i,
                    "batch_size": len(batch),
                    "error": str(batch_error)
                })
        
        return json.dumps({
            "operation": "batch_insert",
            "table": table_name,
            "total_records": len(records),
            "successfully_inserted": total_inserted,
            "failed_batches": failed_batches,
            "batch_size_used": batch_size
        }, indent=2)
        
    except Exception as e:
        return f"Batch insert failed: {str(e)}"


@mcp.tool()
async def bulk_update_records(table_name: str, update_rules: str) -> str:
    """Perform bulk updates based on multiple conditions.
    
    Args:
        table_name: Name of the table
        update_rules: JSON array with update rules. Each rule has 'where', 'set', and optional 'description'
    """
    try:
        engine = await get_azure_engine()
        rules = json.loads(update_rules)
        
        if not isinstance(rules, list):
            return "update_rules must be a JSON array"
        
        results = []
        
        with engine.connect() as connection:
            for i, rule in enumerate(rules):
                try:
                    where_conditions = rule.get('where', {})
                    set_values = rule.get('set', {})
                    description = rule.get('description', f'Rule {i+1}')
                    
                    # Build WHERE clause
                    where_clauses = []
                    where_params = {}
                    for col, value in where_conditions.items():
                        param_name = f"where_{col}_{i}"
                        where_clauses.append(f"{col} = :{param_name}")
                        where_params[param_name] = value
                    
                    # Build SET clause
                    set_clauses = []
                    set_params = {}
                    for col, value in set_values.items():
                        param_name = f"set_{col}_{i}"
                        set_clauses.append(f"{col} = :{param_name}")
                        set_params[param_name] = value
                    
                    if where_clauses and set_clauses:
                        where_sql = " AND ".join(where_clauses)
                        set_sql = ", ".join(set_clauses)
                        
                        update_query = text(f"UPDATE {table_name} SET {set_sql} WHERE {where_sql}")
                        all_params = {**where_params, **set_params}
                        
                        result = connection.execute(update_query, all_params)
                        
                        results.append({
                            "rule": description,
                            "rows_affected": result.rowcount,
                            "where_conditions": where_conditions,
                            "updates": set_values,
                            "status": "success"
                        })
                    
                except Exception as rule_error:
                    results.append({
                        "rule": f"Rule {i+1}",
                        "status": "failed",
                        "error": str(rule_error)
                    })
            
            connection.commit()
        
        return json.dumps({
            "operation": "bulk_update",
            "table": table_name,
            "rules_processed": len(rules),
            "results": results
        }, indent=2)
        
    except Exception as e:
        return f"Bulk update failed: {str(e)}"


# ==================================== Custom Aggregate Functions

@mcp.tool()
async def custom_aggregation(table_name: str, group_by_columns: str, aggregate_functions: str, where_conditions: str = "{}", having_conditions: str = "{}") -> str:
    """Perform custom aggregations with grouping and filtering.
    
    Args:
        table_name: Name of the table
        group_by_columns: JSON array of columns to group by
        aggregate_functions: JSON object with aggregate functions. E.g., {"total_sales": "SUM(UnitPrice * Quantity)", "avg_price": "AVG(UnitPrice)"}
        where_conditions: JSON object with WHERE conditions (optional)
        having_conditions: JSON object with HAVING conditions (optional)
    """
    try:
        engine = await get_azure_engine()
        
        group_cols = json.loads(group_by_columns)
        agg_funcs = json.loads(aggregate_functions)
        where_dict = json.loads(where_conditions) if where_conditions != "{}" else {}
        having_dict = json.loads(having_conditions) if having_conditions != "{}" else {}
        
        # Build SELECT clause
        select_parts = group_cols.copy()
        for alias, func in agg_funcs.items():
            select_parts.append(f"{func} AS {alias}")
        
        select_sql = ", ".join(select_parts)
        
        # Build WHERE clause
        where_sql = ""
        where_params = {}
        if where_dict:
            where_clauses = []
            for col, value in where_dict.items():
                param_name = f"where_{col}"
                where_clauses.append(f"{col} = :{param_name}")
                where_params[param_name] = value
            where_sql = "WHERE " + " AND ".join(where_clauses)
        
        # Build GROUP BY clause
        group_sql = f"GROUP BY {', '.join(group_cols)}" if group_cols else ""
        
        # Build HAVING clause
        having_sql = ""
        having_params = {}
        if having_dict:
            having_clauses = []
            for condition, value in having_dict.items():
                param_name = f"having_{len(having_params)}"
                having_clauses.append(f"{condition} > :{param_name}")
                having_params[param_name] = value
            having_sql = "HAVING " + " AND ".join(having_clauses)
        
        query = text(f"""
            SELECT {select_sql}
            FROM {table_name}
            {where_sql}
            {group_sql}
            {having_sql}
            ORDER BY {group_cols[0] if group_cols else list(agg_funcs.keys())[0]}
        """)
        
        all_params = {**where_params, **having_params}
        
        with engine.connect() as connection:
            result = connection.execute(query, all_params)
            columns = list(result.keys())
            rows = result.fetchall()
            data = [dict(zip(columns, row)) for row in rows]
        
        return json.dumps({
            "aggregation_summary": {
                "table": table_name,
                "grouped_by": group_cols,
                "aggregates": agg_funcs,
                "filters_applied": where_dict,
                "having_conditions": having_dict
            },
            "result_count": len(data),
            "data": data
        }, indent=2, default=str)
        
    except Exception as e:
        return f"Custom aggregation failed: {str(e)}"


@mcp.tool()
async def sales_analytics(date_range_start: str = None, date_range_end: str = None, group_by: str = "month") -> str:
    """Specialized analytics for Northwind sales data.
    
    Args:
        date_range_start: Start date (YYYY-MM-DD format, optional)
        date_range_end: End date (YYYY-MM-DD format, optional)
        group_by: Grouping level: 'day', 'month', 'quarter', 'year', 'category', 'customer', 'employee'
    """
    try:
        engine = await get_azure_engine()
        
        # Build date filter
        date_filter = ""
        params = {}
        if date_range_start and date_range_end:
            date_filter = "AND o.OrderDate BETWEEN :start_date AND :end_date"
            params["start_date"] = date_range_start
            params["end_date"] = date_range_end
        
        # Build grouping
        if group_by == "month":
            group_expr = "FORMAT(o.OrderDate, 'yyyy-MM')"
            group_label = "Month"
        elif group_by == "quarter":
            group_expr = "CONCAT(YEAR(o.OrderDate), '-Q', DATEPART(QUARTER, o.OrderDate))"
            group_label = "Quarter"
        elif group_by == "year":
            group_expr = "YEAR(o.OrderDate)"
            group_label = "Year"
        elif group_by == "day":
            group_expr = "CAST(o.OrderDate AS DATE)"
            group_label = "Date"
        elif group_by == "category":
            group_expr = "c.CategoryName"
            group_label = "Category"
        elif group_by == "customer":
            group_expr = "cust.CompanyName"
            group_label = "Customer"
        elif group_by == "employee":
            group_expr = "CONCAT(e.FirstName, ' ', e.LastName)"
            group_label = "Employee"
        else:
            group_expr = "FORMAT(o.OrderDate, 'yyyy-MM')"
            group_label = "Month"
        
        # Build JOIN clauses based on grouping
        joins = ""
        if group_by == "category":
            joins = """
                JOIN Products p ON od.ProductID = p.ProductID
                JOIN Categories c ON p.CategoryID = c.CategoryID
            """
        elif group_by == "customer":
            joins = "JOIN Customers cust ON o.CustomerID = cust.CustomerID"
        elif group_by == "employee":
            joins = "JOIN Employees e ON o.EmployeeID = e.EmployeeID"
        
        query = text(f"""
            SELECT 
                {group_expr} AS {group_label},
                COUNT(DISTINCT o.OrderID) AS OrderCount,
                SUM(od.UnitPrice * od.Quantity * (1 - od.Discount)) AS TotalSales,
                AVG(od.UnitPrice * od.Quantity * (1 - od.Discount)) AS AverageOrderValue,
                SUM(od.Quantity) AS TotalQuantity,
                COUNT(DISTINCT o.CustomerID) AS UniqueCustomers
            FROM Orders o
            JOIN [Order Details] od ON o.OrderID = od.OrderID
            {joins}
            WHERE 1=1 {date_filter}
            GROUP BY {group_expr}
            ORDER BY {group_expr}
        """)
        
        with engine.connect() as connection:
            result = connection.execute(query, params)
            columns = list(result.keys())
            rows = result.fetchall()
            data = [dict(zip(columns, row)) for row in rows]
        
        # Calculate summary statistics
        total_sales = sum(row['TotalSales'] for row in data if row['TotalSales'])
        total_orders = sum(row['OrderCount'] for row in data)
        
        return json.dumps({
            "analytics_summary": {
                "grouped_by": group_by,
                "date_range": f"{date_range_start} to {date_range_end}" if date_range_start and date_range_end else "All dates",
                "total_sales": total_sales,
                "total_orders": total_orders,
                "periods_analyzed": len(data)
            },
            "data": data
        }, indent=2, default=str)
        
    except Exception as e:
        return f"Sales analytics failed: {str(e)}"


# ==================================== Interactive Data Analysis

@mcp.tool()
async def paginated_query(query: str, page: int = 1, page_size: int = 20, count_total: bool = False) -> str:
    """Execute queries with pagination support for large result sets.
    
    Args:
        query: SQL query to execute (without LIMIT/OFFSET)
        page: Page number (1-based)
        page_size: Records per page (default 20, max 100)
        count_total: Whether to count total records (may be slow for large tables)
    """
    try:
        engine = await get_azure_engine()
        page_size = min(max(1, page_size), 100)
        offset = (page - 1) * page_size
        
        # Add pagination to query
        paginated_query = text(f"""
            {query}
            ORDER BY (SELECT NULL)
            OFFSET {offset} ROWS
            FETCH NEXT {page_size} ROWS ONLY
        """)
        
        with engine.connect() as connection:
            result = connection.execute(paginated_query)
            columns = list(result.keys())
            rows = result.fetchall()
            data = [dict(zip(columns, row)) for row in rows]
            
            total_count = None
            if count_total:
                # Get total count
                count_query = text(f"SELECT COUNT(*) as total FROM ({query}) as subquery")
                count_result = connection.execute(count_query)
                total_count = count_result.fetchone().total
        
        pagination_info = {
            "current_page": page,
            "page_size": page_size,
            "records_on_page": len(data),
            "has_next_page": len(data) == page_size
        }
        
        if total_count is not None:
            pagination_info["total_records"] = total_count
            pagination_info["total_pages"] = (total_count + page_size - 1) // page_size
        
        return json.dumps({
            "pagination": pagination_info,
            "data": data
        }, indent=2, default=str)
        
    except Exception as e:
        return f"Paginated query failed: {str(e)}"


@mcp.tool()
async def data_profiling(table_name: str, columns: str = "[]") -> str:
    """Generate data profiling statistics for table columns.
    
    Args:
        table_name: Name of the table to profile
        columns: JSON array of specific columns to profile (empty array for all columns)
    """
    try:
        engine = await get_azure_engine()
        target_columns = json.loads(columns)
        
        # Get table schema
        schema_query = text(f"""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = '{table_name}'
            ORDER BY ORDINAL_POSITION
        """)
        
        with engine.connect() as connection:
            schema_result = connection.execute(schema_query)
            schema_rows = schema_result.fetchall()
            
            if not schema_rows:
                return f"Table '{table_name}' not found"
            
            # Filter columns if specified
            if target_columns:
                schema_rows = [row for row in schema_rows if row.COLUMN_NAME in target_columns]
            
            profile_results = []
            
            for column_info in schema_rows:
                col_name = column_info.COLUMN_NAME
                data_type = column_info.DATA_TYPE
                
                # Basic statistics query
                if data_type in ['int', 'bigint', 'decimal', 'numeric', 'float', 'real', 'money']:
                    # Numeric column
                    stats_query = text(f"""
                        SELECT 
                            COUNT(*) as total_count,
                            COUNT({col_name}) as non_null_count,
                            COUNT(*) - COUNT({col_name}) as null_count,
                            MIN({col_name}) as min_value,
                            MAX({col_name}) as max_value,
                            AVG(CAST({col_name} AS FLOAT)) as avg_value,
                            COUNT(DISTINCT {col_name}) as distinct_count
                        FROM {table_name}
                    """)
                elif data_type in ['varchar', 'nvarchar', 'char', 'nchar', 'text', 'ntext']:
                    # String column
                    stats_query = text(f"""
                        SELECT 
                            COUNT(*) as total_count,
                            COUNT({col_name}) as non_null_count,
                            COUNT(*) - COUNT({col_name}) as null_count,
                            MIN(LEN({col_name})) as min_length,
                            MAX(LEN({col_name})) as max_length,
                            AVG(CAST(LEN({col_name}) AS FLOAT)) as avg_length,
                            COUNT(DISTINCT {col_name}) as distinct_count
                        FROM {table_name}
                    """)
                else:
                    # Generic column
                    stats_query = text(f"""
                        SELECT 
                            COUNT(*) as total_count,
                            COUNT({col_name}) as non_null_count,
                            COUNT(*) - COUNT({col_name}) as null_count,
                            COUNT(DISTINCT {col_name}) as distinct_count
                        FROM {table_name}
                    """)
                
                stats_result = connection.execute(stats_query)
                stats = dict(stats_result.fetchone())
                
                # Get top values
                top_values_query = text(f"""
                    SELECT TOP 5 {col_name}, COUNT(*) as frequency
                    FROM {table_name}
                    WHERE {col_name} IS NOT NULL
                    GROUP BY {col_name}
                    ORDER BY COUNT(*) DESC
                """)
                
                top_values_result = connection.execute(top_values_query)
                top_values = [dict(row) for row in top_values_result.fetchall()]
                
                profile_results.append({
                    "column_name": col_name,
                    "data_type": data_type,
                    "statistics": stats,
                    "top_values": top_values
                })
        
        return json.dumps({
            "table": table_name,
            "profiling_results": profile_results
        }, indent=2, default=str)
        
    except Exception as e:
        return f"Data profiling failed: {str(e)}"


# ==================================== Query Suggestions and History

@mcp.tool()
async def suggest_queries(context: str, table_focus: str = None) -> str:
    """Generate query suggestions based on context and Northwind database structure.
    
    Args:
        context: Description of what the user wants to analyze or find
        table_focus: Specific table to focus suggestions on (optional)
    """
    try:
        suggestions = []
        
        # Context-based suggestions
        context_lower = context.lower()
        
        if any(term in context_lower for term in ['sales', 'revenue', 'money', 'profit']):
            suggestions.extend([
                {
                    "query": "SELECT c.CompanyName, SUM(od.UnitPrice * od.Quantity * (1 - od.Discount)) AS TotalSales FROM Customers c JOIN Orders o ON c.CustomerID = o.CustomerID JOIN [Order Details] od ON o.OrderID = od.OrderID GROUP BY c.CompanyName ORDER BY TotalSales DESC",
                    "description": "Top customers by total sales revenue",
                    "use_case": "Customer revenue analysis"
                },
                {
                    "query": "SELECT p.ProductName, SUM(od.UnitPrice * od.Quantity * (1 - od.Discount)) AS ProductRevenue FROM Products p JOIN [Order Details] od ON p.ProductID = od.ProductID GROUP BY p.ProductName ORDER BY ProductRevenue DESC",
                    "description": "Best selling products by revenue",
                    "use_case": "Product performance analysis"
                }
            ])
        
        if any(term in context_lower for term in ['customer', 'client', 'buyer']):
            suggestions.extend([
                {
                    "query": "SELECT Country, COUNT(*) AS CustomerCount FROM Customers GROUP BY Country ORDER BY CustomerCount DESC",
                    "description": "Customer distribution by country",
                    "use_case": "Geographic customer analysis"
                },
                {
                    "query": "SELECT c.CompanyName, COUNT(o.OrderID) AS OrderCount FROM Customers c LEFT JOIN Orders o ON c.CustomerID = o.CustomerID GROUP BY c.CompanyName ORDER BY OrderCount DESC",
                    "description": "Customers by order frequency",
                    "use_case": "Customer activity analysis"
                }
            ])
        
        if any(term in context_lower for term in ['product', 'inventory', 'stock']):
            suggestions.extend([
                {
                    "query": "SELECT ProductName, UnitsInStock, ReorderLevel FROM Products WHERE UnitsInStock <= ReorderLevel AND Discontinued = 0",
                    "description": "Products that need reordering",
                    "use_case": "Inventory management"
                },
                {
                    "query": "SELECT c.CategoryName, COUNT(p.ProductID) AS ProductCount, AVG(p.UnitPrice) AS AvgPrice FROM Categories c JOIN Products p ON c.CategoryID = p.CategoryID GROUP BY c.CategoryName",
                    "description": "Product count and average price by category",
                    "use_case": "Category analysis"
                }
            ])
        
        if any(term in context_lower for term in ['employee', 'staff', 'worker']):
            suggestions.extend([
                {
                    "query": "SELECT e.FirstName + ' ' + e.LastName AS EmployeeName, COUNT(o.OrderID) AS OrdersHandled FROM Employees e LEFT JOIN Orders o ON e.EmployeeID = o.EmployeeID GROUP BY e.FirstName, e.LastName ORDER BY OrdersHandled DESC",
                    "description": "Employee performance by orders handled",
                    "use_case": "Employee productivity analysis"
                },
                {
                    "query": "SELECT e.FirstName + ' ' + e.LastName AS EmployeeName, SUM(od.UnitPrice * od.Quantity * (1 - od.Discount)) AS SalesGenerated FROM Employees e JOIN Orders o ON e.EmployeeID = o.EmployeeID JOIN [Order Details] od ON o.OrderID = od.OrderID GROUP BY e.FirstName, e.LastName ORDER BY SalesGenerated DESC",
                    "description": "Employee sales performance",
                    "use_case": "Sales team analysis"
                }
            ])
        
        if any(term in context_lower for term in ['time', 'date', 'trend', 'period']):
            suggestions.extend([
                {
                    "query": "SELECT FORMAT(OrderDate, 'yyyy-MM') AS Month, COUNT(*) AS OrderCount, SUM(Freight) AS TotalFreight FROM Orders GROUP BY FORMAT(OrderDate, 'yyyy-MM') ORDER BY Month",
                    "description": "Monthly order trends with freight costs",
                    "use_case": "Time series analysis"
                },
                {
                    "query": "SELECT DATENAME(WEEKDAY, OrderDate) AS DayOfWeek, COUNT(*) AS OrderCount FROM Orders GROUP BY DATENAME(WEEKDAY, OrderDate), DATEPART(WEEKDAY, OrderDate) ORDER BY DATEPART(WEEKDAY, OrderDate)",
                    "description": "Orders by day of week",
                    "use_case": "Weekly pattern analysis"
                }
            ])
        
        # Table-specific suggestions
        if table_focus:
            table_focus = table_focus.lower()
            if table_focus == 'orders':
                suggestions.append({
                    "query": f"SELECT TOP 10 * FROM Orders ORDER BY OrderDate DESC",
                    "description": f"Recent orders from {table_focus} table",
                    "use_case": "Recent activity review"
                })
            elif table_focus in ['customers', 'products', 'employees']:
                suggestions.append({
                    "query": f"SELECT TOP 10 * FROM {table_focus.title()} ORDER BY 1",
                    "description": f"Sample records from {table_focus} table",
                    "use_case": "Data exploration"
                })
        
        # Default suggestions if none match
        if not suggestions:
            suggestions = [
                {
                    "query": "SELECT COUNT(*) AS TotalOrders, SUM(Freight) AS TotalFreight FROM Orders",
                    "description": "Overall order statistics",
                    "use_case": "General overview"
                },
                {
                    "query": "SELECT TOP 5 CompanyName FROM Customers ORDER BY CompanyName",
                    "description": "Sample customer list",
                    "use_case": "Data exploration"
                }
            ]
        
        return json.dumps({
            "context_analyzed": context,
            "table_focus": table_focus,
            "suggested_queries": suggestions[:8]  # Limit to 8 suggestions
        }, indent=2)
        
    except Exception as e:
        return f"Query suggestion failed: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport='stdio')