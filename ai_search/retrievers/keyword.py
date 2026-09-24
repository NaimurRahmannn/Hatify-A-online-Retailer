"""
Keyword retrieval using PostgreSQL full-text search.

Uses Django's ``SearchVector``, ``SearchQuery``, and ``SearchRank`` over
``ProductSearchDocument.searchable_text``.  The ``simple`` configuration
preserves product, brand, size, and multilingual catalog tokens without
English stop-word removal.
"""

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

from ai_search.models import ProductSearchDocument


from django.db.models import QuerySet

def keyword_search(
    query: str,
    limit: int = 10,
    queryset: QuerySet[ProductSearchDocument] | None = None,
) -> list[ProductSearchDocument]:
    """Return search documents ranked by PostgreSQL full-text relevance.

    Each returned document is annotated with a ``keyword_score`` attribute.
    Only documents with a positive rank are included.
    """
    search_vector = SearchVector("searchable_text", config="simple")
    search_query = SearchQuery(query, config="simple", search_type="websearch")

    base_qs = queryset if queryset is not None else ProductSearchDocument.objects.all()

    results = (
        base_qs.annotate(
            keyword_score=SearchRank(search_vector, search_query),
        )
        .filter(keyword_score__gt=0)
        .order_by("-keyword_score", "pk")[:limit]
    )

    return list(results)
