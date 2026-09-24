from django.contrib import admin

# Register your models here.
from .models import *

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['categroy_name', 'category_type', 'slug']
    list_filter = ['category_type']
    prepopulated_fields = {'slug': ('categroy_name',)}

class ProductImageAdmin(admin.StackedInline):
    model =ProductImage

class ProductAdmin(admin.ModelAdmin):
    list_display = ['product_name', 'category', 'price']
    list_filter = ['category']
    search_fields = ['product_name', 'product_description', 'embedding_description']
    fieldsets = (
        (None, {
            'fields': ('product_name', 'slug', 'category', 'price', 'product_description')
        }),
        ('AI Semantic Search (Internal / Embedding only)', {
            'fields': ('embedding_description',),
            'description': 'Internal detailed description used exclusively for AI vector embeddings and semantic search. This field is NOT displayed to customers on the storefront.'
        }),
        ('Variants', {
            'fields': ('color_variant', 'size_variant')
        }),
    )
    inlines = [ProductImageAdmin]
    filter_horizontal = ['size_variant', 'color_variant']

@admin.register(ColorVariant)
class ColorVariantAdmin(admin.ModelAdmin):
    list_display = ['color_name' , 'price']
    model = ColorVariant

@admin.register(SizeVariant)
class SizeVariantAdmin(admin.ModelAdmin):
    list_display = ['size_name' , 'price']

    model = SizeVariant


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    readonly_fields = ['product', 'product_name', 'size', 'quantity', 'price', 'line_total']
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'first_name', 'last_name', 'email', 'order_status', 'payment_method', 'payment_status', 'total', 'created_at']
    list_filter = ['order_status', 'payment_method', 'payment_status', 'created_at']
    search_fields = ['order_number', 'email', 'first_name', 'last_name', 'transaction_id', 'stripe_checkout_session_id']
    list_editable = ['order_status']
    readonly_fields = ['order_number', 'user', 'payment_status', 'payment_currency', 'payment_amount', 'exchange_rate', 'stripe_checkout_session_id', 'checkout_token', 'transaction_id']
    inlines = [OrderItemInline]

admin.site.register(Product ,ProductAdmin)

admin.site.register(ProductImage)
