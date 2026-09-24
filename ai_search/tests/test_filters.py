"""
Tests for metadata filtering logic.
"""

from django.test import TestCase

from ai_search.filters.metadata import apply_metadata_filters
from ai_search.models import ProductSearchDocument
from ai_search.query_understanding.schemas import QueryAnalysis
from ai_search.tests.helpers import make_product


class MetadataFilterTests(TestCase):
    def setUp(self):
        self.p1 = make_product(product_name="Black Hoodie", price="2500.00")
        self.p2 = make_product(product_name="White Shirt", price="1500.00")
        self.p3 = make_product(product_name="Running Shoes", price="6000.00")
        
        # Manually adjust metadata to simulate indexing
        doc1 = self.p1.search_document
        doc1.metadata["price"] = 2500.00
        doc1.metadata["category"] = "hoodie"
        doc1.metadata["colors"] = ["black"]
        doc1.save()

        doc2 = self.p2.search_document
        doc2.metadata["price"] = 1500.00
        doc2.metadata["category"] = "shirt"
        doc2.metadata["colors"] = ["white"]
        doc2.save()

        doc3 = self.p3.search_document
        doc3.metadata["price"] = 6000.00
        doc3.metadata["category"] = "shoes"
        doc3.metadata["colors"] = ["white", "blue"]
        doc3.save()

    def test_filter_price_max(self):
        qs = ProductSearchDocument.objects.all()
        analysis = QueryAnalysis(original_query="under 3000", price_max=3000.0)
        filtered = apply_metadata_filters(qs, analysis)
        self.assertEqual(filtered.count(), 2)
        pks = [d.product.pk for d in filtered]
        self.assertIn(self.p1.pk, pks)
        self.assertIn(self.p2.pk, pks)
        self.assertNotIn(self.p3.pk, pks)

    def test_filter_category(self):
        qs = ProductSearchDocument.objects.all()
        analysis = QueryAnalysis(original_query="shirt", category="shirt")
        filtered = apply_metadata_filters(qs, analysis)
        self.assertEqual(filtered.count(), 1)
        self.assertEqual(filtered.first().product.pk, self.p2.pk)

    def test_filter_color(self):
        qs = ProductSearchDocument.objects.all()
        analysis = QueryAnalysis(original_query="white", colors=["white"])
        filtered = apply_metadata_filters(qs, analysis)
        self.assertEqual(filtered.count(), 2)
        pks = [d.product.pk for d in filtered]
        self.assertIn(self.p2.pk, pks)
        self.assertIn(self.p3.pk, pks)

    def test_combined_filters(self):
        qs = ProductSearchDocument.objects.all()
        analysis = QueryAnalysis(original_query="white shirt under 2000", colors=["white"], category="shirt", price_max=2000.0)
        filtered = apply_metadata_filters(qs, analysis)
        self.assertEqual(filtered.count(), 1)
        self.assertEqual(filtered.first().product.pk, self.p2.pk)
