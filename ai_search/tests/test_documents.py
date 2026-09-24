"""
Tests for product document generation — preserves all Sprint 1 behavior.
"""

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
from ai_search.models import (
    EmbeddingStatus,
    ProductEmbedding,
    ProductSearchDocument,
)
from ai_search.tests.helpers import make_category, make_color, make_product, make_size
from products.models import Product


class ProductDocumentTests(TestCase):
    """Sprint 1 document generation and signal tests."""

    def setUp(self):
        self.category = make_category()
        self.color = make_color()
        self.size = make_size()

    def test_product_creation_signal(self):
        product = make_product(category=self.category)
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
        self.assertEqual(doc.metadata["colors"], ["red"])
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

    def test_filter_metadata_is_canonical_without_changing_display_text(self):
        product = make_product(category=self.category)
        product.color_variant.add(make_color("Black"))
        product.size_variant.add(make_size("xl"))

        doc = ProductSearchDocument.objects.get(product=product)

        self.assertEqual(doc.metadata["colors"], ["black"])
        self.assertEqual(doc.metadata["sizes"], ["XL"])
        self.assertIn("Color: Black", doc.searchable_text)
        self.assertIn("Size: xl", doc.searchable_text)

    def test_product_update_signal(self):
        product = make_product(
            category=self.category, product_name="Initial Product",
        )
        product.product_name = "Updated Product"
        product.save()

        doc = ProductSearchDocument.objects.get(product=product)
        self.assertIn("Product Name:\nUpdated Product", doc.searchable_text)
        self.assertNotIn("Initial Product", doc.searchable_text)

    def test_partial_product_update_indexes_only_persisted_values(self):
        product = make_product(
            category=self.category, product_name="Persisted Name",
        )
        product.product_name = "Unsaved Name"
        product.product_description = "Persisted description change"
        product.save(update_fields=["product_description"])

        product.refresh_from_db()
        document = ProductSearchDocument.objects.get(product=product)
        self.assertEqual(product.product_name, "Persisted Name")
        self.assertIn("Product Name:\nPersisted Name", document.searchable_text)
        self.assertNotIn("Unsaved Name", document.searchable_text)

    def test_product_deletion(self):
        product = make_product(category=self.category, product_name="Delete Me")
        product_id = product.pk

        self.assertTrue(ProductSearchDocument.objects.filter(product=product).exists())
        product.delete()
        self.assertFalse(
            ProductSearchDocument.objects.filter(product_id=product_id).exists()
        )

    def test_build_search_documents_command(self):
        make_product(
            category=self.category, product_name="Command Product 1", price="20.00",
        )
        make_product(
            category=self.category, product_name="Command Product 2", price="30.00",
        )
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
        product = make_product(
            category=self.category,
            product_description="<p>Soft&nbsp; cotton</p>\n\n winter   layer",
        )
        text = product.search_document.searchable_text
        self.assertNotIn("<p>", text)
        self.assertNotIn("&nbsp;", text)
        self.assertIn("Description:\nSoft cotton winter layer", text)

    def test_document_text_removes_html_encoded_as_entities(self):
        product = make_product(
            category=self.category,
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
                product = make_product(
                    category=self.category, product_name="Still Created",
                )

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

        with self.assertLogs(
            "ai_search.services.product_document_service", level="ERROR",
        ):
            with patch(
                "ai_search.services.product_document_service._build_document_data",
                side_effect=create_invalid_document,
            ):
                product = make_product(
                    category=self.category, product_name="Transaction Safe",
                )

        self.assertTrue(Product.objects.filter(pk=product.pk).exists())
        self.assertFalse(
            ProductSearchDocument.objects.filter(product_id=product.pk).exists()
        )

    def test_embedding_is_one_to_one_and_dimension_is_fixed(self):
        product = make_product(category=self.category)
        document = product.search_document
        # The document service creates an embedding row automatically now.
        embedding = document.embedding
        self.assertEqual(embedding.status, EmbeddingStatus.PENDING)

        # Creating a second embedding for the same document must fail.
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductEmbedding.objects.create(
                product_document=document,
                model_name="second-model",
            )

        field = ProductEmbedding._meta.get_field("embedding")
        self.assertEqual(field.dimensions, 768)
        self.assertIsNotNone(ProductEmbedding._meta.get_field("updated_at"))

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


class DocumentSemanticHashTests(TestCase):
    """Sprint 2 content-hash and embedding-state tests."""

    def setUp(self):
        self.category = make_category()

    def test_document_has_embedding_text_and_content_hash(self):
        product = make_product(category=self.category)
        doc = product.search_document

        self.assertTrue(doc.embedding_text)
        self.assertTrue(doc.content_hash)
        self.assertEqual(len(doc.content_hash), 64)

    def test_embedding_text_excludes_price(self):
        product = make_product(category=self.category, price="999.00")
        doc = product.search_document

        self.assertNotIn("999", doc.embedding_text)
        self.assertIn("999", doc.searchable_text)

    def test_price_change_does_not_change_content_hash(self):
        product = make_product(category=self.category, price="100.00")
        doc = product.search_document
        original_hash = doc.content_hash

        product.price = "200.00"
        product.save()

        doc.refresh_from_db()
        self.assertEqual(doc.content_hash, original_hash)

    def test_description_change_updates_content_hash(self):
        product = make_product(
            category=self.category,
            product_description="Original description",
        )
        doc = product.search_document
        original_hash = doc.content_hash

        product.product_description = "Completely new description"
        product.save()

        doc.refresh_from_db()
        self.assertNotEqual(doc.content_hash, original_hash)

    def test_embedding_state_created_as_pending(self):
        product = make_product(category=self.category)
        embedding = product.search_document.embedding
        self.assertEqual(embedding.status, EmbeddingStatus.PENDING)

    def test_description_change_invalidates_ready_embedding(self):
        product = make_product(
            category=self.category,
            product_description="Original",
        )
        doc = product.search_document
        emb = doc.embedding

        # Simulate a ready embedding.
        emb.embedding = [0.1] * 768
        emb.status = EmbeddingStatus.READY
        emb.content_hash = doc.content_hash
        emb.save()

        # Change semantic content.
        product.product_description = "Changed description"
        product.save()

        emb.refresh_from_db()
        self.assertEqual(emb.status, EmbeddingStatus.PENDING)
        self.assertIsNone(emb.embedding)

    def test_price_change_preserves_ready_embedding(self):
        product = make_product(
            category=self.category, price="100.00",
        )
        doc = product.search_document
        emb = doc.embedding

        # Simulate a ready embedding with matching hash and model.
        from django.conf import settings

        config = settings.AI_SEARCH
        emb.embedding = [0.1] * 768
        emb.status = EmbeddingStatus.READY
        emb.content_hash = doc.content_hash
        emb.model_name = config["EMBEDDING_MODEL"]
        emb.save()

        # Only change price.
        product.price = "200.00"
        product.save()

        emb.refresh_from_db()
        self.assertEqual(emb.status, EmbeddingStatus.READY)
        self.assertIsNotNone(emb.embedding)
