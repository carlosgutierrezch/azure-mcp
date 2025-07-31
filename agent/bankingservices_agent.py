import yaml
from semantic_kernel.agents import ChatCompletionAgent
from kernel.kernel import base_kernel, base_kernel_sync
from semantic_kernel.prompt_template import PromptTemplateConfig
from semantic_kernel.connectors.ai.open_ai import AzureChatPromptExecutionSettings
from semantic_kernel.kernel import KernelArguments
from semantic_kernel.connectors.ai import FunctionChoiceBehavior


class BankingServicesAgent:
    def __init__(self, config_path):
        self.config = self.load_config(config_path)
        self.prompt_template = self.load_prompt_template(self.config["prompt_template"])
        
        self.kernel = base_kernel_sync()
        self.mcp_plugins = []
        self.mcp_contexts = []

        service_id = self.config["service_id"]
        settings = self.kernel.get_prompt_execution_settings_from_service_id(service_id)
        settings.function_choice_behavior = FunctionChoiceBehavior.Auto()
        self.arguments = KernelArguments(
            bank_name=self.config["bank_name"],
            settings=settings,
            chat_history=None,
        )

        self.agent = ChatCompletionAgent(
            kernel=self.kernel,
            name=self.config["name"],
            prompt_template_config=self.prompt_template,
            arguments=self.arguments,
            plugins=[]
        )

    async def initialize_mcp_plugins(self):
        """Initialize MCP plugins asynchronously"""
        try:
            kernel, mcp_plugins = await base_kernel()
            self.kernel = kernel
            self.mcp_plugins = mcp_plugins
            
            # Update agent with new kernel
            self.agent.kernel = self.kernel
            
            # Initialize MCP plugin contexts
            for mcp_plugin in self.mcp_plugins:
                mcp_context = mcp_plugin.__aenter__()
                plugin_instance = await mcp_context
                self.mcp_contexts.append((mcp_plugin, plugin_instance))
                self.kernel.add_plugins([plugin_instance])
                
            print(f"Initialized {len(self.mcp_plugins)} MCP plugins")
            
        except Exception as e:
            print(f"Failed to initialize MCP plugins: {e}")
            # Fall back to sync kernel without MCP
            self.kernel = base_kernel_sync()
            self.agent.kernel = self.kernel

    async def cleanup_mcp_plugins(self):
        """Cleanup MCP plugin contexts"""
        for mcp_plugin, _ in self.mcp_contexts:
            try:
                await mcp_plugin.__aexit__(None, None, None)
            except Exception as e:
                print(f"Warning: Error cleaning up MCP plugin: {e}")
        self.mcp_contexts.clear()

    def get_system_message(self):
        prompt_template = self.agent.prompt_template
        system_message = prompt_template.prompt_template_config.template
        return system_message

    def load_config(self, path):
        with open(path, "r") as file:
            return yaml.safe_load(file)

    def load_prompt_template(self, path):
        with open(path, "r", encoding="utf-8") as file:
            generate_story_yaml = file.read()
        data = yaml.safe_load(generate_story_yaml)
        return PromptTemplateConfig(**data)

    async def get_response(self, messages, history, thread):
        self.agent.arguments["chat_history"] = history
        response = await self.agent.get_response(
            messages=messages, arguments=self.agent.arguments, thread=thread
        )
        return response

    def invoke_stream(self, messages, history, thread):
        self.agent.arguments["chat_history"] = history
        response = self.agent.invoke_stream(
            messages=messages, arguments=self.agent.arguments, thread=thread
        )
        return response

    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize_mcp_plugins()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.cleanup_mcp_plugins()