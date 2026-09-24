"""
Tests for keyword and semantic retrievers.

PostgreSQL-specific tests (FTS, pgvector) require a PostgreSQL backend.
They are skipped automatically when running on SQLite.
"""

from unittest.mock import patch

from django.db import connection
from django.test import TestCase

from ai_search.models import EmbeddingStatus, ProductEmbedding, ProductSearchDocument
from ai_search.tests.helpers import make_embedding_vector, make_product


def _is_postgres():
    return connection.vendor == "postgresql"


class KeywordSearchTests(TestCase):
    """Tests for the keyword retriever using PostgreSQL FTS."""

    def setUp(self):
        self.p1 = make_product(product_name="Black Hoodie", price="2500.00")
        self.p2 = make_product(product_name="White T-Shirt", price="1500.00")
        self.p3 = make_product(
            product_name="Black Jacket",
            product_description="Warm winter black jacket",
        )

    def test_keyword_search_returns_matches(self):
        if not _is_postgres():
            self.skipTest("Requires PostgreSQL for full-text search")

        from ai_search.retrievers.keyword import keyword_search

        results = keyword_search("black hoodie")
        names = [doc.product.product_name for doc in results]

        self.assertIn("Black Hoodie", names)

    def test_keyword_search_has_positive_scores(self):
        if not _is_postgres():
            self.skipTest("Requires PostgreSQL for full-text search")

        from ai_search.retrievers.keyword import keyword_search

        results = keyword_search("black")

        for doc in results:
            self.assertGreater(doc.keyword_score, 0)

    def test_keyword_search_respects_limit(self):
        if not _is_postgres():
            self.skipTest("Requires PostgreSQL for full-text search")

        from ai_search.retrievers.keyword import keyword_search

        results = keyword_search("black", limit=1)
        self.assertLessEqual(len(results), 1)

    def test_keyword_search_no_results_for_unmatched_query(self):
        if not _is_postgres():
            self.skipTest("Requires PostgreSQL for full-text search")

        from ai_search.retrievers.keyword import keyword_search

        results = keyword_search("xyznonexistent12345")
        self.assertEqual(len(results), 0)


class SemanticSearchTests(TestCase):
    """Tests for the semantic retriever using pgvector."""

    def setUp(self):
        self.product = make_product(product_name="Warm Sweater")
        self.doc = self.product.search_document

    def _make_ready_embedding(self, doc, vector=None):
        from django.conf import settings

        config = settings.AI_SEARCH
        emb = doc.embedding
        emb.embedding = vector or make_embedding_vector()
        emb.status = EmbeddingStatus.READY
        emb.content_hash = doc.content_hash
        emb.model_name = config["EMBEDDING_MODEL"]
        emb.save()
        return emb

    @patch("ai_search.retrievers.vector.generate_embedding")
    def test_semantic_search_returns_ready_embeddings(self, mock_gen):
        if not _is_postgres():
            self.skipTest("Requires PostgreSQL for pgvector")

        mock_gen.return_value = make_embedding_vector(value=0.1)
        self._make_ready_embedding(self.doc)

        from ai_search.retrievers.vector import semantic_search

        results = semantic_search("warm winter clothes")
        self.assertTrue(len(results) > 0)
        self.assertTrue(hasattr(results[0], "semantic_score"))

    @patch("ai_search.retrievers.vector.generate_embedding")
    def test_semantic_search_excludes_failed_embeddings(self, mock_gen):
        if not _is_postgres():
            self.skipTest("Requires PostgreSQL for pgvector")

        mock_gen.return_value = make_embedding_vector(value=0.1)
        emb = self.doc.embedding
        emb.status = EmbeddingStatus.FAILED
        emb.save()

        from ai_search.retrievers.vector import semantic_search

        results = semantic_search("warm clothes")
        doc_ids = [doc.pk for doc in results]
        self.assertNotIn(self.doc.pk, doc_ids)

    @patch("ai_search.retrievers.vector.generate_embedding")
    def test_semantic_search_excludes_null_vectors(self, mock_gen):
        if not _is_postgres():
            self.skipTest("Requires PostgreSQL for pgvector")

        mock_gen.return_value = make_embedding_vector(value=0.1)
        emb = self.doc.embedding
        emb.status = EmbeddingStatus.READY
        emb.embedding = None
        emb.save()

        from ai_search.retrievers.vector import semantic_search

        results = semantic_search("warm clothes")
        doc_ids = [doc.pk for doc in results]
        self.assertNotIn(self.doc.pk, doc_ids)
