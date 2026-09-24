"""
Hybrid retrieval service.

Combines keyword (PostgreSQL FTS) and semantic (pgvector cosine) retrieval
into a single ranked result set. Each retriever is called independently and
their scores are normalized before combining with configurable weights.
"""

import logging
from dataclasses import dataclass, field

from django.conf import settings

from ai_search.models import ProductSearchDocument
from ai_search.retrievers.keyword import keyword_search
from ai_search.retrievers.vector import semantic_search
from ai_search.query_understanding import QueryAnalyzer
from ai_search.filters import apply_metadata_filters


logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single ranked product result."""

    document: ProductSearchDocument
    keyword_score: float = 0.0
    semantic_score: float = 0.0
    final_score: float = 0.0


def _normalize_scores(
    scores: dict[int, float],
) -> dict[int, float]:
    """Normalize scores to [0, 1] by dividing by the maximum positive value."""
    if not scores:
        return scores
    max_score = max(scores.values())
    if max_score <= 0:
        return {k: 0.0 for k in scores}
    return {k: v / max_score for k, v in scores.items()}


def retrieve_products(
    query: str,
    limit: int | None = None,
) -> dict:
    """Run hybrid retrieval and return ranked product results.

    If semantic search fails (e.g. Gemini outage), the service degrades
    gracefully to keyword-only results.
    """
    config = getattr(settings, "AI_SEARCH", {})
    effective_limit = limit or config.get("DEFAULT_LIMIT", 10)
    keyword_weight = config.get("KEYWORD_WEIGHT", 0.5)
    semantic_weight = config.get("SEMANTIC_WEIGHT", 0.5)

    # Fetch more candidates from each retriever so the union is not
    # prematurely truncated.
    candidate_limit = effective_limit * 3

    # -----------------------------------------------------------------
    # Query Understanding and Filtering
    # -----------------------------------------------------------------
    analyzer = QueryAnalyzer()
    analysis = analyzer.analyze(query)
    
    base_qs = ProductSearchDocument.objects.all()
    filtered_qs = apply_metadata_filters(base_qs, analysis)

    # -----------------------------------------------------------------
    # Keyword retrieval
    # -----------------------------------------------------------------
    keyword_docs = keyword_search(query, limit=candidate_limit, queryset=filtered_qs)
    keyword_scores: dict[int, float] = {
        doc.pk: doc.keyword_score for doc in keyword_docs
    }

    # -----------------------------------------------------------------
    # Semantic retrieval (degrades gracefully on failure)
    # -----------------------------------------------------------------
    semantic_scores: dict[int, float] = {}
    semantic_docs_map: dict[int, ProductSearchDocument] = {}
    try:
        semantic_docs = semantic_search(query, limit=candidate_limit, queryset=filtered_qs)
        semantic_scores = {
            doc.pk: max(0.0, doc.semantic_score) for doc in semantic_docs
        }
        semantic_docs_map = {doc.pk: doc for doc in semantic_docs}
    except Exception:
        logger.warning(
            "Semantic search failed for query — falling back to keyword-only",
            exc_info=True,
        )

    # -----------------------------------------------------------------
    # Normalize scores independently
    # -----------------------------------------------------------------
    norm_keyword = _normalize_scores(keyword_scores)
    norm_semantic = _normalize_scores(semantic_scores)

    # -----------------------------------------------------------------
    # Collect all candidate document IDs
    # -----------------------------------------------------------------
    all_doc_ids = set(norm_keyword) | set(norm_semantic)
    if not all_doc_ids:
        return {
            "analysis": analysis.model_dump(exclude_none=True),
            "results": [],
        }

    # Build a map of document objects (keyword docs are already loaded)
    docs_map: dict[int, ProductSearchDocument] = {
        doc.pk: doc for doc in keyword_docs
    }
    docs_map.update(semantic_docs_map)

    # Fetch any documents we don't already have in memory
    missing_ids = all_doc_ids - set(docs_map)
    if missing_ids:
        for doc in ProductSearchDocument.objects.filter(pk__in=missing_ids):
            docs_map[doc.pk] = doc

    # -----------------------------------------------------------------
    # Compute final scores with weight renormalization
    # -----------------------------------------------------------------
    results: list[SearchResult] = []
    for doc_id in all_doc_ids:
        doc = docs_map.get(doc_id)
        if doc is None:
            continue

        kw = norm_keyword.get(doc_id, 0.0)
        sem = norm_semantic.get(doc_id, 0.0)

        has_keyword = doc_id in norm_keyword
        has_semantic = doc_id in norm_semantic

        if has_keyword and has_semantic:
            final = keyword_weight * kw + semantic_weight * sem
        elif has_keyword:
            # Renormalize: keyword is the only source.
            final = kw
        else:
            # Renormalize: semantic is the only source.
            final = sem

        results.append(
            SearchResult(
                document=doc,
                keyword_score=round(kw, 4),
                semantic_score=round(sem, 4),
                final_score=round(final, 4),
            )
        )

    # -----------------------------------------------------------------
    # Sort: final_score desc → semantic desc → keyword desc → pk asc
    # -----------------------------------------------------------------
    results.sort(
        key=lambda r: (
            -r.final_score,
            -r.semantic_score,
            -r.keyword_score,
            r.document.pk,
        )
    )

    return {
        "analysis": analysis.model_dump(exclude_none=True),
        "results": results[:effective_limit],
    }
