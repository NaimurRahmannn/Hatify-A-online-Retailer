"""Tests for cached structured query analysis."""

from unittest.mock import Mock, patch

from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from ai_search.query_understanding.cache import (
    analyze_query,
    build_query_cache_key,
)
from ai_search.query_understanding.schemas import QueryAnalysis


class QueryAnalysisCacheTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_second_equivalent_query_uses_cache_and_keeps_current_original(self):
        analyzer = Mock()
        analyzer.analyze.return_value = QueryAnalysis(
            original_query="Black   Hoodie",
            colors=["black"],
        )

        first = analyze_query("Black   Hoodie", analyzer=analyzer)
        second = analyze_query(" black hoodie ", analyzer=analyzer)

        self.assertFalse(first.cache_hit)
        self.assertTrue(second.cache_hit)
        self.assertEqual(second.analysis.original_query, "black hoodie")
        self.assertEqual(second.analysis.colors, ["black"])
        analyzer.analyze.assert_called_once_with("Black   Hoodie")

    def test_cache_key_hashes_instead_of_exposing_query(self):
        key = build_query_cache_key("private black hoodie")

        self.assertTrue(key.startswith("ai_search:query_analysis:v1:"))
        self.assertNotIn("private", key)
        self.assertEqual(len(key.rsplit(":", 1)[-1]), 64)

    def test_malformed_cached_data_is_recomputed(self):
        query = "black hoodie"
        cache.set(build_query_cache_key(query), {"colors": 42})
        analyzer = Mock()
        analyzer.analyze.return_value = QueryAnalysis(
            original_query=query,
            category="hoodie",
        )

        with self.assertLogs("ai_search.query_understanding.cache", level="WARNING"):
            result = analyze_query(query, analyzer=analyzer)

        self.assertFalse(result.cache_hit)
        self.assertEqual(result.analysis.category, "hoodie")
        analyzer.analyze.assert_called_once_with(query)

    @patch("ai_search.query_understanding.cache.cache.get", side_effect=RuntimeError("down"))
    def test_cache_read_failure_degrades_to_uncached_analysis(self, cache_get):
        analyzer = Mock()
        analyzer.analyze.return_value = QueryAnalysis(original_query="black hoodie")

        with self.assertLogs("ai_search.query_understanding.cache", level="WARNING"):
            result = analyze_query("black hoodie", analyzer=analyzer)

        self.assertFalse(result.cache_hit)
        self.assertEqual(result.analysis.original_query, "black hoodie")

    @patch("ai_search.query_understanding.cache.cache.set", side_effect=RuntimeError("down"))
    def test_cache_write_failure_returns_analysis(self, cache_set):
        analyzer = Mock()
        analyzer.analyze.return_value = QueryAnalysis(original_query="black hoodie")

        with self.assertLogs("ai_search.query_understanding.cache", level="WARNING"):
            result = analyze_query("black hoodie", analyzer=analyzer)

        self.assertFalse(result.cache_hit)
        self.assertEqual(result.analysis.original_query, "black hoodie")

    @override_settings(
        AI_SEARCH={**settings.AI_SEARCH, "QUERY_CACHE_TTL": 321},
    )
    @patch("ai_search.query_understanding.cache.cache.set")
    def test_configured_ttl_is_forwarded_to_cache(self, cache_set):
        analyzer = Mock()
        analyzer.analyze.return_value = QueryAnalysis(original_query="black hoodie")

        analyze_query("black hoodie", analyzer=analyzer)

        _, kwargs = cache_set.call_args
        self.assertEqual(kwargs["timeout"], 321)
