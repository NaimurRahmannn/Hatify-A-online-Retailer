from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from unittest.mock import patch

from products.forms import ProductReviewForm
from products.models import Category, Order, OrderItem, Product, ProductReview
from products.review_service import build_review_summary, get_ordered_unit_count


class ReviewFixtureMixin:
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="reviewer@example.com",
            email="reviewer@example.com",
            password="secret-pass",
            first_name="Review",
            last_name="User",
        )
        self.other_user = get_user_model().objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="secret-pass",
        )
        self.category = Category.objects.create(categroy_name="Shirts")
        self.product = Product.objects.create(
            product_name="Oxford Shirt",
            category=self.category,
            price=Decimal("1500.00"),
            product_description="Cotton Oxford shirt",
        )


class ProductReviewModelTests(ReviewFixtureMixin, TestCase):
    def test_valid_review_passes_model_validation(self):
        review = ProductReview(
            product=self.product,
            user=self.user,
            rating=5,
            comment="Excellent fit.",
        )

        review.full_clean()

    def test_rating_outside_one_to_five_fails_validation(self):
        for rating in (0, 6):
            with self.subTest(rating=rating):
                review = ProductReview(
                    product=self.product,
                    user=self.user,
                    rating=rating,
                    comment="Invalid rating",
                )

                with self.assertRaises(ValidationError):
                    review.full_clean()

    def test_database_rejects_duplicate_user_product_review(self):
        ProductReview.objects.create(
            product=self.product,
            user=self.user,
            rating=4,
            comment="First review",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductReview.objects.create(
                product=self.product,
                user=self.user,
                rating=3,
                comment="Duplicate review",
            )

    def test_database_rejects_rating_outside_constraint(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductReview.objects.create(
                product=self.product,
                user=self.user,
                rating=0,
                comment="Database constraint",
            )

    def test_different_users_can_review_same_product(self):
        for user in (self.user, self.other_user):
            ProductReview.objects.create(
                product=self.product,
                user=user,
                rating=4,
                comment="Valid review",
            )

        self.assertEqual(ProductReview.objects.count(), 2)

    def test_same_user_can_review_different_products(self):
        second_product = Product.objects.create(
            product_name="Linen Shirt",
            category=self.category,
            price=Decimal("1800.00"),
            product_description="Linen shirt",
        )
        for product in (self.product, second_product):
            ProductReview.objects.create(
                product=product,
                user=self.user,
                rating=4,
                comment="Valid review",
            )

        self.assertEqual(ProductReview.objects.count(), 2)


class ProductReviewFormTests(ReviewFixtureMixin, TestCase):
    def test_form_coerces_rating_and_strips_comment(self):
        form = ProductReviewForm(
            {"rating": "4", "comment": "  Useful review  "}
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["rating"], 4)
        self.assertEqual(form.cleaned_data["comment"], "Useful review")

    def test_form_rejects_blank_overlong_and_invalid_rating(self):
        cases = (
            ({"rating": "4", "comment": "   "}, "comment"),
            ({"rating": "4", "comment": "x" * 2001}, "comment"),
            ({"rating": "8", "comment": "Text"}, "rating"),
        )
        for data, field in cases:
            with self.subTest(data=data, field=field):
                form = ProductReviewForm(data)

                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)


def create_order(
    product,
    quantity,
    payment_status=Order.PaymentStatus.PENDING,
    order_status="pending",
):
    order = Order.objects.create(
        email="buyer@example.com",
        phone="01700000000",
        first_name="Buyer",
        last_name="One",
        street_address="Road 1",
        city="Dhaka",
        state="",
        zip_code="",
        payment_method="cod",
        payment_status=payment_status,
        order_status=order_status,
        subtotal=product.price * quantity,
        shipping=Decimal("100.00"),
        total=(product.price * quantity) + Decimal("100.00"),
    )
    OrderItem.objects.create(
        order=order,
        product=product,
        product_name=product.product_name,
        size="",
        quantity=quantity,
        price=product.price,
        line_total=product.price * quantity,
    )
    return order


class ProductMetricServiceTests(ReviewFixtureMixin, TestCase):
    def test_empty_review_summary_is_zero_with_empty_stars(self):
        summary = build_review_summary(self.product)

        self.assertEqual(summary.count, 0)
        self.assertEqual(summary.average, 0.0)
        self.assertEqual(summary.stars, ("empty",) * 5)

    def test_review_summary_calculates_average_and_half_star(self):
        ProductReview.objects.create(
            product=self.product,
            user=self.user,
            rating=4,
            comment="Good",
        )
        ProductReview.objects.create(
            product=self.product,
            user=self.other_user,
            rating=5,
            comment="Great",
        )

        summary = build_review_summary(self.product)

        self.assertEqual(summary.count, 2)
        self.assertEqual(summary.average, 4.5)
        self.assertEqual(
            summary.stars,
            ("full", "full", "full", "full", "half"),
        )

    def test_ordered_units_sum_quantities_and_exclude_invalid_outcomes(self):
        create_order(self.product, 2, payment_status=Order.PaymentStatus.PENDING)
        create_order(self.product, 3, payment_status=Order.PaymentStatus.PAID)
        create_order(self.product, 5, payment_status=Order.PaymentStatus.FAILED)
        create_order(
            self.product,
            7,
            payment_status=Order.PaymentStatus.CANCELLED,
        )
        create_order(
            self.product,
            11,
            payment_status=Order.PaymentStatus.REFUNDED,
        )
        create_order(
            self.product,
            13,
            payment_status=Order.PaymentStatus.PENDING,
            order_status="cancelled",
        )

        self.assertEqual(get_ordered_unit_count(self.product), 5)

    def test_product_without_order_lines_has_zero_ordered_units(self):
        self.assertEqual(get_ordered_unit_count(self.product), 0)


class ProductReviewDetailTests(ReviewFixtureMixin, TestCase):
    def test_product_detail_exposes_summary_orders_and_own_review(self):
        own_review = ProductReview.objects.create(
            product=self.product,
            user=self.user,
            rating=4,
            comment="My review",
        )
        create_order(self.product, 3, payment_status=Order.PaymentStatus.PAID)
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("get_product", args=[self.product.slug])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["review_summary"].count, 1)
        self.assertEqual(response.context["ordered_unit_count"], 3)
        self.assertEqual(response.context["own_review"], own_review)
        self.assertEqual(response.context["review_form"].instance, own_review)

    def test_invalid_review_page_number_falls_back_to_a_valid_page(self):
        response = self.client.get(
            reverse("get_product", args=[self.product.slug]),
            {"reviews_page": "not-a-page"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["reviews"].number, 1)

    def test_review_list_is_paginated_ten_per_page(self):
        users = [
            get_user_model().objects.create_user(username=f"user-{number}")
            for number in range(11)
        ]
        ProductReview.objects.bulk_create(
            [
                ProductReview(
                    product=self.product,
                    user=user,
                    rating=4,
                    comment=f"Review {number}",
                )
                for number, user in enumerate(users)
            ]
        )

        response = self.client.get(
            reverse("get_product", args=[self.product.slug])
        )

        self.assertEqual(len(response.context["reviews"]), 10)
        self.assertEqual(response.context["reviews"].paginator.num_pages, 2)

    def test_reviews_are_ordered_newest_first(self):
        older = ProductReview.objects.create(
            product=self.product,
            user=self.user,
            rating=3,
            comment="Older",
        )
        import time; time.sleep(0.05)
        newer = ProductReview.objects.create(
            product=self.product,
            user=self.other_user,
            rating=5,
            comment="Newer",
        )

        response = self.client.get(
            reverse("get_product", args=[self.product.slug])
        )

        self.assertEqual(list(response.context["reviews"]), [newer, older])

    def test_query_count_does_not_grow_with_review_volume(self):
        url = reverse("get_product", args=[self.product.slug])
        with CaptureQueriesContext(connection) as baseline_queries:
            baseline_response = self.client.get(url)
        self.assertIn("reviews", baseline_response.context)
        users = [
            get_user_model().objects.create_user(username=f"scale-{number}")
            for number in range(25)
        ]
        ProductReview.objects.bulk_create(
            [
                ProductReview(
                    product=self.product,
                    user=user,
                    rating=5,
                    comment="Scale review",
                )
                for user in users
            ]
        )

        with CaptureQueriesContext(connection) as populated_queries:
            self.client.get(url)

        self.assertLessEqual(
            len(populated_queries),
            len(baseline_queries) + 1,
        )


class ProductReviewSubmissionTests(ReviewFixtureMixin, TestCase):
    def review_url(self):
        return reverse("submit_review", args=[self.product.slug])

    def test_anonymous_submission_redirects_to_login(self):
        response = self.client.post(
            self.review_url(),
            {"rating": "5", "comment": "Guest attempt"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])
        self.assertEqual(ProductReview.objects.count(), 0)

    def test_signed_in_user_can_review_without_an_order(self):
        self.client.force_login(self.user)
        response = self.client.post(
            self.review_url(),
            {"rating": "5", "comment": "No purchase required"},
        )
        review = ProductReview.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(review.user, self.user)
        self.assertEqual(review.product, self.product)
        self.assertTrue(response["Location"].endswith("#reviews"))

    def test_second_submission_updates_the_existing_row(self):
        review = ProductReview.objects.create(
            product=self.product,
            user=self.user,
            rating=2,
            comment="Old text",
        )
        self.client.force_login(self.user)
        self.client.post(
            self.review_url(),
            {"rating": "5", "comment": "Updated text"},
        )
        review.refresh_from_db()
        self.assertEqual(ProductReview.objects.count(), 1)
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.comment, "Updated text")

    def test_posted_foreign_identifiers_cannot_edit_another_users_review(self):
        foreign = ProductReview.objects.create(
            product=self.product,
            user=self.other_user,
            rating=1,
            comment="Other review",
        )
        self.client.force_login(self.user)
        self.client.post(
            self.review_url(),
            {
                "rating": "4",
                "comment": "My review",
                "user": str(self.other_user.pk),
                "uid": str(foreign.pk),
            },
        )
        foreign.refresh_from_db()
        self.assertEqual(foreign.comment, "Other review")
        self.assertTrue(
            ProductReview.objects.filter(
                product=self.product,
                user=self.user,
                comment="My review",
            ).exists()
        )

    def test_get_is_not_allowed_on_submission_endpoint(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.review_url()).status_code, 405)

    def test_invalid_submission_returns_400_with_bound_errors(self):
        self.client.force_login(self.user)
        response = self.client.post(
            self.review_url(),
            {"rating": "9", "comment": ""},
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.context["review_form"].errors)
        self.assertEqual(ProductReview.objects.count(), 0)

    @patch("products.views.ProductReview.save", side_effect=IntegrityError)
    def test_uniqueness_race_returns_safe_redirect(self, _save):
        self.client.force_login(self.user)
        response = self.client.post(
            self.review_url(),
            {"rating": "4", "comment": "Concurrent review"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].endswith("#reviews"))

