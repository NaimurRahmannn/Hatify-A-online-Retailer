from django.db import models
from pgvector.django import VectorField
from products.models import Product

class ProductSearchDocument(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="search_document")
    searchable_text = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Search Doc for {self.product.product_name}"

class ProductEmbedding(models.Model):
    product_document = models.ForeignKey(ProductSearchDocument, on_delete=models.CASCADE, related_name="embeddings")
    embedding = VectorField(null=True, blank=True)
    model_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Embedding ({self.model_name}) for {self.product_document.product.product_name}"
