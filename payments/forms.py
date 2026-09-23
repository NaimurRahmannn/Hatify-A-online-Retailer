from django import forms


class StripeCheckoutForm(forms.Form):
    checkout_token = forms.UUIDField()
    email = forms.EmailField()
    phone = forms.CharField(max_length=30)
    first_name = forms.CharField(max_length=100)
    last_name = forms.CharField(max_length=100)
    street_address = forms.CharField(max_length=300, required=False)
    city = forms.CharField(max_length=100)
    state = forms.CharField(max_length=100, required=False)
    zip_code = forms.CharField(max_length=20, required=False)
