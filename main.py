import asyncio
import typer
from semantic_kernel.agents import ChatHistoryAgentThread
from agent.agent import AgentSK
from semantic_kernel.contents import ChatHistory
from semantic_kernel.contents.streaming_chat_message_content import (
    StreamingChatMessageContent,
)
from semantic_kernel.contents.utils.author_role import AuthorRole
from dotenv import load_dotenv

load_dotenv(".env")

app = typer.Typer()


@app.command()
def run():
    async def _go():
        print("Inicializando agente")
        
        # Use the agent as an async context manager to handle MCP plugins
        async with AgentSK("config/agent_config.yaml") as agent:
            print("Agente inicializado de manera exitosa")
            
            history = ChatHistory()
            history.add_system_message(agent.get_system_message())

            thread: ChatHistoryAgentThread = None
            is_complete: bool = False

            print("\n" + "="*50)
            print("Asistente bancario listo")
            print("- Escribe 'exit' para salir")
            print("="*50 + "\n")

            while not is_complete:
                user_input = input("Como puedo ayudarte?:> ")
                if not user_input:
                    continue

                if user_input.lower() == "exit":
                    is_complete = True
                    break

                history.add_user_message(user_input)

                try:
                    print(f"Asistente:> ", end="", flush=True)
                    
                    response_chunks = []
                    async for response in agent.invoke_stream(
                        messages=user_input,
                        history=history,
                        thread=thread,
                    ):
                        if (
                            isinstance(response.content, StreamingChatMessageContent)
                            and response.role == AuthorRole.ASSISTANT
                        ):
                            print(str(response.content), end="", flush=True)
                            response_chunks.append(response)

                        thread = response.thread

                    print()  

                    full_response = "".join(str(chunk.content) for chunk in response_chunks if hasattr(chunk, 'content'))
                    if full_response:
                        history.add_assistant_message(full_response)
                        
                except Exception as e:
                    print(f"\nError: {e}")
                    print("Por favor intenta nuevamente o escribe 'exit' para salir.")

            print("\nChao!")

    asyncio.run(_go())


if __name__ == "__main__":
    app()