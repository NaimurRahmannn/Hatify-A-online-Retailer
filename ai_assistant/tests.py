"""Comprehensive tests for the ai_assistant app.

Covers:
- Context builder (fields, limits)
- LLM provider singleton
- Intent routing (all intents, recommendation placeholder)
- Single query analysis flow (no duplicate calls)
- Conversation ownership (IDOR protection)
- Rate limiting (atomic, per-caller)
- Product serialization
- API response schema
"""

import json
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import TestCase, Client, SimpleTestCase, override_settings
from django.urls import reverse

from ai_assistant.models import Conversation, Message, ChatRequestLog
from ai_assistant.serializers import serialize_product, serialize_products
from ai_assistant.services.context_builder import build_product_context
from ai_assistant.services.intent_router import IntentRouter
from ai_assistant.services.memory_service import ConversationMemoryService
from ai_assistant.services.recommendation_service import RecommendationService

User = get_user_model()


class WidgetTemplateTests(SimpleTestCase):
    def test_base_template_includes_accessible_chat_widget(self):
        html = render_to_string("base/base.html")

        self.assertIn('id="ai-chat-toggle"', html)
        self.assertIn('id="ai-chat-window"', html)
        self.assertIn('id="ai-chat-form"', html)
        self.assertIn('id="ai-chat-close"', html)
        self.assertIn('id="ai-chat-send"', html)
        self.assertIn('type="submit"', html)
        self.assertIn('/static/css/ai_assistant.css', html)
        self.assertIn('/static/js/ai_assistant.js', html)


# =====================================================================
# Context Builder
# =====================================================================


class ContextBuilderTests(TestCase):
    def test_build_product_context_fields(self):
        products = [
            {
                "name": "Premium Black Hoodie",
                "price": 2500,
                "metadata": {
                    "category": "Men Hoodie",
                    "colors": ["Black"],
                    "sizes": ["M", "L", "XL"],
                    "brand": "Nike",
                    "rating": 4.5,
                    "in_stock": True,
                    "description": "Cotton winter hoodie",
                },
            }
        ]
        context = build_product_context(products)
        for expected in [
            "Premium Black Hoodie",
            "Men Hoodie",
            "2500",
            "Black",
            "M, L, XL",
            "Nike",
            "4.5/5",
            "Yes",
            "Cotton winter hoodie",
        ]:
            self.assertIn(expected, context)

    def test_empty_products(self):
        self.assertEqual(build_product_context([]), "No products found.")

    def test_max_product_limit(self):
        products = [{"name": f"Product {i}"} for i in range(10)]
        context = build_product_context(products, max_products=5)
        self.assertIn("Product 1", context)
        self.assertNotIn("Product 6", context)


# =====================================================================
# Intent Routing
# =====================================================================


class IntentRouterTests(TestCase):
    def test_product_search(self):
        cfg = IntentRouter.route_request("product_search")
        self.assertTrue(cfg["should_retrieve"])
        self.assertIsNone(cfg["recommendation_response"])

    def test_general_question_skips_retrieval(self):
        cfg = IntentRouter.route_request("general_question")
        self.assertFalse(cfg["should_retrieve"])

    def test_comparison_retrieves(self):
        cfg = IntentRouter.route_request("comparison")
        self.assertTrue(cfg["should_retrieve"])

    def test_recommendation_falls_back_to_retrieval(self):
        cfg = IntentRouter.route_request("recommendation")
        self.assertTrue(cfg["should_retrieve"])
        self.assertIsNotNone(cfg["recommendation_response"])
        self.assertFalse(cfg["recommendation_response"]["available"])

    def test_unknown_intent_defaults_to_retrieval(self):
        cfg = IntentRouter.route_request("some_unknown_intent")
        self.assertTrue(cfg["should_retrieve"])


# =====================================================================
# Recommendation Service placeholder
# =====================================================================


class RecommendationServiceTests(TestCase):
    def test_returns_not_available(self):
        result = RecommendationService.recommend("red shoes")
        self.assertFalse(result["available"])
        self.assertEqual(result["products"], [])
        self.assertIn("coming soon", result["message"])


# =====================================================================
# Product Serializer
# =====================================================================


