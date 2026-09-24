"""Shared test helpers for the ai_search test suite."""

from products.models import Category, ColorVariant, Product, SizeVariant


def make_category(**overrides):
    defaults = {
        "categroy_name": "Test Category",
        "category_type": "MEN",
    }
    defaults.update(overrides)
    return Category.objects.create(**defaults)


def make_color(name="Red"):
    return ColorVariant.objects.create(color_name=name)


def make_size(name="L"):
    return SizeVariant.objects.create(size_name=name)


def make_product(category=None, **overrides):
    if category is None:
        category = make_category()
    defaults = {
        "product_name": "Test Product",
        "price": "100.00",
        "product_description": "A nice test product.",
        "category": category,
    }
    defaults.update(overrides)
    return Product.objects.create(**defaults)


def make_embedding_vector(dimension=768, value=0.1):
    """Return a dummy embedding vector."""
    return [value] * dimension
