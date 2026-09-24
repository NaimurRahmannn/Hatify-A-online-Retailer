import uuid
from django.db import models
from django.conf import settings

class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversations"
    )
    session_id = models.CharField(max_length=255, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Conversation {self.id} ({self.session_id})"


class Message(models.Model):
    class RoleChoices(models.TextChoices):
        USER = 'USER', 'User'
        ASSISTANT = 'ASSISTANT', 'Assistant'

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=RoleChoices.choices)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Message {self.id} ({self.role})"


class ChatRequestLog(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="request_logs")
    query = models.TextField()
    intent = models.CharField(max_length=100, blank=True, null=True)
    retrieval_time_ms = models.FloatField(null=True, blank=True)
    context_time_ms = models.FloatField(null=True, blank=True)
    llm_time_ms = models.FloatField(null=True, blank=True)
    total_time_ms = models.FloatField(null=True, blank=True)
    token_usage = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Log for Conv {self.conversation_id} at {self.created_at}"
