import logging
from typing import Any

from django.db import transaction

from ai_search.models import ProductSearchDocument
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

    colors = unique_clean_values(
        variant.color_name for variant in product.color_variant.all()
    )
    sizes = unique_clean_values(
        variant.size_name for variant in product.size_variant.all()
    )

    brand = _attribute_text(product, "brand")
    material = _attribute_text(product, "material")
    style = _attribute_text(product, "style")
    occasion = _attribute_text(product, "occasion")
    season = _attribute_text(product, "season")
    fit = _attribute_text(product, "fit")
    stock_available = _stock_availability(product)

    sections = [f"Product Name:\n{name}"]
    if category_name:
        sections.append(f"Category:\n{category_name}")
    if brand:
        sections.append(f"Brand:\n{brand}")
    if description:
        sections.append(f"Description:\n{description}")

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
        sections.append("Attributes:\n" + "\n".join(attributes))

    sections.append(f"Price:\n{product.price} BDT")
    if stock_available is not None:
        status = "In stock" if stock_available else "Out of stock"
        sections.append(f"Stock Availability:\n{status}")

    return {
        "text": "\n\n".join(sections),
        "metadata": {
            "product_id": str(product.pk),
            "category": category_name or None,
            "category_type": category_type or None,
            "brand": brand,
            "price": float(product.price),
            "colors": colors,
            "sizes": sizes,
            "stock_available": stock_available,
            "material": material,
            "style": style,
            "occasion": occasion,
            "season": season,
            "gender": gender,
            "fit": fit,
        },
    }


def generate_product_document(product: Product) -> ProductSearchDocument:
    """
    Build and persist the AI-ready document for a product.

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
                    "metadata": document_data["metadata"],
                },
            )
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
