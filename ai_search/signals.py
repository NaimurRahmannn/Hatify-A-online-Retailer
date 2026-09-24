import logging

from django.db import transaction
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from ai_search.services import (
    ProductDocumentGenerationError,
    generate_product_document,
)
from products.models import Product


logger = logging.getLogger(__name__)


def _synchronize_product_document(product: Product) -> None:
    try:
        with transaction.atomic():
            persisted_product = (
                Product.objects.select_related("category")
                .prefetch_related("color_variant", "size_variant")
                .get(pk=product.pk)
            )
            generate_product_document(persisted_product)
    except ProductDocumentGenerationError:
        # The service logs the underlying failure with product context.
        return
    except Exception:
        logger.exception(
            "Product %s was saved, but its AI search document could not be "
            "synchronized",
            product.pk,
        )


@receiver(post_save, sender=Product, dispatch_uid="ai_search.product_saved")
def product_saved(sender, instance, raw=False, **kwargs):
    if not raw:
        _synchronize_product_document(instance)


@receiver(
    m2m_changed,
    sender=Product.color_variant.through,
    dispatch_uid="ai_search.product_color_changed",
)
def product_color_changed(sender, instance, action, reverse=False, **kwargs):
    if not reverse and action in {"post_add", "post_remove", "post_clear"}:
        _synchronize_product_document(instance)


@receiver(
    m2m_changed,
    sender=Product.size_variant.through,
    dispatch_uid="ai_search.product_size_changed",
)
def product_size_changed(sender, instance, action, reverse=False, **kwargs):
    if not reverse and action in {"post_add", "post_remove", "post_clear"}:
        _synchronize_product_document(instance)
