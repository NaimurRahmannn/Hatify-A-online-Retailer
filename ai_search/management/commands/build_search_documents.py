from django.core.management.base import BaseCommand
from products.models import Product
from ai_search.services import generate_product_document

class Command(BaseCommand):
    help = 'Builds ProductSearchDocument for all existing products'

    def handle(self, *args, **kwargs):
        products = Product.objects.all()
        total = products.count()
        self.stdout.write(self.style.NOTICE(f'Found {total} products. Starting document generation...'))
        
        count = 0
        for product in products:
            try:
                generate_product_document(product)
                count += 1
                if count % 10 == 0:
                    self.stdout.write(f'Processed {count}/{total} products...')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error processing product {product.id}: {str(e)}'))
                
        self.stdout.write(self.style.SUCCESS(f'Successfully generated {count} search documents!'))
