from django.urls import path

from payments import views
from payments.webhooks import stripe_webhook


app_name = "payments"

urlpatterns = [
    path("webhook/", stripe_webhook, name="webhook"),
    path("checkout/", views.create_checkout, name="create_checkout"),
    path("retry/<uuid:order_id>/", views.retry_checkout, name="retry"),
    path("success/", views.payment_success, name="success"),
    path("cancel/", views.payment_cancel, name="cancel"),
]
