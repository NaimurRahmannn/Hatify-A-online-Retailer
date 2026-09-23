import os
import logging

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self):
        self.openai_key = os.environ.get("OPENAI_API_KEY")
        self.gemini_key = os.environ.get("GEMINI_API_KEY")
        
        if not self.openai_key and not self.gemini_key:
            logger.warning("No API keys found for EmbeddingService. Embeddings will not be generated.")

    def generate_embedding(self, text):
        """
        Generates an embedding for the given text.
        For now, this is a placeholder interface that returns a mock vector or None.
        Future sprints will implement the actual API calls.
        """
        if self.openai_key:
            return self._generate_openai_embedding(text)
        elif self.gemini_key:
            return self._generate_gemini_embedding(text)
        
        return None, None

    def _generate_openai_embedding(self, text):
        # TODO: Implement OpenAI API call
        # Returns: (vector_list, model_name)
        return None, "text-embedding-3-small"

    def _generate_gemini_embedding(self, text):
        # TODO: Implement Gemini API call
        # Returns: (vector_list, model_name)
        return None, "models/text-embedding-004"

# Singleton instance
embedding_service = EmbeddingService()

def generate_embedding(text):
    return embedding_service.generate_embedding(text)
