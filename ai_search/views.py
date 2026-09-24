"""
AI search views.

Provides the ``POST /api/ai-search/`` endpoint for hybrid product retrieval.
"""

import json
import logging
import time

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from ai_search.models import SearchQueryLog
from ai_search.query_understanding import normalize_query
from ai_search.services.retrieval_service import retrieve_products


logger = logging.getLogger(__name__)
TIMING_KEYS = (
    "analysis_ms",
    "filter_ms",
    "keyword_ms",
    "semantic_ms",
    "ranking_ms",
    "total_ms",
)


@require_POST
def search_view(request):
    """Hybrid product search API endpoint.

    Request::

        POST /api/ai-search/
        Content-Type: application/json
        {"query": "black hoodie under 3000", "limit": 10}

    Response::

        {"results": [{"id": "...", "name": "...", "price": "2500.00",
                       "keyword_score": 0.85, "semantic_score": 0.91,
                       "final_score": 0.88}]}

    The view is CSRF-protected.  Clients on the same site can send the
    CSRF token via the ``X-CSRFToken`` header.
    """
    config = getattr(settings, "AI_SEARCH", {})
    max_query_length = config.get("MAX_QUERY_LENGTH", 500)
    max_limit = config.get("MAX_LIMIT", 50)

    # ------------------------------------------------------------------
    # Parse and validate request body
    # ------------------------------------------------------------------
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse(
            {"error": "Invalid JSON in request body."},
            status=400,
        )

    if not isinstance(body, dict):
        return JsonResponse(
            {"error": "Request body must be a JSON object."},
            status=400,
        )

    query = body.get("query")
    if not isinstance(query, str) or not query.strip():
        return JsonResponse(
            {"error": "A non-empty 'query' string is required."},
            status=400,
        )

    query = query.strip()
    if len(query) > max_query_length:
        return JsonResponse(
            {"error": f"Query must not exceed {max_query_length} characters."},
            status=400,
        )

    limit = body.get("limit")
    if limit is not None:
        if not isinstance(limit, int) or isinstance(limit, bool):
            return JsonResponse(
                {"error": "'limit' must be an integer."},
                status=400,
            )
        if limit < 1 or limit > max_limit:
            return JsonResponse(
                {"error": f"'limit' must be between 1 and {max_limit}."},
                status=400,
            )

    # ------------------------------------------------------------------
    # Execute hybrid retrieval
    # ------------------------------------------------------------------
    request_started = time.perf_counter()
    try:
        results = retrieve_products(query, limit=limit)
    except Exception:
        logger.exception("Unexpected error in hybrid retrieval")
        return JsonResponse(
            {"error": "An internal error occurred. Please try again later."},
            status=500,
        )

    # ------------------------------------------------------------------
    # Serialize response
    # ------------------------------------------------------------------
    product_results = []
    for result in results["results"]:
        doc = result.document
        product = doc.product
        product_results.append(
            {
                "id": str(product.pk),
                "name": product.product_name,
                "price": str(product.price),
                "keyword_score": result.keyword_score,
                "semantic_score": result.semantic_score,
                "final_score": result.final_score,
            }
        )

    # ------------------------------------------------------------------
    # Log query
    # ------------------------------------------------------------------
    raw_timings = results.get("timings", {})
    timings = {
        key: max(0.0, float(raw_timings.get(key, 0.0)))
        for key in TIMING_KEYS
    }
    timings["total_ms"] = round(
        max(0.0, (time.perf_counter() - request_started) * 1000),
        3,
    )

    try:
        SearchQueryLog.objects.create(
            query=query,
            normalized_query=normalize_query(query),
            analysis=results["analysis"],
            result_count=len(product_results),
            execution_time_ms=timings["total_ms"],
            cache_hit=bool(results.get("cache_hit", False)),
            timings=timings,
        )
    except Exception:
        logger.exception("Unable to persist AI search analytics")

    return JsonResponse({
        "analysis": results["analysis"],
        "results": product_results
    })
