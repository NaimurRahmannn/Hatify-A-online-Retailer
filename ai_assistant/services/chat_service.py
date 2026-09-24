import logging
import time

from ai_search.services.retrieval_service import retrieve_products
from ai_search.query_understanding import analyze_query
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
    memory_context = memory_service.get_memory_context(conversation)
    history = memory_context["recent_messages"]
    context_aware_query = memory_service.build_context_aware_query(query, history)

    # ------------------------------------------------------------------
    # Single query analysis – the result is passed downstream so that
    # retrieve_products does NOT re-analyse the same query.
    # ------------------------------------------------------------------
    analysis_start = time.perf_counter()
    analysis_result = analyze_query(context_aware_query)
    analysis = analysis_result.analysis
    intent = analysis.intent
    timings["analysis_ms"] = round((time.perf_counter() - analysis_start) * 1000, 3)

    route_config = IntentRouter.route_request(intent)

    retrieval_results = {"results": []}
    if route_config["should_retrieve"]:
        retrieval_start = time.perf_counter()
        try:
            # Pass the pre-computed analysis so retrieval skips its own.
            retrieval_results = retrieve_products(
                context_aware_query, limit=6, analysis=analysis
            )
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

        if route_config["system_instruction_append"]:
            context += f"\n\nAdditional Instruction: {route_config['system_instruction_append']}"

        response_text = provider.generate_response(query, context, history)
    except Exception as e:
        logger.error(f"LLM generation failed: {e}", exc_info=True)
        if products:
            from ai_assistant.serializers import serialize_products
            serialized = serialize_products(products)
            product_links = []
            for p in serialized:
                p_name = p.get("name") or "Product"
                p_url = p.get("url", "")
                p_price = p.get("price")
                price_str = f" - BDT {p_price}" if p_price is not None and p_price != "" else ""
                if p_url:
                    product_links.append(f"- [{p_name}]({p_url}){price_str}")
                else:
                    product_links.append(f"- {p_name}{price_str}")
            items_str = "\n".join(product_links)
            response_text = f"I found these products that match your request:\n{items_str}"
        else:
            response_text = "I couldn't find any products matching your request. Please try another search."

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

    return {
        "message": response_text,
        "products": products,
        "timings": timings,
        "analysis": analysis.model_dump(),
        "prompt_version": SYSTEM_PROMPT_VERSION,
        "intent": intent,
    }
