import json
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client
from django.urls import reverse

from ai_assistant.models import Conversation, Message, ChatRequestLog
from ai_assistant.services.context_builder import build_product_context
from ai_assistant.services.llm_provider import GeminiLLMProvider, get_llm_provider
from ai_assistant.services.intent_router import IntentRouter


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
                    "description": "Cotton winter hoodie"
                }
            }
        ]
        context = build_product_context(products)
        self.assertIn("Premium Black Hoodie", context)
        self.assertIn("Men Hoodie", context)
        self.assertIn("2500", context)
        self.assertIn("Black", context)
        self.assertIn("M, L, XL", context)
        self.assertIn("Nike", context)
        self.assertIn("4.5/5", context)
        self.assertIn("Yes", context)
        self.assertIn("Cotton winter hoodie", context)

    def test_empty_products(self):
        self.assertEqual(build_product_context([]), "No products found.")
        
    def test_max_product_limit(self):
        products = [{"name": f"Product {i}"} for i in range(10)]
        context = build_product_context(products, max_products=5)
        self.assertIn("Product 1", context)
        self.assertNotIn("Product 6", context)


class LLMProviderTests(TestCase):
    def test_provider_singleton(self):
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test_key"}):
            provider1 = get_llm_provider()
            provider2 = get_llm_provider()
            self.assertIs(provider1, provider2)


class IntentRouterTests(TestCase):
    def test_product_search(self):
        config = IntentRouter.route_request("product_search")
        self.assertTrue(config["should_retrieve"])
        self.assertEqual(config["system_instruction_append"], "")

    def test_general_question(self):
        config = IntentRouter.route_request("general_question")
        self.assertFalse(config["should_retrieve"])
        self.assertNotEqual(config["system_instruction_append"], "")


class ChatServiceTests(TestCase):
    @patch('ai_assistant.services.chat_service.get_query_analyzer')
    @patch('ai_assistant.services.chat_service.retrieve_products')
    @patch('ai_assistant.services.chat_service.get_llm_provider')
    def test_chat_service_flow(self, mock_get_llm, mock_retrieve, mock_get_analyzer):
        from ai_assistant.services.chat_service import process_chat_message
        
        mock_analyzer = MagicMock()
        mock_analysis = MagicMock()
        mock_analysis.intent = "product_search"
        mock_analysis.model_dump.return_value = {"intent": "product_search"}
        mock_analyzer.analyze.return_value = mock_analysis
        mock_get_analyzer.return_value = mock_analyzer

        mock_retrieve.return_value = {
            "analysis": {"intent": "product_search"},
            "results": [{"name": "Mock Product", "price": 100}]
        }
        mock_provider = MagicMock()
        mock_provider.generate_response.return_value = "Mock LLM Response"
        mock_get_llm.return_value = mock_provider

        conversation = Conversation.objects.create(session_id="test_session")
        
        result = process_chat_message("test query", conversation)
        
        self.assertEqual(result["message"], "Mock LLM Response")
        self.assertEqual(len(result["products"]), 1)
        mock_retrieve.assert_called_once()
        mock_provider.generate_response.assert_called_once()
        
        # Check ChatRequestLog creation
        self.assertEqual(ChatRequestLog.objects.count(), 1)


class APITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('ai_assistant:chat')

    @patch('ai_assistant.views.process_chat_message')
    def test_api_success(self, mock_process):
        mock_process.return_value = {
            "message": "Assistant reply",
            "products": [{"id": 1, "name": "Item", "price": 100}],
            "timings": {},
            "prompt_version": "v2",
            "intent": "product_search"
        }
        
        response = self.client.post(
            self.url,
            data=json.dumps({"message": "test message"}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["answer"], "Assistant reply")
        self.assertTrue("conversation_id" in data)
        self.assertEqual(len(data["products"]), 1)

        # Check memory saved
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(Message.objects.count(), 2) # 1 user, 1 assistant

    def test_api_empty_query(self):
        response = self.client.post(
            self.url,
            data=json.dumps({"message": ""}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_api_length_limit(self):
        response = self.client.post(
            self.url,
            data=json.dumps({"message": "A" * 501}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

