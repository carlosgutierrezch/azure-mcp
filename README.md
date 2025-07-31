# Banking Services AI Agent 🤖

A developer-oriented template for building AI agents specialized in banking services using [Microsoft Semantic Kernel](https://github.com/microsoft/semantic-kernel). This project demonstrates how to structure, configure, and extend an agent that interacts with users, leveraging prompt engineering and Azure OpenAI services.

## Features 📄

- **Conversational AI Agent**: Handles user input in a loop, maintaining chat history.
- **Banking Domain Specialization**: Responds only to banking-related queries, enforcing domain boundaries via prompt engineering.
- **Configurable Kernel & Agent**: Easily swap models, endpoints, and prompt templates via YAML configuration.
- **Extensible Plugin System**: Supports plugins (see `config/agent_config.yaml`).
- **Environment-based Secrets**: Uses `.env` for sensitive configuration (API keys, endpoints).
- **Prompt Engineering**: YAML-based prompt templates for clear, maintainable instructions.

## Goals 🎯

- Provide a robust starting point for building domain-specific AI agents.
- Demonstrate best practices for configuration, extensibility, and prompt management.
- Enable rapid prototyping and deployment of conversational agents using Semantic Kernel.

## Technologies Used 👨🏻‍💻

- **Python 3.12+**
- [Microsoft Semantic Kernel](https://github.com/microsoft/semantic-kernel) (`semantic-kernel`)
- [PyYAML](https://pyyaml.org/)
- **Azure OpenAI** (for chat and embeddings)
- **VS Code** (recommended, with launch/debug config)
- **Docker** (for deployment, see `Dockerfile`)

## Repository Structure 📁

```
.
├── .env                   # Environment variables (not committed)
├── .gitignore
├── main.py                # Entry point: CLI chat loop
├── requirements.txt
├── agent/
│   ├── __init__.py
│   ├── bankingservices_agent.py  # Main agent class
│   ├── kernel.py                # Kernel setup and service registration
│   └── __pycache__/
├── config/
│   ├── agent_config.yaml        # Agent config (name, prompt, plugins)
│   └── kernel_config.yaml       # Kernel config (services, models)
├── prompts/
│   └── bankingservices_prompt.yaml  # Prompt template for the agent
└── .vscode/
    └── launch.json              # VS Code debug configuration
```

## Main Components ✏️

- [`main.py`](main.py): CLI loop for user interaction. Instantiates the agent and manages chat history.
- [`agent/bankingservices_agent.py`](agent/bankingservices_agent.py): Defines `BankingServicesAgent`, loads config, prompt, and wraps the Semantic Kernel agent.
- [`agent/kernel.py`](agent/kernel.py): Loads kernel configuration, registers Azure OpenAI services, and manages environment variables.
- [`config/agent_config.yaml`](config/agent_config.yaml): Agent-level settings (name, prompt template, plugins).
- [`config/kernel_config.yaml`](config/kernel_config.yaml): Kernel-level settings (enabled services, model names).
- [`prompts/bankingservices_prompt.yaml`](prompts/bankingservices_prompt.yaml): YAML prompt template enforcing banking-only responses.

## Patterns & Practices 📄

- **Configuration-Driven**: All critical settings are in YAML or `.env` for easy modification.
- **Prompt Engineering**: Prompts are versioned and maintained as YAML files.
- **Separation of Concerns**: Kernel setup, agent logic, and prompt management are modularized.
- **Extensibility**: Plugins can be enabled/disabled via config.
- **Environment Isolation**: Sensitive data is kept out of source control via `.env` and `.gitignore`.

## Getting Started 👨🏻‍💻

### 1. Install Dependencies

```sh
pip install -r requirements.txt
```

### 2. Set Up Environment

Create a `.env` file with your Azure OpenAI credentials:

```
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_gpt-4o_DEPLOYMENT_NAME=...
AZURE_OPENAI_text-embedding-ada-002_DEPLOYMENT_NAME=...
```

### 3. Run the Agent

```sh
python main.py
```

### 4. Debugging

Use the provided VS Code launch configuration for debugging.

## Deployment ⚙️

A sample `Dockerfile` is provided for containerized deployment (see project root).

```sh
.\scripts\build_docker_image.ps1 -imageName my-agent -imageTag v1.0
.\scripts\run_docker_container.ps1 -imageName my-agent -imageTag v1.0 -envFile .env
```

## Extending the Agent 🤖

- **Add new plugins**: Update `config/agent_config.yaml`.
- **Change prompt behavior**: Edit or add YAML files in `prompts/`.
- **Switch models/services**: Edit `config/kernel_config.yaml` and update `.env` as needed.

## References 💻

- [Microsoft Semantic Kernel Documentation](https://learn.microsoft.com/en-us/semantic-kernel/)
- [Azure OpenAI Service](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/overview)