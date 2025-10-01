# Northwind SQL Agent

A developer-oriented template for building AI agents that query and reason over a Northwind-style SQL database using [Microsoft Semantic Kernel](https://github.com/microsoft/semantic-kernel). This repository contains utilities for running an MCP server that exposes SQL helper tools and a Semantic Kernel-based agent that uses prompt templates in `prompts/`.

## What actually lives in this repository

Top-level (root) entries:

- `.dockerignore`
- `.git/` (git repo)
- `.gitignore`
- `agent/` (agent implementation)
- `config/` (agent and kernel configuration)
- `Dockerfile`
- `kernel/` (kernel initializers)
- `main.py` (CLI entry used in examples)
- `mcp_server/` (MCP server implementation that connects to Azure SQL)
- `plugins/` (plugin implementations)
- `prompts/` (prompt YAML templates)
- `README.md` (this file)
- `requirements.txt`
- `scripts/` (helper powershell scripts)

Notable directories and files (actual names):

- `src/`
    - `agent.py` — the Semantic Kernel agent wrapper and MCP plugin handling
    - `__init__.py`

- `config/`
    - `agent_config.yaml`
    - `kernel_config.yaml`

- `kernel/`
    - `kernel.py` — kernel setup helpers used by the agent

- `mcp_server/`
    - `server.py` — MCP tools and Azure SQL integration (this is where the Northwind helpers were added)
    - `demo.py`, `pyproject.toml`, `.python-version`, `README.md`, `uv.lock`

- `plugins/`
    - `azure_blob_plugin.py`
    - `__init__.py`

- `prompts/`
    - `northwind_prompt.yaml` — the prompt template now present in the repo

- `scripts/`
    - `build_docker_image.ps1`
    - `run_docker_container.ps1`

I examined the repository contents and updated this README so the structure and filenames described here match the actual files on disk.

## Quick start (aligns with repo layout)

1. Create and activate a Python virtual environment and install dependencies:

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

2. Configure environment variables in a `.env` file (examples):

```text
SERVER_NAME=your-azure-sql-server.database.windows.net
DATABASE=your-database-name
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_API_KEY=...
```

3. Run the example agent CLI (uses `main.py`):

```bash
python main.py
```

4. Run the MCP server (found in `mcp_server/server.py`) via the MCP inspector or directly with your MCP workflow.

## Northwind-specific tools (where they are implemented)

The MCP tools that query the database live in `mcp_server/server.py`. Tools available (examples):

- `execute_query(query: str)`
- `get_tables()`
- `get_table_schema(table_name: str)`
- `get_sample_data(table_name: str, limit: int)`
- `search_customers(search_criteria: str, limit: int)`
- `get_customer_orders(customer_id: str, limit: int)`
- `get_order_details(order_id: int)`
- `search_products(search_criteria: str, limit: int)`
- `get_product_info(product_id: int)`

If you want the agent to use the `prompts/northwind_prompt.yaml` by default, ensure `config/agent_config.yaml` references that file (I can update it if you want).

## Next steps I can help with

- Update `config/agent_config.yaml` to point to `prompts/northwind_prompt.yaml`.
- Add a small `demo_northwind.py` that exercises `mcp_server` tools programmatically.
- Add unit tests that mock the DB engine and validate the MCP tool outputs.

If you'd like me to perform any of those, tell me which and I'll proceed.
