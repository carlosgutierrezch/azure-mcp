"""
Database Manager for conversation persistence
"""
import sqlite3
import json
import os
import threading
import time
from datetime import datetime
from typing import List, Dict, Optional
from contextlib import contextmanager
from semantic_kernel.contents import ChatHistory
from semantic_kernel.contents.chat_message_content import ChatMessageContent
from semantic_kernel.contents.utils.author_role import AuthorRole


class DatabaseManager:
    """Manages conversation storage in SQLite"""
    
    def __init__(self, db_path: str = "database/db_messages.db"):
        """
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._lock = threading.RLock()
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = None
        max_retries = 5
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                with self._lock:
                    conn = sqlite3.connect(
                        self.db_path,
                        timeout=30.0,
                        check_same_thread=False
                    )
                    # Enable WAL mode for better concurrency
                    conn.execute('PRAGMA journal_mode=WAL')
                    # Set busy timeout
                    conn.execute('PRAGMA busy_timeout=30000')
                    yield conn
                    break
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    if conn:
                        conn.close()
                    time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                    continue
                else:
                    raise
            finally:
                if conn:
                    conn.close()
    
    def init_database(self):
        """Initialize database tables if they don't exist"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create conversations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    title TEXT
                )
            """)
            
            # Create messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
                )
            """)
            
            # Create index for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversation_messages 
                ON messages(conversation_id, timestamp)
            """)
            
            conn.commit()
    
    def create_conversation(self, conversation_id: str, title: str = None) -> str:
        """Create a new conversation"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            try:
                cursor.execute(
                    "INSERT INTO conversations (conversation_id, title) VALUES (?, ?)",
                    (conversation_id, title or "New Conversation")
                )
                conn.commit()
            except sqlite3.IntegrityError:
                # Conversation already exists
                pass
        
        return conversation_id
    
    def save_message(self, 
                     conversation_id: str, 
                     role: str, 
                     content: str,
                     metadata: Dict = None):
        """Save a message to the database"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Ensure conversation exists
            self.create_conversation(conversation_id)
            
            # Save message
            cursor.execute(
                """INSERT INTO messages (conversation_id, role, content, metadata) 
                   VALUES (?, ?, ?, ?)""",
                (conversation_id, role, content, json.dumps(metadata) if metadata else None)
            )
            
            # Update conversation timestamp
            cursor.execute(
                "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE conversation_id = ?",
                (conversation_id,)
            )
            
            conn.commit()
    
    def get_messages(self, 
                     conversation_id: str, 
                     limit: Optional[int] = None,
                     offset: int = 0) -> List[Dict]:
        """
        Retrieve messages from database
        
        Args:
            conversation_id: Conversation to retrieve
            limit: Maximum number of messages to retrieve (None = all)
            offset: Number of messages to skip from the start
        
        Returns:
            List of message dictionaries
        """
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            cursor = conn.cursor()
            
            query = """
                SELECT id, conversation_id, role, content, timestamp, metadata
                FROM messages
                WHERE conversation_id = ?
                ORDER BY timestamp ASC
            """
            
            if limit:
                query += f" LIMIT {limit} OFFSET {offset}"
            
            cursor.execute(query, (conversation_id,))
            rows = cursor.fetchall()
            
            messages = []
            for row in rows:
                messages.append({
                    'id': row['id'],
                    'conversation_id': row['conversation_id'],
                    'role': row['role'],
                    'content': row['content'],
                    'timestamp': row['timestamp'],
                    'metadata': json.loads(row['metadata']) if row['metadata'] else None
                })
            
            return messages
    
    def get_recent_messages(self, 
                           conversation_id: str, 
                           count: int = 20) -> List[Dict]:
        """Get the most recent N messages"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get total message count
            cursor.execute(
                "SELECT COUNT(*) as total FROM messages WHERE conversation_id = ?",
                (conversation_id,)
            )
            total = cursor.fetchone()['total']
            
            # Calculate offset to get last N messages
            offset = max(0, total - count)
        
        return self.get_messages(conversation_id, limit=count, offset=offset)
    
    def messages_to_chat_history(self, messages: List[Dict]) -> ChatHistory:
        """Convert database messages to ChatHistory object"""
        history = ChatHistory()
        
        for msg in messages:
            role_map = {
                'system': AuthorRole.SYSTEM,
                'user': AuthorRole.USER,
                'assistant': AuthorRole.ASSISTANT
            }
            
            role = role_map.get(msg['role'], AuthorRole.USER)
            
            # Create ChatMessageContent
            message = ChatMessageContent(
                role=role,
                content=msg['content']
            )
            
            history.add_message(message)
        
        return history
    
    def get_conversation_stats(self, conversation_id: str) -> Dict:
        """Get statistics about a conversation"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT COUNT(*) as total FROM messages WHERE conversation_id = ?",
                (conversation_id,)
            )
            total_messages = cursor.fetchone()[0]
            
            cursor.execute(
                """SELECT role, COUNT(*) as count 
                   FROM messages 
                   WHERE conversation_id = ? 
                   GROUP BY role""",
                (conversation_id,)
            )
            role_counts = {row[0]: row[1] for row in cursor.fetchall()}
            
            return {
                'total_messages': total_messages,
                'role_counts': role_counts
            }
    
    def list_conversations(self, limit: int = 10) -> List[Dict]:
        """List recent conversations"""
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                """SELECT conversation_id, title, created_at, updated_at
                   FROM conversations
                   ORDER BY updated_at DESC
                   LIMIT ?""",
                (limit,)
            )
            
            conversations = []
            for row in cursor.fetchall():
                conversations.append({
                    'conversation_id': row['conversation_id'],
                    'title': row['title'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                })
            
            return conversations
    
    def delete_conversation(self, conversation_id: str):
        """Delete a conversation and all its messages"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            cursor.execute("DELETE FROM conversations WHERE conversation_id = ?", (conversation_id,))
            
            conn.commit()
    
    def update_conversation_title(self, conversation_id: str, title: str):
        """Update conversation title"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                "UPDATE conversations SET title = ? WHERE conversation_id = ?",
                (title, conversation_id)
            )
            
            conn.commit()