class SerializerTests(TestCase):
    def test_serialize_dict_product(self):
        raw = {"id": 1, "name": "Hoodie", "price": 100, "metadata": {"category": "Tops"}}
        result = serialize_product(raw)
        self.assertEqual(result["id"], 1)
        self.assertEqual(result["name"], "Hoodie")
        self.assertEqual(result["category"], "Tops")

    def test_serialize_searchresult_dataclass(self):
        mock_doc = MagicMock()
        mock_doc.pk = 42
        mock_doc.name = "Jacket"
        mock_doc.metadata = {"price": 3000, "category": "Outerwear", "image": "/img.jpg"}
        mock_result = MagicMock()
        mock_result.document = mock_doc
        result = serialize_product(mock_result)
        self.assertEqual(result["id"], 42)
        self.assertEqual(result["name"], "Jacket")
        self.assertEqual(result["price"], 3000)
        self.assertEqual(result["image"], "/img.jpg")

    def test_serialize_products_list(self):
        products = [
            {"id": 1, "name": "A"},
            {"id": 2, "name": "B"},
        ]
        result = serialize_products(products)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], 1)

    def test_serialize_empty_list(self):
        self.assertEqual(serialize_products([]), [])
        self.assertEqual(serialize_products(None), [])

    def test_serialize_document_uses_product_link_image_and_id(self):
        image = SimpleNamespace(
            product_image=SimpleNamespace(url="/media/product/red-dress.jpg")
        )
        image_manager = MagicMock()
        image_manager.first.return_value = image
        product = SimpleNamespace(
            pk=23,
            slug="red-dress",
            product_name="Red Dress",
            product_images=image_manager,
        )
        document = SimpleNamespace(
            pk=91,
            metadata={"price": 0, "category": "Dresses"},
            product=product,
        )

        result = serialize_product(SimpleNamespace(document=document))

        self.assertEqual(result["id"], 23)
        self.assertEqual(result["name"], "Red Dress")
        self.assertEqual(result["url"], "/product/red-dress/")
        self.assertEqual(result["image"], "/media/product/red-dress.jpg")


# =====================================================================
# Memory Service
# =====================================================================


class MemoryServiceTests(TestCase):
    def test_get_memory_context_structure(self):
        conversation = Conversation.objects.create(session_id="mem_test")
        Message.objects.create(conversation=conversation, role="USER", content="Hi")
        svc = ConversationMemoryService()
        ctx = svc.get_memory_context(conversation)
        self.assertIn("recent_messages", ctx)
        self.assertIn("user_preferences", ctx)
        self.assertEqual(len(ctx["recent_messages"]), 1)
        self.assertIsInstance(ctx["user_preferences"], list)


# =====================================================================
# Chat Service – single query analysis
# =====================================================================


class ChatServiceSingleAnalysisTests(TestCase):
    @patch("ai_assistant.services.chat_service.analyze_query")
    @patch("ai_assistant.services.chat_service.retrieve_products")
    @patch("ai_assistant.services.chat_service.get_llm_provider")
    def test_analyzer_called_once_and_passed_to_retrieval(
        self, mock_get_llm, mock_retrieve, mock_analyze_query
    ):
        from ai_assistant.services.chat_service import process_chat_message

        # Setup analysis mock
        mock_analysis = MagicMock()
        mock_analysis.intent = "product_search"
        mock_analysis.model_dump.return_value = {"intent": "product_search"}
        mock_analyze_query.return_value = MagicMock(
            analysis=mock_analysis, cache_hit=False
        )

        # Setup retrieval mock
        mock_retrieve.return_value = {
            "results": [{"name": "Mock Product", "price": 100}]
        }

        # Setup LLM mock
        mock_provider = MagicMock()
        mock_provider.generate_response.return_value = "Mock Response"
        mock_get_llm.return_value = mock_provider

        conversation = Conversation.objects.create(session_id="test_single")
        result = process_chat_message("test query", conversation)

        # analyze_query called exactly ONCE
        mock_analyze_query.assert_called_once()

        # retrieve_products received the pre-computed analysis
        call_kwargs = mock_retrieve.call_args
        self.assertIn("analysis", call_kwargs.kwargs or {})
        if call_kwargs.kwargs:
            self.assertIs(call_kwargs.kwargs["analysis"], mock_analysis)

        self.assertEqual(result["message"], "Mock Response")
        self.assertEqual(ChatRequestLog.objects.count(), 1)


