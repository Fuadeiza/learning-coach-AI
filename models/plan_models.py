from typing import List
from pydantic import BaseModel, Field

class StudySession(BaseModel):
    day: int = Field(..., description="The day of the study session.")
    topic: str = Field(..., description="The topic of the study session.")
    duration: str = Field(..., description="The duration of the study session.")

class StudyPlan(BaseModel):
    sessions: List[StudySession] = Field(..., description="A list of study sessions.")


class PlanRequest(BaseModel):
    topics: List[str]
    days: int
    daily_minutes: int = 30
    level: str = "beginner"