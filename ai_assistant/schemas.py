from typing import List, Optional
from pydantic import BaseModel, Field

class ProductSchema(BaseModel):
    id: int
    name: str
    price: float
    # We can add more fields if needed for the response

class ChatRequestSchema(BaseModel):
    message: str = Field(..., description="The user's chat message")

class ChatResponseSchema(BaseModel):
    message: str = Field(..., description="The assistant's response")
    products: List[ProductSchema] = Field(default_factory=list, description="Retrieved products")
    conversation_id: str = Field(..., description="The UUID of the conversation")
