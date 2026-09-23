import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.urls import reverse
import stripe

from payments.order_service import bdt_to_minor_units
from products.models import Order


logger = logging.getLogger(__name__)


class StripeCheckoutError(RuntimeError):
    pass


def _checkout_line_items(order):
    line_items = []
    calculated_minor_units = 0

    for item in order.items.all():
        unit_amount = bdt_to_minor_units(item.price, order.exchange_rate)
        name = item.product_name
        if item.size:
            name = f"{name} ({item.size})"
        line_items.append(
            {
                "price_data": {
                    "currency": order.payment_currency,
                    "product_data": {"name": name},
                    "unit_amount": unit_amount,
                },
                "quantity": item.quantity,
            }
        )
        calculated_minor_units += unit_amount * item.quantity

    shipping_minor_units = bdt_to_minor_units(order.shipping, order.exchange_rate)
    line_items.append(
        {
            "price_data": {
                "currency": order.payment_currency,
                "product_data": {"name": "Shipping"},
                "unit_amount": shipping_minor_units,
            },
            "quantity": 1,
        }
    )
    calculated_minor_units += shipping_minor_units

    expected_minor_units = int(order.payment_amount * Decimal("100"))
    if calculated_minor_units != expected_minor_units:
        raise StripeCheckoutError("Order payment amount is inconsistent. Please contact support.")
    return line_items


def _retrieve_open_session(session_id):
    try:
        session = stripe.checkout.Session.retrieve(
            session_id,
            api_key=settings.STRIPE_SECRET_KEY,
        )
    except stripe.StripeError as error:
        logger.warning(
            "Stripe Checkout retrieval failed for session %s (%s)",
            session_id,
            error.__class__.__name__,
        )
        raise StripeCheckoutError("Unable to resume Stripe Checkout. Please try again.")
    if session.status != "open":
        raise StripeCheckoutError("This Stripe Checkout session is no longer available.")
    return session


def create_or_reuse_checkout_session(order, request):
    if not settings.STRIPE_ENABLED:
        raise StripeCheckoutError("Stripe Checkout is currently unavailable.")
    if order.payment_method != "stripe" or order.payment_status != Order.PaymentStatus.PENDING:
        raise StripeCheckoutError("This order is not eligible for Stripe Checkout.")
    if order.stripe_checkout_session_id:
        return _retrieve_open_session(order.stripe_checkout_session_id)

    line_items = _checkout_line_items(order)
    success_url = request.build_absolute_uri(reverse("payments:success")) + "?session_id={CHECKOUT_SESSION_ID}"
    cancel_url = request.build_absolute_uri(reverse("payments:cancel")) + f"?order={order.uid}"
    metadata = {"order_id": str(order.uid), "order_number": str(order.order_number)}

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=line_items,
            customer_email=order.email,
            client_reference_id=str(order.uid),
            metadata=metadata,
            payment_intent_data={"metadata": metadata},
            success_url=success_url,
            cancel_url=cancel_url,
            api_key=settings.STRIPE_SECRET_KEY,
            idempotency_key=f"haatify-order-{order.uid}",
        )
    except stripe.StripeError as error:
        logger.warning(
            "Stripe Checkout creation failed for order %s (%s)",
            order.uid,
            error.__class__.__name__,
        )
        raise StripeCheckoutError("Unable to start Stripe Checkout. Please try again.")

    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(pk=order.pk)
        if locked_order.stripe_checkout_session_id:
            if locked_order.stripe_checkout_session_id != session.id:
                raise StripeCheckoutError("Unable to resume Stripe Checkout. Please try again.")
        else:
            locked_order.stripe_checkout_session_id = session.id
            locked_order.save(update_fields=["stripe_checkout_session_id"])
        order.stripe_checkout_session_id = locked_order.stripe_checkout_session_id
    return session
