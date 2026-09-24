"""Pydantic schemas for the AI Assistant chat API.

These schemas define the request / response contract validated at the
API boundary so that business logic never handles raw JSON.
"""

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """Incoming chat request body."""

    message: str = Field(..., min_length=1, max_length=500)
    conversation_id: str | None = Field(default=None)

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Message must not be blank.")
        return stripped


class ProductResponse(BaseModel):
    """A single product in the API response."""

    id: int | str | None = None
    name: str = ""
    price: float | str | None = None
    image: str = ""
    category: str = ""
    metadata: dict = Field(default_factory=dict)


class ChatResponse(BaseModel):
    """Outgoing chat response body."""

    conversation_id: str
    answer: str
    products: list[ProductResponse] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
