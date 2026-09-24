from django.urls import path

from ai_search import views

app_name = "ai_search"

urlpatterns = [
    path("", views.search_view, name="search"),
]
