# MCP Server Setup Guide

This guide covers the complete setup and startup process for the MCP (Model Context Protocol) server with Azure SQL Database integration.

## Prerequisites

- **Python 3.11+** (managed via pyenv)
- **Node.js** (for MCP Inspector)
- **uv** (Python package manager)
- **Azure credentials** (for database access)

## Initial Project Setup

### 1. Set Python Version
```powershell
# Set global Python version (if not already set)
pyenv global 3.11.4

# Or set local version for this project
pyenv local 3.11.4
```

### 2. Create Project with uv
```powershell
# Create the project directory and navigate to it
uv init mcp_server
cd mcp_server
```

### 3. Create and Activate Virtual Environment
```powershell
# Create virtual environment using uv
uv venv

# Activate the virtual environment (Windows)
.venv\Scripts\activate
```

### 4. Install Dependencies
```powershell
# Sync dependencies from pyproject.toml
uv sync

# Or add individual packages if needed
uv add mcp[cli] httpx sqlalchemy pyodbc azure-identity python-dotenv semantic-kernel
```

### 5. Configure Environment Variables
Create a `.env` file in the parent directory (`../`) with:
```env
SERVER_NAME=your-azure-sql-server.database.windows.net
DATABASE=your-database-name
AZURE_OPENAI_ENDPOINT=https://your-openai-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
AZURE_OPENAI_GPT-4.1-MINI_DEPLOYMENT_NAME=your-deployment-name
```

## Running the MCP Server

### Method 1: MCP Inspector (Web UI) - Recommended for Testing

1. **Navigate to project directory:**
   ```powershell
   cd C:\Users\postc\OneDrive\Desktop\mcp\mcp_server
   ```

2. **Ensure virtual environment is activated:**
   ```powershell
   .venv\Scripts\activate
   ```

3. **Start MCP Inspector:**
   ```powershell
   npx @modelcontextprotocol/inspector uv --directory . run server.py
   ```

   **Expected Output:**
   ```
   Starting MCP inspector...
   ⚙️ Proxy server listening on localhost:6277
   🔑 Session token: [your-session-token]
   🚀 MCP Inspector is up and running at:
      http://localhost:6274/?MCP_PROXY_AUTH_TOKEN=[token]
   🌐 Opening browser...
   ```

4. **Access the Inspector:**
   - Browser will open automatically
   - Or manually navigate to the provided URL
   - Test your tools in the web interface

### Method 2: Direct Integration (demo.py)

1. **Navigate to project directory:**
   ```powershell
   cd C:\Users\postc\OneDrive\Desktop\mcp\mcp_server
   ```

2. **Run the demo script:**
   ```powershell
   uv run demo.py
   ```

   This will:
   - Connect to Azure OpenAI
   - Start MCP server in background
   - Execute a test query
   - Display results

### Method 3: Direct MCP Server (for debugging)

1. **Run server directly:**
   ```powershell
   uv run server.py
   ```
   
   *Note: This waits for stdin input and is mainly used by MCP clients.*

## Available Tools

Your MCP server provides these database tools:

### General Database Tools
- **`execute_query(query: str)`** - Execute custom SQL queries
- **`get_tables()`** - List all database tables
- **`get_table_schema(table_name: str)`** - Get table structure
- **`get_sample_data(table_name: str, limit: int)`** - Get sample rows

### Northwind-Specific Tools
- **`search_customers(search_criteria: str, limit: int)`** - Search customers by `CompanyName`, `ContactName`, `City`, or `Country`.
- **`get_customer_orders(customer_id: str, limit: int)`** - List recent orders for a `CustomerID` (e.g., `ALFKI`).
- **`get_order_details(order_id: int)`** - Get order header and line items for a specific `OrderID`.
- **`search_products(search_criteria: str, limit: int)`** - Search products by product name, category name, or supplier name.
- **`get_product_info(product_id: int)`** - Get detailed product information including supplier and category.

## Project Structure

```
mcp_server/
├── .venv/                 # Virtual environment (created by uv)
├── .python-version       # Python version file
├── pyproject.toml        # Project configuration and dependencies
├── server.py             # Main MCP server implementation
├── demo.py               # Integration demo with Semantic Kernel
└── ../.env              # Environment variables (in parent directory)
```

## Troubleshooting

### Common Issues

1. **"No global/local python version has been set"**
   ```powershell
   pyenv local 3.11.4
   ```

2. **"The Python request resolved to Python X.X.X, which is incompatible"**
   - Update `pyproject.toml` to match your Python version:
   ```toml
   requires-python = ">=3.11"  # Adjust as needed
   ```

3. **Module import errors:**
   ```powershell
   uv sync  # Reinstall dependencies
   ```

4. **Azure authentication errors:**
   - Verify `.env` file exists in parent directory
   - Check Azure credentials are valid
   - Ensure Azure CLI is logged in: `az login`

5. **MCP Inspector path errors:**
   - Use relative path: `--directory .` instead of absolute paths
   - Ensure you're in the project directory

### Dependency Management

- **Add new dependency:** `uv add package-name`
- **Remove dependency:** `uv remove package-name`
- **Update dependencies:** `uv sync`
- **Show installed packages:** `uv pip list`

## Testing the Setup

### Quick Test Sequence

1. **Test MCP server starts:**
   ```powershell
   uv run server.py
   # Should start without errors (Ctrl+C to stop)
   ```

2. **Test Inspector connection:**
   ```powershell
   npx @modelcontextprotocol/inspector uv --directory . run server.py
   # Should open browser and show tools
   ```

3. **Test database integration:**
   ```powershell
   uv run demo.py
   # Should connect and attempt database query
   ```

## Next Steps

1. **Configure Azure credentials** in `.env` file
2. **Test database connectivity** using `get_tables()` tool
3. **Test and customize the Northwind tools** based on your database schema (table/column names may differ if your Northwind variant is modified)
4. **Integrate with your preferred MCP client** (Claude, etc.)

---