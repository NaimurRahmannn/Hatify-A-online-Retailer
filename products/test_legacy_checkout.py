from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from products.models import Category, Order, Product


class LegacyCheckoutTests(TestCase):
    def setUp(self):
        category = Category.objects.create(categroy_name="Men")
        self.product = Product.objects.create(
            product_name="Shirt",
            category=category,
            price=Decimal("250"),
            product_description="Test",
        )
        self.base = {
            "email": "guest@example.com",
            "phone": "123",
            "first_name": "A",
            "last_name": "B",
            "street_address": "Road",
            "city": "Dhaka",
            "state": "",
            "zip_code": "",
            "product_ids": [str(self.product.pk)],
            "quantities": ["2"],
            "sizes": [""],
        }

    def test_guest_cod_order_is_preserved_and_uses_database_price(self):
        response = self.client.post(
            reverse("place_order"),
            {**self.base, "payment_method": "cod", "price": "0.01"},
        )
        order = Order.objects.get()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.total, Decimal("600"))
        self.assertIsNone(order.user)

    def test_bkash_and_nagad_still_require_transaction_id(self):
        for method in ("bkash", "nagad"):
            with self.subTest(method=method):
                response = self.client.post(
                    reverse("place_order"),
                    {**self.base, "payment_method": method},
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(Order.objects.count(), 0)

    def test_legacy_endpoint_does_not_accept_stripe(self):
        self.client.post(
            reverse("place_order"),
            {**self.base, "payment_method": "stripe"},
        )
        self.assertFalse(Order.objects.filter(payment_method="stripe").exists())
