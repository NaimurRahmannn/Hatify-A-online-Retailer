import json
import os
import logging
from unittest.mock import patch, MagicMock

from django.conf import settings
from ai_assistant.services.chat_service import process_chat_message
from ai_assistant.models import Conversation

logger = logging.getLogger(__name__)

class RAGEvaluator:
    def __init__(self, dataset_path: str = None):
        if not dataset_path:
            dataset_path = os.path.join(settings.BASE_DIR, "ai_assistant", "evaluation", "dataset.json")
        with open(dataset_path, "r") as f:
            self.dataset = json.load(f)

    @patch('ai_assistant.services.llm_provider.GeminiLLMProvider.generate_response')
    def evaluate(self, mock_generate_response):
        """
        Run the dataset through the chat service to evaluate retrieval and context.
        Mock the LLM to test deterministic retrieval without incurring API costs.
        """
        results = []
        for case in self.dataset:
            query = case["query"]
            
            # Setup a temporary conversation
            conversation = Conversation.objects.create(session_id="eval_session")
            
            # Setup mock response
            mock_generate_response.return_value = "Mocked LLM Response for evaluation."
            
            try:
                # Process
                result = process_chat_message(query, conversation)
                
                # Check retrieval relevance
                retrieved_names = [p.get("name", "") if isinstance(p, dict) else p.document.name for p in result["products"]]
                
                matched_products = [ep for ep in case["expected_products"] if any(ep.lower() in rn.lower() for rn in retrieved_names)]
                retrieval_score = len(matched_products) / len(case["expected_products"]) if case["expected_products"] else 1.0
                
                results.append({
                    "query": query,
                    "retrieval_score": retrieval_score,
                    "retrieved_products": retrieved_names,
                    "timings": result["timings"]
                })
            except Exception as e:
                logger.error(f"Eval failed for query: {query}", exc_info=True)
                results.append({"query": query, "error": str(e)})
                
        return results

    def print_report(self, results):
        print("=== RAG Evaluation Report ===")
        for res in results:
            print(f"Query: {res.get('query')}")
            if "error" in res:
                print(f"  Error: {res['error']}")
            else:
                print(f"  Retrieval Score: {res['retrieval_score'] * 100}%")
                print(f"  Retrieved: {res['retrieved_products']}")
            print("-" * 20)
