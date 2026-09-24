"""
Query Analyzer module combining LLM extraction and rule-based fallbacks.
"""

import json
import logging
from typing import Any, Protocol, runtime_checkable

from django.conf import settings
from pydantic import ValidationError

from ai_search.query_understanding.extractors import apply_rules
from ai_search.query_understanding.prompts import QUERY_ANALYZER_SYSTEM_PROMPT
from ai_search.query_understanding.schemas import QueryAnalysis


logger = logging.getLogger(__name__)


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
        llm_data = {}
        if self.provider:
            extracted = self.provider.analyze(query)
            if extracted:
                llm_data = extracted

        # 3. Merge them (LLM takes precedence if present, otherwise rules)
        merged = {
            "original_query": query,
            "intent": "product_search",
        }
        
        # Override with LLM data first
        merged.update(llm_data)

        # Fallback to rules data for missing attributes
        for key, value in rules_data.items():
            if not merged.get(key):
                merged[key] = value

        # 4. Validate with Pydantic
        try:
            return QueryAnalysis(**merged)
        except ValidationError as exc:
            logger.error("QueryAnalysis validation failed: %s", exc)
            # Minimal fallback
            return QueryAnalysis(original_query=query, intent="product_search", **rules_data)

