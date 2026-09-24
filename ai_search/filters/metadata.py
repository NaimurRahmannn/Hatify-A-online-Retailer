"""
Applies structured query analysis to filter a Django QuerySet of ProductSearchDocument.
"""

from django.db.models import Q, QuerySet

from ai_search.models import ProductSearchDocument
from ai_search.query_understanding.normalization import unique_values
from ai_search.query_understanding.schemas import QueryAnalysis


STORE_CATEGORY_MAPPINGS: dict[str, list[str]] = {
    "shirt": ["SHIRTS", "shirt", "shirts"],
    "shirts": ["SHIRTS", "shirt", "shirts"],
    "t-shirt": ["T-SHIRTS", "t-shirt", "t-shirts", "tshirt", "tshirts", "tee", "tees"],
    "t-shirts": ["T-SHIRTS", "t-shirt", "t-shirts", "tshirt", "tshirts", "tee", "tees"],
    "tshirt": ["T-SHIRTS", "t-shirt", "t-shirts", "tshirt", "tshirts", "tee", "tees"],
    "tshirts": ["T-SHIRTS", "t-shirt", "t-shirts", "tshirt", "tshirts", "tee", "tees"],
    "tee": ["T-SHIRTS", "t-shirt", "t-shirts", "tshirt", "tshirts", "tee", "tees"],
    "tees": ["T-SHIRTS", "t-shirt", "t-shirts", "tshirt", "tshirts", "tee", "tees"],
    "hoodie": ["HOODIES | SWEATSHIRTS", "hoodie", "hoodies", "sweatshirt", "sweatshirts"],
    "hoodies": ["HOODIES | SWEATSHIRTS", "hoodie", "hoodies", "sweatshirt", "sweatshirts"],
    "sweatshirt": ["HOODIES | SWEATSHIRTS", "hoodie", "hoodies", "sweatshirt", "sweatshirts"],
    "sweatshirts": ["HOODIES | SWEATSHIRTS", "hoodie", "hoodies", "sweatshirt", "sweatshirts"],
    "suit": ["SUITS | BLAZERS", "suit", "suits", "blazer", "blazers"],
    "suits": ["SUITS | BLAZERS", "suit", "suits", "blazer", "blazers"],
    "blazer": ["SUITS | BLAZERS", "suit", "suits", "blazer", "blazers"],
    "blazers": ["SUITS | BLAZERS", "suit", "suits", "blazer", "blazers"],
    "sweater": ["CARDIGANS | SWEATERS", "sweater", "sweaters", "cardigan", "cardigans", "jumper", "jumpers"],
    "sweaters": ["CARDIGANS | SWEATERS", "sweater", "sweaters", "cardigan", "cardigans", "jumper", "jumpers"],
    "cardigan": ["CARDIGANS | SWEATERS", "sweater", "sweaters", "cardigan", "cardigans", "jumper", "jumpers"],
    "cardigans": ["CARDIGANS | SWEATERS", "sweater", "sweaters", "cardigan", "cardigans", "jumper", "jumpers"],
    "pant": ["PANTS | JEANS", "pant", "pants", "jean", "jeans", "trouser", "trousers"],
    "pants": ["PANTS | JEANS", "pant", "pants", "jean", "jeans", "trouser", "trousers"],
    "jean": ["PANTS | JEANS", "pant", "pants", "jean", "jeans", "trouser", "trousers"],
    "jeans": ["PANTS | JEANS", "pant", "pants", "jean", "jeans", "trouser", "trousers"],
    "jacket": ["JACKETS", "jacket", "jackets"],
    "jackets": ["JACKETS", "jacket", "jackets"],
    "saree": ["SAREE", "saree", "sarees", "sari", "saris"],
    "sarees": ["SAREE", "saree", "sarees", "sari", "saris"],
}


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
        cat_str = str(analysis.category).strip()
        cat_lower = cat_str.lower()
        if cat_lower in STORE_CATEGORY_MAPPINGS:
            cat_q = Q()
            for variant in STORE_CATEGORY_MAPPINGS[cat_lower]:
                cat_q |= Q(metadata__category__iexact=variant)
            filters &= cat_q
        else:
            filters &= Q(metadata__category__iexact=cat_str)

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
