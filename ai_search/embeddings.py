import logging
import os
from typing import TypeAlias

from django.conf import settings


logger = logging.getLogger(__name__)


EmbeddingResult: TypeAlias = tuple[list[float] | None, str | None]


class EmbeddingService:
    def __init__(self) -> None:
        self.openai_key = os.environ.get("OPENAI_API_KEY")
        self.gemini_key = os.environ.get("GEMINI_API_KEY")
        self.provider = os.environ.get("AI_SEARCH_EMBEDDING_PROVIDER", "").lower()
        self.openai_model = os.environ.get(
            "OPENAI_EMBEDDING_MODEL",
            "text-embedding-3-small",
        )
        self.gemini_model = os.environ.get(
            "GEMINI_EMBEDDING_MODEL",
            "models/text-embedding-004",
        )

        if not self.provider:
            if self.openai_key:
                self.provider = "openai"
            elif self.gemini_key:
                self.provider = "gemini"

    def generate_embedding(self, text: str) -> EmbeddingResult:
        """
        Return a provider embedding when available, otherwise a retryable empty result.

        Provider calls remain placeholders in Sprint 1. Errors are deliberately
        contained so document and product persistence are unaffected.
        """
        model_name = self._configured_model_name()
        if not text or not text.strip():
            logger.warning("Embedding generation skipped because text was empty")
            return None, model_name

        try:
            if self.provider == "openai" and self.openai_key:
                result = self._generate_openai_embedding(text)
            elif self.provider == "gemini" and self.gemini_key:
                result = self._generate_gemini_embedding(text)
            else:
                logger.warning(
                    "Embedding generation skipped because provider credentials "
                    "are not configured"
                )
                return None, model_name

            vector, returned_model = result
            expected_dimension = settings.AI_SEARCH_EMBEDDING_DIMENSION
            if vector is not None and len(vector) != expected_dimension:
                raise ValueError(
                    "Embedding dimension mismatch: "
                    f"expected {expected_dimension}, "
                    f"received {len(vector)}"
                )
            return vector, returned_model or model_name
        except Exception:
            logger.exception(
                "Embedding generation failed for provider %s; "
                "the embedding remains retryable",
                self.provider or "unconfigured",
            )
            return None, model_name

    def _configured_model_name(self) -> str | None:
        if self.provider == "openai":
            return self.openai_model
        if self.provider == "gemini":
            return self.gemini_model
        return None

    def _generate_openai_embedding(self, text: str) -> EmbeddingResult:
        # Provider integration is intentionally deferred until Sprint 2.
        return None, self.openai_model

    def _generate_gemini_embedding(self, text: str) -> EmbeddingResult:
        # Provider integration is intentionally deferred until Sprint 2.
        return None, self.gemini_model


embedding_service = EmbeddingService()


def generate_embedding(text: str) -> EmbeddingResult:
    return embedding_service.generate_embedding(text)
