from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import resolve, reverse

from accounts.views import login_page, register_page


class GoogleAuthConfigurationTests(SimpleTestCase):
    def test_google_enabled_matches_complete_credentials(self):
        expected = bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)
        self.assertIs(settings.GOOGLE_AUTH_ENABLED, expected)
        google = settings.SOCIALACCOUNT_PROVIDERS["google"]
        self.assertEqual("APP" in google, expected)

    def test_google_provider_uses_secure_account_linking(self):
        google = settings.SOCIALACCOUNT_PROVIDERS["google"]
        self.assertEqual(google["SCOPE"], ["profile", "email"])
        self.assertEqual(google["AUTH_PARAMS"], {"access_type": "online"})
        self.assertIs(google["OAUTH_PKCE_ENABLED"], True)
        self.assertIs(google["EMAIL_AUTHENTICATION"], True)
        self.assertIs(google["EMAIL_AUTHENTICATION_AUTO_CONNECT"], True)
        self.assertIs(settings.SOCIALACCOUNT_LOGIN_ON_GET, False)
        self.assertIs(settings.SOCIALACCOUNT_STORE_TOKENS, False)


class AuthenticationRouteTests(SimpleTestCase):
    def test_existing_login_route_is_preserved(self):
        self.assertIs(resolve(reverse("login")).func, login_page)

    def test_existing_registration_route_is_preserved(self):
        self.assertIs(resolve(reverse("register")).func, register_page)

    def test_google_routes_resolve(self):
        self.assertEqual(reverse("google_login"), "/accounts/google/login/")
        self.assertEqual(
            reverse("google_callback"),
            "/accounts/google/login/callback/",
        )


TEST_GOOGLE_PROVIDER = {
    "google": {
        "APP": {
            "client_id": "test-client.apps.googleusercontent.com",
            "secret": "test-secret",
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        "OAUTH_PKCE_ENABLED": True,
        "EMAIL_AUTHENTICATION": True,
        "EMAIL_AUTHENTICATION_AUTO_CONNECT": True,
    }
}


@override_settings(
    GOOGLE_AUTH_ENABLED=True,
    SOCIALACCOUNT_PROVIDERS=TEST_GOOGLE_PROVIDER,
)
class GoogleAuthTemplateTests(TestCase):
    def test_login_page_has_csrf_protected_google_post(self):
        response = self.client.get(reverse("login"))
        self.assertContains(
            response,
            'action="/accounts/google/login/?process=login"',
        )
        self.assertContains(response, 'method="post"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, "Continue with Google")
        self.assertContains(response, "images/logos/google_symbol.png")

    def test_registration_page_has_google_post(self):
        response = self.client.get(reverse("register"))
        self.assertContains(
            response,
            'action="/accounts/google/login/?process=login"',
        )
        self.assertContains(response, 'method="post"')
        self.assertContains(response, "Continue with Google")

    def test_google_get_does_not_start_oauth(self):
        response = self.client.get(reverse("google_login"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("accounts.google.com", response.get("Location", ""))

    def test_google_post_starts_oauth(self):
        response = self.client.post(reverse("google_login"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("accounts.google.com", response["Location"])


@override_settings(GOOGLE_AUTH_ENABLED=False)
class DisabledGoogleAuthTemplateTests(SimpleTestCase):
    def test_login_page_hides_google_action(self):
        response = self.client.get(reverse("login"))
        self.assertNotContains(response, "Continue with Google")

    def test_registration_page_hides_google_action(self):
        response = self.client.get(reverse("register"))
        self.assertNotContains(response, "Continue with Google")


class GoogleLogoTests(SimpleTestCase):
    def test_google_logo_is_discoverable(self):
        self.assertIsNotNone(finders.find("images/logos/google_symbol.png"))
