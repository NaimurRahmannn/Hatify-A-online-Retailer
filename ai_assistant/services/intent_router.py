class IntentRouter:
    """Routes the user request based on the identified intent."""
    
    @staticmethod
    def route_request(intent: str) -> dict:
        """
        Returns routing configuration based on intent.
        
        Returns:
            dict: {
                "should_retrieve": bool,
                "system_instruction_append": str,
            }
        """
        intent = (intent or "general_question").lower()

        if intent == "product_search":
            return {
                "should_retrieve": True,
                "system_instruction_append": ""
            }
        elif intent == "comparison":
            return {
                "should_retrieve": True,
                "system_instruction_append": "Compare the features, prices, and styles of the retrieved products."
            }
        elif intent == "recommendation":
            # Future placeholder for a recommendation engine. For now, use hybrid retrieval.
            return {
                "should_retrieve": True,
                "system_instruction_append": "Recommend the best product among these options based on the user's implicit preferences."
            }
        elif intent == "general_question":
            return {
                "should_retrieve": False,
                "system_instruction_append": "Answer the general question based on your fashion expertise. Do not invent Haatify products."
            }
        else:
            # Fallback
            return {
                "should_retrieve": True,
                "system_instruction_append": ""
            }
