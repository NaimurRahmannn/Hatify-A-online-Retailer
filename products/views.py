from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib import messages
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q
from products.forms import ProductReviewForm
from products.models import Product, Category, Order, OrderItem, ProductReview
from products.checkout_snapshots import (
    CheckoutSnapshotError,
    create_checkout_snapshot,
)
from products.review_service import build_review_summary, get_ordered_unit_count
import logging
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


def _get_cart(request):
    return request.session.get("cart", [])


def _save_cart(request, cart):
    request.session["cart"] = cart
    total = 0
    for item in cart:
        try:
            total += int(item.get("quantity", 0))
        except (TypeError, ValueError):
            continue
    request.session["cart_count"] = total
    request.session.modified = True


from ai_search.services.retrieval_service import retrieve_products

def search(request):
    query = request.GET.get('q', '').strip()
    products = []
    if query:
        try:
            results = retrieve_products(query)
            products = [res.document.product for res in results.get("results", [])]
        except Exception:
            logger.exception("AI search failed, falling back to standard search")
            products = Product.objects.filter(
                Q(product_name__icontains=query)
                | Q(category__categroy_name__icontains=query)
                | Q(product_description__icontains=query)
            ).distinct()
    return render(request, 'product/search.html', {'products': products, 'query': query})


def _product_detail_context(request, product, review_form=None):
    reviews = product.reviews.select_related("user").all()
    reviews_page = Paginator(reviews, 10).get_page(
        request.GET.get("reviews_page", 1)
    )
    own_review = None
    if request.user.is_authenticated:
        own_review = ProductReview.objects.filter(
            product=product,
            user=request.user,
        ).first()
    if review_form is None:
        review_form = ProductReviewForm(instance=own_review)
    return {
        "product": product,
        "review_summary": build_review_summary(product),
        "ordered_unit_count": get_ordered_unit_count(product),
        "reviews": reviews_page,
        "own_review": own_review,
        "review_form": review_form,
    }


def _product_reviews_url(product):
    return f'{reverse("get_product", kwargs={"slug": product.slug})}#reviews'


@login_required
@require_POST
def submit_review(request, slug):
    product = get_object_or_404(Product, slug=slug)
    existing = ProductReview.objects.filter(
        product=product,
        user=request.user,
    ).first()
    form = ProductReviewForm(request.POST, instance=existing)
    if not form.is_valid():
        return render(
            request,
            "product/product.html",
            _product_detail_context(request, product, review_form=form),
            status=400,
        )

    was_created = existing is None
    try:
        with transaction.atomic():
            locked_review = (
                ProductReview.objects.select_for_update()
                .filter(product=product, user=request.user)
                .first()
            )
            locked_form = ProductReviewForm(request.POST, instance=locked_review)
            if not locked_form.is_valid():
                return render(
                    request,
                    "product/product.html",
                    _product_detail_context(
                        request,
                        product,
                        review_form=locked_form,
                    ),
                    status=400,
                )
            review = locked_form.save(commit=False)
            review.product = product
            review.user = request.user
            review.save()
    except IntegrityError:
        concurrent_review = ProductReview.objects.filter(
            product=product,
            user=request.user,
        ).first()
        logger.warning(
            "Concurrent review write rejected for product=%s user=%s existing=%s",
            product.pk,
            request.user.pk,
            concurrent_review.pk if concurrent_review else None,
        )
        messages.error(
            request,
            "Your review changed in another request. Please try again.",
        )
        return redirect(_product_reviews_url(product))

    messages.success(
        request,
        "Your review was submitted." if was_created else "Your review was updated.",
    )
    return redirect(_product_reviews_url(product))


def get_product(request, slug):
    product = get_object_or_404(
        Product.objects.prefetch_related(
            "product_images",
            "color_variant",
            "size_variant",
        ),
        slug=slug,
    )
    return render(
        request,
        "product/product.html",
        _product_detail_context(request, product),
    )


