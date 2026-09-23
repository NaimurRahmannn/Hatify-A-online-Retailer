from django.db import models
from django.conf import settings
from django.utils.text import slugify
from base.models import Basemodel

CATEGORY_TYPE_CHOICES = (
    ('MEN', 'Men'),
    ('WOMEN', 'Women'),
)

class Category(Basemodel):
    categroy_name=models.CharField(max_length=100)
    slug=models.SlugField(unique=True, null=True, blank=True)
    category_type=models.CharField(max_length=10, choices=CATEGORY_TYPE_CHOICES, default='MEN')
    
    def save(self, *args, **kwargs):
        base_slug = slugify(self.categroy_name)
        slug = base_slug
        n = 1
        while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f"{base_slug}-{n}"
            n += 1
        self.slug = slug
        super(Category, self).save(*args, **kwargs)
        
    def __str__(self) -> str:
        return f"{self.categroy_name} ({self.get_category_type_display()})"
    
class ColorVariant(Basemodel):
    color_name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self) -> str:
        return self.color_name

class SizeVariant(Basemodel):
    size_name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    def __str__(self) -> str:
        return self.size_name

   
class Product(Basemodel):
    product_name=models.CharField(max_length=100)
    slug=models.SlugField(unique=True, null=True, blank=True)
    category=models.ForeignKey(Category,on_delete=models.CASCADE,related_name="products")
    price=models.DecimalField(max_digits=10, decimal_places=2)
    product_description=models.TextField()
    color_variant = models.ManyToManyField(ColorVariant , blank=True)
    size_variant = models.ManyToManyField(SizeVariant , blank=True)
    def save(self , *args , **kwargs):
        base_slug = slugify(self.product_name)
        slug = base_slug
        n = 1
        while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f"{base_slug}-{n}"
            n += 1
        self.slug = slug
        super(Product ,self).save(*args , **kwargs)
    def __str__(self) -> str:
        return self.product_name
    
class ProductImage(Basemodel):
    product=models.ForeignKey(Product,on_delete=models.CASCADE,related_name="product_images")
    product_image=models.ImageField(upload_to="product")

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Image for {self.product.product_name}"


PAYMENT_METHOD_CHOICES = (
    ('card', 'Legacy Card'),
    ('stripe', 'Stripe Checkout'),
    ('bkash', 'bKash'),
    ('nagad', 'Nagad'),
    ('cod', 'Cash on Delivery'),
)

ORDER_STATUS_CHOICES = (
    ('pending', 'Pending'),
    ('processing', 'Processing'),
    ('shipped', 'Shipped'),
    ('delivered', 'Delivered'),
    ('cancelled', 'Cancelled'),
)

class Order(Basemodel):
    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'
        REFUNDED = 'refunded', 'Refunded'

    order_number = models.PositiveIntegerField(unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='orders',
    )
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    street_address = models.CharField(max_length=300)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES)
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )
    payment_currency = models.CharField(max_length=3, blank=True, default='')
    payment_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    stripe_checkout_session_id = models.CharField(max_length=255, null=True, blank=True, unique=True)
    checkout_token = models.UUIDField(null=True, blank=True, unique=True)
    order_status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default='pending')
    transaction_id = models.CharField(max_length=100, blank=True, default='')
    reference = models.CharField(max_length=100, blank=True, default='')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    shipping = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        if not self.order_number:
            last = Order.objects.order_by('-order_number').first()
            self.order_number = (last.order_number + 1) if last else 1001
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order #{self.order_number}"


class OrderItem(Basemodel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_name = models.CharField(max_length=200)
    size = models.CharField(max_length=50, blank=True, default='')
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.product_name} x{self.quantity}"

