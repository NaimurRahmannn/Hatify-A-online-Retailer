"""Settings used by the automated test suite.

The deployed database is configured through ``.env``. Tests use an isolated
database selected independently from the deployed ``DATABASE_URL``.
"""

import os

import dj_database_url

from .settings import *  # noqa: F403


AI_SEARCH_TEST_DATABASE_URL = os.environ.get(
    "AI_SEARCH_TEST_DATABASE_URL", ""
).strip()

if AI_SEARCH_TEST_DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            AI_SEARCH_TEST_DATABASE_URL,
            conn_max_age=0,
        ),
    }
    AI_SEARCH_ENABLE_POSTGRES_INDEXES = True
    MIGRATION_MODULES = {}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
    AI_SEARCH_ENABLE_POSTGRES_INDEXES = False
    # PostgreSQL's CREATE EXTENSION statement is not available in SQLite. Let
    # the test runner create current ai_search models directly, with the
    # PostgreSQL-only runtime indexes disabled above.
    MIGRATION_MODULES = {"ai_search": None}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "haatify-ai-search-tests",
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

MIDDLEWARE = [
    middleware
    for middleware in MIDDLEWARE
    if middleware != "whitenoise.middleware.WhiteNoiseMiddleware"
]
