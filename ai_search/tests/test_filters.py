"""
Tests for metadata filtering logic.
"""

from unittest import skipUnless

from django.db import connection
from django.test import SimpleTestCase, TestCase

from ai_search.filters.metadata import apply_metadata_filters
from ai_search.models import ProductSearchDocument
from ai_search.query_understanding.schemas import QueryAnalysis
from ai_search.tests.helpers import make_product


class RecordingQuerySet:
    def __init__(self):
        self.filter_args = ()

    def filter(self, *args, **kwargs):
        self.filter_args = args
        return self


class MetadataFilterQueryTests(SimpleTestCase):
    def test_color_filter_uses_exact_json_array_containment(self):
        queryset = RecordingQuerySet()

        apply_metadata_filters(
            queryset,
            QueryAnalysis(original_query="black", colors=["Black"]),
        )

        emitted = repr(queryset.filter_args)
        self.assertIn("metadata__contains", emitted)
        self.assertIn("{'colors': ['black']}", emitted)
        self.assertNotIn("icontains", emitted)

    def test_size_filter_uses_exact_json_array_containment(self):
        queryset = RecordingQuerySet()

        apply_metadata_filters(
            queryset,
            QueryAnalysis(original_query="size xl", sizes=["xl"]),
        )

        emitted = repr(queryset.filter_args)
        self.assertIn("metadata__contains", emitted)
        self.assertIn("{'sizes': ['XL']}", emitted)

    def test_scalar_filters_use_case_insensitive_exact_lookups(self):
        queryset = RecordingQuerySet()

        apply_metadata_filters(
            queryset,
            QueryAnalysis(
                original_query="nike hoodie",
                category="hoodie",
                brand="Nike",
                gender="men",
            ),
        )

        emitted = repr(queryset.filter_args)
        self.assertIn("metadata__category__iexact", emitted)
        self.assertIn("metadata__brand__iexact", emitted)
        self.assertIn("metadata__gender__iexact", emitted)
        self.assertNotIn("icontains", emitted)


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

    @skipUnless(connection.vendor == "postgresql", "PostgreSQL JSONB required")
    def test_filter_color(self):
        qs = ProductSearchDocument.objects.all()
        analysis = QueryAnalysis(original_query="white", colors=["white"])
        filtered = apply_metadata_filters(qs, analysis)
        self.assertEqual(filtered.count(), 2)
        pks = [d.product.pk for d in filtered]
        self.assertIn(self.p2.pk, pks)
        self.assertIn(self.p3.pk, pks)

    @skipUnless(connection.vendor == "postgresql", "PostgreSQL JSONB required")
    def test_combined_filters(self):
        qs = ProductSearchDocument.objects.all()
        analysis = QueryAnalysis(original_query="white shirt under 2000", colors=["white"], category="shirt", price_max=2000.0)
        filtered = apply_metadata_filters(qs, analysis)
        self.assertEqual(filtered.count(), 1)
        self.assertEqual(filtered.first().product.pk, self.p2.pk)


@skipUnless(connection.vendor == "postgresql", "PostgreSQL JSONB required")
class PostgreSQLMetadataContainmentTests(TestCase):
    def test_black_does_not_match_blackberry(self):
        black = make_product(product_name="Black Hoodie")
        blackberry = make_product(product_name="Blackberry Jacket")

        black_doc = black.search_document
        black_doc.metadata["colors"] = ["black"]
        black_doc.save(update_fields=["metadata"])

        blackberry_doc = blackberry.search_document
        blackberry_doc.metadata["colors"] = ["blackberry"]
        blackberry_doc.save(update_fields=["metadata"])

        filtered = apply_metadata_filters(
            ProductSearchDocument.objects.all(),
            QueryAnalysis(original_query="black", colors=["black"]),
        )

        product_ids = set(filtered.values_list("product_id", flat=True))
        self.assertEqual(product_ids, {black.pk})
