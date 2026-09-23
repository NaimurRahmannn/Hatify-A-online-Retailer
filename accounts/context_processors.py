from django.conf import settings


def google_auth(request):
    return {"google_auth_enabled": settings.GOOGLE_AUTH_ENABLED}
