"""Product response serializer for the AI Assistant API.

Normalizes internal retrieval objects (SearchResult dataclasses, dicts, etc.)
into a clean, stable API contract so the view layer never inspects domain
internals.
"""

from django.urls import reverse


def _first_present(*values):
    """Return the first value that is not ``None`` or an empty string."""
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _public_scalar(value):
    """Keep response identifiers/text primitive when loose test doubles appear."""
    return value if isinstance(value, (str, int)) else None


def _product_image_url(product) -> str:
    """Return the first image URL without leaking storage failures."""
    if product is None:
        return ""
    try:
        image = product.product_images.first()
        return image.product_image.url if image else ""
    except (AttributeError, ValueError):
        return ""


def _product_url(slug) -> str:
    if not isinstance(slug, str) or not slug:
        return ""
    return reverse("get_product", kwargs={"slug": slug})


def serialize_product(product) -> dict:
    """Convert a single retrieval result into the public API shape.

    Accepts:
        - a ``SearchResult`` dataclass (has ``.document``)
        - a plain dict with optional nested ``document`` key
        - a plain dict that *is* the document
    """
    # Unwrap SearchResult dataclass → its .document
    if hasattr(product, "document"):
        doc = product.document
    elif isinstance(product, dict) and "document" in product:
        doc = product["document"]
    else:
        doc = product

    if isinstance(doc, dict):
        metadata = doc.get("metadata", {})
        slug = _first_present(doc.get("slug"), metadata.get("slug"))
        return {
            "id": _first_present(
                doc.get("product_id"), metadata.get("product_id"),
                doc.get("pk"), doc.get("id")
            ),
            "name": doc.get("name", ""),
            "price": _first_present(metadata.get("price"), doc.get("price")),
            "image": _first_present(
                doc.get("image"), metadata.get("image")
            ) or "",
            "category": metadata.get("category", ""),
            "url": _first_present(
                doc.get("url"), metadata.get("url"), _product_url(slug)
            ) or "",
            "metadata": metadata,
        }

    # ORM model instance (ProductSearchDocument)
    metadata = dict(doc.metadata) if isinstance(doc.metadata, dict) else {}
    product = getattr(doc, "product", None)
    product_id = _public_scalar(getattr(product, "pk", None))
    product_name = _public_scalar(getattr(product, "product_name", "")) or ""
    product_slug = _public_scalar(getattr(product, "slug", "")) or ""
    product_desc = getattr(product, "product_description", "") or ""
    product_emb_desc = getattr(product, "embedding_description", "") or ""
    if product_desc and not metadata.get("description"):
        metadata["description"] = product_desc
    if product_emb_desc and not metadata.get("search_details"):
        metadata["search_details"] = product_emb_desc

    return {
        "id": _first_present(product_id, metadata.get("product_id"), doc.pk),
        "name": _first_present(getattr(doc, "name", ""), product_name) or "",
        "price": metadata.get("price"),
        "image": _first_present(
            metadata.get("image"), _product_image_url(product)
        ) or "",
        "category": metadata.get("category", ""),
        "url": _first_present(metadata.get("url"), _product_url(product_slug)) or "",
        "metadata": metadata,
    }


def serialize_products(products) -> list[dict]:
    """Serialize a list of retrieval results."""
    return [serialize_product(p) for p in (products or [])]
