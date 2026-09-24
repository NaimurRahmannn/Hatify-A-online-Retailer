import json
import logging
import uuid
import time
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from ai_assistant.models import Conversation, Message
from ai_assistant.services.chat_service import process_chat_message

logger = logging.getLogger(__name__)

def check_rate_limit(request) -> bool:
    """Returns True if request is allowed, False if rate limited."""
    if request.user.is_authenticated:
        limit = getattr(settings, 'AI_CHAT_RATE_LIMIT_AUTHENTICATED', 50)
        key = f"rate_limit:chat:auth:{request.user.id}"
    else:
        limit = getattr(settings, 'AI_CHAT_RATE_LIMIT_ANONYMOUS', 10)
        client_ip = request.META.get('REMOTE_ADDR', 'unknown')
        key = f"rate_limit:chat:anon:{client_ip}"
        
    requests = cache.get(key, 0)
    if requests >= limit:
        return False
        
    cache.set(key, requests + 1, timeout=60)
    return True

@csrf_exempt
@require_POST
def chat_view(request):
    if not check_rate_limit(request):
        return JsonResponse({"error": "Too many requests. Please try again later."}, status=429)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    query = body.get("message")
    if not query or not isinstance(query, str) or not query.strip():
        return JsonResponse({"error": "A non-empty 'message' string is required."}, status=400)

    query = query.strip()
    if len(query) > 500:
        return JsonResponse({"error": "Message exceeds maximum length of 500 characters."}, status=400)

    conversation_id_str = body.get("conversation_id")
    
    conversation = None
    if conversation_id_str:
        try:
            conversation = Conversation.objects.get(id=uuid.UUID(conversation_id_str))
        except (ValueError, Conversation.DoesNotExist):
            pass
            
    if not conversation:
        user = request.user if request.user.is_authenticated else None
        session_id = request.session.session_key or str(uuid.uuid4())
        conversation = Conversation.objects.create(user=user, session_id=session_id)

    Message.objects.create(
        conversation=conversation,
        role=Message.RoleChoices.USER,
        content=query
    )

    try:
        result = process_chat_message(query, conversation)
    except Exception as e:
        logger.error(f"Chat processing error: {e}", exc_info=True)
        return JsonResponse({"error": "An internal error occurred. Please try again later."}, status=500)

    metadata = {}
    if "timings" in result:
        metadata["timings"] = result["timings"]
    if "analysis" in result:
        metadata["analysis"] = result["analysis"]
    metadata["prompt_version"] = result.get("prompt_version")
    metadata["intent"] = result.get("intent")
        
    Message.objects.create(
        conversation=conversation,
        role=Message.RoleChoices.ASSISTANT,
        content=result["message"],
        metadata=metadata
    )

    product_list = []
    for p in result.get("products", []):
        if isinstance(p, dict):
            doc = p.get("document", p)
            product_list.append({
                "id": doc.get("pk") if isinstance(doc, dict) else getattr(doc, "pk", getattr(doc, "id", None)),
                "name": doc.get("name") if isinstance(doc, dict) else getattr(doc, "name", ""),
                "price": doc.get("metadata", {}).get("price") if isinstance(doc, dict) else getattr(doc, "metadata", {}).get("price"),
            })
        else:
            doc = p.document
            product_list.append({
                "id": doc.pk,
                "name": doc.name,
                "price": doc.metadata.get("price") if isinstance(doc.metadata, dict) else getattr(doc, "price", None)
            })

    return JsonResponse({
        "conversation_id": str(conversation.id),
        "answer": result["message"],
        "products": product_list,
        "metadata": result.get("timings", {})
    })
