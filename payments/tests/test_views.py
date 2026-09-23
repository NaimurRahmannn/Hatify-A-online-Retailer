import uuid
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from products.models import Category, Order, Product


@override_settings(
    STRIPE_ENABLED=True,
    STRIPE_BDT_PER_USD=Decimal("120"),
    STRIPE_CURRENCY="usd",
    STRIPE_SECRET_KEY="sk_test_secret",
)
class PaymentViewTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            "owner",
            email="owner@example.com",
            password="pass",
        )
        self.other = get_user_model().objects.create_user(
            "other",
            password="pass",
        )
        self.order = Order.objects.create(
            user=self.owner,
            email=self.owner.email,
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
            stripe_checkout_session_id="cs_test_owned",
        )

    def test_guest_checkout_post_redirects_to_login(self):
        response = self.client.post(reverse("payments:create_checkout"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_other_user_cannot_view_success_cancel_or_stripe_invoice(self):
        self.client.force_login(self.other)

        self.assertEqual(
            self.client.get(
                reverse("payments:success"),
                {"session_id": "cs_test_owned"},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("payments:cancel"),
                {"order": self.order.uid},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("invoice", args=[self.order.order_number]),
            ).status_code,
            403,
        )

    @patch("payments.views.create_or_reuse_checkout_session")
    def test_owner_retry_redirects_to_same_open_session(self, session_service):
        session_service.return_value.url = "https://checkout.stripe.test/owned"
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("payments:retry", args=[self.order.uid]),
        )

        self.assertRedirects(
            response,
            "https://checkout.stripe.test/owned",
            fetch_redirect_response=False,
        )

    def test_success_page_does_not_mark_pending_order_paid(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("payments:success"),
            {"session_id": "cs_test_owned"},
        )

        self.order.refresh_from_db()
        self.assertContains(response, "Payment is processing")
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PENDING)

    def test_malformed_cancel_order_identifier_returns_not_found(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse("payments:cancel"),
            {"order": "not-a-uuid"},
        )

        self.assertEqual(response.status_code, 404)

    @patch("payments.views.create_or_reuse_checkout_session")
    def test_authenticated_checkout_creates_backend_order_and_redirects(self, session_service):
        category = Category.objects.create(categroy_name="Men")
        product = Product.objects.create(
            product_name="Shirt",
            category=category,
            price=Decimal("240"),
            product_description="Test",
        )
        token = uuid.uuid4()
        session = self.client.session
        session["checkout_snapshots"] = {
            str(token): {
                "created_at": timezone.now().timestamp(),
                "lines": [
                    {"product_id": str(product.pk), "quantity": 1, "size": ""}
                ],
            }
        }
        session.save()
        session_service.return_value.url = "https://checkout.stripe.test/new"
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("payments:create_checkout"),
            {
                "checkout_token": str(token),
                "email": "owner@example.com",
                "phone": "123",
                "first_name": "A",
                "last_name": "B",
                "street_address": "Road",
                "city": "Dhaka",
                "state": "",
                "zip_code": "",
            },
        )

        self.assertRedirects(
            response,
            "https://checkout.stripe.test/new",
            fetch_redirect_response=False,
        )
        self.assertTrue(
            Order.objects.filter(
                checkout_token=token,
                user=self.owner,
                payment_method="stripe",
            ).exists()
        )
