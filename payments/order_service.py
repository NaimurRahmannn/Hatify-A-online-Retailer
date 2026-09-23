from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
import uuid

from django.conf import settings
from django.db import IntegrityError, transaction

from products.models import Order, OrderItem, Product


BDT_SHIPPING_CHARGE = Decimal("100.00")
MAX_CHECKOUT_LINES = 100
MAX_QUANTITY = 99


class CheckoutValidationError(ValueError):
    pass


def bdt_to_minor_units(amount, rate):
    amount = Decimal(amount)
    rate = Decimal(rate)
    if rate <= 0:
        raise CheckoutValidationError("Stripe exchange rate is unavailable.")
    return int(
        (amount / rate * Decimal("100")).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def _owned_order_for_token(user, checkout_token):
    order = Order.objects.filter(checkout_token=checkout_token).first()
    if order is None:
        return None
    if order.user_id != user.pk:
        raise CheckoutValidationError("This checkout session does not belong to you.")
    return order


def _normalize_lines(lines):
    if not lines:
        raise CheckoutValidationError("No items were provided for checkout.")

    consolidated = defaultdict(int)
    for line in lines:
        try:
            product_id = uuid.UUID(str(line.get("product_id", "")))
            quantity = int(line.get("quantity", 0))
        except (TypeError, ValueError, AttributeError):
            raise CheckoutValidationError("Checkout contains an invalid product or quantity.")
        if quantity < 1 or quantity > MAX_QUANTITY:
            raise CheckoutValidationError("Each product quantity must be between 1 and 99.")
        size = str(line.get("size", "") or "").strip()
        consolidated[(product_id, size)] += quantity

    if len(consolidated) > MAX_CHECKOUT_LINES:
        raise CheckoutValidationError("Checkout cannot contain more than 100 product lines.")
    if any(quantity > MAX_QUANTITY for quantity in consolidated.values()):
        raise CheckoutValidationError("Each product quantity must be between 1 and 99.")
    return consolidated


def _validated_items(lines, exchange_rate):
    consolidated = _normalize_lines(lines)
    product_ids = {product_id for product_id, _size in consolidated}
    products = {
        product.pk: product
        for product in Product.objects.filter(pk__in=product_ids).prefetch_related("size_variant")
    }
    if len(products) != len(product_ids):
        raise CheckoutValidationError("One or more products are no longer available.")

    items = []
    subtotal = Decimal("0.00")
    payment_minor_units = 0
    for (product_id, size), quantity in consolidated.items():
        product = products[product_id]
        configured_sizes = {
            value.strip()
            for value in product.size_variant.values_list("size_name", flat=True)
        }
        if configured_sizes and size not in configured_sizes:
            raise CheckoutValidationError(f"Select a valid size for {product.product_name}.")
        if not configured_sizes and size:
            raise CheckoutValidationError(f"{product.product_name} does not use size variants.")

        line_total = product.price * quantity
        unit_minor_units = bdt_to_minor_units(product.price, exchange_rate)
        subtotal += line_total
        payment_minor_units += unit_minor_units * quantity
        items.append(
            {
                "product": product,
                "quantity": quantity,
                "size": size,
                "line_total": line_total,
            }
        )

    payment_minor_units += bdt_to_minor_units(BDT_SHIPPING_CHARGE, exchange_rate)
    return items, subtotal, payment_minor_units


def create_or_get_stripe_order(user, checkout_token, lines, shipping_data):
    if not getattr(user, "is_authenticated", False):
        raise CheckoutValidationError("Sign in before paying with Stripe.")
    try:
        checkout_token = uuid.UUID(str(checkout_token))
    except (TypeError, ValueError, AttributeError):
        raise CheckoutValidationError("Checkout session is invalid.")

    existing = _owned_order_for_token(user, checkout_token)
    if existing is not None:
        return existing, False

    required_shipping = ("email", "phone", "first_name", "last_name", "city")
    if any(not str(shipping_data.get(field, "")).strip() for field in required_shipping):
        raise CheckoutValidationError("Please fill in all required shipping fields.")

    exchange_rate = settings.STRIPE_BDT_PER_USD
    if exchange_rate is None or exchange_rate <= 0:
        raise CheckoutValidationError("Stripe exchange rate is unavailable.")

    try:
        with transaction.atomic():
            existing = _owned_order_for_token(user, checkout_token)
            if existing is not None:
                return existing, False

            items, subtotal, payment_minor_units = _validated_items(
                lines,
                exchange_rate,
            )
            order = Order.objects.create(
                user=user,
                checkout_token=checkout_token,
                email=shipping_data["email"].strip(),
                phone=shipping_data["phone"].strip(),
                first_name=shipping_data["first_name"].strip(),
                last_name=shipping_data["last_name"].strip(),
                street_address=shipping_data.get("street_address", "").strip(),
                city=shipping_data["city"].strip(),
                state=shipping_data.get("state", "").strip(),
                zip_code=shipping_data.get("zip_code", "").strip(),
                payment_method="stripe",
                payment_status=Order.PaymentStatus.PENDING,
                payment_currency=settings.STRIPE_CURRENCY,
                payment_amount=Decimal(payment_minor_units) / Decimal("100"),
                exchange_rate=exchange_rate,
                subtotal=subtotal,
                shipping=BDT_SHIPPING_CHARGE,
                total=subtotal + BDT_SHIPPING_CHARGE,
            )
            OrderItem.objects.bulk_create(
                [
                    OrderItem(
                        order=order,
                        product=item["product"],
                        product_name=item["product"].product_name,
                        size=item["size"],
                        quantity=item["quantity"],
                        price=item["product"].price,
                        line_total=item["line_total"],
                    )
                    for item in items
                ]
            )
            return order, True
    except IntegrityError:
        existing = _owned_order_for_token(user, checkout_token)
        if existing is not None:
            return existing, False
        raise CheckoutValidationError("Unable to create this order. Please try again.")
