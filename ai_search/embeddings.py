"""
Provider-neutral embedding generation for AI search.

Defines an ``EmbeddingProvider`` protocol, the concrete
``GeminiEmbeddingProvider``, and a factory driven by Django settings.

Provider classes never write database models.  Retrievers never manage
provider state.  Tests mock the provider/network boundary.
"""

import logging
import os
from typing import Protocol, runtime_checkable

from django.conf import settings


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class EmbeddingConfigError(Exception):
    """Raised when embedding configuration is invalid or incomplete."""


class EmbeddingProviderError(Exception):
    """Raised when a provider fails to generate an embedding."""


class EmbeddingDimensionError(EmbeddingProviderError):
    """Raised when an embedding vector has an unexpected dimension."""


# ---------------------------------------------------------------------------
# Provider protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol that every embedding provider must satisfy."""

    def generate(self, text: str, purpose: str = "document") -> list[float]:
        """Generate an embedding vector for *text*.

        Args:
            text: The content to embed.
            purpose: Either ``"document"`` (for indexing) or ``"query"``
                     (for retrieval).

        Returns:
            A list of floats whose length matches the configured dimension.

        Raises:
            EmbeddingProviderError: On provider / network failure.
            EmbeddingDimensionError: On unexpected vector length.
        """
        ...


# ---------------------------------------------------------------------------
# Gemini provider
# ---------------------------------------------------------------------------


class GeminiEmbeddingProvider:
    """Embedding provider using Google Gemini via the ``google-genai`` SDK.

    Gemini Embedding 2 does not use the older ``task_type`` parameter.
    Instead, stable retrieval instructions are prepended to the input text
    so the model produces vectors tuned for document or query retrieval.
    """

    _DOCUMENT_PREFIX = "Represent this product for retrieval: "
    _QUERY_PREFIX = (
        "Represent this search query for retrieving relevant products: "
    )

    def __init__(self, api_key: str, model: str, dimension: int) -> None:
        if not api_key:
            raise EmbeddingConfigError("GEMINI_API_KEY is not set")
        if not model:
            raise EmbeddingConfigError("Embedding model is not configured")

        self._model = model
        self._dimension = dimension

        # Lazy import avoids import-time failures when the SDK is absent.
        from google import genai

        self._client = genai.Client(api_key=api_key)

    def generate(self, text: str, purpose: str = "document") -> list[float]:
        """Generate a Gemini embedding with retrieval instructions."""
        if purpose == "query":
            prefixed = f"{self._QUERY_PREFIX}{text}"
        else:
            prefixed = f"{self._DOCUMENT_PREFIX}{text}"

        try:
            result = self._client.models.embed_content(
                model=self._model,
                contents=prefixed,
                config={"output_dimensionality": self._dimension},
            )
        except Exception as exc:
            raise EmbeddingProviderError(
                f"Gemini embedding generation failed for model {self._model}"
            ) from exc

        if not result.embeddings or not result.embeddings[0].values:
            raise EmbeddingProviderError(
                "Gemini returned an empty embedding response"
            )

        vector = list(result.embeddings[0].values)

        if len(vector) != self._dimension:
            raise EmbeddingDimensionError(
                f"Expected {self._dimension} dimensions, got {len(vector)}"
            )

        if not all(isinstance(v, (int, float)) for v in vector):
            raise EmbeddingProviderError(
                "Gemini returned non-numeric values in embedding"
            )

        return vector


# ---------------------------------------------------------------------------
# Provider registry and factory
# ---------------------------------------------------------------------------

_PROVIDERS: dict[str, type] = {
    "gemini": GeminiEmbeddingProvider,
}


def get_provider(provider_name: str | None = None) -> EmbeddingProvider:
    """Create an embedding provider from the ``AI_SEARCH`` configuration.

    Validates configuration before any network request.
    """
    config = getattr(settings, "AI_SEARCH", {})
    name = (provider_name or config.get("EMBEDDING_PROVIDER", "")).lower()

    if not name:
        raise EmbeddingConfigError(
            "AI_SEARCH['EMBEDDING_PROVIDER'] is not configured"
        )

    provider_cls = _PROVIDERS.get(name)
    if provider_cls is None:
        raise EmbeddingConfigError(
            f"Unknown embedding provider: {name!r}. "
            f"Available: {', '.join(sorted(_PROVIDERS))}"
        )

    model = config.get("EMBEDDING_MODEL", "")
    dimension = config.get("EMBEDDING_DIMENSION", 768)

    if name == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY", "")
        return provider_cls(api_key=api_key, model=model, dimension=dimension)

    raise EmbeddingConfigError(
        f"Provider {name!r} is registered but not fully configured"
    )


def generate_embedding(text: str, purpose: str = "document") -> list[float]:
    """Convenience function: generate an embedding with the configured provider."""
    provider = get_provider()
    return provider.generate(text, purpose=purpose)
