from django.contrib import admin
from django.utils.text import Truncator

from .models import (
    EmbeddingStatus,
    ProductEmbedding,
    ProductSearchDocument,
    SearchQueryLog,
)


@admin.register(ProductSearchDocument)
class ProductSearchDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "content_hash_short",
        "has_embedding",
        "created_at",
        "updated_at",
        "search_text_preview",
    )
    list_filter = ("created_at", "updated_at")
    search_fields = ("product__product_name", "searchable_text")
    readonly_fields = ("created_at", "updated_at", "content_hash")

    @admin.display(description="Search text preview")
    def search_text_preview(self, obj: ProductSearchDocument) -> str:
        return Truncator(obj.searchable_text).chars(120)

    @admin.display(description="Content hash")
    def content_hash_short(self, obj: ProductSearchDocument) -> str:
        return obj.content_hash[:12] + "…" if obj.content_hash else "—"

    @admin.display(description="Embedding", boolean=True)
    def has_embedding(self, obj: ProductSearchDocument) -> bool:
        try:
            return obj.embedding.status == EmbeddingStatus.READY
        except ProductEmbedding.DoesNotExist:
            return False


@admin.register(ProductEmbedding)
class ProductEmbeddingAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "status",
        "model_name",
        "attempt_count",
        "last_attempt_at",
        "created_at",
        "updated_at",
    )
    list_filter = ("status", "model_name", "created_at", "updated_at")
    search_fields = ("product_document__product__product_name",)
    readonly_fields = (
        "created_at",
        "updated_at",
        "content_hash",
        "error_message",
    )

    @admin.display(
        description="Product",
        ordering="product_document__product__product_name",
    )
    def product(self, obj: ProductEmbedding) -> str:
        return obj.product_document.product.product_name


@admin.register(SearchQueryLog)
class SearchQueryLogAdmin(admin.ModelAdmin):
    list_display = (
        "query_preview",
        "result_count",
        "cache_hit",
        "execution_time_ms",
        "created_at",
    )
    list_filter = ("cache_hit", "created_at")
    search_fields = ("query", "normalized_query")
    readonly_fields = (
        "query",
        "normalized_query",
        "analysis",
        "result_count",
        "execution_time_ms",
        "cache_hit",
        "timings",
        "created_at",
    )

    @admin.display(description="Query")
    def query_preview(self, obj: SearchQueryLog) -> str:
        return Truncator(obj.query).chars(100)
