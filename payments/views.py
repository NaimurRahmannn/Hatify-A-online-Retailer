import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.http import Http404
from django.urls import reverse
from django.views.decorators.http import require_POST

from payments.forms import StripeCheckoutForm
from payments.order_service import CheckoutValidationError, create_or_get_stripe_order
from payments.services import StripeCheckoutError, create_or_reuse_checkout_session
from products.checkout_snapshots import (
    CheckoutSnapshotError,
    get_checkout_snapshot,
    subtract_order_from_cart_once,
)
from products.models import Order


def _checkout_error(request, message):
    messages.error(request, message)
    return redirect("checkout")


@login_required
@require_POST
def create_checkout(request):
    if not settings.STRIPE_ENABLED:
        return _checkout_error(request, "Stripe Checkout is currently unavailable.")

    form = StripeCheckoutForm(request.POST)
    if not form.is_valid():
        return _checkout_error(request, "Please review your checkout details and try again.")

    try:
        lines = get_checkout_snapshot(request, form.cleaned_data["checkout_token"])
        shipping_data = {
            field: form.cleaned_data[field]
            for field in (
                "email",
                "phone",
                "first_name",
                "last_name",
                "street_address",
                "city",
                "state",
                "zip_code",
            )
        }
        order, _created = create_or_get_stripe_order(
            request.user,
            form.cleaned_data["checkout_token"],
            lines,
            shipping_data,
        )
        checkout_session = create_or_reuse_checkout_session(order, request)
    except (CheckoutSnapshotError, CheckoutValidationError, StripeCheckoutError) as error:
        return _checkout_error(request, str(error))

    return redirect(checkout_session.url)


@login_required
@require_POST
def retry_checkout(request, order_id):
    order = get_object_or_404(
        Order,
        pk=order_id,
        user=request.user,
        payment_method="stripe",
        payment_status=Order.PaymentStatus.PENDING,
    )
    try:
        checkout_session = create_or_reuse_checkout_session(order, request)
    except StripeCheckoutError as error:
        messages.error(request, str(error))
        cancel_url = reverse("payments:cancel")
        return redirect(f"{cancel_url}?order={order.uid}")
    return redirect(checkout_session.url)


@login_required
def payment_success(request):
    order = get_object_or_404(
        Order,
        stripe_checkout_session_id=request.GET.get("session_id", ""),
        user=request.user,
        payment_method="stripe",
    )
    subtract_order_from_cart_once(request, order)
    return render(request, "payments/success.html", {"order": order})


@login_required
def payment_cancel(request):
    try:
        order_id = uuid.UUID(request.GET.get("order", ""))
    except (TypeError, ValueError, AttributeError):
        raise Http404("Order not found.")
    order = get_object_or_404(
        Order,
        pk=order_id,
        user=request.user,
        payment_method="stripe",
    )
    return render(request, "payments/cancel.html", {"order": order})
