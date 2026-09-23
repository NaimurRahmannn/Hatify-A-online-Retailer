from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from products.models import Product
from ai_search.services import generate_product_document

@receiver(post_save, sender=Product)
def product_saved(sender, instance, created, **kwargs):
    generate_product_document(instance)

@receiver(m2m_changed, sender=Product.color_variant.through)
def product_color_changed(sender, instance, action, **kwargs):
    if action in ['post_add', 'post_remove', 'post_clear']:
        generate_product_document(instance)

@receiver(m2m_changed, sender=Product.size_variant.through)
def product_size_changed(sender, instance, action, **kwargs):
    if action in ['post_add', 'post_remove', 'post_clear']:
        generate_product_document(instance)
