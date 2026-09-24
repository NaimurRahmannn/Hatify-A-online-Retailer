"""Tests for anonymous search-query analytics."""

from django.contrib import admin
from django.test import SimpleTestCase

from ai_search.models import SearchQueryLog


class SearchQueryLogModelTests(SimpleTestCase):
    def test_model_has_only_required_analytics_fields(self):
        field_names = {field.name for field in SearchQueryLog._meta.get_fields()}

        self.assertTrue(
            {
                "query",
                "normalized_query",
                "analysis",
                "result_count",
                "execution_time_ms",
                "cache_hit",
                "timings",
                "created_at",
            }.issubset(field_names)
        )
        self.assertNotIn("user", field_names)
        self.assertNotIn("original_query", field_names)
        self.assertNotIn("extracted_filters", field_names)

    def test_normalized_query_is_indexed(self):
        field = SearchQueryLog._meta.get_field("normalized_query")

        self.assertTrue(field.db_index)

    def test_timings_default_is_not_shared(self):
        first = SearchQueryLog()
        second = SearchQueryLog()

        first.timings["total_ms"] = 1.0
        self.assertEqual(second.timings, {})

    def test_admin_exposes_operational_columns(self):
        model_admin = admin.site._registry[SearchQueryLog]

        self.assertTrue(
            {
                "query_preview",
                "result_count",
                "cache_hit",
                "execution_time_ms",
                "created_at",
            }.issubset(set(model_admin.list_display))
        )
