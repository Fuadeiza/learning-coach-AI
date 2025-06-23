from pydantic import BaseModel 
from typing import Literal


class ExplainRequest(BaseModel):
    topic: str
    level: Literal["beginner", "intermediate", "advanced"] = "beginner"


class ExplainResponse(BaseModel):
    explanation: str
