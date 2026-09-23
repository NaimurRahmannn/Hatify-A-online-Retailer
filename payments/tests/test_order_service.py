import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from payments.order_service import (
    CheckoutValidationError,
    bdt_to_minor_units,
    create_or_get_stripe_order,
)
from products.models import Category, Product, SizeVariant


@override_settings(STRIPE_CURRENCY="usd", STRIPE_BDT_PER_USD=Decimal("120"))
class StripeOrderServiceTests(TestCase):
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
            price=Decimal("240.00"),
            product_description="Test",
        )
        self.size = SizeVariant.objects.create(size_name="M")
        self.product.size_variant.add(self.size)
        self.shipping = {
            "email": "buyer@example.com",
            "phone": "123",
            "first_name": "A",
            "last_name": "B",
            "street_address": "Road",
            "city": "Dhaka",
            "state": "",
            "zip_code": "",
        }

    def test_rounds_bdt_to_usd_minor_units_half_up(self):
        self.assertEqual(
            bdt_to_minor_units(Decimal("100"), Decimal("120")),
            83,
        )

    def test_database_price_wins_and_charge_audit_matches_line_cents(self):
        order, created = create_or_get_stripe_order(
            self.user,
            uuid.uuid4(),
            [
                {
                    "product_id": str(self.product.pk),
                    "quantity": 2,
                    "size": "M",
                    "price": "0.01",
                }
            ],
            self.shipping,
        )

        self.assertTrue(created)
        self.assertEqual(order.subtotal, Decimal("480.00"))
        self.assertEqual(order.total, Decimal("580.00"))
        self.assertEqual(order.payment_amount, Decimal("4.83"))
        self.assertEqual(order.items.get().price, Decimal("240.00"))

    def test_same_token_returns_same_owned_order(self):
        token = uuid.uuid4()
        first, created = create_or_get_stripe_order(
            self.user,
            token,
            [{"product_id": str(self.product.pk), "quantity": 1, "size": "M"}],
            self.shipping,
        )
        second, repeated = create_or_get_stripe_order(
            self.user,
            token,
            [],
            {},
        )

        self.assertTrue(created)
        self.assertFalse(repeated)
        self.assertEqual(first.pk, second.pk)

    def test_token_owned_by_another_user_is_rejected(self):
        token = uuid.uuid4()
        create_or_get_stripe_order(
            self.user,
            token,
            [{"product_id": str(self.product.pk), "quantity": 1, "size": "M"}],
            self.shipping,
        )
        other = get_user_model().objects.create_user("other", password="pass")

        with self.assertRaises(CheckoutValidationError):
            create_or_get_stripe_order(other, token, [], {})

    def test_invalid_quantity_missing_product_and_invalid_size_are_rejected(self):
        bad_lines = [
            [{"product_id": str(self.product.pk), "quantity": 0, "size": "M"}],
            [{"product_id": str(self.product.pk), "quantity": 100, "size": "M"}],
            [{"product_id": str(uuid.uuid4()), "quantity": 1, "size": ""}],
            [{"product_id": str(self.product.pk), "quantity": 1, "size": "XL"}],
            [{"product_id": "not-a-uuid", "quantity": 1, "size": "M"}],
        ]

        for lines in bad_lines:
            with self.subTest(lines=lines), self.assertRaises(CheckoutValidationError):
                create_or_get_stripe_order(
                    self.user,
                    uuid.uuid4(),
                    lines,
                    self.shipping,
                )
