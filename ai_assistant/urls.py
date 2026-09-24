from django.urls import path
from ai_assistant.views import chat_view

app_name = "ai_assistant"

urlpatterns = [
    path('chat/', chat_view, name='chat'),
]