def add_to_cart(request, slug):
    product = get_object_or_404(Product, slug=slug)
    if request.method == "POST":
        qty_raw = request.POST.get("quantity", "1")
        try:
            quantity = int(qty_raw)
        except ValueError:
            quantity = 1
        if quantity < 1:
            quantity = 1
        size = request.POST.get("select_size") or ""
    else:
        quantity = 1
        size = request.GET.get("size", "")

    if product.size_variant.exists() and not size:
        messages.error(request, "Please select a size before adding to cart.")
        next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
        if next_url:
            return redirect(next_url)
        return redirect("get_product", slug=product.slug)

    cart = _get_cart(request)
    for item in cart:
        if item.get("product_id") == str(product.pk) and item.get("size", "") == size:
            item["quantity"] = item.get("quantity", 0) + quantity
            _save_cart(request, cart)
            next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
            if next_url:
                return redirect(next_url)
            return redirect("get_product", slug=product.slug)

    cart.append({"product_id": str(product.pk), "quantity": quantity, "size": size})
    _save_cart(request, cart)
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if next_url:
        return redirect(next_url)
    return redirect("get_product", slug=product.slug)


def cart(request):
    cart = _get_cart(request)
    cart_items = []
    subtotal = 0

    for item in cart:
        product = Product.objects.filter(pk=item.get("product_id")).first()
        if not product:
            continue
        quantity = item.get("quantity", 1)
        line_total = product.price * quantity
        subtotal += line_total
        cart_items.append(
            {
                "product": product,
                "quantity": quantity,
                "size": item.get("size", ""),
                "line_total": line_total,
            }
        )

    shipping = 100 if cart_items else 0
    context = {
        "cart_items": cart_items,
        "subtotal": subtotal,
        "shipping": shipping,
        "total": subtotal + shipping,
    }
    return render(request, "product/cart.html", context)


def remove_from_cart(request, slug):
    product = get_object_or_404(Product, slug=slug)
    size = request.GET.get("size", "")
    cart = _get_cart(request)
    new_cart = []

    for item in cart:
        if item.get("product_id") == str(product.pk) and item.get("size", "") == size:
            continue
        new_cart.append(item)

    _save_cart(request, new_cart)
    return redirect("cart")


