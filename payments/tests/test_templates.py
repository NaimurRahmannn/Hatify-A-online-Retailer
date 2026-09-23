from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from products.models import Category, Order, Product


class PaymentTemplateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "buyer",
            email="buyer@example.com",
            password="pass",
        )
        category = Category.objects.create(categroy_name="Men")
        self.product = Product.objects.create(
            product_name="Shirt",
            category=category,
            price=Decimal("240"),
            product_description="Test",
        )

    def put_product_in_cart(self):
        session = self.client.session
        session["cart"] = [
            {"product_id": str(self.product.pk), "quantity": 1, "size": ""}
        ]
        session.save()

    def make_stripe_order(self, status=Order.PaymentStatus.PENDING):
        return Order.objects.create(
            user=self.user,
            email=self.user.email,
            phone="1",
            first_name="A",
            last_name="B",
            street_address="Road",
            city="Dhaka",
            state="",
            zip_code="",
            payment_method="stripe",
            payment_status=status,
            subtotal=Decimal("240"),
            shipping=Decimal("100"),
            total=Decimal("340"),
            payment_currency="usd",
            payment_amount=Decimal("2.83"),
            exchange_rate=Decimal("120"),
            stripe_checkout_session_id=f"cs_test_{status}",
        )

    @override_settings(STRIPE_ENABLED=True)
    def test_enabled_checkout_renders_hosted_stripe_without_card_inputs(self):
        self.client.force_login(self.user)
        self.put_product_in_cart()

        response = self.client.get(reverse("checkout"))

        self.assertContains(response, 'name="checkout_token"')
        self.assertContains(response, f'action="{reverse("payments:create_checkout")}"')
        self.assertContains(response, 'value="stripe"')
        self.assertContains(response, "Stripe-hosted")
        self.assertContains(response, "Proceed to Stripe Payment")
        for forbidden in ("card_number", "card_expiry", "card_cvv", "card_name"):
            self.assertNotContains(response, forbidden)

    @override_settings(STRIPE_ENABLED=False)
    def test_disabled_checkout_omits_stripe_and_defaults_to_legacy_action(self):
        self.put_product_in_cart()

        response = self.client.get(reverse("checkout"))

        self.assertNotContains(response, 'value="stripe"')
        self.assertContains(response, f'action="{reverse("place_order")}"')
        self.assertContains(response, 'value="bkash" checked')

    def test_success_page_renders_each_persisted_payment_state(self):
        expected_messages = {
            Order.PaymentStatus.PENDING: "Payment is processing",
            Order.PaymentStatus.PAID: "Payment confirmed",
            Order.PaymentStatus.FAILED: "Payment failed",
            Order.PaymentStatus.CANCELLED: "Payment cancelled",
            Order.PaymentStatus.REFUNDED: "Payment refunded",
        }
        self.client.force_login(self.user)

        for status, expected in expected_messages.items():
            order = self.make_stripe_order(status)
            with self.subTest(status=status):
                response = self.client.get(
                    reverse("payments:success"),
                    {"session_id": order.stripe_checkout_session_id},
                )
                self.assertContains(response, expected)

    def test_cancel_page_has_csrf_protected_retry_and_does_not_change_status(self):
        order = self.make_stripe_order()
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("payments:cancel"),
            {"order": order.uid},
        )

        self.assertContains(response, reverse("payments:retry", args=[order.uid]))
        self.assertContains(response, "csrfmiddlewaretoken")
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.PENDING)

    def test_stripe_invoice_displays_method_and_payment_status(self):
        order = self.make_stripe_order(Order.PaymentStatus.PAID)
        self.client.force_login(self.user)

        response = self.client.get(reverse("invoice", args=[order.order_number]))

        self.assertContains(response, "Stripe Checkout")
        self.assertContains(response, "Payment status:")
        self.assertContains(response, "Paid")
