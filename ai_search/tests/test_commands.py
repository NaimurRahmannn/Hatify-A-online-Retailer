"""
Tests for management commands.
"""

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from ai_search.embeddings import EmbeddingConfigError, EmbeddingProviderError
from ai_search.models import EmbeddingStatus, ProductEmbedding
from ai_search.tests.helpers import make_embedding_vector, make_product


class GenerateEmbeddingsCommandTests(TestCase):
    """Tests for the generate_embeddings management command."""

    @patch("ai_search.management.commands.generate_embeddings.get_provider")
    @patch("ai_search.services.embedding_service.generate_embedding")
    def test_processes_all_documents(self, mock_gen, mock_provider):
        mock_gen.return_value = make_embedding_vector()
        make_product(product_name="Product A")
        make_product(product_name="Product B")

        out = StringIO()
        call_command("generate_embeddings", stdout=out)
        output = out.getvalue()

        self.assertIn("Success: 2", output)

    @patch("ai_search.management.commands.generate_embeddings.get_provider")
    @patch("ai_search.services.embedding_service.generate_embedding")
    def test_skips_current_embeddings(self, mock_gen, mock_provider):
        mock_gen.return_value = make_embedding_vector()
        make_product(product_name="Already Done")

        call_command("generate_embeddings", stdout=StringIO())

        # Second run should skip.
        out = StringIO()
        call_command("generate_embeddings", stdout=out)
        output = out.getvalue()

        self.assertIn("Skipped: 1", output)

    @patch("ai_search.management.commands.generate_embeddings.get_provider")
    @patch("ai_search.services.embedding_service.generate_embedding")
    def test_force_regenerates(self, mock_gen, mock_provider):
        mock_gen.return_value = make_embedding_vector()
        make_product(product_name="Force Me")

        call_command("generate_embeddings", stdout=StringIO())

        out = StringIO()
        call_command("generate_embeddings", "--force", stdout=out)
        output = out.getvalue()

        self.assertIn("Success: 1", output)
        self.assertEqual(mock_gen.call_count, 2)

    @patch(
        "ai_search.management.commands.generate_embeddings.get_provider",
        side_effect=EmbeddingConfigError("bad config"),
    )
    def test_invalid_config_raises_command_error(self, mock_provider):
        with self.assertRaises(CommandError):
            call_command("generate_embeddings", stdout=StringIO())

    @patch("ai_search.management.commands.generate_embeddings.get_provider")
    @patch(
        "ai_search.services.embedding_service.generate_embedding",
        side_effect=EmbeddingProviderError("provider down"),
    )
    def test_partial_failure_continues(self, mock_gen, mock_provider):
        make_product(product_name="Fail A")
        make_product(product_name="Fail B")

        out = StringIO()
        call_command("generate_embeddings", stdout=out)
        output = out.getvalue()

        self.assertIn("Failed:", output)
