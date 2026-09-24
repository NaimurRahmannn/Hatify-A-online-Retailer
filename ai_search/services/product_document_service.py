"""
Product document generation service.

Builds and persists AI-ready search documents for products. This module was
originally ``ai_search/services.py`` and has been moved into the services
package without changing its public API.
"""

import hashlib
import logging
from typing import Any

from django.conf import settings
from django.db import transaction

from ai_search.models import EmbeddingStatus, ProductEmbedding, ProductSearchDocument
from ai_search.query_understanding.normalization import unique_values
from ai_search.utils import normalize_text, unique_clean_values
from products.models import Product


logger = logging.getLogger(__name__)


class ProductDocumentGenerationError(RuntimeError):
    """Raised when a product cannot be converted into a search document."""


def _attribute_text(product: Product, field_name: str) -> str | None:
    value = getattr(product, field_name, None)
    if value is None:
        return None

    for name_field in (f"{field_name}_name", "name"):
        if hasattr(value, name_field):
            value = getattr(value, name_field)
            break

    cleaned = normalize_text(value)
    return cleaned or None


def _stock_availability(product: Product) -> bool | None:
    value = getattr(product, "stock_available", None)
    return value if isinstance(value, bool) else None


def _build_document_data(product: Product) -> dict[str, Any]:
    category = getattr(product, "category", None)
    category_name = normalize_text(getattr(category, "categroy_name", ""))
    category_type = (
        normalize_text(category.get_category_type_display()) if category else ""
    )
    gender = normalize_text(getattr(category, "category_type", "")).lower() or None

    name = normalize_text(product.product_name)
    description = normalize_text(product.product_description)
    if description.casefold() == name.casefold():
        description = ""
    embedding_description = normalize_text(getattr(product, "embedding_description", "") or "")
    if embedding_description.casefold() == name.casefold() or embedding_description.casefold() == description.casefold():
        embedding_description = ""

    colors = unique_clean_values(
        variant.color_name for variant in product.color_variant.all()
    )
    sizes = unique_clean_values(
        variant.size_name for variant in product.size_variant.all()
    )
    metadata_colors = unique_values(colors, transform=str.casefold)
    metadata_sizes = unique_values(sizes, transform=str.upper)

    brand = _attribute_text(product, "brand")
    material = _attribute_text(product, "material")
    style = _attribute_text(product, "style")
    occasion = _attribute_text(product, "occasion")
    season = _attribute_text(product, "season")
    fit = _attribute_text(product, "fit")
    stock_available = _stock_availability(product)

    # -----------------------------------------------------------------
    # Semantic sections (stable product attributes for embedding_text)
    # -----------------------------------------------------------------
    semantic_sections: list[str] = [f"Product Name:\n{name}"]
    if category_name:
        semantic_sections.append(f"Category:\n{category_name}")
    if brand:
        semantic_sections.append(f"Brand:\n{brand}")
    if description:
        semantic_sections.append(f"Description:\n{description}")
    if embedding_description:
        semantic_sections.append(f"Search Details:\n{embedding_description}")

    attributes: list[str] = []
    if colors:
        attributes.append(f"Color: {', '.join(colors)}")
    if sizes:
        attributes.append(f"Size: {', '.join(sizes)}")
    for label, value in (
        ("Material", material),
        ("Style", style),
        ("Occasion", occasion),
        ("Season", season),
        ("Gender", category_type or None),
        ("Fit", fit),
    ):
        if value:
            attributes.append(f"{label}: {value}")
    if attributes:
        semantic_sections.append("Attributes:\n" + "\n".join(attributes))

    # -----------------------------------------------------------------
    # Volatile sections (change frequently, excluded from embedding)
    # -----------------------------------------------------------------
    volatile_sections: list[str] = [f"Price:\n{product.price} BDT"]
    if stock_available is not None:
        status = "In stock" if stock_available else "Out of stock"
        volatile_sections.append(f"Stock Availability:\n{status}")

    embedding_text = "\n\n".join(semantic_sections)
    searchable_text = "\n\n".join(semantic_sections + volatile_sections)
    content_hash = hashlib.sha256(embedding_text.encode("utf-8")).hexdigest()

    return {
        "text": searchable_text,
        "embedding_text": embedding_text,
        "content_hash": content_hash,
        "metadata": {
            "product_id": str(product.pk),
            "category": category_name or None,
            "category_type": category_type or None,
            "brand": brand,
            "price": float(product.price),
            "colors": metadata_colors,
            "sizes": metadata_sizes,
            "stock_available": stock_available,
            "material": material,
            "style": style,
            "occasion": occasion,
            "season": season,
            "gender": gender,
            "fit": fit,
        },
    }


def _ensure_embedding_state(document: ProductSearchDocument) -> None:
    """Ensure an embedding-state row exists and invalidate stale vectors.

    This runs inside the caller's transaction.  It never makes an external
    API call — only creates or updates a database row.
    """
    config = getattr(settings, "AI_SEARCH", {})
    model_name = config.get("EMBEDDING_MODEL", "")

    embedding, created = ProductEmbedding.objects.get_or_create(
        product_document=document,
        defaults={
            "model_name": model_name,
            "status": EmbeddingStatus.PENDING,
        },
    )

    if created:
        return

    hash_matches = embedding.content_hash == document.content_hash
    model_matches = embedding.model_name == model_name

    is_current = (
        embedding.status == EmbeddingStatus.READY
        and embedding.embedding is not None
        and hash_matches
        and model_matches
    )

    if is_current:
        return  # Vector is up-to-date — nothing to do.

    if not hash_matches or not model_matches:
        # Semantic content or configured model changed — invalidate.
        # Retain attempt_count and last_attempt_at for observability.
        embedding.embedding = None
        embedding.status = EmbeddingStatus.PENDING
        embedding.error_message = ""
        embedding.model_name = model_name
        embedding.save(
            update_fields=[
                "embedding",
                "status",
                "error_message",
                "model_name",
                "updated_at",
            ]
        )


def generate_product_document(product: Product) -> ProductSearchDocument:
    """
    Build and persist the AI-ready document for a product.

    Also ensures a one-to-one embedding-state row exists and invalidates
    stale vectors when the semantic content hash changes.

    Callers can catch ``ProductDocumentGenerationError`` without depending on
    lower-level ORM or data-normalization exceptions.
    """
    try:
        with transaction.atomic():
            document_data = _build_document_data(product)
            document, _ = ProductSearchDocument.objects.update_or_create(
                product=product,
                defaults={
                    "searchable_text": document_data["text"],
                    "embedding_text": document_data["embedding_text"],
                    "content_hash": document_data["content_hash"],
                    "metadata": document_data["metadata"],
                },
            )
            _ensure_embedding_state(document)
            return document
    except Exception as exc:
        product_id = getattr(product, "pk", None)
        logger.exception(
            "Failed to generate search document for product %s",
            product_id,
        )
        raise ProductDocumentGenerationError(
            f"Unable to generate search document for product {product_id}"
        ) from exc
