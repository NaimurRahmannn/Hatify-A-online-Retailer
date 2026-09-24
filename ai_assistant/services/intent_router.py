"""Intent-based routing for the AI Assistant pipeline.

Maps the ``intent`` extracted by QueryAnalysis to a routing
configuration that tells the chat service whether to invoke the
Hybrid Retrieval Engine and what additional LLM instructions to
append.
"""

from ai_assistant.services.recommendation_service import RecommendationService


class IntentRouter:
    """Routes the user request based on the identified intent."""

    @staticmethod
    def route_request(intent: str) -> dict:
        """Return routing configuration for the given intent.

        Returns:
            dict: {
                "should_retrieve": bool,
                "system_instruction_append": str,
                "recommendation_response": dict | None,
            }
        """
        intent = (intent or "general_question").lower()

        if intent == "product_search":
            return {
                "should_retrieve": True,
                "system_instruction_append": "",
                "recommendation_response": None,
            }

        if intent == "comparison":
            return {
                "should_retrieve": True,
                "system_instruction_append": (
                    "Compare the features, prices, and styles of the "
                    "retrieved products."
                ),
                "recommendation_response": None,
            }

        if intent == "recommendation":
            # Delegate to the RecommendationService placeholder.
            rec = RecommendationService.recommend("")
            if rec["available"]:
                # Future: when the engine is live, return its products.
                return {
                    "should_retrieve": False,
                    "system_instruction_append": "",
                    "recommendation_response": rec,
                }
            # Engine not ready – fall back to hybrid retrieval.
            return {
                "should_retrieve": True,
                "system_instruction_append": (
                    "The personalized recommendation engine is not yet "
                    "available. Use the retrieved products to suggest "
                    "the best options based on the user's query."
                ),
                "recommendation_response": rec,
            }

        if intent == "general_question":
            return {
                "should_retrieve": False,
                "system_instruction_append": (
                    "Answer the general question based on your fashion "
                    "expertise. Do not invent Haatify products."
                ),
                "recommendation_response": None,
            }

        # Fallback for unknown intents
        return {
            "should_retrieve": True,
            "system_instruction_append": "",
            "recommendation_response": None,
        }
