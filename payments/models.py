from base.models import Basemodel
from django.db import models


class StripeWebhookEvent(Basemodel):
    event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.event_type}: {self.event_id}"
