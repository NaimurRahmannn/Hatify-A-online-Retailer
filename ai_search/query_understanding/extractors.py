"""
Rule-based extraction for query understanding.
Provides deterministic extraction for common attributes to complement or fallback from LLMs.
"""

import re
from typing import Any

# Simple dictionaries for common attributes
KNOWN_COLORS = {"black", "white", "blue", "red", "green", "yellow", "gray", "grey", "pink", "purple", "brown", "navy"}
KNOWN_CATEGORIES = {"shirt", "t-shirt", "tshirt", "hoodie", "jacket", "shoe", "shoes", "sneaker", "sneakers", "dress", "pants", "jeans"}
KNOWN_SIZES = {"xs", "s", "m", "l", "xl", "xxl"}


def extract_price(query: str) -> dict[str, float]:
    """Extract price_min and price_max from a query using regex."""
    result: dict[str, float] = {}
    query_lower = query.lower()

    # Match "between X and Y"
    between_match = re.search(r"between\s+(\d+(?:\.\d+)?)\s+and\s+(\d+(?:\.\d+)?)", query_lower)
    if between_match:
        result["price_min"] = float(between_match.group(1))
        result["price_max"] = float(between_match.group(2))
        return result

    # Match "under X" or "below X" or "< X"
    under_match = re.search(r"(?:under|below|<)\s*(\d+(?:\.\d+)?)", query_lower)
    if under_match:
        result["price_max"] = float(under_match.group(1))
    
    # Match "over X" or "above X" or "> X"
    over_match = re.search(r"(?:over|above|>)\s*(\d+(?:\.\d+)?)", query_lower)
    if over_match:
        result["price_min"] = float(over_match.group(1))

    return result


def extract_colors(query: str) -> list[str]:
    """Extract known colors from query."""
    words = set(re.findall(r"\b\w+\b", query.lower()))
    return list(words.intersection(KNOWN_COLORS))


def extract_categories(query: str) -> list[str]:
    """Extract known categories from query."""
    words = set(re.findall(r"\b\w+\b", query.lower()))
    # normalize plurals/variants back to base
    found = []
    for w in words:
        if w in KNOWN_CATEGORIES:
            if w in ("shoes", "sneaker", "sneakers"):
                found.append("shoe")
            elif w in ("t-shirt", "tshirt"):
                found.append("shirt")
            elif w == "jeans":
                found.append("pants")
            else:
                found.append(w)
    return list(set(found))


def extract_sizes(query: str) -> list[str]:
    """Extract known sizes from query."""
    # Match standard alphabetic sizes as standalone words
    words = set(re.findall(r"\b\w+\b", query.lower()))
    sizes = list(words.intersection(KNOWN_SIZES))

    # Match numeric shoe/clothing sizes like 42, 43.5
    numeric_sizes = re.findall(r"\b(3[5-9]|4[0-9]|50)(?:\.[05])?\b", query)
    sizes.extend(numeric_sizes)

    return [s.upper() for s in sizes]


def apply_rules(query: str) -> dict[str, Any]:
    """Apply all rules to extract parameters from query."""
    data: dict[str, Any] = {}
    
    prices = extract_price(query)
    if "price_min" in prices:
        data["price_min"] = prices["price_min"]
    if "price_max" in prices:
        data["price_max"] = prices["price_max"]
        
    colors = extract_colors(query)
    if colors:
        data["colors"] = colors
        
    categories = extract_categories(query)
    if categories:
        data["category"] = categories[0]  # Just take the first for simplicity
        
    sizes = extract_sizes(query)
    if sizes:
        data["sizes"] = sizes
        
    return data
