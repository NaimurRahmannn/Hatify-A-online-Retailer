import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from payments.models import StripeWebhookEvent
from products.models import Order


class PaymentModelTests(TestCase):
    def make_order(self, **overrides):
        values = {
            "email": "buyer@example.com",
            "phone": "1",
            "first_name": "A",
            "last_name": "B",
            "street_address": "Road",
            "city": "Dhaka",
            "state": "",
            "zip_code": "",
            "payment_method": "stripe",
            "subtotal": Decimal("100.00"),
            "shipping": Decimal("100.00"),
            "total": Decimal("200.00"),
        }
        values.update(overrides)
        return Order.objects.create(**values)

    def test_stripe_order_supports_owner_status_and_audit_fields(self):
        user = get_user_model().objects.create_user("buyer", password="pass")
        token = uuid.uuid4()

        order = self.make_order(
            user=user,
            checkout_token=token,
            payment_currency="usd",
            payment_amount=Decimal("1.66"),
            exchange_rate=Decimal("120.500000"),
            stripe_checkout_session_id="cs_test_123",
        )

        self.assertEqual(order.payment_status, Order.PaymentStatus.PENDING)
        self.assertEqual(order.user, user)
        self.assertEqual(order.checkout_token, token)

    def test_legacy_order_can_remain_unowned_and_card_choice_is_preserved(self):
        order = self.make_order(payment_method="card")

        self.assertIsNone(order.user)
        self.assertEqual(order.get_payment_method_display(), "Legacy Card")

    def test_checkout_token_and_session_id_are_unique_when_present(self):
        token = uuid.uuid4()
        self.make_order(
            checkout_token=token,
            stripe_checkout_session_id="cs_test_unique",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_order(checkout_token=token)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_order(stripe_checkout_session_id="cs_test_unique")

    def test_webhook_event_id_is_unique(self):
        StripeWebhookEvent.objects.create(
            event_id="evt_1",
            event_type="checkout.session.completed",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            StripeWebhookEvent.objects.create(
                event_id="evt_1",
                event_type="checkout.session.completed",
            )
