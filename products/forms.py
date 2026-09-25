from django import forms

from products.models import ProductReview


class ProductReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        choices=[
            (value, f"{value} star{'s' if value != 1 else ''}")
            for value in range(5, 0, -1)
        ],
        coerce=int,
        empty_value=None,
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    comment = forms.CharField(
        max_length=2000,
        strip=True,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Share your experience with this product",
            }
        ),
    )

    class Meta:
        model = ProductReview
        fields = ("rating", "comment")

    def clean_comment(self):
        comment = self.cleaned_data["comment"].strip()
        if not comment:
            raise forms.ValidationError("Review text is required.")
        return comment
