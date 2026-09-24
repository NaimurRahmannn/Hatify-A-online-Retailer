"""Django-cache integration for structured query analysis."""

import hashlib
import logging
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.cache import cache
from pydantic import ValidationError

from ai_search.query_understanding.analyzer import QueryAnalyzer, get_query_analyzer
from ai_search.query_understanding.normalization import normalize_query
from ai_search.query_understanding.schemas import QueryAnalysis


logger = logging.getLogger(__name__)
CACHE_KEY_VERSION = "v1"


@dataclass(frozen=True)
class AnalysisResult:
    analysis: QueryAnalysis
    cache_hit: bool


def build_query_cache_key(query: str) -> str:
    """Build a versioned cache key without exposing raw query text."""
    digest = hashlib.sha256(normalize_query(query).encode("utf-8")).hexdigest()
    return f"ai_search:query_analysis:{CACHE_KEY_VERSION}:{digest}"


def _analysis_from_payload(query: str, payload: Any) -> QueryAnalysis:
    if not isinstance(payload, dict):
        raise TypeError("Cached query analysis must be a mapping")
    return QueryAnalysis(original_query=query.strip(), **payload)


def analyze_query(
    query: str,
    analyzer: QueryAnalyzer | None = None,
) -> AnalysisResult:
    """Return cached structured analysis or compute and cache it safely."""
    cache_key = build_query_cache_key(query)
    cached_payload: Any = None

    try:
        cached_payload = cache.get(cache_key)
    except Exception:
        logger.warning("Query analysis cache read failed", exc_info=True)

    if cached_payload is not None:
        try:
            return AnalysisResult(
                analysis=_analysis_from_payload(query, cached_payload),
                cache_hit=True,
            )
        except (TypeError, ValidationError, ValueError):
            logger.warning("Discarding invalid cached query analysis")
            try:
                cache.delete(cache_key)
            except Exception:
                logger.warning("Query analysis cache delete failed", exc_info=True)

    active_analyzer = analyzer or get_query_analyzer()
    generated = active_analyzer.analyze(query.strip())
    payload = generated.model_dump(mode="json", exclude={"original_query"})
    analysis = _analysis_from_payload(query, payload)
    timeout = getattr(settings, "AI_SEARCH", {}).get("QUERY_CACHE_TTL", 900)

    try:
        cache.set(cache_key, payload, timeout=timeout)
    except Exception:
        logger.warning("Query analysis cache write failed", exc_info=True)

    return AnalysisResult(analysis=analysis, cache_hit=False)
