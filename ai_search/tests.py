import os
from importlib import import_module
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models.signals import post_save
from django.test import TestCase

from ai_search.apps import AiSearchConfig
from ai_search.embeddings import EmbeddingService
from ai_search.models import ProductEmbedding, ProductSearchDocument
from products.models import Category, ColorVariant, Product, SizeVariant


class AiSearchTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            categroy_name="Test Category",
            category_type="MEN",
        )
        self.color = ColorVariant.objects.create(color_name="Red")
        self.size = SizeVariant.objects.create(size_name="L")

    def create_product(self, **overrides):
        values = {
            "product_name": "Test Product",
            "price": "100.00",
            "product_description": "A nice test product.",
            "category": self.category,
        }
        values.update(overrides)
        return Product.objects.create(**values)

    def test_product_creation_signal(self):
        product = self.create_product()
        product.color_variant.add(self.color)
        product.size_variant.add(self.size)

        doc = ProductSearchDocument.objects.get(product=product)

        self.assertIn("Product Name:\nTest Product", doc.searchable_text)
        self.assertIn("Category:\nTest Category", doc.searchable_text)
        self.assertIn("Description:\nA nice test product.", doc.searchable_text)
        self.assertIn("Color: Red", doc.searchable_text)
        self.assertIn("Size: L", doc.searchable_text)

        self.assertEqual(doc.metadata["product_id"], str(product.pk))
        self.assertEqual(doc.metadata["category"], "Test Category")
        self.assertEqual(doc.metadata["category_type"], "Men")
        self.assertEqual(doc.metadata["gender"], "men")
        self.assertEqual(doc.metadata["price"], 100.0)
        self.assertEqual(doc.metadata["colors"], ["Red"])
        self.assertEqual(doc.metadata["sizes"], ["L"])
        for field in (
            "brand",
            "stock_available",
            "material",
            "style",
            "occasion",
            "season",
            "fit",
        ):
            self.assertIsNone(doc.metadata[field])

    def test_product_update_signal(self):
        product = self.create_product(product_name="Initial Product")

        product.product_name = "Updated Product"
        product.save()

        doc = ProductSearchDocument.objects.get(product=product)
        self.assertIn("Product Name:\nUpdated Product", doc.searchable_text)
        self.assertNotIn("Initial Product", doc.searchable_text)

    def test_partial_product_update_indexes_only_persisted_values(self):
        product = self.create_product(product_name="Persisted Name")
        product.product_name = "Unsaved Name"
        product.product_description = "Persisted description change"

        product.save(update_fields=["product_description"])

        product.refresh_from_db()
        document = ProductSearchDocument.objects.get(product=product)
        self.assertEqual(product.product_name, "Persisted Name")
        self.assertIn("Product Name:\nPersisted Name", document.searchable_text)
        self.assertNotIn("Unsaved Name", document.searchable_text)

    def test_product_deletion(self):
        product = self.create_product(product_name="Delete Me")
        product_id = product.pk

        self.assertTrue(ProductSearchDocument.objects.filter(product=product).exists())

        product.delete()

        self.assertFalse(
            ProductSearchDocument.objects.filter(product_id=product_id).exists()
        )

    def test_build_search_documents_command(self):
        self.create_product(product_name="Command Product 1", price="20.00")
        self.create_product(product_name="Command Product 2", price="30.00")

        ProductSearchDocument.objects.all().delete()

        self.assertEqual(ProductSearchDocument.objects.count(), 0)

        out = StringIO()
        call_command("build_search_documents", stdout=out)

        self.assertEqual(ProductSearchDocument.objects.count(), 2)
        self.assertIn("Successfully generated 2 search documents!", out.getvalue())

    def test_ai_search_app_config_loads_product_signal(self):
        config = apps.get_app_config("ai_search")

        self.assertIsInstance(config, AiSearchConfig)
        self.assertTrue(post_save.has_listeners(Product))

    def test_document_text_removes_html_and_normalizes_whitespace(self):
        product = self.create_product(
            product_description="<p>Soft&nbsp; cotton</p>\n\n winter   layer",
        )

        text = product.search_document.searchable_text

        self.assertNotIn("<p>", text)
        self.assertNotIn("&nbsp;", text)
        self.assertIn("Description:\nSoft cotton winter layer", text)

    def test_document_text_removes_html_encoded_as_entities(self):
        product = self.create_product(
            product_description="&lt;b&gt;Soft&lt;/b&gt; cotton",
        )

        text = product.search_document.searchable_text

        self.assertNotIn("<b>", text)
        self.assertIn("Description:\nSoft cotton", text)

    def test_document_generation_failure_does_not_break_product_creation(self):
        with self.assertLogs("ai_search.signals", level="ERROR"):
            with patch(
                "ai_search.signals.generate_product_document",
                side_effect=RuntimeError("document backend unavailable"),
            ):
                product = self.create_product(product_name="Still Created")

        self.assertTrue(Product.objects.filter(pk=product.pk).exists())
        self.assertFalse(
            ProductSearchDocument.objects.filter(product_id=product.pk).exists()
        )

    def test_document_database_failure_does_not_poison_product_transaction(self):
        def create_invalid_document(product):
            ProductSearchDocument.objects.create(
                product=product,
                searchable_text=None,
            )

        with self.assertLogs("ai_search.services", level="ERROR"):
            with patch(
                "ai_search.services._build_document_data",
                side_effect=create_invalid_document,
            ):
                product = self.create_product(product_name="Transaction Safe")

        self.assertTrue(Product.objects.filter(pk=product.pk).exists())
        self.assertFalse(
            ProductSearchDocument.objects.filter(product_id=product.pk).exists()
        )

    def test_embedding_is_one_to_one_and_dimension_is_fixed(self):
        product = self.create_product()
        document = product.search_document
        ProductEmbedding.objects.create(
            product_document=document,
            model_name="test-model",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductEmbedding.objects.create(
                product_document=document,
                model_name="second-model",
            )

        field = ProductEmbedding._meta.get_field("embedding")
        self.assertEqual(field.dimensions, 768)
        self.assertIsNotNone(ProductEmbedding._meta.get_field("updated_at"))

    def test_embedding_failure_returns_empty_retryable_result(self):
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-key",
                "GEMINI_API_KEY": "",
                "AI_SEARCH_EMBEDDING_PROVIDER": "openai",
            },
            clear=False,
        ):
            service = EmbeddingService()

        with self.assertLogs("ai_search.embeddings", level="ERROR"):
            with patch.object(
                service,
                "_generate_openai_embedding",
                side_effect=RuntimeError("provider unavailable"),
            ):
                embedding, model_name = service.generate_embedding("valid text")

        self.assertIsNone(embedding)
        self.assertEqual(model_name, "text-embedding-3-small")

    def test_embedding_service_initialization_without_keys_is_quiet(self):
        with patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "", "GEMINI_API_KEY": ""},
            clear=False,
        ):
            with self.assertNoLogs("ai_search.embeddings", level="WARNING"):
                EmbeddingService()

    def test_embedding_migration_prefers_older_valid_vector(self):
        migration = import_module(
            "ai_search.migrations.0002_harden_product_embeddings"
        )
        newer_empty = SimpleNamespace(embedding=None)
        older_valid = SimpleNamespace(embedding=[0.0] * 768)

        selected = migration.select_embedding_to_keep(
            [newer_empty, older_valid]
        )

        self.assertIs(selected, older_valid)
