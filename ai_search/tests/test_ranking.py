"""
Tests for the hybrid ranking algorithm.
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from ai_search.models import ProductSearchDocument
from ai_search.query_understanding import AnalysisResult, QueryAnalysis
from ai_search.services.retrieval_service import (
    SearchResult,
    _normalize_scores,
    retrieve_products,
)
from ai_search.tests.helpers import make_product


class NormalizationTests(TestCase):
    """Test score normalization logic."""

    def test_normalize_empty(self):
        self.assertEqual(_normalize_scores({}), {})

    def test_normalize_single_score(self):
        result = _normalize_scores({1: 0.5})
        self.assertAlmostEqual(result[1], 1.0)

    def test_normalize_multiple_scores(self):
        result = _normalize_scores({1: 1.0, 2: 0.5, 3: 0.25})
        self.assertAlmostEqual(result[1], 1.0)
        self.assertAlmostEqual(result[2], 0.5)
        self.assertAlmostEqual(result[3], 0.25)

    def test_normalize_all_zeros(self):
        result = _normalize_scores({1: 0.0, 2: 0.0})
        self.assertAlmostEqual(result[1], 0.0)
        self.assertAlmostEqual(result[2], 0.0)


class HybridRankingTests(TestCase):
    """Test the hybrid retrieval and ranking logic."""

    def setUp(self):
        self.p1 = make_product(product_name="Black Hoodie")
        self.p2 = make_product(product_name="White T-Shirt")
        self.p3 = make_product(product_name="Winter Jacket")
        
        analysis_patcher = patch(
            "ai_search.services.retrieval_service.analyze_query",
        )
        self.mock_cached_analysis = analysis_patcher.start()
        self.mock_cached_analysis.return_value = AnalysisResult(
            analysis=QueryAnalysis(original_query="test", intent="product_search"),
            cache_hit=True,
        )
        self.addCleanup(analysis_patcher.stop)

    @patch("ai_search.services.retrieval_service.semantic_search")
    @patch("ai_search.services.retrieval_service.keyword_search")
    def test_combines_keyword_and_semantic(self, mock_kw, mock_sem):
        doc1 = self.p1.search_document
        doc2 = self.p2.search_document

        # Mock keyword results.
        doc1.keyword_score = 0.9
        doc2.keyword_score = 0.5
        mock_kw.return_value = [doc1, doc2]

        # Mock semantic results.
        doc1_sem = ProductSearchDocument.objects.get(pk=doc1.pk)
        doc1_sem.semantic_score = 0.8
        mock_sem.return_value = [doc1_sem]

        results = retrieve_products("test query")["results"]

        # doc1 should be ranked first (both keyword + semantic).
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0].document.pk, doc1.pk)
        self.assertGreater(results[0].keyword_score, 0)
        self.assertGreater(results[0].semantic_score, 0)

    @patch("ai_search.services.retrieval_service.semantic_search")
    @patch("ai_search.services.retrieval_service.keyword_search")
    def test_keyword_only_result_not_capped(self, mock_kw, mock_sem):
        """A strong keyword-only match should score 1.0, not 0.5."""
        doc1 = self.p1.search_document
        doc1.keyword_score = 0.95
        mock_kw.return_value = [doc1]
        mock_sem.return_value = []

        results = retrieve_products("test")["results"]

        self.assertEqual(len(results), 1)
        # With renormalization, a single-source match gets full score.
        self.assertAlmostEqual(results[0].final_score, 1.0, places=2)

    @patch("ai_search.services.retrieval_service.semantic_search")
    @patch("ai_search.services.retrieval_service.keyword_search")
    def test_semantic_only_result_not_capped(self, mock_kw, mock_sem):
        """A strong semantic-only match should score 1.0, not 0.5."""
        doc1 = self.p1.search_document
        doc1.semantic_score = 0.95
        mock_kw.return_value = []
        mock_sem.return_value = [doc1]

        results = retrieve_products("test")["results"]

        self.assertEqual(len(results), 1)
        self.assertAlmostEqual(results[0].final_score, 1.0, places=2)

    @patch("ai_search.services.retrieval_service.semantic_search")
    @patch("ai_search.services.retrieval_service.keyword_search")
    def test_no_results(self, mock_kw, mock_sem):
        mock_kw.return_value = []
        mock_sem.return_value = []

        payload = retrieve_products("xyznonexistent")
        self.assertEqual(payload["results"], [])
        self.assertTrue(payload["cache_hit"])
        self.assertEqual(
            set(payload["timings"]),
            {
                "analysis_ms",
                "filter_ms",
                "keyword_ms",
                "semantic_ms",
                "ranking_ms",
                "total_ms",
            },
        )
        self.assertTrue(
            all(value >= 0 for value in payload["timings"].values())
        )

    @patch(
        "ai_search.services.retrieval_service.semantic_search",
        side_effect=Exception("Gemini down"),
    )
    @patch("ai_search.services.retrieval_service.keyword_search")
    def test_semantic_failure_degrades_to_keyword(self, mock_kw, mock_sem):
        doc1 = self.p1.search_document
        doc1.keyword_score = 0.8
        mock_kw.return_value = [doc1]

        with self.assertLogs("ai_search.services.retrieval_service", level="WARNING"):
            payload = retrieve_products("test query")

        results = payload["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].semantic_score, 0.0)
        self.assertGreaterEqual(payload["timings"]["semantic_ms"], 0.0)

    @patch("ai_search.services.retrieval_service.semantic_search")
    @patch("ai_search.services.retrieval_service.keyword_search")
    def test_results_sorted_by_final_score(self, mock_kw, mock_sem):
        doc1 = self.p1.search_document
        doc2 = self.p2.search_document
        doc3 = self.p3.search_document

        doc1.keyword_score = 0.3
        doc2.keyword_score = 0.9
        doc3.keyword_score = 0.6
        mock_kw.return_value = [doc2, doc3, doc1]
        mock_sem.return_value = []

        results = retrieve_products("test")["results"]

        scores = [r.final_score for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))
