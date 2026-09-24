"""Normalization helpers shared by query understanding and filtering."""

from collections.abc import Callable, Iterable


def normalize_query(query: str) -> str:
    """Return the canonical form used for cache identity and analytics."""
    return " ".join(query.split()).casefold()


def unique_values(
    values: Iterable[object],
    *,
    transform: Callable[[str], str] | None = None,
) -> list[str]:
    """Clean and deduplicate values while preserving their first-seen order."""
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned = " ".join(str(value).split())
        if not cleaned:
            continue
        normalized = transform(cleaned) if transform else cleaned
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)

    return result
