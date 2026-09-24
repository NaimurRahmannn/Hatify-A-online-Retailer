import json
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client
from django.urls import reverse

from ai_assistant.models import Conversation, Message
from ai_assistant.services.context_builder import build_product_context
from ai_assistant.services.llm_provider import GeminiLLMProvider, get_llm_provider


class ContextBuilderTests(TestCase):
    def test_build_product_context(self):
        products = [
            {
                "name": "Premium Black Hoodie",
                "price": 2500,
                "metadata": {
                    "category": "Men Hoodie",
                    "colors": ["Black"],
                    "sizes": ["M", "L", "XL"],
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
        self.assertIn("Cotton winter hoodie", context)

    def test_empty_products(self):
        self.assertEqual(build_product_context([]), "No products found.")


class LLMProviderTests(TestCase):
    @patch('ai_assistant.services.llm_provider.genai.Client')
    def test_gemini_provider(self, mock_client):
        mock_response = MagicMock()
        mock_response.text = "Here is a black hoodie."
        mock_client.return_value.models.generate_content.return_value = mock_response

        with patch.dict("os.environ", {"GEMINI_API_KEY": "test_key"}):
            provider = GeminiLLMProvider()
            response = provider.generate_response("black hoodie", "Context", [])
            self.assertEqual(response, "Here is a black hoodie.")
            mock_client.return_value.models.generate_content.assert_called_once()


class ChatServiceTests(TestCase):
    @patch('ai_assistant.services.chat_service.retrieve_products')
    @patch('ai_assistant.services.chat_service.get_llm_provider')
    def test_chat_service_flow(self, mock_get_llm, mock_retrieve):
        from ai_assistant.services.chat_service import process_chat_message
        
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


class APITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('ai_assistant:chat')

    @patch('ai_assistant.views.process_chat_message')
    def test_api_success(self, mock_process):
        mock_process.return_value = {
            "message": "Assistant reply",
            "products": [{"id": 1, "name": "Item", "price": 100}],
            "timings": {}
        }
        
        response = self.client.post(
            self.url,
            data=json.dumps({"message": "test message"}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["message"], "Assistant reply")
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


class MemoryTests(TestCase):
    @patch('ai_assistant.services.chat_service.retrieve_products')
    @patch('ai_assistant.services.chat_service.get_llm_provider')
    def test_memory_passed_to_llm(self, mock_get_llm, mock_retrieve):
        from ai_assistant.services.chat_service import process_chat_message
        
        mock_retrieve.return_value = {"analysis": {}, "results": []}
        mock_provider = MagicMock()
        mock_provider.generate_response.return_value = "Response"
        mock_get_llm.return_value = mock_provider

        conversation = Conversation.objects.create(session_id="test_session")
        Message.objects.create(conversation=conversation, role="USER", content="I like black")
        Message.objects.create(conversation=conversation, role="ASSISTANT", content="Noted")
        
        process_chat_message("Show me jackets", conversation)
        
        # Check that generate_response received the history
        args, kwargs = mock_provider.generate_response.call_args
        history = args[2]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].content, "I like black")
