"""
Query Analyzer module combining LLM extraction and rule-based fallbacks.
"""

import json
import logging
from collections.abc import Mapping
from functools import lru_cache
from typing import Any, Protocol, runtime_checkable

from django.conf import settings
from pydantic import ValidationError

from ai_search.query_understanding.extractors import apply_rules
from ai_search.query_understanding.normalization import unique_values
from ai_search.query_understanding.prompts import QUERY_ANALYZER_SYSTEM_PROMPT
from ai_search.query_understanding.schemas import QueryAnalysis


logger = logging.getLogger(__name__)


def _list_value(data: Mapping[str, Any], plural: str, singular: str) -> list[Any]:
    value = data.get(plural, data.get(singular, []))
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _scalar_value(
    data: Mapping[str, Any], singular: str, plural: str
) -> Any | None:
    value = data.get(singular)
    if value not in (None, "", []):
        return value
    values = data.get(plural)
    if isinstance(values, (list, tuple)) and values:
        return values[0]
    return None


def merge_analysis(
    query: str,
    rules_data: Mapping[str, Any],
    llm_data: Mapping[str, Any] | None,
) -> QueryAnalysis:
    """Merge deterministic evidence with semantic provider output."""
    provider_data = llm_data if isinstance(llm_data, Mapping) else {}
    merged: dict[str, Any] = {
        "original_query": query,
        "intent": provider_data.get("intent") or "product_search",
    }

    for field_name in ("gender", "occasion", "season", "style", "keywords"):
        value = provider_data.get(field_name)
        if value not in (None, "", []):
            merged[field_name] = value

    merged["colors"] = unique_values(
        _list_value(rules_data, "colors", "color")
        + _list_value(provider_data, "colors", "color"),
        transform=str.casefold,
    )
    merged["sizes"] = unique_values(
        _list_value(rules_data, "sizes", "size")
        + _list_value(provider_data, "sizes", "size"),
        transform=str.upper,
    )

    for singular, plural in (("category", "categories"), ("brand", "brands")):
        value = _scalar_value(rules_data, singular, plural)
        if value is None:
            value = _scalar_value(provider_data, singular, plural)
        if value not in (None, ""):
            merged[singular] = value

    for field_name in ("price_min", "price_max"):
        value = rules_data.get(field_name)
        if value is None:
            value = provider_data.get(field_name)
        if value is not None:
            merged[field_name] = value

    return QueryAnalysis(**merged)


@runtime_checkable
class QueryProvider(Protocol):
    """Protocol for LLM query providers."""

    def analyze(self, query: str) -> dict[str, Any] | None:
        """Analyze the query and return a raw dictionary matching QueryAnalysis."""
        ...


class GeminiQueryProvider:
    """Gemini-based query provider using Structured Outputs (JSON Schema)."""

    def __init__(self, api_key: str, model: str) -> None:
        self.model = model
        from google import genai
        from google.genai import types
        self._client = genai.Client(api_key=api_key)
        self._types = types

    def analyze(self, query: str) -> dict[str, Any] | None:
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=query,
                config=self._types.GenerateContentConfig(
                    system_instruction=QUERY_ANALYZER_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    # Generate schema dynamically from Pydantic model
                    response_schema=QueryAnalysis.model_json_schema(),
                    temperature=0.0,
                )
            )
            if not response.text:
                return None
            return json.loads(response.text)
        except Exception:
            logger.exception("Gemini Query Analysis failed.")
            return None


class QueryAnalyzer:
    """Main analyzer that combines LLM and rule-based extraction."""

    def __init__(self, provider: QueryProvider | None = None):
        self.provider = provider or self._get_default_provider()

    def _get_default_provider(self) -> QueryProvider | None:
        config = getattr(settings, "AI_SEARCH", {})
        provider_name = config.get("QUERY_PROVIDER", "gemini").lower()
        model = config.get("QUERY_MODEL", "gemini-2.5-flash")

        if provider_name == "gemini":
            import os
            api_key = os.environ.get("GEMINI_API_KEY")
            if api_key:
                return GeminiQueryProvider(api_key=api_key, model=model)
            else:
                logger.warning("GEMINI_API_KEY not set. Falling back to rule-based analysis only.")
        return None

    def analyze(self, query: str) -> QueryAnalysis:
        """
        Analyze a user query using LLM and fallback rules.
        """
        # 1. Start with rule-based extraction
        rules_data = apply_rules(query)
        
        # 2. Try LLM extraction
        llm_data: Mapping[str, Any] | None = None
        if self.provider:
            try:
                llm_data = self.provider.analyze(query)
            except Exception:
                logger.warning(
                    "Query analysis provider failed; using deterministic rules",
                    exc_info=True,
                )

        # 4. Validate with Pydantic
        try:
            return merge_analysis(query, rules_data, llm_data)
        except ValidationError as exc:
            logger.error("QueryAnalysis validation failed: %s", exc)
            return merge_analysis(query, rules_data, None)


@lru_cache(maxsize=1)
def get_query_analyzer() -> QueryAnalyzer:
    """Return the process-local default analyzer and provider client."""
    return QueryAnalyzer()
