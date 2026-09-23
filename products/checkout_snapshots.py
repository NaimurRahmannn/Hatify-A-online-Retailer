from collections import defaultdict
from datetime import timedelta
import uuid

from django.utils import timezone


SNAPSHOT_SESSION_KEY = "checkout_snapshots"
CLEANED_ORDERS_SESSION_KEY = "cleaned_checkout_orders"
SNAPSHOT_TTL = timedelta(minutes=30)
MAX_SNAPSHOTS = 5
MAX_LINES = 100


class CheckoutSnapshotError(ValueError):
    pass


def _prune_expired(snapshots, now):
    minimum_timestamp = (now - SNAPSHOT_TTL).timestamp()
    return {
        token: snapshot
        for token, snapshot in snapshots.items()
        if isinstance(snapshot, dict)
        and isinstance(snapshot.get("created_at"), (int, float))
        and snapshot["created_at"] >= minimum_timestamp
    }


def create_checkout_snapshot(request, lines, now=None):
    now = now or timezone.now()
    consolidated = defaultdict(int)

    for line in lines:
        product_id = str(line.get("product_id", "")).strip()
        size = str(line.get("size", "") or "").strip()
        try:
            quantity = int(line.get("quantity", 0))
        except (TypeError, ValueError):
            quantity = 0
        consolidated[(product_id, size)] += quantity

    if not consolidated or len(consolidated) > MAX_LINES:
        raise CheckoutSnapshotError("Checkout must contain between 1 and 100 product lines.")

    normalized_lines = [
        {"product_id": product_id, "quantity": quantity, "size": size}
        for (product_id, size), quantity in consolidated.items()
    ]
    snapshots = _prune_expired(
        dict(request.session.get(SNAPSHOT_SESSION_KEY, {})),
        now,
    )
    token = str(uuid.uuid4())
    snapshots[token] = {
        "created_at": now.timestamp(),
        "lines": normalized_lines,
    }

    if len(snapshots) > MAX_SNAPSHOTS:
        ordered_tokens = sorted(
            snapshots,
            key=lambda item: snapshots[item]["created_at"],
        )
        for old_token in ordered_tokens[:-MAX_SNAPSHOTS]:
            snapshots.pop(old_token, None)

    request.session[SNAPSHOT_SESSION_KEY] = snapshots
    request.session.modified = True
    return token


def get_checkout_snapshot(request, token, now=None):
    now = now or timezone.now()
    token = str(token)
    snapshots = _prune_expired(
        dict(request.session.get(SNAPSHOT_SESSION_KEY, {})),
        now,
    )
    request.session[SNAPSHOT_SESSION_KEY] = snapshots
    request.session.modified = True

    snapshot = snapshots.get(token)
    if not snapshot or not isinstance(snapshot.get("lines"), list):
        raise CheckoutSnapshotError("Checkout session has expired. Please review your cart again.")

    return [dict(line) for line in snapshot["lines"]]


def subtract_order_from_cart_once(request, order):
    order_id = str(order.uid)
    cleaned_orders = list(request.session.get(CLEANED_ORDERS_SESSION_KEY, []))
    if order_id in cleaned_orders:
        return

    purchased = defaultdict(int)
    for item in order.items.all():
        if item.product_id is None:
            continue
        purchased[(str(item.product_id), item.size or "")] += item.quantity

    updated_cart = []
    for line in request.session.get("cart", []):
        product_id = str(line.get("product_id", ""))
        size = line.get("size", "") or ""
        try:
            quantity = int(line.get("quantity", 0))
        except (TypeError, ValueError):
            quantity = 0
        remaining = quantity - purchased.get((product_id, size), 0)
        if remaining > 0:
            updated_line = dict(line)
            updated_line["quantity"] = remaining
            updated_cart.append(updated_line)

    request.session["cart"] = updated_cart
    request.session["cart_count"] = sum(line["quantity"] for line in updated_cart)
    cleaned_orders.append(order_id)
    request.session[CLEANED_ORDERS_SESSION_KEY] = cleaned_orders[-20:]
    request.session.modified = True