class ProductReviewTemplateTests(ReviewFixtureMixin, TestCase):
    def test_product_page_uses_live_counts_not_placeholders(self):
        ProductReview.objects.create(
            product=self.product,
            user=self.user,
            rating=4,
            comment="Live review",
        )
        create_order(self.product, 2, payment_status=Order.PaymentStatus.PAID)
        response = self.client.get(reverse("get_product", args=[self.product.slug]))
        self.assertContains(response, "1 review")
        self.assertContains(response, "2 orders")
        self.assertNotContains(response, "132 reviews")
        self.assertNotContains(response, "154 orders")

    def test_guest_sees_login_prompt_but_not_review_form(self):
        response = self.client.get(reverse("get_product", args=[self.product.slug]))
        self.assertContains(response, "Sign in to write a review")
        self.assertNotContains(response, 'id="product-review-form"')

    def test_signed_in_user_sees_create_or_edit_form(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("get_product", args=[self.product.slug]))
        self.assertContains(response, 'id="product-review-form"')
        self.assertContains(response, "Write a review")
        ProductReview.objects.create(
            product=self.product,
            user=self.user,
            rating=4,
            comment="Existing text",
        )
        response = self.client.get(reverse("get_product", args=[self.product.slug]))
        self.assertContains(response, "Update your review")
        self.assertContains(response, "Existing text")

    def test_review_comment_is_html_escaped(self):
        ProductReview.objects.create(
            product=self.product,
            user=self.user,
            rating=3,
            comment='<script>alert("xss")</script>',
        )
        response = self.client.get(reverse("get_product", args=[self.product.slug]))
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, '<script>alert("xss")</script>')

    def test_zero_and_singular_labels_are_grammatical(self):
        response = self.client.get(reverse("get_product", args=[self.product.slug]))
        self.assertContains(response, "0 reviews")
        self.assertContains(response, "0 orders")
        ProductReview.objects.create(
            product=self.product,
            user=self.user,
            rating=5,
            comment="Only review",
        )
        create_order(self.product, 1, payment_status=Order.PaymentStatus.PENDING)
        response = self.client.get(reverse("get_product", args=[self.product.slug]))
        self.assertContains(response, "1 review")
        self.assertContains(response, "1 order")

from django.contrib import admin

class ProductReviewAdminTests(ReviewFixtureMixin, TestCase):
    def test_review_is_registered_in_admin(self):
        self.assertIn(ProductReview, admin.site._registry)

    def test_review_identity_is_readonly_after_creation(self):
        model_admin = admin.site._registry[ProductReview]
        review = ProductReview.objects.create(
            product=self.product,
            user=self.user,
            rating=5,
            comment="Admin test",
        )
        readonly = model_admin.get_readonly_fields(None, review)
        self.assertIn("product", readonly)
        self.assertIn("user", readonly)
