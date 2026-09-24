from django.contrib import admin
from django.utils.text import Truncator

from .models import ProductEmbedding, ProductSearchDocument


@admin.register(ProductSearchDocument)
class ProductSearchDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "created_at",
        "updated_at",
        "search_text_preview",
    )
    list_filter = ("created_at", "updated_at")
    search_fields = ("product__product_name", "searchable_text")
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Search text preview")
    def search_text_preview(self, obj: ProductSearchDocument) -> str:
        return Truncator(obj.searchable_text).chars(120)


@admin.register(ProductEmbedding)
class ProductEmbeddingAdmin(admin.ModelAdmin):
    list_display = ("product", "model_name", "embedding_status", "created_at")
    list_filter = ("model_name", "created_at")
    search_fields = ("product_document__product__product_name",)
    readonly_fields = ("created_at", "updated_at")

    @admin.display(
        description="Product",
        ordering="product_document__product__product_name",
    )
    def product(self, obj: ProductEmbedding) -> str:
        return obj.product_document.product.product_name

    @admin.display(description="Embedding status", boolean=True)
    def embedding_status(self, obj: ProductEmbedding) -> bool:
        return obj.embedding is not None
