"""
Utility script to manage conversations in the database
"""
import typer
from src.database_manager import DatabaseManager
from tabulate import tabulate

app = typer.Typer()
db = DatabaseManager(db_path="database/db_messages.db")


@app.command()
def list_conversations(limit: int = 10):
    """List recent conversations"""
    conversations = db.list_conversations(limit=limit)
    
    if not conversations:
        print("No conversations found.")
        return
    
    table_data = []
    for conv in conversations:
        stats = db.get_conversation_stats(conv['conversation_id'])
        table_data.append([
            conv['conversation_id'][:8] + "...",
            conv['title'],
            stats['total_messages'],
            conv['updated_at']
        ])
    
    print("\n=== Recent Conversations ===")
    print(tabulate(table_data, 
                   headers=['ID (short)', 'Title', 'Messages', 'Last Updated'],
                   tablefmt='grid'))
    print("\nUse full ID to resume: python main.py --conversation-id <FULL_ID>")


@app.command()
def show_conversation(conversation_id: str, limit: int = None):
    """Show messages from a specific conversation"""
    messages = db.get_messages(conversation_id, limit=limit)
    
    if not messages:
        print(f"No messages found for conversation: {conversation_id}")
        return
    
    print(f"\n=== Conversation: {conversation_id} ===\n")
    
    for msg in messages:
        role = msg['role'].upper()
        content = msg['content'][:200] + "..." if len(msg['content']) > 200 else msg['content']
        timestamp = msg['timestamp']
        
        print(f"[{timestamp}] {role}:")
        print(f"{content}\n")
        print("-" * 80 + "\n")


@app.command()
def delete_conversation(conversation_id: str, confirm: bool = typer.Option(False, "--confirm")):
    """Delete a conversation"""
    if not confirm:
        print(f"Are you sure you want to delete conversation {conversation_id}?")
        print("Use --confirm flag to proceed")
        return
    
    db.delete_conversation(conversation_id)
    print(f"Conversation {conversation_id} deleted successfully.")


@app.command()
def update_title(conversation_id: str, title: str):
    """Update conversation title"""
    db.update_conversation_title(conversation_id, title)
    print(f"Title updated to: {title}")


@app.command()
def stats(conversation_id: str):
    """Show statistics for a conversation"""
    stats = db.get_conversation_stats(conversation_id)
    
    print(f"\n=== Statistics for {conversation_id} ===")
    print(f"Total messages: {stats['total_messages']}")
    print(f"\nBreakdown by role:")
    for role, count in stats['role_counts'].items():
        print(f"  {role}: {count}")
    print()


@app.command()
def export_conversation(conversation_id: str, output_file: str = None):
    """Export conversation to text file"""
    messages = db.get_messages(conversation_id)
    
    if not messages:
        print(f"No messages found for conversation: {conversation_id}")
        return
    
    if not output_file:
        output_file = f"conversation_{conversation_id[:8]}.txt"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"Conversation ID: {conversation_id}\n")
        f.write("=" * 80 + "\n\n")
        
        for msg in messages:
            f.write(f"[{msg['timestamp']}] {msg['role'].upper()}:\n")
            f.write(f"{msg['content']}\n")
            f.write("-" * 80 + "\n\n")
    
    print(f"Conversation exported to: {output_file}")


@app.command()
def init_db():
    """Initialize database tables"""
    db.init_database()
    print("Database initialized successfully.")


if __name__ == "__main__":
    app()
