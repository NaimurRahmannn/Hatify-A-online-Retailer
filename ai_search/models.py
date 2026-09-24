from django.conf import settings
from django.db import models
from pgvector.django import VectorField

from products.models import Product


EMBEDDING_DIMENSION = settings.AI_SEARCH_EMBEDDING_DIMENSION


class ProductSearchDocument(models.Model):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="search_document",
    )
    searchable_text = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Search Doc for {self.product.product_name}"


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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        product_name = self.product_document.product.product_name
        return f"Embedding ({self.model_name}) for {product_name}"
