from decimal import Decimal

from django.test import SimpleTestCase

from payments.config import build_stripe_configuration


class StripeConfigurationTests(SimpleTestCase):
    def valid_values(self):
        return {
            "STRIPE_PUBLIC_KEY": "pk_test_public",
            "STRIPE_SECRET_KEY": "sk_test_secret",
            "STRIPE_WEBHOOK_SECRET": "whsec_signing",
            "STRIPE_CURRENCY": "USD",
            "STRIPE_BDT_PER_USD": "120.50",
        }

    def test_valid_test_configuration_is_enabled_and_normalized(self):
        config = build_stripe_configuration(self.valid_values())

        self.assertTrue(config.enabled)
        self.assertEqual(config.currency, "usd")
        self.assertEqual(config.bdt_per_unit, Decimal("120.50"))

    def test_missing_secret_disables_stripe(self):
        values = self.valid_values()
        values["STRIPE_WEBHOOK_SECRET"] = ""

        self.assertFalse(build_stripe_configuration(values).enabled)

    def test_live_keys_disable_stripe(self):
        values = self.valid_values()
        values["STRIPE_SECRET_KEY"] = "sk_live_forbidden"

        self.assertFalse(build_stripe_configuration(values).enabled)

    def test_invalid_nonpositive_or_unsupported_conversion_disables_stripe(self):
        for rate, currency in (
            ("bad", "usd"),
            ("0", "usd"),
            ("-1", "usd"),
            ("120", "eur"),
        ):
            values = self.valid_values()
            values["STRIPE_BDT_PER_USD"] = rate
            values["STRIPE_CURRENCY"] = currency

            with self.subTest(rate=rate, currency=currency):
                self.assertFalse(build_stripe_configuration(values).enabled)
