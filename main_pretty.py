import asyncio
import typer
import uuid
import re
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

# Rich imports for beautiful terminal output
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.prompt import Prompt
from rich.markdown import Markdown

load_dotenv(".env")

app = typer.Typer()
console = Console()


def parse_ascii_table(text: str) -> tuple:
    """
    Parse ASCII tables from text and return (tables, clean_text)
    Returns list of table data and text without tables
    """
    tables = []
    clean_text = text
    
    # Split text into lines
    lines = text.split('\n')
    
    i = 0
    table_ranges = []  # Store (start, end, table_data) tuples
    
    while i < len(lines):
        line = lines[i].strip()
        
        # Check if this line looks like a table row (has multiple |)
        if line.count('|') >= 3:  # At least | col1 | col2 |
            # Found potential table start
            table_lines = []
            start_idx = i
            
            # Collect consecutive lines that look like table rows
            while i < len(lines):
                current_line = lines[i].strip()
                
                # Check if it's a table line or empty line between table rows
                if current_line.count('|') >= 3:
                    table_lines.append(current_line)
                    i += 1
                elif current_line == '' and i + 1 < len(lines) and lines[i + 1].strip().count('|') >= 3:
                    # Empty line followed by another table line - might be continuation
                    i += 1
                else:
                    break
            
            # Process the collected table lines
            if len(table_lines) >= 1:  # At least 1 row (could be header or data)
                # Remove separator lines
                data_lines = []
                for line in table_lines:
                    # Skip lines that are just separators (-, |, and spaces)
                    if re.match(r'^[\s\-|+=]+$', line):
                        continue
                    data_lines.append(line)
                
                if len(data_lines) >= 1:
                    # Check if first line looks like a header (has text, not just numbers)
                    first_line_parts = data_lines[0].split('|')
                    first_line_cols = [col.strip() for col in first_line_parts[1:-1] if col.strip()]
                    
                    # Determine if we have a header
                    has_header = False
                    if len(data_lines) >= 2:
                        # Check if first line looks more like header than data
                        # Headers usually have words, not just numbers
                        non_numeric = sum(1 for col in first_line_cols if not col.replace('.', '').replace('-', '').isdigit())
                        if non_numeric > len(first_line_cols) / 2:
                            has_header = True
                    
                    if has_header:
                        header = first_line_cols
                        data_start = 1
                    else:
                        # No header, create generic one
                        header = [f"Col{i+1}" for i in range(len(first_line_cols))]
                        data_start = 0
                    
                    # Parse data rows
                    rows = []
                    for line in data_lines[data_start:]:
                        parts = line.split('|')
                        cols = [col.strip() for col in parts[1:-1]]
                        
                        # Pad or trim to match header length
                        while len(cols) < len(header):
                            cols.append('')
                        cols = cols[:len(header)]
                        
                        if any(col for col in cols):  # At least one non-empty cell
                            rows.append(cols)
                    
                    if rows:
                        table_data = {'header': header, 'rows': rows}
                        table_ranges.append((start_idx, i, table_data))
        else:
            i += 1
    
    # Replace tables in reverse order to maintain indices
    for start_idx, end_idx, table_data in reversed(table_ranges):
        tables.insert(0, table_data)
        table_start = '\n'.join(lines[start_idx:end_idx])
        placeholder = f"\n[TABLE_{len(table_ranges) - len(tables)}]\n"
        clean_text = clean_text.replace(table_start, placeholder, 1)
    
    return tables, clean_text


def render_rich_table(table_data: dict, title: str = None) -> Table:
    """Render a Rich table from parsed data"""
    table = Table(
        title=title,
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        border_style="blue",
        title_style="bold magenta",
        show_lines=False,
        padding=(0, 1)
    )
    
    # Add columns with better width handling
    for col in table_data['header']:
        table.add_column(col, style="white", overflow="fold", no_wrap=False)
    
    # Add rows
    for row in table_data['rows']:
        table.add_row(*row)
    
    return table


def has_markdown_formatting(text: str) -> bool:
    """Check if text has markdown formatting like **bold**, *italic*, etc."""
    # Check for common markdown patterns
    markdown_patterns = [
        r'\*\*[^\*]+\*\*',  # **bold**
        r'`[^`]+`',          # `code`
        r'^\s*[-*+]\s',      # lists
        r'^\s*\d+\.\s',      # numbered lists
        r'^#+\s',            # headers
    ]
    
    for pattern in markdown_patterns:
        if re.search(pattern, text, re.MULTILINE):
            return True
    return False


