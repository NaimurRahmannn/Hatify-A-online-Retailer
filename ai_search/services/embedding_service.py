"""
Embedding persistence service.

Owns the state machine for generating and storing a single product embedding.
The split-transaction design avoids holding database locks during network I/O
while the second hash check prevents a slow provider response from overwriting
newer content.
"""

import logging

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from ai_search.embeddings import (
    EmbeddingConfigError,
    EmbeddingProviderError,
    generate_embedding,
)
from ai_search.models import EmbeddingStatus, ProductEmbedding, ProductSearchDocument


logger = logging.getLogger(__name__)


def _is_usable(
    embedding: ProductEmbedding,
    document: ProductSearchDocument,
    model_name: str,
) -> bool:
    """Check the complete usable-vector invariant."""
    return (
        embedding.status == EmbeddingStatus.READY
        and embedding.embedding is not None
        and embedding.model_name == model_name
        and embedding.content_hash == document.content_hash
    )


def generate_embedding_for_document(
    document_id: int,
    *,
    force: bool = False,
) -> bool:
    """Generate and persist an embedding for one search document.

    Returns ``True`` on success, ``False`` on skip or failure.
    Never raises — failures are recorded in the embedding row.
    """
    config = getattr(settings, "AI_SEARCH", {})
    model_name = config.get("EMBEDDING_MODEL", "")

    # ------------------------------------------------------------------
    # Phase 1: Lock, create-or-get, and mark PROCESSING
    # ------------------------------------------------------------------
    try:
        with transaction.atomic():
            document = (
                ProductSearchDocument.objects.select_for_update().get(
                    pk=document_id,
                )
            )
            embedding, _created = (
                ProductEmbedding.objects.select_for_update().get_or_create(
                    product_document=document,
                    defaults={
                        "model_name": model_name,
                        "status": EmbeddingStatus.PENDING,
                    },
                )
            )

            if not force and _is_usable(embedding, document, model_name):
                return False  # Current — skip.

            embedding.status = EmbeddingStatus.PROCESSING
            embedding.attempt_count = F("attempt_count") + 1
            embedding.last_attempt_at = timezone.now()
            embedding.save(
                update_fields=[
                    "status",
                    "attempt_count",
                    "last_attempt_at",
                    "updated_at",
                ]
            )

        captured_hash = document.content_hash
    except ProductSearchDocument.DoesNotExist:
        logger.warning(
            "Search document %s no longer exists — skipping embedding",
            document_id,
        )
        return False

    # ------------------------------------------------------------------
    # Phase 2: Generate embedding *outside* any transaction
    # ------------------------------------------------------------------
    text = document.embedding_text or document.searchable_text
    if not text or not text.strip():
        logger.warning(
            "Search document %s has no embeddable text — marking FAILED",
            document_id,
        )
        with transaction.atomic():
            ProductEmbedding.objects.filter(
                product_document_id=document_id,
            ).update(
                embedding=None,
                status=EmbeddingStatus.FAILED,
                error_message="No embeddable text available",
            )
        return False

    try:
        vector = generate_embedding(text, purpose="document")
    except (EmbeddingProviderError, EmbeddingConfigError) as exc:
        safe_error = str(exc)[:500]
        logger.warning(
            "Embedding generation failed for document %s: %s",
            document_id,
            safe_error,
        )
        with transaction.atomic():
            emb = ProductEmbedding.objects.select_for_update().get(
                product_document_id=document_id,
            )
            emb.embedding = None
            emb.status = EmbeddingStatus.FAILED
            emb.error_message = safe_error
            emb.save(
                update_fields=[
                    "embedding",
                    "status",
                    "error_message",
                    "updated_at",
                ]
            )
        return False

    # ------------------------------------------------------------------
    # Phase 3: Re-lock and save — reject stale results
    # ------------------------------------------------------------------
    with transaction.atomic():
        document = ProductSearchDocument.objects.select_for_update().get(
            pk=document_id,
        )
        emb = ProductEmbedding.objects.select_for_update().get(
            product_document_id=document_id,
        )

        if captured_hash and document.content_hash != captured_hash:
            # Content changed while the provider call was running.
            logger.info(
                "Document %s content changed during embedding generation "
                "— discarding stale vector",
                document_id,
            )
            emb.status = EmbeddingStatus.PENDING
            emb.error_message = ""
            emb.save(update_fields=["status", "error_message", "updated_at"])
            return False

        emb.embedding = vector
        emb.model_name = model_name
        emb.content_hash = document.content_hash
        emb.status = EmbeddingStatus.READY
        emb.error_message = ""
        emb.save(
            update_fields=[
                "embedding",
                "model_name",
                "content_hash",
                "status",
                "error_message",
                "updated_at",
            ]
        )

    logger.info(
        "Embedding generated for document %s (model=%s)",
        document_id,
        model_name,
    )
    return True
