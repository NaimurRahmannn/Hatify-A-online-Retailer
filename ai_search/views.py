"""
AI search views.

Provides the ``POST /api/ai-search/`` endpoint for hybrid product retrieval.
"""

import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from ai_search.models import SearchQueryLog
from ai_search.services.retrieval_service import retrieve_products


logger = logging.getLogger(__name__)


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
    SearchQueryLog.objects.create(
        user=request.user if request.user.is_authenticated else None,
        original_query=query,
        extracted_filters=results["analysis"],
        result_count=len(product_results),
    )

    return JsonResponse({
        "analysis": results["analysis"],
        "results": product_results
    })
