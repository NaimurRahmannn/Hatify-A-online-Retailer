from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping


@dataclass(frozen=True)
class StripeConfiguration:
    public_key: str
    secret_key: str
    webhook_secret: str
    currency: str
    bdt_per_unit: Decimal | None
    enabled: bool


def build_stripe_configuration(values: Mapping[str, str]) -> StripeConfiguration:
    public_key = values.get("STRIPE_PUBLIC_KEY", "").strip()
    secret_key = values.get("STRIPE_SECRET_KEY", "").strip()
    webhook_secret = values.get("STRIPE_WEBHOOK_SECRET", "").strip()
    currency = values.get("STRIPE_CURRENCY", "usd").strip().lower()

    try:
        bdt_per_unit = Decimal(values.get("STRIPE_BDT_PER_USD", "").strip())
    except (InvalidOperation, AttributeError):
        bdt_per_unit = None

    enabled = bool(
        public_key.startswith("pk_test_")
        and secret_key.startswith("sk_test_")
        and webhook_secret.startswith("whsec_")
        and currency == "usd"
        and bdt_per_unit is not None
        and bdt_per_unit > 0
    )

    return StripeConfiguration(
        public_key=public_key,
        secret_key=secret_key,
        webhook_secret=webhook_secret,
        currency=currency,
        bdt_per_unit=bdt_per_unit,
        enabled=enabled,
    )
