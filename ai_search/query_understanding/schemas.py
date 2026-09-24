"""
Query understanding schema definitions using Pydantic.
"""

from typing import Literal

from pydantic import BaseModel, Field


IntentType = Literal["product_search", "recommendation", "comparison", "general_question"]


class QueryAnalysis(BaseModel):
    """Structured search intent extracted from a user query."""

    original_query: str = Field(..., description="The exact raw query from the user.")
    intent: IntentType = Field(
        default="product_search",
        description="The primary intent of the user's query.",
    )
    category: str | None = Field(
        default=None,
        description="Product category (e.g., 'shirt', 'hoodie', 'jacket', 'shoe').",
    )
    brand: str | None = Field(
        default=None,
        description="Explicit brand name mentioned.",
    )
    colors: list[str] = Field(
        default_factory=list,
        description="Colors mentioned in the query.",
    )
    sizes: list[str] = Field(
        default_factory=list,
        description="Sizes mentioned (e.g., 'S', 'M', 'L', 'XL', '42').",
    )
    price_min: float | None = Field(
        default=None,
        description="Minimum requested price.",
    )
    price_max: float | None = Field(
        default=None,
        description="Maximum requested price.",
    )
    gender: str | None = Field(
        default=None,
        description="Target gender (e.g., 'men', 'women', 'unisex').",
    )
    occasion: str | None = Field(
        default=None,
        description="Occasion (e.g., 'casual', 'wedding', 'formal').",
    )
    season: str | None = Field(
        default=None,
        description="Season (e.g., 'winter', 'summer').",
    )
    style: str | None = Field(
        default=None,
        description="Style keywords.",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Important keywords extracted from the query that are not captured in other fields.",
    )

    def is_meaningful_filter(self) -> bool:
        """Return True if the analysis extracted any actionable metadata filters."""
        return any(
            [
                self.category,
                self.brand,
                self.colors,
                self.sizes,
                self.price_min is not None,
                self.price_max is not None,
                self.gender,
            ]
        )
