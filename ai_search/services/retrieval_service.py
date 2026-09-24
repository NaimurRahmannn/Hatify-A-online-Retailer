"""
Hybrid retrieval service.

Combines keyword (PostgreSQL FTS) and semantic (pgvector cosine) retrieval
into a single ranked result set. Each retriever is called independently and
their scores are normalized before combining with configurable weights.
"""

import logging
import time
from dataclasses import dataclass, field

from django.conf import settings

from ai_search.models import ProductSearchDocument
from ai_search.retrievers.keyword import keyword_search
from ai_search.retrievers.vector import semantic_search
from ai_search.query_understanding import analyze_query
from ai_search.query_understanding.schemas import QueryAnalysis
from ai_search.filters import apply_metadata_filters


logger = logging.getLogger(__name__)


def _elapsed_ms(start: float) -> float:
    """Return a non-negative elapsed duration rounded for telemetry."""
    return round(max(0.0, (time.perf_counter() - start) * 1000), 3)


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
    analysis=None,
) -> dict:
    """Run hybrid retrieval and return ranked product results.

    If semantic search fails (e.g. Gemini outage), the service degrades
    gracefully to keyword-only results.

    Args:
        query: The user's search query string.
        limit: Maximum number of results to return.
        analysis: An optional pre-computed QueryAnalysis object. When
            provided the internal ``analyze_query`` call is skipped,
            eliminating duplicate work in pipelines that have already
            performed query understanding (e.g. the chat service).
    """
    total_started = time.perf_counter()
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
    cache_hit = False
    phase_started = time.perf_counter()
    if analysis is not None:
        # Caller already ran query understanding – reuse it.
        analysis_ms = 0.0
    else:
        analysis_result = analyze_query(query)
        analysis = analysis_result.analysis
        cache_hit = analysis_result.cache_hit
    analysis_ms = _elapsed_ms(phase_started)

    phase_started = time.perf_counter()
    base_qs = ProductSearchDocument.objects.all()
    filtered_qs = apply_metadata_filters(base_qs, analysis)
    
    # If filtered_qs is empty because secondary metadata (like colors or sizes)
    # was not tagged on the catalog, relax to category-only filtering so semantic
    # vector search and keyword retrieval can still find relevant products.
    if not filtered_qs.exists() and analysis and analysis.category:
        relaxed_analysis = QueryAnalysis(
            original_query=analysis.original_query,
            category=analysis.category
        )
        relaxed_qs = apply_metadata_filters(base_qs, relaxed_analysis)
        if relaxed_qs.exists():
            filtered_qs = relaxed_qs

    filter_ms = _elapsed_ms(phase_started)

    # -----------------------------------------------------------------
    # Keyword retrieval
    # -----------------------------------------------------------------
    phase_started = time.perf_counter()
    
    search_query_str = query
    if analysis:
        search_terms = []
        if analysis.category:
            search_terms.append(analysis.category)
        if analysis.brand:
            search_terms.append(analysis.brand)
        if analysis.gender:
            search_terms.append(analysis.gender)
        if analysis.style:
            search_terms.append(analysis.style)
        if analysis.occasion:
            search_terms.append(analysis.occasion)
        if analysis.season:
            search_terms.append(analysis.season)
        search_terms.extend(analysis.colors)
        search_terms.extend(analysis.sizes)
        search_terms.extend(analysis.keywords)
        
        search_terms = [str(t) for t in search_terms if t]
        if search_terms:
            search_query_str = " ".join(search_terms)
        else:
            words = [
                w for w in query.split()
                if w.lower() not in {
                    "show", "me", "find", "looking", "for", "please", "can", "you",
                    "i", "want", "get", "give", "list", "search", "display", "the",
                    "a", "an", "all", "of", "in", "with", "some", "any"
                }
            ]
            if words:
                search_query_str = " ".join(words)

    keyword_docs = keyword_search(search_query_str, limit=candidate_limit, queryset=filtered_qs)
    keyword_scores: dict[int, float] = {
        doc.pk: doc.keyword_score for doc in keyword_docs
    }
    keyword_ms = _elapsed_ms(phase_started)

    # -----------------------------------------------------------------
    # Semantic retrieval (degrades gracefully on failure)
    # -----------------------------------------------------------------
    semantic_scores: dict[int, float] = {}
    semantic_docs_map: dict[int, ProductSearchDocument] = {}
    phase_started = time.perf_counter()
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
    semantic_ms = _elapsed_ms(phase_started)

    # -----------------------------------------------------------------
    # Normalize scores independently
    # -----------------------------------------------------------------
    phase_started = time.perf_counter()
    norm_keyword = _normalize_scores(keyword_scores)
    norm_semantic = _normalize_scores(semantic_scores)

    # -----------------------------------------------------------------
    # Collect all candidate document IDs
    # -----------------------------------------------------------------
    all_doc_ids = set(norm_keyword) | set(norm_semantic)
    # Build a map of document objects (keyword docs are already loaded)
    docs_map: dict[int, ProductSearchDocument] = {
        doc.pk: doc for doc in keyword_docs
    }
    docs_map.update(semantic_docs_map)

    # If both keyword and semantic searches returned 0 candidates,
    # but analysis produced meaningful metadata filters that matched documents,
    # include those filtered documents as candidates.
    if not all_doc_ids and analysis and analysis.is_meaningful_filter():
        fallback_candidates = list(filtered_qs[:candidate_limit])
        for doc in fallback_candidates:
            all_doc_ids.add(doc.pk)
            docs_map[doc.pk] = doc
            norm_keyword[doc.pk] = 1.0

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

    ranked_results = results[:effective_limit]
    ranking_ms = _elapsed_ms(phase_started)
    timings = {
        "analysis_ms": analysis_ms,
        "filter_ms": filter_ms,
        "keyword_ms": keyword_ms,
        "semantic_ms": semantic_ms,
        "ranking_ms": ranking_ms,
        "total_ms": _elapsed_ms(total_started),
    }

    return {
        "analysis": analysis.model_dump(exclude_none=True),
        "results": ranked_results,
        "cache_hit": cache_hit,
        "timings": timings,
    }
