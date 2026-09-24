"""
Tests for the embedding provider layer and embedding persistence service.
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from ai_search.embeddings import (
    EmbeddingConfigError,
    EmbeddingDimensionError,
    EmbeddingProviderError,
    GeminiEmbeddingProvider,
    generate_embedding,
    get_provider,
)
from ai_search.models import EmbeddingStatus, ProductEmbedding
from ai_search.services.embedding_service import generate_embedding_for_document
from ai_search.tests.helpers import make_embedding_vector, make_product


class ProviderSelectionTests(TestCase):
    """Test the provider factory and configuration validation."""

    @override_settings(AI_SEARCH={"EMBEDDING_PROVIDER": ""})
    def test_missing_provider_raises(self):
        with self.assertRaises(EmbeddingConfigError):
            get_provider()

    @override_settings(AI_SEARCH={"EMBEDDING_PROVIDER": "unknown"})
    def test_unknown_provider_raises(self):
        with self.assertRaises(EmbeddingConfigError):
            get_provider("unknown")

    @override_settings(
        AI_SEARCH={
            "EMBEDDING_PROVIDER": "gemini",
            "EMBEDDING_MODEL": "gemini-embedding-2",
            "EMBEDDING_DIMENSION": 768,
        },
    )
    @patch.dict("os.environ", {"GEMINI_API_KEY": ""})
    def test_missing_api_key_raises(self):
        with self.assertRaises(EmbeddingConfigError):
            get_provider()

    @override_settings(
        AI_SEARCH={
            "EMBEDDING_PROVIDER": "gemini",
            "EMBEDDING_MODEL": "",
            "EMBEDDING_DIMENSION": 768,
        },
    )
    @patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"})
    def test_missing_model_raises(self):
        with self.assertRaises(EmbeddingConfigError):
            get_provider()


class GeminiProviderTests(TestCase):
    """Test the Gemini embedding provider with mocked SDK."""

    def _make_provider(self):
        with patch.object(GeminiEmbeddingProvider, "__init__", return_value=None):
            provider = GeminiEmbeddingProvider(
                api_key="test-key",
                model="gemini-embedding-2",
                dimension=768,
            )
            provider._model = "gemini-embedding-2"
            provider._dimension = 768
            provider._client = MagicMock()
        return provider

    def test_generate_document_embedding(self):
        provider = self._make_provider()
        mock_embedding = MagicMock()
        mock_embedding.values = make_embedding_vector()
        provider._client.models.embed_content.return_value = MagicMock(
            embeddings=[mock_embedding],
        )

        vector = provider.generate("test text", purpose="document")

        self.assertEqual(len(vector), 768)
        # Verify document prefix is used.
        call_args = provider._client.models.embed_content.call_args
        self.assertIn("Represent this product for retrieval:", call_args.kwargs["contents"])

    def test_generate_query_embedding(self):
        provider = self._make_provider()
        mock_embedding = MagicMock()
        mock_embedding.values = make_embedding_vector()
        provider._client.models.embed_content.return_value = MagicMock(
            embeddings=[mock_embedding],
        )

        vector = provider.generate("search query", purpose="query")

        self.assertEqual(len(vector), 768)
        call_args = provider._client.models.embed_content.call_args
        self.assertIn("Represent this search query", call_args.kwargs["contents"])

    def test_dimension_mismatch_raises(self):
        provider = self._make_provider()
        mock_embedding = MagicMock()
        mock_embedding.values = [0.1] * 512  # Wrong dimension
        provider._client.models.embed_content.return_value = MagicMock(
            embeddings=[mock_embedding],
        )

        with self.assertRaises(EmbeddingDimensionError):
            provider.generate("test text")

    def test_empty_response_raises(self):
        provider = self._make_provider()
        provider._client.models.embed_content.return_value = MagicMock(
            embeddings=[],
        )

        with self.assertRaises(EmbeddingProviderError):
            provider.generate("test text")

    def test_provider_network_error_raises(self):
        provider = self._make_provider()
        provider._client.models.embed_content.side_effect = ConnectionError(
            "network down"
        )

        with self.assertRaises(EmbeddingProviderError):
            provider.generate("test text")


class EmbeddingServiceTests(TestCase):
    """Test the embedding persistence state machine."""

    def setUp(self):
        self.product = make_product()
        self.doc = self.product.search_document

    @patch("ai_search.services.embedding_service.generate_embedding")
    def test_successful_embedding_generation(self, mock_gen):
        mock_gen.return_value = make_embedding_vector()

        result = generate_embedding_for_document(self.doc.pk)

        self.assertTrue(result)
        emb = ProductEmbedding.objects.get(product_document=self.doc)
        self.assertEqual(emb.status, EmbeddingStatus.READY)
        self.assertIsNotNone(emb.embedding)
        self.assertEqual(emb.content_hash, self.doc.content_hash)
        self.assertEqual(emb.error_message, "")

    @patch("ai_search.services.embedding_service.generate_embedding")
    def test_skip_current_embedding(self, mock_gen):
        mock_gen.return_value = make_embedding_vector()

        # First call — generates embedding.
        generate_embedding_for_document(self.doc.pk)

        # Second call without force — should skip.
        result = generate_embedding_for_document(self.doc.pk)
        self.assertFalse(result)
        self.assertEqual(mock_gen.call_count, 1)

    @patch("ai_search.services.embedding_service.generate_embedding")
    def test_force_regeneration(self, mock_gen):
        mock_gen.return_value = make_embedding_vector()

        generate_embedding_for_document(self.doc.pk)
        generate_embedding_for_document(self.doc.pk, force=True)

        self.assertEqual(mock_gen.call_count, 2)

    @patch(
        "ai_search.services.embedding_service.generate_embedding",
        side_effect=EmbeddingProviderError("API down"),
    )
    def test_provider_failure_marks_failed(self, mock_gen):
        result = generate_embedding_for_document(self.doc.pk)

        self.assertFalse(result)
        emb = ProductEmbedding.objects.get(product_document=self.doc)
        self.assertEqual(emb.status, EmbeddingStatus.FAILED)
        self.assertIsNone(emb.embedding)
        self.assertIn("API down", emb.error_message)

    @patch("ai_search.services.embedding_service.generate_embedding")
    def test_retry_after_failure(self, mock_gen):
        mock_gen.side_effect = [
            EmbeddingProviderError("temporary"),
            make_embedding_vector(),
        ]

        generate_embedding_for_document(self.doc.pk)
        emb = ProductEmbedding.objects.get(product_document=self.doc)
        self.assertEqual(emb.status, EmbeddingStatus.FAILED)

        generate_embedding_for_document(self.doc.pk)
        emb.refresh_from_db()
        self.assertEqual(emb.status, EmbeddingStatus.READY)
        self.assertIsNotNone(emb.embedding)

    @patch("ai_search.services.embedding_service.generate_embedding")
    def test_attempt_count_increments(self, mock_gen):
        mock_gen.side_effect = EmbeddingProviderError("fail")

        generate_embedding_for_document(self.doc.pk)
        generate_embedding_for_document(self.doc.pk)

        emb = ProductEmbedding.objects.get(product_document=self.doc)
        self.assertEqual(emb.attempt_count, 2)
        self.assertIsNotNone(emb.last_attempt_at)

    @patch("ai_search.services.embedding_service.generate_embedding")
    def test_bounded_error_message(self, mock_gen):
        long_error = "x" * 1000
        mock_gen.side_effect = EmbeddingProviderError(long_error)

        generate_embedding_for_document(self.doc.pk)

        emb = ProductEmbedding.objects.get(product_document=self.doc)
        self.assertLessEqual(len(emb.error_message), 500)
