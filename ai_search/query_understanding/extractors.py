"""
Rule-based extraction for query understanding.
Provides deterministic extraction for common attributes to complement or fallback from LLMs.
"""

import re
from typing import Any

# Simple dictionaries for common attributes
KNOWN_COLORS = {
    "black", "white", "blue", "red", "green", "yellow", "gray", "grey",
    "pink", "purple", "brown", "navy", "beige", "orange", "maroon",
    "olive", "teal", "cream", "khaki"
}
KNOWN_CATEGORIES = {
    "shirt", "shirts", "t-shirt", "t-shirts", "tshirt", "tshirts",
    "hoodie", "hoodies", "jacket", "jackets", "shoe", "shoes",
    "sneaker", "sneakers", "dress", "dresses", "pants", "jeans",
    "sweater", "sweaters", "cardigan", "cardigans", "blazer", "blazers",
    "suit", "suits", "saree", "sarees", "skirt", "skirts"
}
KNOWN_SIZES = {"xs", "s", "m", "l", "xl", "xxl", "xxxl", "2xl", "3xl"}

CATEGORY_PATTERNS: list[tuple[str, list[str]]] = [
    ("t-shirt", [r"\bt[\-\s]?shirts?\b", r"\btees?\b", r"\btshirt\b", r"\btshirts\b"]),
    ("shirt", [r"\bshirts?\b", r"\btops?\b", r"\bbutton[\-\s]?down\b", r"\boxford\b"]),
    ("hoodie", [r"\bhoodies?\b", r"\bsweatshirts?\b", r"\bhoody\b"]),
    ("suit", [r"\bsuits?\b", r"\bblazers?\b", r"\btuxedos?\b", r"\btux\b"]),
    ("sweater", [r"\bsweaters?\b", r"\bcardigans?\b", r"\bjumpers?\b", r"\bknit(?:wear)?\b", r"\bskirts?\b", r"\bskirt\b"]),
    ("jacket", [r"\bjackets?\b", r"\bcoats?\b", r"\bbombers?\b", r"\bblousons?\b"]),
    ("pants", [r"\bpants?\b", r"\bjeans?\b", r"\btrousers?\b", r"\bdenims?\b", r"\bjoggers?\b", r"\bbarrel pants\b"]),
    ("saree", [r"\bsarees?\b", r"\bsaris?\b", r"\bsari\b"]),
    ("shoe", [r"\bshoes?\b", r"\bsneakers?\b", r"\bboots?\b", r"\bfootwear\b"]),
]


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
    words = set(re.findall(r"\b[a-z]+\b", query.lower()))
    return list(words.intersection(KNOWN_COLORS))


def extract_categories(query: str) -> list[str]:
    """Extract known categories from query using pattern matching."""
    q = query.lower()
    q_norm = re.sub(r"[\-_]", " ", q)
    found = []
    for cat_name, patterns in CATEGORY_PATTERNS:
        for pat in patterns:
            if re.search(pat, q) or re.search(pat, q_norm):
                found.append(cat_name)
                break
    return found


def extract_sizes(query: str) -> list[str]:
    """Extract known sizes from query."""
    # Match standard alphabetic sizes as standalone words
    words = set(re.findall(r"\b[a-z0-9]+\b", query.lower()))
    sizes = list(words.intersection(KNOWN_SIZES))

    # Match numeric shoe/clothing sizes like 42, 43.5
    numeric_sizes = re.findall(r"\b(3[5-9]|4[0-9]|50)(?:\.[05])?\b", query)
    sizes.extend(numeric_sizes)

    return [s.upper() for s in sizes]


def extract_gender(query: str) -> str | None:
    """Extract target gender from query."""
    q = query.lower()
    if re.search(r"\b(women|woman|female|ladies|lady|girls?)\b", q):
        return "women"
    if re.search(r"\b(men|man|male|gents|gentleman|boys?)\b", q):
        return "men"
    return None


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
        data["category"] = categories[0]
        
    sizes = extract_sizes(query)
    if sizes:
        data["sizes"] = sizes

    gender = extract_gender(query)
    if gender:
        data["gender"] = gender
        
    return data
