from django.shortcuts import render
from django.shortcuts import redirect, render
from django.contrib import messages
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth import authenticate , login , logout
from django.http import HttpResponseRedirect,HttpResponse
from .models import Profile
from base.emails import send_account_activation_email
import logging
from django.utils.http import url_has_allowed_host_and_scheme


logger = logging.getLogger(__name__)
def _safe_login_redirect(request):
    candidate = request.POST.get("next") or request.GET.get("next") or ""
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return getattr(settings, 'LOGIN_REDIRECT_URL', '/')


def login_page(request):
    next_url = _safe_login_redirect(request)
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        if not User.objects.filter(username=email).exists():
            messages.warning(request, "Account not found.")
            return render(
                request,
                "accounts/login.html",
                {"next": next_url},
            )

        user_obj = authenticate(username=email, password=password)
        if user_obj:
            login(request, user_obj)
            return redirect(next_url)

        messages.warning(request, "Invalid credentials")
        return render(
            request,
            "accounts/login.html",
            {"next": next_url},
        )

    return render(
        request,
        "accounts/login.html",
        {"next": next_url},
    )
def register_page(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        user_obj = User.objects.filter(username = email)

        if user_obj.exists():
            messages.warning(request, 'Email is already taken.')
            return HttpResponseRedirect(request.path_info)
        
        print(email)

        user_obj = User.objects.create(first_name = first_name , last_name= last_name , email = email , username = email)
        user_obj.set_password(password)
        user_obj.save()

        email_token = str(user_obj.profile.email_token)
        email_user = (settings.EMAIL_HOST_USER or '').strip()
        email_password = (settings.EMAIL_HOST_PASSWORD or '').strip()

        if email_user and email_password:
            try:
                send_account_activation_email(email, email_token)
            except Exception as e:
                logger.exception('Activation email failed for user %s: %s', email, e)

        messages.success(request, 'Account created successfully. Please login.')
        return HttpResponseRedirect(request.path_info)

    return render(request,'accounts/register.html')
def logout_page(request):
    logout(request)
    return redirect('/')

def activate_email(request , email_token):
    try:
        user = Profile.objects.get(email_token= email_token)
        user.is_email_verified = True
        user.save()
        return redirect('/')
    except Exception as e:
        return HttpResponse('Invalid Email token')
