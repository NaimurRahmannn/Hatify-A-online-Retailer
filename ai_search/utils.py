"""Small text-normalization helpers for AI search documents."""

import html
import re
from collections.abc import Iterable
from typing import Any

from django.utils.html import strip_tags


_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(value: Any) -> str:
    """Convert a value to clean, single-spaced plain text."""
    if value is None:
        return ""

    plain_text = strip_tags(html.unescape(str(value)))
    return _WHITESPACE_RE.sub(" ", plain_text).strip()


def unique_clean_values(values: Iterable[Any]) -> list[str]:
    """Normalize, de-duplicate, and deterministically order text values."""
    unique = {
        cleaned.casefold(): cleaned
        for value in values
        if (cleaned := normalize_text(value))
    }
    return sorted(unique.values(), key=str.casefold)
