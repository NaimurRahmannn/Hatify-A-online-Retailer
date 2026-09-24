"""
Applies structured query analysis to filter a Django QuerySet of ProductSearchDocument.
"""

from django.db.models import Q, QuerySet

from ai_search.models import ProductSearchDocument
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
        # Assuming category might be stored case-insensitively or similarly
        filters &= Q(metadata__category__icontains=analysis.category)

    # Brand
    if analysis.brand:
        filters &= Q(metadata__brand__icontains=analysis.brand)

    # Gender
    if analysis.gender:
        filters &= Q(metadata__gender__icontains=analysis.gender)

    # Colors
    if analysis.colors:
        # If product metadata has a list of colors, we can check if it contains any of the requested colors.
        # SQLite JSON1 extension supports this via Django, PostgreSQL definitely does.
        # Using a Q object with OR for multiple colors
        color_q = Q()
        for color in analysis.colors:
            color_q |= Q(metadata__colors__icontains=color)
        filters &= color_q

    # Sizes
    if analysis.sizes:
        size_q = Q()
        for size in analysis.sizes:
            size_q |= Q(metadata__sizes__icontains=size)
        filters &= size_q

    return queryset.filter(filters)
