import logging
import time

from ai_search.query_understanding.analyzer import get_query_analyzer
from ai_search.services.retrieval_service import retrieve_products
from ai_assistant.services.context_builder import build_product_context
from ai_assistant.services.llm_provider import get_llm_provider
from ai_assistant.models import Conversation, Message

logger = logging.getLogger(__name__)


def process_chat_message(query: str, conversation: Conversation) -> dict:
    """
    Process a chat message, perform retrieval if necessary, and generate AI response.
    """
    start_time = time.perf_counter()
    timings = {}

    # 1. Fetch conversation history (last 5 messages)
    history = list(conversation.messages.order_by("created_at")[:5])

    # Optional: We could build a combined query here (like "I like black" + "show jackets"),
    # but for simplicity, we pass the raw query to the QueryAnalyzer. The analyzer might just 
    # extract the current query's intent, and the LLM will see the history anyway. 
    # To truly use memory for retrieval, we'd augment the query before retrieval.
    # We will just append the last few messages' content if they are from the user, to give context
    # to the analyzer. But the instructions say "Use previous messages as context... Next query: show me jackets -> Assistant should understand black".
    # Since our retrieval engine only sees the string passed to it, we can construct a context-aware query for retrieval.
    context_aware_query = query
    recent_user_msgs = [m for m in history if m.role == "USER"]
    if recent_user_msgs:
        # Just prepend the last user message to give some context to the analyzer/retriever
        # e.g., "I like black color. show me jackets"
        context_aware_query = f"{recent_user_msgs[-1].content}. {query}"

    # 2. Query Understanding (using existing retriever, which calls analyzer internally)
    # The instructions say: "Send query to existing QueryAnalyzer -> Run existing Hybrid Retrieval Engine"
    # Actually, retrieve_products(query) does both!
    retrieval_start = time.perf_counter()
    
    retrieval_results = {"analysis": {}, "results": []}
    try:
        retrieval_results = retrieve_products(context_aware_query, limit=5)
    except Exception as e:
        logger.error(f"Retrieval failed: {e}", exc_info=True)
        # We can still proceed without products if retrieval fails
    
    timings["retrieval_time_ms"] = round((time.perf_counter() - retrieval_start) * 1000, 3)

    intent = retrieval_results.get("analysis", {}).get("intent", "general_question")
    products = retrieval_results.get("results", [])

    # If the intent is purely general_question, we might optionally skip retrieval, but
    # the instructions say: "Retrieve mentioned products and compare" or "Answer without product retrieval".
    # retrieve_products handles returning results regardless. We just pass them to the LLM.

    # 3. Build Context
    context_start = time.perf_counter()
    context = build_product_context(products)
    timings["context_build_time_ms"] = round((time.perf_counter() - context_start) * 1000, 3)

    # 4. Generate Response
    llm_start = time.perf_counter()
    try:
        provider = get_llm_provider()
        response_text = provider.generate_response(query, context, history)
    except Exception as e:
        logger.error(f"LLM generation failed: {e}", exc_info=True)
        response_text = "I found these products that match your request."
    
    timings["llm_generation_time_ms"] = round((time.perf_counter() - llm_start) * 1000, 3)
    timings["total_time_ms"] = round((time.perf_counter() - start_time) * 1000, 3)

    return {
        "message": response_text,
        "products": products,
        "timings": timings,
        "analysis": retrieval_results.get("analysis", {})
    }
