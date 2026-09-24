import os
from abc import ABC, abstractmethod
from google import genai
from django.conf import settings

from ai_assistant.prompts import SYSTEM_PROMPT


class LLMProvider(ABC):
    @abstractmethod
    def generate_response(self, query: str, context: str, conversation_history: list) -> str:
        """Generate response based on query, context, and conversation history."""
        pass


class GeminiLLMProvider(LLMProvider):
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        self.model_name = getattr(settings, "AI_SEARCH", {}).get(
            "CHAT_MODEL", "gemini-3.6-flash"
        )
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
        self.client = genai.Client(api_key=self.api_key)

    def generate_response(self, query: str, context: str, conversation_history: list) -> str:
        # Prepare system instruction and context
        full_system_instruction = f"{SYSTEM_PROMPT}\n\nContext (Retrieved Products):\n{context}"
        
        # Build contents
        contents = []
        for msg in conversation_history:
            # We map our RoleChoices to Gemini roles
            role = "user" if msg.role == "USER" else "model"
            contents.append(
                {"role": role, "parts": [{"text": msg.content}]}
            )
            
        # Add the current query
        contents.append({"role": "user", "parts": [{"text": query}]})

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=genai.types.GenerateContentConfig(
                system_instruction=full_system_instruction,
                temperature=0.3,
            )
        )
        return response.text


import functools

@functools.lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    provider = getattr(settings, "AI_SEARCH", {}).get("CHAT_PROVIDER", "gemini").lower()
    if provider == "gemini":
        return GeminiLLMProvider()
    else:
        raise ValueError(f"Unknown chat provider: {provider}")
