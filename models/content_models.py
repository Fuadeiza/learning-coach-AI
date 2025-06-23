from typing import List, Optional
from pydantic import BaseModel

class ContentRequest(BaseModel):
    topic: str
    level: str = "beginner"

class MaterialItem(BaseModel):
    title: str
    description: str
    url: str
    type: str  # video, article, documentation, course, book, tutorial
    provider: str
    difficulty: str
    estimated_time: str
    rating: Optional[str] = None

class ContentResponse(BaseModel):
    content: dict  # Enhanced response with materials, prerequisites, etc.

class EnhancedContentResponse(BaseModel):
    materials: List[MaterialItem]
    prerequisites: List[str]
    learning_path: List[str]
    related_topics: List[str]
    topic: str
    level: str