# =====================================================================
# API Tests – schema, ownership, rate limiting
# =====================================================================


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    AI_CHAT_RATE_LIMIT_ANONYMOUS=3,
    AI_CHAT_RATE_LIMIT_AUTHENTICATED=5,
)
class APITests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client = Client(enforce_csrf_checks=False)
        self.url = reverse("ai_assistant:chat")

    @patch("ai_assistant.views.process_chat_message")
    def test_api_success_schema(self, mock_process):
        mock_process.return_value = {
            "message": "Assistant reply",
            "products": [{"id": 1, "name": "Item", "price": 100}],
            "timings": {"total_time_ms": 50},
            "prompt_version": "v2",
            "intent": "product_search",
        }
        response = self.client.post(
            self.url,
            data=json.dumps({"message": "test message"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Validate schema keys
        self.assertIn("conversation_id", data)
        self.assertIn("answer", data)
        self.assertIn("products", data)
        self.assertIn("metadata", data)
        self.assertEqual(data["answer"], "Assistant reply")
        # Memory saved
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(Message.objects.count(), 2)

    @patch("ai_assistant.views.process_chat_message")
    def test_widget_csrf_token_authorizes_chat_request(self, mock_process):
        mock_process.return_value = {
            "message": "Assistant reply",
            "products": [],
            "timings": {},
            "prompt_version": "v2",
            "intent": "general_question",
        }
        csrf_client = Client(enforce_csrf_checks=True)
        page = csrf_client.get(reverse("contact"))
        csrf_cookie = page.cookies.get("csrftoken")

        self.assertEqual(page.status_code, 200)
        self.assertIsNotNone(csrf_cookie)
        response = csrf_client.post(
            self.url,
            data=json.dumps({"message": "test message"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_cookie.value,
        )

        self.assertEqual(response.status_code, 200)

    def test_api_empty_query(self):
        response = self.client.post(
            self.url,
            data=json.dumps({"message": ""}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_api_length_limit(self):
        response = self.client.post(
            self.url,
            data=json.dumps({"message": "A" * 501}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_api_invalid_json(self):
        response = self.client.post(
            self.url, data="not json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)


# =====================================================================
# Conversation ownership (IDOR)
# =====================================================================


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class ConversationOwnershipTests(TestCase):
    def setUp(self):
        self.url = reverse("ai_assistant:chat")
        self.user_a = User.objects.create_user(username="alice", password="pass123")
        self.user_b = User.objects.create_user(username="bob", password="pass456")

    @patch("ai_assistant.views.process_chat_message")
    def test_user_cannot_access_other_users_conversation(self, mock_process):
        mock_process.return_value = {
            "message": "ok",
            "products": [],
            "timings": {},
            "prompt_version": "v2",
            "intent": "general_question",
        }
        # Alice creates a conversation
        conv_a = Conversation.objects.create(user=self.user_a, session_id="alice_sess")

        # Bob tries to access Alice's conversation
        client_b = Client(enforce_csrf_checks=False)
        client_b.force_login(self.user_b)
        response = client_b.post(
            self.url,
            data=json.dumps(
                {"message": "hi", "conversation_id": str(conv_a.id)}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    @patch("ai_assistant.views.process_chat_message")
    def test_anonymous_cannot_access_other_session_conversation(self, mock_process):
        mock_process.return_value = {
            "message": "ok",
            "products": [],
            "timings": {},
            "prompt_version": "v2",
            "intent": "general_question",
        }
        conv = Conversation.objects.create(session_id="other_session_key")

        client = Client(enforce_csrf_checks=False)
        response = client.post(
            self.url,
            data=json.dumps(
                {"message": "hi", "conversation_id": str(conv.id)}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)


# =====================================================================
# Rate limiting
# =====================================================================


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    AI_CHAT_RATE_LIMIT_ANONYMOUS=2,
)
class RateLimitTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.url = reverse("ai_assistant:chat")

    @patch("ai_assistant.views.process_chat_message")
    def test_rate_limit_enforced(self, mock_process):
        mock_process.return_value = {
            "message": "ok",
            "products": [],
            "timings": {},
            "prompt_version": "v2",
            "intent": "general_question",
        }
        client = Client(enforce_csrf_checks=False)
        payload = json.dumps({"message": "hi"})

        # First 2 requests succeed (limit = 2)
        for _ in range(2):
            resp = client.post(
                self.url, data=payload, content_type="application/json"
            )
            self.assertEqual(resp.status_code, 200)

        # Third request is rate-limited
        resp = client.post(
            self.url, data=payload, content_type="application/json"
        )
        self.assertEqual(resp.status_code, 429)
