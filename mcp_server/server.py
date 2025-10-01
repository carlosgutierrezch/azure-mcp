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

if __name__ == "__main__":
    mcp.run(transport='stdio')