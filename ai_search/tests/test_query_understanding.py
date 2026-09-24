"""
Tests for Query Understanding components.
"""

from unittest.mock import patch

from django.test import SimpleTestCase

from ai_search.query_understanding.extractors import apply_rules
from ai_search.query_understanding.schemas import QueryAnalysis
from ai_search.query_understanding import analyzer as analyzer_module
from ai_search.query_understanding.analyzer import QueryAnalyzer


class FakeProvider:
    """Provider double that keeps Gemini outside unit tests."""

    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.calls = 0

    def analyze(self, query):
        self.calls += 1
        if self.error:
            raise self.error
        return self.payload


class ExtractorTests(SimpleTestCase):
    """Tests for rule-based extraction fallbacks."""

    def test_extract_price_under(self):
        result = apply_rules("black shoes under 5000")
        self.assertEqual(result.get("price_max"), 5000)

    def test_extract_price_between(self):
        result = apply_rules("jacket between 2000 and 6000.5")
        self.assertEqual(result.get("price_min"), 2000)
        self.assertEqual(result.get("price_max"), 6000.5)

    def test_extract_colors(self):
        result = apply_rules("white shirt and red pants")
        colors = result.get("colors", [])
        self.assertIn("white", colors)
        self.assertIn("red", colors)

    def test_extract_category(self):
        result = apply_rules("where can I find running sneakers")
        self.assertEqual(result.get("category"), "shoe")

    def test_extract_size(self):
        result = apply_rules("black hoodie size XL or 42")
        sizes = result.get("sizes", [])
        self.assertIn("XL", sizes)
        self.assertIn("42", sizes)


class AnalyzerTests(SimpleTestCase):
    """Tests for the overall QueryAnalyzer orchestration."""

    def test_analyzer_merges_llm_and_rules(self):
        provider = FakeProvider({
            "category": "hoodie",
            "colors": ["black"],
            "intent": "product_search"
        })
        analyzer = QueryAnalyzer(provider=provider)

        # "under 3000" is missing from LLM return, should be caught by rules
        result = analyzer.analyze("black hoodie under 3000")

        self.assertEqual(result.category, "hoodie")
        self.assertEqual(result.colors, ["black"])
        self.assertEqual(result.price_max, 3000.0)

    def test_rule_price_takes_precedence_over_llm(self):
        provider = FakeProvider({
            "price_max": 2500.0,
        })
        analyzer = QueryAnalyzer(provider=provider)

        result = analyzer.analyze("black hoodie under 3000")

        self.assertEqual(result.price_max, 3000.0)

    def test_empty_llm_list_does_not_erase_rule_values(self):
        analyzer = QueryAnalyzer(provider=FakeProvider({"colors": []}))

        result = analyzer.analyze("black hoodie")

        self.assertEqual(result.colors, ["black"])

    def test_rule_and_llm_lists_are_merged_without_duplicates(self):
        analyzer = QueryAnalyzer(
            provider=FakeProvider({"colors": ["BLACK", "navy"], "sizes": ["L"]})
        )

        result = analyzer.analyze("black hoodie size XL")

        self.assertEqual(result.colors, ["black", "navy"])
        self.assertEqual(result.sizes, ["XL", "L"])

    def test_explicit_rule_category_overrides_llm_category(self):
        analyzer = QueryAnalyzer(provider=FakeProvider({"category": "jacket"}))

        result = analyzer.analyze("black hoodie")

        self.assertEqual(result.category, "hoodie")

    def test_provider_cannot_override_original_query(self):
        analyzer = QueryAnalyzer(
            provider=FakeProvider({"original_query": "different query"})
        )

        result = analyzer.analyze("black hoodie")

        self.assertEqual(result.original_query, "black hoodie")

    def test_provider_exception_falls_back_to_rules(self):
        analyzer = QueryAnalyzer(provider=FakeProvider(error=RuntimeError("down")))

        with self.assertLogs("ai_search.query_understanding.analyzer", level="WARNING"):
            result = analyzer.analyze("black shoes under 5000")

        self.assertEqual(result.colors, ["black"])
        self.assertEqual(result.category, "shoe")
        self.assertEqual(result.price_max, 5000.0)

    def test_none_provider_response_falls_back_to_rules(self):
        result = QueryAnalyzer(provider=FakeProvider(None)).analyze(
            "black shoes under 5000"
        )

        self.assertEqual(result.colors, ["black"])
        self.assertEqual(result.price_max, 5000.0)

    @patch("ai_search.query_understanding.analyzer.QueryAnalyzer")
    def test_default_analyzer_is_reused(self, analyzer_class):
        get_query_analyzer = getattr(analyzer_module, "get_query_analyzer", None)
        self.assertIsNotNone(get_query_analyzer)
        get_query_analyzer.cache_clear()
        self.addCleanup(get_query_analyzer.cache_clear)

        first = get_query_analyzer()
        second = get_query_analyzer()

        self.assertIs(first, second)
        analyzer_class.assert_called_once_with()
