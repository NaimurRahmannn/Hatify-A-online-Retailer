"""Product response serializer for the AI Assistant API.

Normalizes internal retrieval objects (SearchResult dataclasses, dicts, etc.)
into a clean, stable API contract so the view layer never inspects domain
internals.
"""


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
        return {
            "id": doc.get("pk") or doc.get("id"),
            "name": doc.get("name", ""),
            "price": metadata.get("price") or doc.get("price"),
            "image": metadata.get("image", ""),
            "category": metadata.get("category", ""),
            "metadata": metadata,
        }

    # ORM model instance (ProductSearchDocument)
    metadata = doc.metadata if isinstance(doc.metadata, dict) else {}
    return {
        "id": doc.pk,
        "name": doc.name,
        "price": metadata.get("price"),
        "image": metadata.get("image", ""),
        "category": metadata.get("category", ""),
        "metadata": metadata,
    }


def serialize_products(products) -> list[dict]:
    """Serialize a list of retrieval results."""
    return [serialize_product(p) for p in (products or [])]
