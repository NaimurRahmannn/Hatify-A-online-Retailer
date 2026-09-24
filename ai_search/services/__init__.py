"""
AI search service layer.

Re-exports from sub-modules so that existing imports like
``from ai_search.services import generate_product_document`` continue to work.
"""

from ai_search.services.product_document_service import (  # noqa: F401
    ProductDocumentGenerationError,
    generate_product_document,
)
