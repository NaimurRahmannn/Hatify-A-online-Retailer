from django.urls import path
from products.views import (
    get_product,
    add_to_cart,
    cart,
    remove_from_cart,
    update_cart,
    buy_now,
    checkout,
    category_products,
    place_order,
    invoice,
    search,
    gender_products,
    submit_review,
)

urlpatterns = [
    path('search/', search, name="search"),
    path('gender/<str:gender>/', gender_products, name="gender_products"),
    path('cart/', cart, name="cart"),
    path('cart/update/', update_cart, name="update_cart"),
    path('checkout/', checkout, name="checkout"),
    path('place-order/', place_order, name="place_order"),
    path('invoice/<int:order_number>/', invoice, name="invoice"),
    path('buy-now/<slug>/', buy_now, name="buy_now"),
    path('add-to-cart/<slug>/', add_to_cart, name="add_to_cart"),
    path('remove-from-cart/<slug>/', remove_from_cart, name="remove_from_cart"),
    path('category/<slug:slug>/', category_products, name="category_products"),
    path('<slug:slug>/reviews/', submit_review, name="submit_review"),
    path('<slug>/', get_product, name="get_product"),
]
