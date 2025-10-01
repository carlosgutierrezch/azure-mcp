"""
History Manager for conversation context management
"""
from semantic_kernel.contents import ChatHistory
from semantic_kernel.contents.utils.author_role import AuthorRole


class HistoryManager:
    """Manages chat history to prevent context overflow"""
    
    def __init__(self, 
                 max_messages: int = 10,
                 max_tokens: int = 50000,
                 summarize_at: int = 15):
        """
        Args:
            max_messages: Maximum number of recent messages to keep
            max_tokens: Approximate token limit
            summarize_at: Trigger summarization when messages exceed this count
        """
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self.summarize_at = summarize_at
        self.summary = None
    
    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation: ~4 chars per token"""
        return len(text) // 4
    
    def get_history_size(self, history: ChatHistory) -> dict:
        """Get current history statistics"""
        total_chars = sum(len(str(msg.content)) for msg in history.messages)
        return {
            "messages": len(history.messages),
            "characters": total_chars,
            "estimated_tokens": self.estimate_tokens(str(total_chars))
        }
    
    def trim_history(self, history: ChatHistory) -> ChatHistory:
        """
        Trim history to keep system message + recent messages
        """
        if len(history.messages) <= self.max_messages + 1:
            return history
        
        # Always keep system message
        system_message = history.messages[0]
        
        # Keep most recent messages
        recent_messages = history.messages[-(self.max_messages):]
        
        new_history = ChatHistory()
        new_history.add_message(system_message)
        
        # Add summary if exists
        if self.summary:
            new_history.add_system_message(
                f"\n[Resumen de conversación anterior]: {self.summary}"
            )
        
        # Add recent messages
        for msg in recent_messages:
            new_history.add_message(msg)
        
        return new_history
    
    def should_trim(self, history: ChatHistory) -> bool:
        """Check if history should be trimmed"""
        stats = self.get_history_size(history)
        return (
            stats["messages"] > self.max_messages + 1 or
            stats["estimated_tokens"] > self.max_tokens
        )
    
    def create_summary(self, history: ChatHistory) -> str:
        """
        Create a simple summary of the conversation
        (In production, you'd use the LLM to generate this)
        """
        # Simple summary: count topics discussed
        user_messages = [
            msg for msg in history.messages 
            if msg.role == AuthorRole.USER
        ]
        
        topics = [str(msg.content)[:50] for msg in user_messages[-5:]]
        
        return f"Temas discutidos: {', '.join(topics)}"
    
    def manage_history(self, history: ChatHistory) -> ChatHistory:
        """
        Main method to manage history
        """
        if self.should_trim(history):
            # Optionally create summary before trimming
            if len(history.messages) > self.summarize_at and not self.summary:
                self.summary = self.create_summary(history)
            
            return self.trim_history(history)
        
        return history
