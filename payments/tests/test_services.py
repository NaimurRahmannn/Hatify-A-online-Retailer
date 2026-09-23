from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
import stripe

from payments.services import StripeCheckoutError, create_or_reuse_checkout_session
from products.models import Order, OrderItem


@override_settings(
    STRIPE_ENABLED=True,
    STRIPE_SECRET_KEY="sk_test_secret",
    STRIPE_CURRENCY="usd",
)
class StripeSessionServiceTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            "buyer",
            email="buyer@example.com",
        )
        self.order = Order.objects.create(
            user=user,
            email=user.email,
            phone="1",
            first_name="A",
            last_name="B",
            street_address="Road",
            city="Dhaka",
            state="",
            zip_code="",
            payment_method="stripe",
            subtotal=Decimal("240"),
            shipping=Decimal("100"),
            total=Decimal("340"),
            payment_currency="usd",
            payment_amount=Decimal("2.83"),
            exchange_rate=Decimal("120"),
        )
        OrderItem.objects.create(
            order=self.order,
            product=None,
            product_name="Shirt",
            quantity=1,
            price=Decimal("240"),
            line_total=Decimal("240"),
        )
        self.request = RequestFactory().post(
            "/payments/checkout/",
            HTTP_HOST="localhost",
        )

    def stripe_session(self, session_id="cs_test_1", status="open"):
        return stripe.checkout.Session.construct_from(
            {
                "id": session_id,
                "object": "checkout.session",
                "url": f"https://checkout.stripe.test/{session_id}",
                "status": status,
            },
            "sk_test_secret",
        )

    @patch("payments.services.stripe.checkout.Session.create")
    def test_creates_backend_priced_session_with_metadata_and_idempotency(self, create):
        create.return_value = self.stripe_session()

        session = create_or_reuse_checkout_session(self.order, self.request)

        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["mode"], "payment")
        self.assertEqual(kwargs["client_reference_id"], str(self.order.uid))
        self.assertEqual(kwargs["idempotency_key"], f"haatify-order-{self.order.uid}")
        self.assertEqual(
            sum(
                line["price_data"]["unit_amount"] * line["quantity"]
                for line in kwargs["line_items"]
            ),
            283,
        )
        self.assertEqual(kwargs["metadata"]["order_id"], str(self.order.uid))
        self.assertEqual(
            kwargs["payment_intent_data"]["metadata"]["order_id"],
            str(self.order.uid),
        )
        self.assertIn("{CHECKOUT_SESSION_ID}", kwargs["success_url"])
        self.assertEqual(session.id, "cs_test_1")
        self.order.refresh_from_db()
        self.assertEqual(self.order.stripe_checkout_session_id, "cs_test_1")

    @patch("payments.services.stripe.checkout.Session.retrieve")
    def test_existing_open_session_is_reused(self, retrieve):
        self.order.stripe_checkout_session_id = "cs_test_existing"
        self.order.save(update_fields=["stripe_checkout_session_id"])
        retrieve.return_value = self.stripe_session("cs_test_existing")

        session = create_or_reuse_checkout_session(self.order, self.request)

        self.assertEqual(session.id, "cs_test_existing")

    def test_nonpending_order_cannot_create_session(self):
        self.order.payment_status = Order.PaymentStatus.PAID
        self.order.save(update_fields=["payment_status"])

        with self.assertRaises(StripeCheckoutError):
            create_or_reuse_checkout_session(self.order, self.request)

    @patch("payments.services.stripe.checkout.Session.create")
    def test_stripe_api_failure_raises_customer_safe_error(self, create):
        create.side_effect = stripe.StripeError("secret provider detail")

        with self.assertRaisesMessage(
            StripeCheckoutError,
            "Unable to start Stripe Checkout. Please try again.",
        ):
            create_or_reuse_checkout_session(self.order, self.request)
