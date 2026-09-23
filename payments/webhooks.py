import logging
from decimal import Decimal
import uuid

from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import stripe

from payments.models import StripeWebhookEvent
from products.models import Order


logger = logging.getLogger(__name__)


class PaymentVerificationError(ValueError):
    pass


def _value(container, key, default=None):
    if container is None:
        return default
    if hasattr(container, "get"):
        return container.get(key, default)
    return getattr(container, key, default)


def _payment_intent_id(value):
    if not value:
        return ""
    if isinstance(value, str):
        return value
    return str(_value(value, "id", ""))


def _verify_checkout_amount(order, stripe_session):
    expected_amount = int(order.payment_amount * Decimal("100"))
    received_amount = _value(stripe_session, "amount_total")
    received_currency = str(_value(stripe_session, "currency", "")).lower()
    if received_amount != expected_amount or received_currency != order.payment_currency:
        raise PaymentVerificationError(
            f"Stripe amount verification failed for order {order.uid}."
        )


def _checkout_order(stripe_session):
    session_id = _value(stripe_session, "id", "")
    if not session_id:
        return None
    return (
        Order.objects.select_for_update()
        .filter(stripe_checkout_session_id=session_id, payment_method="stripe")
        .first()
    )


def _mark_checkout_paid(order, stripe_session):
    _verify_checkout_amount(order, stripe_session)
    if order.payment_status == Order.PaymentStatus.REFUNDED:
        return
    order.payment_status = Order.PaymentStatus.PAID
    order.transaction_id = _payment_intent_id(
        _value(stripe_session, "payment_intent")
    )
    order.save(update_fields=["payment_status", "transaction_id"])


def _process_checkout_event(event_type, stripe_session):
    order = _checkout_order(stripe_session)
    if order is None:
        return

    if event_type == "checkout.session.completed":
        if _value(stripe_session, "payment_status") == "paid":
            _mark_checkout_paid(order, stripe_session)
    elif event_type == "checkout.session.async_payment_succeeded":
        _mark_checkout_paid(order, stripe_session)
    elif event_type == "checkout.session.async_payment_failed":
        if order.payment_status == Order.PaymentStatus.PENDING:
            order.payment_status = Order.PaymentStatus.FAILED
            order.save(update_fields=["payment_status"])
    elif event_type == "checkout.session.expired":
        if order.payment_status == Order.PaymentStatus.PENDING:
            order.payment_status = Order.PaymentStatus.CANCELLED
            order.save(update_fields=["payment_status"])


def _process_payment_intent_failure(payment_intent):
    metadata = _value(payment_intent, "metadata", {})
    order_id = _value(metadata, "order_id", "")
    try:
        order_id = uuid.UUID(str(order_id))
    except (TypeError, ValueError, AttributeError):
        return
    order = (
        Order.objects.select_for_update()
        .filter(pk=order_id, payment_method="stripe")
        .first()
    )
    if order is not None and order.payment_status == Order.PaymentStatus.PENDING:
        order.payment_status = Order.PaymentStatus.FAILED
        order.save(update_fields=["payment_status"])


def _process_refund(charge):
    is_full_refund = bool(_value(charge, "refunded", False)) or (
        _value(charge, "amount") is not None
        and _value(charge, "amount_refunded") == _value(charge, "amount")
    )
    if not is_full_refund:
        return
    payment_intent_id = _payment_intent_id(_value(charge, "payment_intent"))
    if not payment_intent_id:
        return
    order = (
        Order.objects.select_for_update()
        .filter(
            transaction_id=payment_intent_id,
            payment_method="stripe",
            payment_status=Order.PaymentStatus.PAID,
        )
        .first()
    )
    if order is not None:
        order.payment_status = Order.PaymentStatus.REFUNDED
        order.save(update_fields=["payment_status"])


def process_stripe_event(event):
    event_id = str(_value(event, "id", ""))
    event_type = str(_value(event, "type", ""))
    if not event_id or not event_type:
        raise PaymentVerificationError("Stripe event is missing its identifier or type.")

    try:
        with transaction.atomic():
            if StripeWebhookEvent.objects.filter(event_id=event_id).exists():
                return

            event_data = _value(event, "data", {})
            stripe_object = _value(event_data, "object", {})
            if event_type in {
                "checkout.session.completed",
                "checkout.session.async_payment_succeeded",
                "checkout.session.async_payment_failed",
                "checkout.session.expired",
            }:
                _process_checkout_event(event_type, stripe_object)
            elif event_type == "payment_intent.payment_failed":
                _process_payment_intent_failure(stripe_object)
            elif event_type == "charge.refunded":
                _process_refund(stripe_object)

            StripeWebhookEvent.objects.create(
                event_id=event_id,
                event_type=event_type,
            )
    except IntegrityError:
        # A concurrent delivery inserted the same event first; its transaction won.
        return


@csrf_exempt
@require_POST
def stripe_webhook(request):
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET
    if not webhook_secret or not webhook_secret.startswith("whsec_"):
        return HttpResponse("Stripe webhook is not configured.", status=503)

    try:
        event = stripe.Webhook.construct_event(
            request.body,
            request.headers.get("Stripe-Signature", ""),
            webhook_secret,
        )
    except (ValueError, stripe.SignatureVerificationError):
        return HttpResponse("Invalid webhook signature.", status=400)

    try:
        process_stripe_event(event)
    except PaymentVerificationError as error:
        logger.error("Stripe webhook verification rejected (%s)", error.__class__.__name__)
        return HttpResponse("Payment verification failed.", status=409)
    except Exception as error:
        logger.error("Stripe webhook processing failed (%s)", error.__class__.__name__)
        return HttpResponse("Webhook processing failed.", status=500)
    return HttpResponse(status=200)
