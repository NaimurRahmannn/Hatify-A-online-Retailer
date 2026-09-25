from dataclasses import dataclass

from django.db.models import Avg, Count, IntegerField, Sum, Value
from django.db.models.functions import Coalesce

from products.models import Order, OrderItem, Product


@dataclass(frozen=True)
class ReviewSummary:
    count: int
    average: float
    stars: tuple[str, ...]


def build_review_summary(product: Product) -> ReviewSummary:
    values = product.reviews.aggregate(
        count=Count("uid"),
        average=Avg("rating"),
    )
    average = round(float(values["average"] or 0), 1)
    stars = tuple(
        "full"
        if average >= position
        else "half"
        if average >= position - 0.5
        else "empty"
        for position in range(1, 6)
    )
    return ReviewSummary(
        count=int(values["count"] or 0),
        average=average,
        stars=stars,
    )


def get_ordered_unit_count(product: Product) -> int:
    invalid_payment_states = (
        Order.PaymentStatus.FAILED,
        Order.PaymentStatus.CANCELLED,
        Order.PaymentStatus.REFUNDED,
    )
    result = (
        OrderItem.objects.filter(product=product)
        .exclude(order__order_status="cancelled")
        .exclude(order__payment_status__in=invalid_payment_states)
        .aggregate(
            total=Coalesce(
                Sum("quantity"),
                Value(0),
                output_field=IntegerField(),
            )
        )
    )
    return int(result["total"])
