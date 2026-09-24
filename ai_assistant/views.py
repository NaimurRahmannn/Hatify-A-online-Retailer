import json
import logging
import uuid
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from ai_assistant.models import Conversation, Message
from ai_assistant.services.chat_service import process_chat_message

logger = logging.getLogger(__name__)

# Disabling CSRF for this API endpoint since it will likely be used by mobile apps 
# or frontend clients that handle auth via tokens, but you can adjust later.
@csrf_exempt
@require_POST
def chat_view(request):
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    query = body.get("message")
    if not query or not isinstance(query, str) or not query.strip():
        return JsonResponse({"error": "A non-empty 'message' string is required."}, status=400)

    query = query.strip()
    conversation_id_str = body.get("conversation_id")
    
    conversation = None
    if conversation_id_str:
        try:
            conversation = Conversation.objects.get(id=uuid.UUID(conversation_id_str))
        except (ValueError, Conversation.DoesNotExist):
            pass
            
    if not conversation:
        user = request.user if request.user.is_authenticated else None
        # generate a new session id if None
        session_id = request.session.session_key or str(uuid.uuid4())
        conversation = Conversation.objects.create(user=user, session_id=session_id)

    # Save user message
    user_message = Message.objects.create(
        conversation=conversation,
        role=Message.RoleChoices.USER,
        content=query
    )

    try:
        result = process_chat_message(query, conversation)
    except Exception as e:
        logger.error(f"Chat processing error: {e}", exc_info=True)
        return JsonResponse({"error": "An internal error occurred."}, status=500)

    # Save assistant message
    metadata = {}
    if "timings" in result:
        metadata["timings"] = result["timings"]
    if "analysis" in result:
        metadata["analysis"] = result["analysis"]
        
    Message.objects.create(
        conversation=conversation,
        role=Message.RoleChoices.ASSISTANT,
        content=result["message"],
        metadata=metadata
    )

    # Convert UUID in products if any to string for JSON serialization
    # Actually retrieve_products already returns dicts with string IDs in some cases, 
    # but let's be safe: it returns the output of SearchResult which we serialize.
    # The requirement is: products: [{"id": 1, "name": "...", "price": 2500}]
    
    # We will just construct the product dictionary exactly as expected
    product_list = []
    for p in result.get("products", []):
        if isinstance(p, dict):
            # If it's already a dict from retrieval service
            doc = p.get("document", p)
            product_list.append({
                "id": doc.get("pk") if isinstance(doc, dict) else getattr(doc, "pk", getattr(doc, "id", None)),
                "name": doc.get("name") if isinstance(doc, dict) else getattr(doc, "name", ""),
                "price": doc.get("metadata", {}).get("price") if isinstance(doc, dict) else getattr(doc, "metadata", {}).get("price"),
            })
        else:
            # If it's a SearchResult object
            doc = p.document
            product_list.append({
                "id": doc.pk,
                "name": doc.name,
                "price": doc.metadata.get("price") if isinstance(doc.metadata, dict) else getattr(doc, "price", None)
            })

    return JsonResponse({
        "message": result["message"],
        "products": product_list,
        "conversation_id": str(conversation.id),
        "timings": result.get("timings", {})
    })
