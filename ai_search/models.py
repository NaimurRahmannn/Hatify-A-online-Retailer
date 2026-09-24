from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector
from django.db import models
from pgvector.django import HnswIndex, VectorField

from products.models import Product


EMBEDDING_DIMENSION = settings.AI_SEARCH_EMBEDDING_DIMENSION


class ProductSearchDocument(models.Model):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="search_document",
    )
    searchable_text = models.TextField()
    embedding_text = models.TextField(blank=True, default="")
    content_hash = models.CharField(
        max_length=64, blank=True, default="", db_index=True,
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = (
            [
                GinIndex(
                    SearchVector("searchable_text", config="simple"),
                    name="search_doc_fts_gin",
                ),
            ]
            if getattr(settings, "AI_SEARCH_ENABLE_POSTGRES_INDEXES", True)
            else []
        )

    def __str__(self) -> str:
        return f"Search Doc for {self.product.product_name}"


class EmbeddingStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    PROCESSING = "PROCESSING", "Processing"
    READY = "READY", "Ready"
    FAILED = "FAILED", "Failed"


class ProductEmbedding(models.Model):
    product_document = models.OneToOneField(
        ProductSearchDocument,
        on_delete=models.CASCADE,
        related_name="embedding",
    )
    embedding = VectorField(
        dimensions=EMBEDDING_DIMENSION,
        null=True,
        blank=True,
    )
    model_name = models.CharField(max_length=100)
    status = models.CharField(
        max_length=20,
        choices=EmbeddingStatus.choices,
        default=EmbeddingStatus.PENDING,
    )
    content_hash = models.CharField(max_length=64, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    attempt_count = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = (
            [
                HnswIndex(
                    name="embedding_hnsw_cosine",
                    fields=["embedding"],
                    m=16,
                    ef_construction=64,
                    opclasses=["vector_cosine_ops"],
                ),
            ]
            if getattr(settings, "AI_SEARCH_ENABLE_POSTGRES_INDEXES", True)
            else []
        )

    def __str__(self) -> str:
        product_name = self.product_document.product.product_name
        return f"Embedding ({self.model_name}) for {product_name}"


class SearchQueryLog(models.Model):
    """
    Log of user search queries for analytics and ranking improvements.
    """
    query = models.CharField(
        max_length=500,
        help_text="The validated search query.",
    )
    normalized_query = models.CharField(
        max_length=500,
        db_index=True,
        help_text="Canonical query used for analytics and cache identity.",
    )
    analysis = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured intent and filters extracted from the query.",
    )
    result_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of results returned.",
    )
    execution_time_ms = models.FloatField(
        default=0.0,
        help_text="End-to-end search execution time in milliseconds.",
    )
    cache_hit = models.BooleanField(
        default=False,
        help_text="Whether structured query analysis came from cache.",
    )
    timings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Per-phase retrieval timings in milliseconds.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Search Query Log"
        verbose_name_plural = "Search Query Logs"

    def __str__(self) -> str:
        return f"Query: {self.query} ({self.created_at})"
