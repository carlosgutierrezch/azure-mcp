import os
import asyncio
from pathlib import Path

from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import (
    AzureChatCompletion,
)
from semantic_kernel.agents import ChatCompletionAgent
from semantic_kernel.connectors.mcp import MCPStdioPlugin
from dotenv import load_dotenv

load_dotenv("../.env")

class Config:
    AOAI_ENDPOINT = os.getenv(
        "AZURE_OPENAI_ENDPOINT"
    )
    AOAI_KEY = os.getenv(
        "AZURE_OPENAI_API_KEY"
    )
    DEPLOYMENT_NAME = os.getenv(
        "AZURE_OPENAI_GPT_41_DEPLOYMENT_NAME"
    )
    
    SERVER_NAME = os.getenv(
        "SERVER_NAME"
    )
    DATABASE = os.getenv(
        "DATABASE"
    )
    
    MCP_SERVER_PATH = "server.py"
    MCP_COMMAND = "uv"
    MCP_ARGS = ["run"]
    
    AGENT_NAME = "ABANCA-Assistant"
    AGENT_INSTRUCTIONS = """Eres un asistente que puede usar herramientas para responder preguntas sobre la base de datos.
Cuando te pregunten sobre tablas, SIEMPRE usa la función get_tables() para obtener la información actualizada.
No digas que no puedes conectarte sin intentar usar las herramientas disponibles.

Funciones disponibles:
- get_tables(): Obtiene lista de todas las tablas
- get_table_schema(table_name): Obtiene esquema de una tabla específica  
- get_sample_data(table_name, limit): Obtiene datos de muestra de una tabla
- execute_query(query): Ejecuta una consulta SQL personalizada"""

    TEST_MESSAGE = "¿Puedes consultar las tablas existentes en la base de datos y decirme el nombre de cada una de ellas?"


def create_kernel() -> Kernel:
    """Create and configure the kernel with Azure OpenAI service"""
    kernel = Kernel()
    
    azure_service = AzureChatCompletion(
        service_id="default",
        deployment_name=Config.DEPLOYMENT_NAME,
        endpoint=Config.AOAI_ENDPOINT,
        api_key=Config.AOAI_KEY,
    )
    
    kernel.add_service(azure_service)
    return kernel


async def create_mcp_plugin() -> MCPStdioPlugin:
    """Create and configure the MCP plugin"""
    if not os.path.exists(Config.MCP_SERVER_PATH):
        raise FileNotFoundError(f"MCP server file not found: {Config.MCP_SERVER_PATH}")
    
    env_vars = os.environ.copy()
    env_vars.update({
        "SERVER_NAME": Config.SERVER_NAME,
        "DATABASE": Config.DATABASE
    })
    
    # Create the MCP plugin
    plugin = MCPStdioPlugin(
        name="ABANCAMCP",
        description="MCP ABANCA Plugin for Azure SQL Database",
        command=Config.MCP_COMMAND,
        args=Config.MCP_ARGS + [Config.MCP_SERVER_PATH],
        cwd=".",
        env=env_vars
    )
    
    return plugin


def create_agent(kernel: Kernel) -> ChatCompletionAgent:
    """Create the ChatCompletionAgent"""
    return ChatCompletionAgent(
        kernel=kernel,
        name=Config.AGENT_NAME,
        instructions=Config.AGENT_INSTRUCTIONS,
    )


async def main():
    """Main execution function"""
    try:
        print("Initializing ABANCA Assistant...")
        
        print("Setting up Azure OpenAI connection...")
        kernel = create_kernel()
        
        print("🔌 Creating MCP plugin...")
        mcp_plugin = await create_mcp_plugin()
        
        # Run with MCP plugin
        async with mcp_plugin as plugin:
            print("MCP plugin connected successfully!")
            
            kernel.add_plugins([plugin])
            
            print("Creating agent...")
            agent = create_agent(kernel)
            print("Agent created successfully!")
            
            print(f"Sending test message: {Config.TEST_MESSAGE}")
            response = await agent.get_response(messages=Config.TEST_MESSAGE)
            
            print("\n" + "="*50)
            print("Respuesta del agente:")
            print("="*50)
            print(response.content)
            print("="*50)
            
    except FileNotFoundError as e:
        print(f"File Error: {e}")
        print("Make sure 'server.py' exists in the current directory")
        
    except Exception as e:
        print(f"Error: {e}")
        print(f"Tipo de error: {type(e).__name__}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("Starting ABANCA MCP Assistant...")
    asyncio.run(main())