"""Settings used by the automated test suite.

The deployed database is configured through ``.env``. Tests use an isolated
in-memory database so running them can never mutate deployed data.
"""

from .settings import *  # noqa: F403


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# PostgreSQL's CREATE EXTENSION statement is not available in SQLite. Let the
# test runner create the current ai_search models directly instead.
MIGRATION_MODULES = {"ai_search": None}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
