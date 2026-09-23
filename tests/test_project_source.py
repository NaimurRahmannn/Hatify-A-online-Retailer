from ast import parse
from pathlib import Path
from unittest import TestCase


ROOT = Path(__file__).resolve().parents[1]


class ProjectSourceTests(TestCase):
    def test_settings_and_urlconf_are_valid_python(self):
        for relative_path in (
            "Ecommerce_Storefront/settings.py",
            "Ecommerce_Storefront/urls.py",
        ):
            source = (ROOT / relative_path).read_text(encoding="utf-8")
            parse(source, filename=relative_path)

    def test_stripe_secrets_are_not_hardcoded(self):
        import re

        checked = [
            ROOT / "Ecommerce_Storefront/settings.py",
            ROOT / "payments/services.py",
            ROOT / "payments/webhooks.py",
        ]
        for path in checked:
            source = path.read_text(encoding="utf-8")
            self.assertNotRegex(source, r"sk_(?:test|live)_[A-Za-z0-9]{12,}")
            self.assertNotRegex(source, r"whsec_[A-Za-z0-9]{12,}")

    def test_payment_urlconf_is_included(self):
        source = (ROOT / "Ecommerce_Storefront/urls.py").read_text(encoding="utf-8")
        self.assertIn('include("payments.urls")', source.replace("'", '"'))
