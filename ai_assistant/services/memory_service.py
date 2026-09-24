from ai_assistant.models import Conversation

class ConversationMemoryService:
    """Manages conversational memory for the LLM."""
    
    def __init__(self, max_messages: int = 5):
        self.max_messages = max_messages

    def get_formatted_history(self, conversation: Conversation) -> list:
        """
        Fetches the recent history and formats it for the LLM.
        Strips unnecessary metadata to save tokens.
        """
        recent_messages = list(conversation.messages.order_by("-created_at")[:self.max_messages])
        recent_messages.reverse() # chronological order
        return recent_messages

    def build_context_aware_query(self, query: str, history: list) -> str:
        """
        Combines recent user preferences with the current query to ensure 
        the retrieval engine has enough context (e.g., 'show cheaper ones' -> 'black hoodie show cheaper ones').
        """
        recent_user_content = []
        # Gather the last few user intents
        for msg in history[-3:]:
            if msg.role == "USER":
                recent_user_content.append(msg.content.strip())
                
        if not recent_user_content:
            return query
            
        context_string = " ".join(recent_user_content)
        # Prevent repeating the exact query if it's already in the context string
        if query not in context_string:
            return f"{context_string} {query}"
            
        return context_string
