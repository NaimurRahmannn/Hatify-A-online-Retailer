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
