import os
import yaml
import importlib

from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai.services.azure_chat_completion import (
    AzureChatCompletion,
)
from semantic_kernel.connectors.ai.open_ai.services.azure_text_embedding import (
    AzureTextEmbedding,
)

from semantic_kernel.connectors.ai import FunctionChoiceBehavior
from dotenv import load_dotenv

from plugins.emoji_enhancer_plugin import EmojiEnhancerPlugin
from semantic_kernel.connectors.mcp import MCPStdioPlugin

load_dotenv()

aoai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
aoai_key = os.getenv("AZURE_OPENAI_API_KEY")

PKG_ROOT = __name__.split(".")[0]


def _load_config(path):
    with open(path, "r") as file:
        return yaml.safe_load(file)


def _add_chat_service(k: Kernel, service_id: str, deployment: str):
    k.add_service(
        AzureChatCompletion(
            service_id=service_id,
            deployment_name=deployment,
            endpoint=aoai_endpoint,
            api_key=aoai_key,
        )
    )


def _add_embeddings_service(k: Kernel, service_id: str, deployment: str):
    k.add_service(
        AzureTextEmbedding(
            service_id=service_id,
            deployment_name=deployment,
            endpoint=aoai_endpoint,
            api_key=aoai_key,
        )
    )


def _create_plugin(plugin_spec):
    if isinstance(plugin_spec, str):
        name, args, kwargs, alias = plugin_spec, [], {}, None
    else:
        name = plugin_spec["name"]
        class_name = plugin_spec["class_name"]
        args = plugin_spec.get("args", [])
        kwargs = plugin_spec.get("kwargs", {})
        alias = plugin_spec.get("alias")  # may be None

    for dotted in (f"plugins.{name}", class_name):
        try:
            mod = importlib.import_module(dotted)
            cls = getattr(mod, class_name)
            break
        except (ModuleNotFoundError, AttributeError):
            continue
    else:
        raise ImportError(f"Could not find plugin class {name}")

    instance = cls(*args, **kwargs)
    return instance, alias or cls.__name__  # alias defaults to class name


async def _create_mcp_plugin(plugin_spec):
    """Create an MCP plugin based on specification"""
    name = plugin_spec["name"]
    description = plugin_spec.get("description", f"MCP Plugin: {name}")
    command = plugin_spec["command"]
    args = plugin_spec["args"]
    server_path = plugin_spec["server_path"]
    cwd = plugin_spec.get("cwd", ".")
    
    env_vars = os.environ.copy()
    if "env_vars" in plugin_spec:
        env_vars.update(plugin_spec["env_vars"])
    
    if not os.path.exists(server_path):
        raise FileNotFoundError(f"MCP server file not found: {server_path}")
    
    # Create the MCP plugin
    plugin = MCPStdioPlugin(
        name=name,
        description=description,
        command=command,
        args=args + [server_path],
        cwd=cwd,
        env=env_vars
    )
    
    return plugin


async def base_kernel() -> Kernel:
    k = Kernel()
    c = _load_config("./config/kernel_config.yaml")

    # Add AI services
    for service_spec in c["services"]:
        if service_spec["type"] == "completion" and service_spec["enable"] is True:
            _add_chat_service(
                k,
                service_spec["name"],
                os.getenv(
                    f"AZURE_OPENAI_{service_spec["name"]}_DEPLOYMENT_NAME",
                    service_spec["name"],
                ),
            )
        if service_spec["type"] == "embeddings" and service_spec["enable"] is True:
            _add_embeddings_service(
                k,
                service_spec["name"],
                os.getenv(
                    f"AZURE_OPENAI_{service_spec["name"]}_DEPLOYMENT_NAME",
                    service_spec["name"],
                ),
            )

    # Add regular plugins
    for plugin_spec in c["plugins"]:
        if plugin_spec["enable"] is True and plugin_spec["type"] != "mcp":
            plugin, alias = _create_plugin(plugin_spec)
            k.add_plugin(plugin=plugin, plugin_name=alias)

    # Handle MCP plugins separately - they need to be initialized and managed differently
    mcp_plugins = []
    for plugin_spec in c["plugins"]:
        if plugin_spec["enable"] is True and plugin_spec["type"] == "mcp":
            mcp_plugin = await _create_mcp_plugin(plugin_spec)
            mcp_plugins.append(mcp_plugin)

    return k, mcp_plugins


# Synchronous version for backward compatibility
def base_kernel_sync() -> Kernel:
    k = Kernel()
    c = _load_config("./config/kernel_config.yaml")

    # Add AI services
    for service_spec in c["services"]:
        if service_spec["type"] == "completion" and service_spec["enable"] is True:
            _add_chat_service(
                k,
                service_spec["name"],
                os.getenv(
                    f"AZURE_OPENAI_{service_spec["name"]}_DEPLOYMENT_NAME",
                    service_spec["name"],
                ),
            )
        if service_spec["type"] == "embeddings" and service_spec["enable"] is True:
            _add_embeddings_service(
                k,
                service_spec["name"],
                os.getenv(
                    f"AZURE_OPENAI_{service_spec["name"]}_DEPLOYMENT_NAME",
                    service_spec["name"],
                ),
            )

    # Add only non-MCP plugins
    for plugin_spec in c["plugins"]:
        if plugin_spec["enable"] is True and plugin_spec["type"] != "mcp":
            plugin, alias = _create_plugin(plugin_spec)
            k.add_plugin(plugin=plugin, plugin_name=alias)

    return k