from django.contrib import admin
from .models import ProductSearchDocument, ProductEmbedding

@admin.register(ProductSearchDocument)
class ProductSearchDocumentAdmin(admin.ModelAdmin):
    list_display = ('product', 'created_at', 'updated_at')
    search_fields = ('product__product_name', 'searchable_text')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ProductEmbedding)
class ProductEmbeddingAdmin(admin.ModelAdmin):
    list_display = ('product_document', 'model_name', 'created_at')
    list_filter = ('model_name',)
    search_fields = ('product_document__product__product_name',)
    readonly_fields = ('created_at',)
