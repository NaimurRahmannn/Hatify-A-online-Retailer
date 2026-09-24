"""
Applies structured query analysis to filter a Django QuerySet of ProductSearchDocument.
"""

from django.db.models import Q, QuerySet

from ai_search.models import ProductSearchDocument
from ai_search.query_understanding.normalization import unique_values
from ai_search.query_understanding.schemas import QueryAnalysis


def apply_metadata_filters(
    queryset: QuerySet[ProductSearchDocument], analysis: QueryAnalysis
) -> QuerySet[ProductSearchDocument]:
    """
    Apply hard filters to the queryset based on the extracted metadata.
    
    Since metadata is stored in a JSONField (metadata), we use Django's
    JSONField lookups (e.g., metadata__price__lte).
    """
    if not analysis.is_meaningful_filter():
        return queryset

    filters = Q()

    # Price filters
    if analysis.price_max is not None:
        filters &= Q(metadata__price__lte=analysis.price_max)
    if analysis.price_min is not None:
        filters &= Q(metadata__price__gte=analysis.price_min)

    # Category
    if analysis.category:
        filters &= Q(metadata__category__iexact=analysis.category)

    # Brand
    if analysis.brand:
        filters &= Q(metadata__brand__iexact=analysis.brand)

    # Gender
    if analysis.gender:
        filters &= Q(metadata__gender__iexact=analysis.gender)

    # Colors
    if analysis.colors:
        color_q = Q()
        for color in unique_values(analysis.colors, transform=str.casefold):
            color_q |= Q(metadata__contains={"colors": [color]})
        filters &= color_q

    # Sizes
    if analysis.sizes:
        size_q = Q()
        for size in unique_values(analysis.sizes, transform=str.upper):
            size_q |= Q(metadata__contains={"sizes": [size]})
        filters &= size_q

    return queryset.filter(filters)
