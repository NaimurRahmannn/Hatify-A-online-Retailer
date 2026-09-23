import hashlib
import hmac
import json
import time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from payments.models import StripeWebhookEvent
from products.models import Order


@override_settings(STRIPE_WEBHOOK_SECRET="whsec_test_signing")
class StripeWebhookTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("buyer")
        self.order = Order.objects.create(
            user=user,
            email="buyer@example.com",
            phone="1",
            first_name="A",
            last_name="B",
            street_address="Road",
            city="Dhaka",
            state="",
            zip_code="",
            payment_method="stripe",
            subtotal=Decimal("100"),
            shipping=Decimal("100"),
            total=Decimal("200"),
            payment_currency="usd",
            payment_amount=Decimal("1.67"),
            exchange_rate=Decimal("120"),
            stripe_checkout_session_id="cs_test_1",
        )

    def event(self, event_id, event_type, stripe_object):
        return {
            "id": event_id,
            "object": "event",
            "type": event_type,
            "data": {"object": stripe_object},
        }

    def completed_event(
        self,
        event_id="evt_1",
        amount=167,
        currency="usd",
        status="paid",
    ):
        return self.event(
            event_id,
            "checkout.session.completed",
            {
                "id": "cs_test_1",
                "object": "checkout.session",
                "payment_status": status,
                "amount_total": amount,
                "currency": currency,
                "payment_intent": "pi_test_1",
            },
        )

    def signed_post(self, event, secret="whsec_test_signing"):
        payload = json.dumps(event, separators=(",", ":")).encode()
        timestamp = int(time.time())
        digest = hmac.new(
            secret.encode(),
            f"{timestamp}.".encode() + payload,
            hashlib.sha256,
        ).hexdigest()
        return self.client.post(
            reverse("payments:webhook"),
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=f"t={timestamp},v1={digest}",
        )

    def test_invalid_signature_does_not_update_order(self):
        response = self.signed_post(self.completed_event(), secret="wrong")

        self.assertEqual(response.status_code, 400)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PENDING)

    def test_completed_paid_event_verifies_amount_and_marks_paid(self):
        response = self.signed_post(self.completed_event())

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(self.order.transaction_id, "pi_test_1")

    def test_completed_unpaid_event_remains_pending(self):
        response = self.signed_post(self.completed_event(status="unpaid"))

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PENDING)

    def test_amount_or_currency_mismatch_is_retryable_and_not_recorded(self):
        for event_id, amount, currency in (
            ("evt_amount", 999, "usd"),
            ("evt_currency", 167, "eur"),
        ):
            with self.subTest(event_id=event_id):
                response = self.signed_post(
                    self.completed_event(event_id, amount, currency),
                )
                self.assertEqual(response.status_code, 409)
                self.assertFalse(
                    StripeWebhookEvent.objects.filter(event_id=event_id).exists()
                )

    def test_duplicate_event_is_harmless(self):
        self.assertEqual(self.signed_post(self.completed_event()).status_code, 200)
        self.assertEqual(self.signed_post(self.completed_event()).status_code, 200)

        self.assertEqual(
            StripeWebhookEvent.objects.filter(event_id="evt_1").count(),
            1,
        )

    def test_async_success_failure_and_expiry_transitions(self):
        succeeded = self.event(
            "evt_success",
            "checkout.session.async_payment_succeeded",
            {
                "id": "cs_test_1",
                "object": "checkout.session",
                "amount_total": 167,
                "currency": "usd",
                "payment_intent": "pi_async",
            },
        )
        self.assertEqual(self.signed_post(succeeded).status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)

        self.order.payment_status = Order.PaymentStatus.PENDING
        self.order.transaction_id = ""
        self.order.save(update_fields=["payment_status", "transaction_id"])
        failed = self.event(
            "evt_failed",
            "checkout.session.async_payment_failed",
            {"id": "cs_test_1", "object": "checkout.session"},
        )
        self.assertEqual(self.signed_post(failed).status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.FAILED)

        self.order.payment_status = Order.PaymentStatus.PENDING
        self.order.save(update_fields=["payment_status"])
        expired = self.event(
            "evt_expired",
            "checkout.session.expired",
            {"id": "cs_test_1", "object": "checkout.session"},
        )
        self.assertEqual(self.signed_post(expired).status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.CANCELLED)

    def test_payment_intent_failure_uses_immutable_order_metadata(self):
        event = self.event(
            "evt_pi_failed",
            "payment_intent.payment_failed",
            {
                "id": "pi_failed",
                "object": "payment_intent",
                "metadata": {"order_id": str(self.order.uid)},
            },
        )

        self.assertEqual(self.signed_post(event).status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.FAILED)

    def test_full_refund_marks_refunded_partial_refund_does_not(self):
        self.order.payment_status = Order.PaymentStatus.PAID
        self.order.transaction_id = "pi_test_1"
        self.order.save(update_fields=["payment_status", "transaction_id"])
        partial = self.event(
            "evt_partial",
            "charge.refunded",
            {
                "id": "ch_partial",
                "object": "charge",
                "payment_intent": "pi_test_1",
                "amount": 167,
                "amount_refunded": 50,
                "refunded": False,
            },
        )
        full = self.event(
            "evt_full",
            "charge.refunded",
            {
                "id": "ch_full",
                "object": "charge",
                "payment_intent": "pi_test_1",
                "amount": 167,
                "amount_refunded": 167,
                "refunded": True,
            },
        )

        self.assertEqual(self.signed_post(partial).status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)
        self.assertEqual(self.signed_post(full).status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.REFUNDED)

    def test_late_failure_does_not_downgrade_paid_or_refunded(self):
        self.assertEqual(self.signed_post(self.completed_event()).status_code, 200)
        failed = self.event(
            "evt_late_failure",
            "checkout.session.async_payment_failed",
            {"id": "cs_test_1", "object": "checkout.session"},
        )
        self.assertEqual(self.signed_post(failed).status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)

        self.order.payment_status = Order.PaymentStatus.REFUNDED
        self.order.save(update_fields=["payment_status"])
        expired = self.event(
            "evt_late_expiry",
            "checkout.session.expired",
            {"id": "cs_test_1", "object": "checkout.session"},
        )
        self.assertEqual(self.signed_post(expired).status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.REFUNDED)
