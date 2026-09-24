"""
Tests for Query Understanding components.
"""

from unittest.mock import patch, MagicMock

from django.test import TestCase

from ai_search.query_understanding.extractors import apply_rules
from ai_search.query_understanding.schemas import QueryAnalysis
from ai_search.query_understanding.analyzer import QueryAnalyzer, GeminiQueryProvider


class ExtractorTests(TestCase):
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


class AnalyzerTests(TestCase):
    """Tests for the overall QueryAnalyzer orchestration."""

    @patch("ai_search.query_understanding.analyzer.GeminiQueryProvider.analyze")
    def test_analyzer_merges_llm_and_rules(self, mock_llm_analyze):
        mock_llm_analyze.return_value = {
            "category": "hoodie",
            "colors": ["black"],
            "intent": "product_search"
        }
        
        # We manually inject GeminiQueryProvider 
        provider = GeminiQueryProvider("dummy_key", "dummy_model")
        analyzer = QueryAnalyzer(provider=provider)

        # "under 3000" is missing from LLM return, should be caught by rules
        result = analyzer.analyze("black hoodie under 3000")

        self.assertEqual(result.category, "hoodie")
        self.assertEqual(result.colors, ["black"])
        self.assertEqual(result.price_max, 3000.0)

    @patch("ai_search.query_understanding.analyzer.GeminiQueryProvider.analyze")
    def test_analyzer_llm_takes_precedence(self, mock_llm_analyze):
        mock_llm_analyze.return_value = {
            "price_max": 2500.0,
        }
        
        provider = GeminiQueryProvider("dummy_key", "dummy_model")
        analyzer = QueryAnalyzer(provider=provider)

        result = analyzer.analyze("black hoodie under 3000")

        # The LLM extraction of 2500 should override rule extraction of 3000
        self.assertEqual(result.price_max, 2500.0)
