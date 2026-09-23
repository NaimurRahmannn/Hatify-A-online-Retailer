from django.test import TestCase
from products.models import Product, Category, ColorVariant, SizeVariant
from ai_search.models import ProductSearchDocument
from django.core.management import call_command
from io import StringIO

class AiSearchTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(categroy_name='Test Category', category_type='MEN')
        self.color = ColorVariant.objects.create(color_name='Red')
        self.size = SizeVariant.objects.create(size_name='L')
        
    def test_product_creation_signal(self):
        # Create a product
        product = Product.objects.create(
            product_name='Test Product',
            price=100.00,
            product_description='A nice test product.',
            category=self.category
        )
        
        # Adding m2m triggers post_add signal
        product.color_variant.add(self.color)
        product.size_variant.add(self.size)

        # Document should be generated
        doc = ProductSearchDocument.objects.get(product=product)
        
        self.assertIn('Test Product', doc.searchable_text)
        self.assertIn('Test Category', doc.searchable_text)
        self.assertIn('Red', doc.searchable_text)
        self.assertIn('L', doc.searchable_text)
        
        self.assertEqual(doc.metadata['category'], 'Test Category')
        self.assertIn('Red', doc.metadata['colors'])
        
    def test_product_update_signal(self):
        product = Product.objects.create(
            product_name='Initial Product',
            price=50.00,
            product_description='Desc',
            category=self.category
        )
        
        # Update product
        product.product_name = 'Updated Product'
        product.save()
        
        doc = ProductSearchDocument.objects.get(product=product)
        self.assertIn('Updated Product', doc.searchable_text)
        
    def test_product_deletion(self):
        product = Product.objects.create(
            product_name='Delete Me',
            price=10.00,
            product_description='Desc',
            category=self.category
        )
        
        self.assertTrue(ProductSearchDocument.objects.filter(product=product).exists())
        
        product.delete()
        
        # Check document is deleted via CASCADE
        self.assertFalse(ProductSearchDocument.objects.filter(product__product_name='Delete Me').exists())

    def test_build_search_documents_command(self):
        product1 = Product.objects.create(
            product_name='Command Product 1',
            price=20.00,
            product_description='Desc',
            category=self.category
        )
        product2 = Product.objects.create(
            product_name='Command Product 2',
            price=30.00,
            product_description='Desc',
            category=self.category
        )
        
        # Wipe documents
        ProductSearchDocument.objects.all().delete()
        
        self.assertEqual(ProductSearchDocument.objects.count(), 0)
        
        out = StringIO()
        call_command('build_search_documents', stdout=out)
        
        self.assertEqual(ProductSearchDocument.objects.count(), 2)
        self.assertIn('Successfully generated 2 search documents!', out.getvalue())
