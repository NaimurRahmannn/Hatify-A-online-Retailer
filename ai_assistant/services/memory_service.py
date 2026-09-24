"""Conversation memory service.

Provides structured memory context for the RAG pipeline with an
extensible interface ready for future summarization and preference
extraction (Sprint 5+).
"""

from ai_assistant.models import Conversation


class ConversationMemoryService:
    """Manages conversational memory for the LLM."""

    def __init__(self, max_messages: int = 5):
        self.max_messages = max_messages

    # ------------------------------------------------------------------
    # Core accessors
    # ------------------------------------------------------------------

    def get_formatted_history(self, conversation: Conversation) -> list:
        """Return the most recent messages in chronological order."""
        recent = list(
            conversation.messages.order_by("-created_at")[: self.max_messages]
        )
        recent.reverse()
        return recent

    def get_memory_context(self, conversation: Conversation) -> dict:
        """Return structured memory context for the pipeline.

        Returns:
            {
                "recent_messages": [Message, ...],
                "user_preferences": [],   # placeholder for Sprint 5
            }
        """
        recent = self.get_formatted_history(conversation)
        return {
            "recent_messages": recent,
            "user_preferences": self._extract_user_preferences(recent),
        }

    # ------------------------------------------------------------------
    # Query augmentation
    # ------------------------------------------------------------------

    def build_context_aware_query(self, query: str, history: list) -> str:
        """Prepend recent user utterances so retrieval has conversational
        context (e.g. *"I like black"* + *"show me jackets"*).
        """
        recent_user_content = []
        for msg in history[-3:]:
            if msg.role == "USER":
                recent_user_content.append(msg.content.strip())

        if not recent_user_content:
            return query

        context_string = " ".join(recent_user_content)
        if query not in context_string:
            return f"{context_string} {query}"
        return context_string

    # ------------------------------------------------------------------
    # Placeholder hooks for Sprint 5
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_user_preferences(messages: list) -> list:
        """Placeholder: extract user preferences from conversation history.

        Will be implemented in Sprint 5 when the Recommendation Engine
        is added.  For now returns an empty list.
        """
        return []

    @staticmethod
    def summarize_conversation(conversation: Conversation) -> str:
        """Placeholder: produce a concise summary for long conversations.

        Will be implemented when token-budget management is needed for
        conversations exceeding the context window.
        """
        raise NotImplementedError(
            "Conversation summarization is planned for a future sprint."
        )
