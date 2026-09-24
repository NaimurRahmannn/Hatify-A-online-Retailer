"""
Tests for the search API endpoint.
"""

import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from ai_search.services.retrieval_service import SearchResult
from ai_search.tests.helpers import make_product


class SearchAPITests(TestCase):
    """Tests for POST /api/ai-search/."""

    def setUp(self):
        self.url = "/api/ai-search/"
        self.product = make_product(product_name="Black Hoodie", price="2500.00")

    def _post(self, data, content_type="application/json"):
        return self.client.post(
            self.url,
            data=json.dumps(data) if isinstance(data, dict) else data,
            content_type=content_type,
        )

    @patch("ai_search.views.retrieve_products")
    def test_successful_search(self, mock_retrieve):
        doc = self.product.search_document
        mock_retrieve.return_value = {
            "analysis": {"category": "hoodie", "color": "black"},
            "results": [
                SearchResult(
                    document=doc,
                    keyword_score=0.85,
                    semantic_score=0.91,
                    final_score=0.88,
                ),
            ]
        }

        response = self._post({"query": "black hoodie"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["results"]), 1)

        result = data["results"][0]
        self.assertEqual(result["name"], "Black Hoodie")
        self.assertEqual(result["price"], "2500.00")
        self.assertEqual(result["keyword_score"], 0.85)
        self.assertEqual(result["semantic_score"], 0.91)
        self.assertEqual(result["final_score"], 0.88)

    @patch("ai_search.views.retrieve_products")
    def test_empty_results(self, mock_retrieve):
        mock_retrieve.return_value = {"analysis": {}, "results": []}

        response = self._post({"query": "nonexistent product"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])

    def test_malformed_json_returns_400(self):
        response = self.client.post(
            self.url,
            data="not json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_missing_query_returns_400(self):
        response = self._post({})
        self.assertEqual(response.status_code, 400)

    def test_empty_query_returns_400(self):
        response = self._post({"query": ""})
        self.assertEqual(response.status_code, 400)

    def test_non_string_query_returns_400(self):
        response = self._post({"query": 123})
        self.assertEqual(response.status_code, 400)

    def test_query_too_long_returns_400(self):
        response = self._post({"query": "x" * 501})
        self.assertEqual(response.status_code, 400)

    def test_invalid_limit_type_returns_400(self):
        response = self._post({"query": "test", "limit": "ten"})
        self.assertEqual(response.status_code, 400)

    def test_limit_too_low_returns_400(self):
        response = self._post({"query": "test", "limit": 0})
        self.assertEqual(response.status_code, 400)

    def test_limit_too_high_returns_400(self):
        response = self._post({"query": "test", "limit": 100})
        self.assertEqual(response.status_code, 400)

    @patch("ai_search.views.retrieve_products")
    def test_valid_limit_accepted(self, mock_retrieve):
        mock_retrieve.return_value = {"analysis": {}, "results": []}

        response = self._post({"query": "test", "limit": 5})
        self.assertEqual(response.status_code, 200)
        mock_retrieve.assert_called_once_with("test", limit=5)

    def test_get_method_not_allowed(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    @patch(
        "ai_search.views.retrieve_products",
        side_effect=Exception("unexpected"),
    )
    def test_internal_error_returns_500(self, mock_retrieve):
        response = self._post({"query": "test"})
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertIn("error", data)
        # Must not expose exception details.
        self.assertNotIn("unexpected", data["error"])

    @patch("ai_search.views.retrieve_products")
    def test_price_serialized_as_decimal_string(self, mock_retrieve):
        doc = self.product.search_document
        mock_retrieve.return_value = {
            "analysis": {},
            "results": [
                SearchResult(document=doc, final_score=0.9),
            ]
        }

        response = self._post({"query": "test"})
        result = response.json()["results"][0]

        # Price must be a string, not a float.
        self.assertIsInstance(result["price"], str)
        self.assertEqual(result["price"], "2500.00")

    @patch("ai_search.views.retrieve_products")
    def test_product_id_is_string(self, mock_retrieve):
        doc = self.product.search_document
        mock_retrieve.return_value = {
            "analysis": {},
            "results": [
                SearchResult(document=doc, final_score=0.9),
            ]
        }

        response = self._post({"query": "test"})
        result = response.json()["results"][0]
        self.assertIsInstance(result["id"], str)
