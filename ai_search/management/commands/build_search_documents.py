from django.core.management.base import BaseCommand

from ai_search.services import generate_product_document
from products.models import Product


class Command(BaseCommand):
    help = "Builds ProductSearchDocument for all existing products"

    def handle(self, *args, **kwargs):
        products = Product.objects.select_related("category").prefetch_related(
            "color_variant",
            "size_variant",
        )
        total = products.count()
        self.stdout.write(
            self.style.NOTICE(
                f"Found {total} products. Starting document generation..."
            )
        )

        count = 0
        failure_count = 0
        for product in products:
            try:
                generate_product_document(product)
                count += 1
                if count % 10 == 0:
                    self.stdout.write(f"Processed {count}/{total} products...")
            except Exception as exc:
                failure_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"Error processing product {product.pk}: {exc}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully generated {count} search documents!"
            )
        )
        if failure_count:
            self.stdout.write(
                self.style.WARNING(
                    f"{failure_count} product(s) failed and can be retried."
                )
            )
