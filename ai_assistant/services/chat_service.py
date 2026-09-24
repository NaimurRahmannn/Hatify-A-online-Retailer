import logging
import time

from ai_search.services.retrieval_service import retrieve_products
from ai_search.query_understanding.analyzer import get_query_analyzer
from ai_assistant.services.context_builder import build_product_context
from ai_assistant.services.llm_provider import get_llm_provider
from ai_assistant.services.intent_router import IntentRouter
from ai_assistant.services.memory_service import ConversationMemoryService
from ai_assistant.prompts import SYSTEM_PROMPT_VERSION
from ai_assistant.models import Conversation, ChatRequestLog

logger = logging.getLogger(__name__)


def process_chat_message(query: str, conversation: Conversation) -> dict:
    start_time = time.perf_counter()
    timings = {}

    memory_service = ConversationMemoryService(max_messages=5)
    history = memory_service.get_formatted_history(conversation)
    context_aware_query = memory_service.build_context_aware_query(query, history)

    # Pre-analyze intent if possible, or we could just use retrieve_products
    # We will use the QueryAnalyzer to get the intent FIRST, so we can route.
    analysis_start = time.perf_counter()
    analyzer = get_query_analyzer()
    analysis_result = analyzer.analyze(context_aware_query)
    intent = analysis_result.intent
    timings["analysis_ms"] = round((time.perf_counter() - analysis_start) * 1000, 3)

    route_config = IntentRouter.route_request(intent)

    retrieval_results = {"results": []}
    if route_config["should_retrieve"]:
        retrieval_start = time.perf_counter()
        try:
            # We already analyzed, but retrieve_products does its own analysis. 
            # In a fully optimized system, we'd pass the analysis down, but for now we just call it.
            retrieval_results = retrieve_products(context_aware_query, limit=5)
        except Exception as e:
            logger.error(f"Retrieval failed: {e}", exc_info=True)
        timings["retrieval_time_ms"] = round((time.perf_counter() - retrieval_start) * 1000, 3)

    products = retrieval_results.get("results", [])

    context_start = time.perf_counter()
    context = build_product_context(products)
    timings["context_build_time_ms"] = round((time.perf_counter() - context_start) * 1000, 3)

    llm_start = time.perf_counter()
    try:
        provider = get_llm_provider()
        
        # We can append routing instructions to the context block internally
        if route_config["system_instruction_append"]:
            context += f"\n\nAdditional Instruction: {route_config['system_instruction_append']}"

        response_text = provider.generate_response(query, context, history)
    except Exception as e:
        logger.error(f"LLM generation failed: {e}", exc_info=True)
        if products:
            response_text = "I found these products that match your request."
        else:
            response_text = "I'm having trouble processing that request right now. Please try again later."
    
    timings["llm_generation_time_ms"] = round((time.perf_counter() - llm_start) * 1000, 3)
    timings["total_time_ms"] = round((time.perf_counter() - start_time) * 1000, 3)
    
    ChatRequestLog.objects.create(
        conversation=conversation,
        query=query,
        intent=intent,
        retrieval_time_ms=timings.get("retrieval_time_ms"),
        context_time_ms=timings.get("context_build_time_ms"),
        llm_time_ms=timings.get("llm_generation_time_ms"),
        total_time_ms=timings.get("total_time_ms"),
    )

    # Return structured data for the API and logging
    return {
        "message": response_text,
        "products": products,
        "timings": timings,
        "analysis": analysis_result.model_dump(),
        "prompt_version": SYSTEM_PROMPT_VERSION,
        "intent": intent,
    }
