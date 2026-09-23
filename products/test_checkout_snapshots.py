from datetime import timedelta
from types import SimpleNamespace

from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.utils import timezone

from products.checkout_snapshots import (
    CheckoutSnapshotError,
    create_checkout_snapshot,
    get_checkout_snapshot,
    subtract_order_from_cart_once,
)


class CheckoutSnapshotTests(TestCase):
    def request(self):
        request = RequestFactory().get("/")
        SessionMiddleware(lambda value: value).process_request(request)
        request.session.save()
        return request

    def test_snapshot_consolidates_lines_and_round_trips(self):
        request = self.request()
        token = create_checkout_snapshot(
            request,
            [
                {"product_id": "a", "quantity": 1, "size": "M"},
                {"product_id": "a", "quantity": 2, "size": "M"},
            ],
        )

        self.assertEqual(
            get_checkout_snapshot(request, token),
            [{"product_id": "a", "quantity": 3, "size": "M"}],
        )

    def test_expired_snapshot_is_rejected(self):
        request = self.request()
        old = timezone.now() - timedelta(minutes=31)
        token = create_checkout_snapshot(
            request,
            [{"product_id": "a", "quantity": 1, "size": ""}],
            now=old,
        )

        with self.assertRaises(CheckoutSnapshotError):
            get_checkout_snapshot(request, token, now=timezone.now())

    def test_session_keeps_only_five_snapshots(self):
        request = self.request()
        tokens = [
            create_checkout_snapshot(
                request,
                [{"product_id": str(index), "quantity": 1, "size": ""}],
            )
            for index in range(6)
        ]

        with self.assertRaises(CheckoutSnapshotError):
            get_checkout_snapshot(request, tokens[0])
        self.assertEqual(len(request.session["checkout_snapshots"]), 5)

    def test_cart_cleanup_subtracts_once_and_preserves_later_quantity(self):
        request = self.request()
        request.session["cart"] = [
            {"product_id": "p1", "quantity": 4, "size": "M"},
            {"product_id": "p2", "quantity": 1, "size": ""},
        ]
        item = SimpleNamespace(product_id="p1", quantity=2, size="M")
        order = SimpleNamespace(
            uid="order-1",
            items=SimpleNamespace(all=lambda: [item]),
        )

        subtract_order_from_cart_once(request, order)
        subtract_order_from_cart_once(request, order)

        self.assertEqual(
            request.session["cart"],
            [
                {"product_id": "p1", "quantity": 2, "size": "M"},
                {"product_id": "p2", "quantity": 1, "size": ""},
            ],
        )
        self.assertEqual(request.session["cart_count"], 3)
