import asyncio
import typer
import uuid
from datetime import datetime
from semantic_kernel.agents import ChatHistoryAgentThread
from src.agent import AgentSK
from src.history_manager import HistoryManager
from src.database_manager import DatabaseManager
from semantic_kernel.contents import ChatHistory
from semantic_kernel.contents.streaming_chat_message_content import (
    StreamingChatMessageContent,
)
from semantic_kernel.contents.utils.author_role import AuthorRole
from dotenv import load_dotenv

load_dotenv(".env")

app = typer.Typer()


@app.command()
def run(
    conversation_id: str = None,
    list_conversations: bool = False
):
    """
    Run the banking assistant
    
    Args:
        conversation_id: Resume a specific conversation (optional)
        list_conversations: List recent conversations
    """
    
    async def _go():
        nonlocal conversation_id
        
        # Initialize database manager
        db = DatabaseManager(db_path="database/db_messages.db")
        
        # List conversations if requested
        if list_conversations:
            conversations = db.list_conversations(limit=10)
            print("\n=== Recent Conversations ===")
            for conv in conversations:
                stats = db.get_conversation_stats(conv['conversation_id'])
                print(f"\nID: {conv['conversation_id']}")
                print(f"Title: {conv['title']}")
                print(f"Updated: {conv['updated_at']}")
                print(f"Messages: {stats['total_messages']}")
            print("\nUse: python main.py --conversation-id <ID> to resume\n")
            return
        
        print("Inicializando agente")
        
        # Initialize history manager
        history_manager = HistoryManager(
            max_messages=10,      # Keep last 10 messages in context
            max_tokens=50000,     # Approximate token limit
            summarize_at=15       # Summarize when exceeding 15 messages
        )
        
        # Generate or use existing conversation ID
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            print(f"Nueva conversación: {conversation_id}")
            db.create_conversation(conversation_id, title=f"Conversación {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        else:
            print(f"Resumiendo conversación: {conversation_id}")
            # Load existing messages
            existing_messages = db.get_messages(conversation_id)
            if existing_messages:
                print(f"Cargados {len(existing_messages)} mensajes previos")
        
        # Use the agent as an async context manager to handle MCP plugins
        async with AgentSK("config/agent_config.yaml") as agent:
            print("Agente inicializado de manera exitosa")
            
            # Initialize history
            history = ChatHistory()
            system_message = agent.get_system_message()
            history.add_system_message(system_message)
            
            # Save system message to database (only once per conversation)
            existing_messages = db.get_messages(conversation_id, limit=1)
            if not existing_messages:
                db.save_message(conversation_id, "system", system_message)
            
            # Load recent messages from database for context
            recent_db_messages = db.get_recent_messages(conversation_id, count=10)
            for msg in recent_db_messages:
                if msg['role'] != 'system':  # System already added
                    if msg['role'] == 'user':
                        history.add_user_message(msg['content'])
                    elif msg['role'] == 'assistant':
                        history.add_assistant_message(msg['content'])

            thread: ChatHistoryAgentThread = None
            is_complete: bool = False

            print("\n" + "="*50)
            print("Asistente bancario listo")
            print(f"Conversación ID: {conversation_id}")
            print("- Escribe 'exit' para salir")
            print("- Escribe 'stats' para ver estadísticas")
            print("="*50 + "\n")

            while not is_complete:
                user_input = input("Como puedo ayudarte?:> ")
                if not user_input:
                    continue

                if user_input.lower() == "exit":
                    is_complete = True
                    break
                
                if user_input.lower() == "stats":
                    stats = db.get_conversation_stats(conversation_id)
                    print(f"\n=== Estadísticas de la Conversación ===")
                    print(f"Total de mensajes: {stats['total_messages']}")
                    print(f"Desglose por rol: {stats['role_counts']}")
                    hist_stats = history_manager.get_history_size(history)
                    print(f"Mensajes en contexto actual: {hist_stats['messages']}")
                    print(f"Tokens estimados en contexto: {hist_stats['estimated_tokens']}\n")
                    continue

                # Add user message to history
                history.add_user_message(user_input)
                
                # Save user message to database
                db.save_message(conversation_id, "user", user_input)

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
                        # Add to history
                        history.add_assistant_message(full_response)
                        
                        # Save assistant response to database
                        db.save_message(conversation_id, "assistant", full_response)
                    
                    # Manage history to prevent context overflow
                    # Note: This only affects what's sent to the API, not what's stored in DB
                    history = history_manager.manage_history(history)
                    
                    # Print history stats for monitoring
                    stats = history_manager.get_history_size(history)
                    print(f"[Info] Contexto: {stats['messages']} mensajes, ~{stats['estimated_tokens']} tokens | DB: {db.get_conversation_stats(conversation_id)['total_messages']} mensajes totales")
                        
                except Exception as e:
                    print(f"\nError: {e}")
                    print("Por favor intenta nuevamente o escribe 'exit' para salir.")

            print(f"\n¡Hasta luego! Conversación guardada con ID: {conversation_id}")

    asyncio.run(_go())


if __name__ == "__main__":
    app()
