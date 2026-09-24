"""AI Assistant chat API views.

Security features:
- Atomic cache-based rate limiting (no race conditions)
- Conversation ownership verification (IDOR protection)
- Pydantic input validation
- Proper CSRF handling via Django middleware
"""

import json
import logging
import uuid

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from ai_assistant.models import Conversation, Message
from ai_assistant.schemas import ChatRequest, ChatResponse, ProductResponse
from ai_assistant.serializers import serialize_products
from ai_assistant.services.chat_service import process_chat_message

from pydantic import ValidationError

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Rate limiting (atomic)
# ------------------------------------------------------------------

def check_rate_limit(request) -> bool:
    """Atomically check and increment the per-caller request counter.

    Uses ``cache.add`` + ``cache.incr`` which map to Redis SETNX + INCR,
    eliminating the get-then-set race condition.
    """
    if request.user.is_authenticated:
        limit = getattr(settings, "AI_CHAT_RATE_LIMIT_AUTHENTICATED", 50)
        key = f"rate_limit:chat:auth:{request.user.id}"
    else:
        limit = getattr(settings, "AI_CHAT_RATE_LIMIT_ANONYMOUS", 10)
        client_ip = request.META.get("REMOTE_ADDR", "unknown")
        key = f"rate_limit:chat:anon:{client_ip}"

    try:
        # add() only sets the key if it doesn't already exist (atomic).
        added = cache.add(key, 0, timeout=60)
        # incr() is atomic in Redis/memcached.
        current = cache.incr(key)
    except Exception:
        # If cache is unavailable, allow the request (fail-open).
        logger.warning("Rate-limit cache unavailable – allowing request", exc_info=True)
        return True

    return current <= limit


# ------------------------------------------------------------------
# Conversation ownership helpers
# ------------------------------------------------------------------

def _get_owned_conversation(conversation_id_str: str, request) -> Conversation | None:
    """Fetch a conversation only if the current caller owns it.

    Authenticated users: matched by ``user``.
    Anonymous users: matched by ``session_id``.
    """
    try:
        conv_uuid = uuid.UUID(conversation_id_str)
    except (ValueError, AttributeError):
        return None

    if request.user.is_authenticated:
        return Conversation.objects.filter(id=conv_uuid, user=request.user).first()

    session_key = request.session.session_key
    if not session_key:
        return None
    return Conversation.objects.filter(id=conv_uuid, session_id=session_key).first()


def _create_conversation(request) -> Conversation:
    """Create a new conversation bound to the current caller."""
    user = request.user if request.user.is_authenticated else None
    if not request.session.session_key:
        request.session.create()
    session_id = request.session.session_key
    return Conversation.objects.create(user=user, session_id=session_id)


# ------------------------------------------------------------------
# Main view
# ------------------------------------------------------------------

@require_POST
def chat_view(request):
    # --- Rate limiting ---
    if not check_rate_limit(request):
        return JsonResponse(
            {"error": "Too many requests. Please try again later."}, status=429
        )

    # --- Parse & validate input ---
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    try:
        chat_req = ChatRequest(**body)
    except ValidationError as exc:
        errors = exc.errors()
        msg = errors[0]["msg"] if errors else "Invalid request."
        return JsonResponse({"error": msg}, status=400)

    query = chat_req.message.strip()

    # --- Resolve conversation (with ownership check) ---
    conversation = None
    if chat_req.conversation_id:
        conversation = _get_owned_conversation(chat_req.conversation_id, request)
        if conversation is None:
            return JsonResponse(
                {"error": "Conversation not found."}, status=404
            )

    if not conversation:
        conversation = _create_conversation(request)

    # --- Persist the user message ---
    Message.objects.create(
        conversation=conversation,
        role=Message.RoleChoices.USER,
        content=query,
    )

    # --- Process ---
    try:
        result = process_chat_message(query, conversation)
    except Exception as e:
        logger.error(f"Chat processing error: {e}", exc_info=True)
        return JsonResponse(
            {"error": "An internal error occurred. Please try again later."},
            status=500,
        )

    # --- Build metadata for assistant message ---
    msg_metadata = {}
    if "timings" in result:
        msg_metadata["timings"] = result["timings"]
    if "analysis" in result:
        msg_metadata["analysis"] = result["analysis"]
    msg_metadata["prompt_version"] = result.get("prompt_version")
    msg_metadata["intent"] = result.get("intent")

    Message.objects.create(
        conversation=conversation,
        role=Message.RoleChoices.ASSISTANT,
        content=result["message"],
        metadata=msg_metadata,
    )

    # --- Serialize response ---
    product_list = serialize_products(result.get("products", []))

    response = ChatResponse(
        conversation_id=str(conversation.id),
        answer=result["message"],
        products=[ProductResponse(**p) for p in product_list],
        metadata={
            "intent": result.get("intent", ""),
            "timings": result.get("timings", {}),
        },
    )

    return JsonResponse(response.model_dump())
