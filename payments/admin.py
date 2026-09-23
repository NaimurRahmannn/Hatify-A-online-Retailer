from django.contrib import admin

from payments.models import StripeWebhookEvent


@admin.register(StripeWebhookEvent)
class StripeWebhookEventAdmin(admin.ModelAdmin):
    list_display = ["event_id", "event_type", "created_at"]
    search_fields = ["event_id", "event_type"]
    readonly_fields = ["event_id", "event_type", "created_at", "updated_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
