"""Recommendation service placeholder.

Provides a clear interface boundary for Sprint 5's Personalized
Recommendation Engine.  Until then, all calls return a
``NotImplementedError``-style response so the system never generates
fake recommendations.
"""


class RecommendationService:
    """Interface for product recommendation logic.

    Sprint 5 will implement this with collaborative filtering,
    user preference vectors, and purchase history analysis.
    """

    @staticmethod
    def recommend(query: str, user=None, limit: int = 5) -> dict:
        """Return personalized product recommendations.

        Returns:
            dict with ``available`` flag and a human-readable ``message``
            when the engine is not yet implemented.
        """
        return {
            "available": False,
            "message": (
                "Personalized recommendations are coming soon! "
                "In the meantime, try searching for products directly."
            ),
            "products": [],
        }
