"""
Semantic vector retrieval using pgvector cosine similarity.

Generates a query embedding, then compares it against stored
``ProductEmbedding`` vectors using cosine distance.  Only embeddings that
satisfy the complete usable-vector invariant are included.
"""

from django.conf import settings
from django.db.models import ExpressionWrapper, F, FloatField, Value

from pgvector.django import CosineDistance

from ai_search.embeddings import generate_embedding
from ai_search.models import EmbeddingStatus, ProductSearchDocument


def semantic_search(
    query: str,
    limit: int = 10,
) -> list[ProductSearchDocument]:
    """Return search documents ranked by cosine similarity to the query.

    Each returned document is annotated with a ``semantic_score`` attribute
    (``1 - cosine_distance``).

    Raises:
        Any exception from embedding generation is propagated so the caller
        (retrieval service) can handle graceful degradation.
    """
    config = getattr(settings, "AI_SEARCH", {})
    model_name = config.get("EMBEDDING_MODEL", "")

    query_vector = generate_embedding(query, purpose="query")

    results = (
        ProductSearchDocument.objects.filter(
            embedding__status=EmbeddingStatus.READY,
            embedding__embedding__isnull=False,
            embedding__model_name=model_name,
            embedding__content_hash=F("content_hash"),
        )
        .annotate(
            _cosine_distance=CosineDistance(
                "embedding__embedding", query_vector,
            ),
        )
        .annotate(
            semantic_score=ExpressionWrapper(
                Value(1.0, output_field=FloatField()) - F("_cosine_distance"),
                output_field=FloatField(),
            ),
        )
        .order_by("_cosine_distance", "pk")[:limit]
    )

    return list(results)