def update_cart(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid method"}, status=405)

    product_id = request.POST.get("product_id", "")
    size = request.POST.get("size", "")
    qty_raw = request.POST.get("quantity", "1")
    try:
        quantity = int(qty_raw)
    except ValueError:
        quantity = 1

    cart = _get_cart(request)
    updated = False

    new_cart = []
    for item in cart:
        if item.get("product_id") == product_id and item.get("size", "") == size:
            updated = True
            if quantity > 0:
                item["quantity"] = quantity
                new_cart.append(item)
            continue
        new_cart.append(item)

    if not updated and quantity > 0:
        new_cart.append({"product_id": product_id, "quantity": quantity, "size": size})

    _save_cart(request, new_cart)

    subtotal = 0
    line_total = 0
    cart_count = 0

    for item in new_cart:
        product = Product.objects.filter(pk=item.get("product_id")).first()
        if not product:
            continue
        item_qty = item.get("quantity", 1)
        cart_count += item_qty
        subtotal += product.price * item_qty
        if item.get("product_id") == product_id and item.get("size", "") == size:
            line_total = product.price * item_qty

    shipping = 100 if subtotal > 0 else 0

    return JsonResponse(
        {
            "success": True,
            "removed": quantity <= 0,
            "line_total": line_total,
            "subtotal": subtotal,
            "shipping": shipping,
            "total": subtotal + shipping,
            "cart_count": cart_count,
        }
    )


def buy_now(request, slug):
    product = get_object_or_404(Product, slug=slug)

    if request.method == "POST":
        qty_raw = request.POST.get("quantity", "1")
        size = request.POST.get("select_size") or ""
    else:
        qty_raw = request.GET.get("quantity", "1")
        size = request.GET.get("size", "")

    size = size.strip()

    try:
        quantity = int(qty_raw)
    except ValueError:
        quantity = 1

    if quantity < 1:
        quantity = 1

    if product.size_variant.exists() and not size:
        # If size is missing from the request, default to the first configured size.
        size = product.size_variant.values_list("size_name", flat=True).first() or ""
        if not size:
            messages.error(request, "Please select a size before Buy now.")
            return redirect("get_product", slug=product.slug)

    line_total = product.price * quantity
    subtotal = line_total
    checkout_items = [
        {
            "product": product,
            "quantity": quantity,
            "size": size,
            "line_total": line_total,
        }
    ]
    try:
        checkout_token = create_checkout_snapshot(
            request,
            [
                {
                    "product_id": str(item["product"].pk),
                    "quantity": item["quantity"],
                    "size": item["size"],
                }
                for item in checkout_items
            ],
        )
    except CheckoutSnapshotError as error:
        messages.error(request, str(error))
        return redirect("get_product", slug=product.slug)

    context = {
        "checkout_items": checkout_items,
        "subtotal": subtotal,
        "shipping": 100,
        "total": subtotal + 100,
        "back_url": "get_product",
        "back_url_kwargs": {"slug": product.slug},
        "checkout_token": checkout_token,
        "stripe_enabled": settings.STRIPE_ENABLED,
    }
    return render(request, "product/checkout.html", context)


def checkout(request):
    cart = _get_cart(request)
    checkout_items = []
    subtotal = 0

    for item in cart:
        product = Product.objects.filter(pk=item.get("product_id")).first()
        if not product:
            continue
        quantity = item.get("quantity", 1)
        line_total = product.price * quantity
        subtotal += line_total
        checkout_items.append(
            {
                "product": product,
                "quantity": quantity,
                "size": item.get("size", ""),
                "line_total": line_total,
            }
        )

    if not checkout_items:
        messages.error(request, "Your cart is empty.")
        return redirect("cart")

    try:
        checkout_token = create_checkout_snapshot(
            request,
            [
                {
                    "product_id": str(item["product"].pk),
                    "quantity": item["quantity"],
                    "size": item["size"],
                }
                for item in checkout_items
            ],
        )
    except CheckoutSnapshotError as error:
        messages.error(request, str(error))
        return redirect("cart")

    context = {
        "checkout_items": checkout_items,
        "subtotal": subtotal,
        "shipping": 100,
        "total": subtotal + 100,
        "back_url": "cart",
        "checkout_token": checkout_token,
        "stripe_enabled": settings.STRIPE_ENABLED,
    }
    return render(request, "product/checkout.html", context)


def category_products(request, slug):
    category = get_object_or_404(Category, slug=slug)
    sort = request.GET.get('sort', 'default')
    products = Product.objects.filter(category=category)
    if sort == 'price_low':
        products = products.order_by('price')
    elif sort == 'price_high':
        products = products.order_by('-price')
    context = {
        "products": products,
        "current_category": category,
        "current_sort": sort,
    }
    return render(request, "home/index.html", context)


def gender_products(request, gender):
    gender_upper = gender.upper()
    if gender_upper not in ('MEN', 'WOMEN'):
        return redirect('index')
    sort = request.GET.get('sort', 'default')
    products = Product.objects.filter(category__category_type=gender_upper)
    if sort == 'price_low':
        products = products.order_by('price')
    elif sort == 'price_high':
        products = products.order_by('-price')
    context = {
        "products": products,
        "current_gender": gender_upper,
        "current_sort": sort,
    }
    return render(request, "home/index.html", context)


def place_order(request):
    if request.method != "POST":
        return redirect("cart")

    # Collect form data
    email = request.POST.get("email", "").strip()
    phone = request.POST.get("phone", "").strip()
    first_name = request.POST.get("first_name", "").strip()
    last_name = request.POST.get("last_name", "").strip()
    street_address = request.POST.get("street_address", "").strip()
    city = request.POST.get("city", "").strip()
    state = request.POST.get("state", "").strip()
    zip_code = request.POST.get("zip_code", "").strip()
    payment_method = request.POST.get("payment_method", "cod").strip()

    # Validate payment method
    valid_methods = ['card', 'bkash', 'nagad', 'cod']
    if payment_method not in valid_methods:
        payment_method = 'cod'

    # Keep required fields in sync with checkout.html.
    required = [email, phone, first_name, last_name, city]
    if not all(required):
        messages.error(request, "Please fill in all required fields.")
        return redirect(request.META.get("HTTP_REFERER", "cart"))

    # Payment-specific fields
    transaction_id = ""
    reference = ""
    if payment_method == "bkash":
        transaction_id = request.POST.get("bkash_trx_id", "").strip()
        reference = request.POST.get("bkash_reference", "").strip()
        if not transaction_id:
            messages.error(request, "bKash Transaction ID is required.")
            return redirect(request.META.get("HTTP_REFERER", "cart"))
    elif payment_method == "nagad":
        transaction_id = request.POST.get("nagad_trx_id", "").strip()
        reference = request.POST.get("nagad_reference", "").strip()
        if not transaction_id:
            messages.error(request, "Nagad Transaction ID is required.")
            return redirect(request.META.get("HTTP_REFERER", "cart"))

    # Build order items from hidden fields
    product_ids = request.POST.getlist("product_ids")
    quantities = request.POST.getlist("quantities")
    sizes = request.POST.getlist("sizes")

    if not product_ids:
        messages.error(request, "No items to order.")
        return redirect("cart")

    subtotal = 0
    items_data = []
    for pid, qty_raw, size in zip(product_ids, quantities, sizes):
        product = Product.objects.filter(pk=pid).first()
        if not product:
            continue
        try:
            quantity = int(qty_raw)
        except (ValueError, TypeError):
            quantity = 1
        if quantity < 1:
            quantity = 1
        line_total = product.price * quantity
        subtotal += line_total
        items_data.append({
            "product": product,
            "quantity": quantity,
            "size": size,
            "line_total": line_total,
        })

    if not items_data:
        messages.error(request, "No valid items to order.")
        return redirect("cart")

    shipping = 100
    total = subtotal + shipping

    # Create order
    order = Order.objects.create(
        email=email,
        phone=phone,
        first_name=first_name,
        last_name=last_name,
        street_address=street_address,
        city=city,
        state=state,
        zip_code=zip_code,
        payment_method=payment_method,
        transaction_id=transaction_id,
        reference=reference,
        subtotal=subtotal,
        shipping=shipping,
        total=total,
    )

    for item in items_data:
        OrderItem.objects.create(
            order=order,
            product=item["product"],
            product_name=item["product"].product_name,
            size=item["size"],
            quantity=item["quantity"],
            price=item["product"].price,
            line_total=item["line_total"],
        )

    # Clear cart
    _save_cart(request, [])

    return redirect("invoice", order_number=order.order_number)


def invoice(request, order_number):
    order = get_object_or_404(Order, order_number=order_number)
    if order.payment_method == "stripe":
        if not request.user.is_staff and (
            not request.user.is_authenticated or order.user_id != request.user.id
        ):
            return HttpResponseForbidden("You do not have permission to view this invoice.")
    # Preserve the existing guest-compatible behavior for legacy payment methods.
    # Only allow the person who placed the order (or staff) to view the invoice
    elif not request.user.is_staff and order.email != request.POST.get('email', request.GET.get('email', '')):
        if request.user.is_authenticated and order.email != request.user.email:
            return HttpResponseForbidden("You do not have permission to view this invoice.")
    context = {
        "order": order,
        "order_items": order.items.all(),
    }
    return render(request, "product/invoice.html", context)
