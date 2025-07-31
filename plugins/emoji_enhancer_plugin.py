from typing import Dict
from semantic_kernel.functions.kernel_function_decorator import kernel_function

class EmojiEnhancerPlugin():
    def __init__(self):
        # Define a simple emoji mapping
        self.emoji_map: Dict[str, str] = {            
            "bank": "🏦",
            "money": "💰",
            "cash": "💵",
            "credit": "💳",
            "debit": "🏧",
            "loan": "📄",
            "interest": "📈",
            "investment": "📊",
            "savings": "💸",
            "account": "🧾",
            "payment": "💳",
            "transfer": "🔁",
            "deposit": "➕",
            "withdrawal": "➖",
            "balance": "⚖️",
            "mortgage": "🏠",
            "insurance": "🛡️",
            "budget": "📝",
            "tax": "🧾",
            "profit": "📈",
            "loss": "📉"
        }

    @kernel_function(name="add_emojis", description="Enhance text with relevant emojis")
    def add_emojis(self, text: str) -> str:
        """Add emojis to the input text based on keyword matching."""
        words = text.split()
        enhanced_words = []

        for word in words:
            clean_word = word.lower().strip(".,!?")
            emoji = self.emoji_map.get(clean_word, "")
            enhanced_words.append(word + (" " + emoji if emoji else ""))

        return " ".join(enhanced_words)