def format_response(text: str) -> None:
    """Format and print response with tables rendered beautifully"""
    # Parse tables from text
    tables, clean_text = parse_ascii_table(text)
    
    if not tables:
        # No tables found, just print normally
        if has_markdown_formatting(text):
            md = Markdown(text)
            console.print(md)
        else:
            console.print(text)
        return
    
    # Split text by table placeholders
    parts = re.split(r'\[TABLE_(\d+)\]', clean_text)
    
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
            
        # Check if this is a table reference
        if part.isdigit():
            table_idx = int(part)
            if table_idx < len(tables):
                console.print()
                rich_table = render_rich_table(tables[table_idx])
                console.print(rich_table)
                console.print()
        else:
            # Check if text has markdown formatting
            if has_markdown_formatting(part):
                # Render as markdown
                md = Markdown(part)
                console.print(md)
            else:
                # Print regular text
                console.print(part)


def print_welcome_banner(conversation_id: str, is_new: bool = True):
    """Print a beautiful welcome banner"""
    status = "Nueva Conversación" if is_new else "Conversación Resumida"
    
    banner_text = f"""[bold cyan]Asistente Bancario Inteligente[/bold cyan]

[yellow]Estado:[/yellow] [bold green]Inicializado[/bold green]
[yellow]Conversación ID:[/yellow] [dim]{conversation_id}[/dim]
[yellow]Fecha:[/yellow] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    console.print(Panel(
        banner_text,
        title=f"[bold magenta]{status}[/bold magenta]",
        border_style="bright_blue",
        box=box.DOUBLE,
        padding=(1, 2)
    ))


def print_commands_help():
    """Print available commands in a nice format"""
    commands_table = Table(
        title="Comandos Disponibles",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        border_style="blue"
    )
    
    commands_table.add_column("Comando", style="yellow", no_wrap=True)
    commands_table.add_column("Descripción", style="white")
    
    commands_table.add_row("[bold]exit[/bold]", "Salir del asistente")
    commands_table.add_row("[bold]stats[/bold]", "Ver estadísticas de la conversación")
    commands_table.add_row("[bold]help[/bold]", "Mostrar esta ayuda")
    commands_table.add_row("[bold]clear[/bold]", "Limpiar la pantalla")
    
    console.print(commands_table)
    console.print()


def print_conversation_list(conversations: list):
    """Print conversations in a beautiful table"""
    if not conversations:
        console.print("[yellow]No hay conversaciones recientes[/yellow]\n")
        return
    
    table = Table(
        title="Conversaciones Recientes",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        border_style="blue"
    )
    
    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Título", style="white")
    table.add_column("Mensajes", justify="center", style="magenta")
    table.add_column("Última Actualización", style="green")
    
    for i, conv in enumerate(conversations, 1):
        table.add_row(
            str(i),
            conv['conversation_id'][:8] + "...",
            conv['title'],
            str(conv.get('message_count', 'N/A')),
            conv['updated_at']
        )
    
    console.print(table)
    console.print("\n[dim]Usa: python main_pretty.py --conversation-id <ID> para resumir[/dim]\n")


def print_stats(db_stats: dict, history_stats: dict):
    """Print conversation statistics"""
    stats_table = Table(
        title="Estadísticas de la Conversación",
        box=box.ROUNDED,
        show_header=False,
        border_style="green"
    )
    
    stats_table.add_column("Métrica", style="cyan", no_wrap=True)
    stats_table.add_column("Valor", style="yellow")
    
    stats_table.add_row("Total de mensajes en DB", str(db_stats['total_messages']))
    stats_table.add_row("Mensajes de usuario", str(db_stats['role_counts'].get('user', 0)))
    stats_table.add_row("Mensajes del asistente", str(db_stats['role_counts'].get('assistant', 0)))
    stats_table.add_row("Mensajes en contexto actual", str(history_stats['messages']))
    stats_table.add_row("Tokens estimados en contexto", f"~{history_stats['estimated_tokens']}")
    
    console.print(stats_table)
    console.print()


@app.command()
def run(
    conversation_id: str = None,
    list_conversations: bool = False
):
    """
    Run the banking assistant with beautiful terminal interface
    
    Args:
        conversation_id: Resume a specific conversation (optional)
        list_conversations: List recent conversations
    """
    
    async def _go():
        nonlocal conversation_id
        
        # Initialize database manager
        with console.status("[bold green]Inicializando base de datos...", spinner="dots"):
            db = DatabaseManager(db_path="database/db_messages.db")
        
        # List conversations if requested
        if list_conversations:
            conversations = db.list_conversations(limit=10)
            console.print()
            print_conversation_list(conversations)
            return
        
        # Initialize components
        with console.status("[bold green]Inicializando agente...", spinner="dots"):
            # Initialize history manager
            history_manager = HistoryManager(
                max_messages=10,
                max_tokens=50000,
                summarize_at=15
            )
            
            # Generate or use existing conversation ID
            is_new_conversation = not conversation_id
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
                db.create_conversation(
                    conversation_id, 
                    title=f"Conversación {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                )
        
        console.print()
        
        # Use the agent as an async context manager
        async with AgentSK("config/agent_config.yaml") as agent:
            # Print welcome banner
            print_welcome_banner(conversation_id, is_new_conversation)
            
            # Show commands
            print_commands_help()
            
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
            if recent_db_messages:
                console.print(f"[dim]Cargados {len(recent_db_messages)} mensajes previos[/dim]\n")
                for msg in recent_db_messages:
                    if msg['role'] != 'system':
                        if msg['role'] == 'user':
                            history.add_user_message(msg['content'])
                        elif msg['role'] == 'assistant':
                            history.add_assistant_message(msg['content'])

            thread: ChatHistoryAgentThread = None
            is_complete: bool = False

            while not is_complete:
                # Prompt for user input with rich styling
                try:
                    user_input = Prompt.ask("\n[bold blue]Usuario[/bold blue]")
                except (KeyboardInterrupt, EOFError):
                    is_complete = True
                    break
                
                if not user_input:
                    continue

                # Handle commands
                if user_input.lower() == "exit":
                    is_complete = True
                    break
                
                if user_input.lower() == "help":
                    print_commands_help()
                    continue
                
                if user_input.lower() == "clear":
                    console.clear()
                    print_welcome_banner(conversation_id, False)
                    continue
                
                if user_input.lower() == "stats":
                    db_stats = db.get_conversation_stats(conversation_id)
                    hist_stats = history_manager.get_history_size(history)
                    print_stats(db_stats, hist_stats)
                    continue

                # Add user message to history
                history.add_user_message(user_input)
                
                # Save user message to database
                db.save_message(conversation_id, "user", user_input)

                try:
                    response_chunks = []
                    
                    # Show a spinner while waiting for response
                    with console.status("[bold green]Pensando...", spinner="dots"):
                        # Collect all response chunks WITHOUT displaying them
                        async for response in agent.invoke_stream(
                            messages=user_input,
                            history=history,
                            thread=thread,
                        ):
                            if (
                                isinstance(response.content, StreamingChatMessageContent)
                                and response.role == AuthorRole.ASSISTANT
                            ):
                                response_chunks.append(response)

                            thread = response.thread

                    # Build full response
                    full_response = "".join(
                        str(chunk.content) 
                        for chunk in response_chunks 
                        if hasattr(chunk, 'content')
                    )
                    
                    if full_response:
                        # Print assistant prefix
                        console.print("\n[bold green]Asistente[/bold green]:")
                        
                        # Always try to format the response
                        format_response(full_response)
                        
                        # Add to history
                        history.add_assistant_message(full_response)
                        
                        # Save assistant response to database
                        db.save_message(conversation_id, "assistant", full_response)
                    
                    # Manage history
                    history = history_manager.manage_history(history)
                    
                    # Print compact stats
                    stats = history_manager.get_history_size(history)
                    db_stats = db.get_conversation_stats(conversation_id)
                    console.print(
                        f"\n[dim]Contexto: {stats['messages']} msgs, "
                        f"~{stats['estimated_tokens']} tokens | "
                        f"DB: {db_stats['total_messages']} msgs totales[/dim]"
                    )
                        
                except Exception as e:
                    console.print(f"\n[bold red]Error:[/bold red] {e}")
                    console.print("[yellow]Por favor intenta nuevamente o escribe 'exit' para salir.[/yellow]\n")

            # Goodbye message
            console.print()
            console.print(Panel(
                f"[bold green]Conversación guardada exitosamente[/bold green]\n\n"
                f"[yellow]ID:[/yellow] [dim]{conversation_id}[/dim]\n"
                f"[cyan]Hasta luego[/cyan]",
                title="Sesión Finalizada",
                border_style="green",
                box=box.ROUNDED
            ))

    asyncio.run(_go())


if __name__ == "__main__":
    app()
