from typing import List
from pydantic import BaseModel, Field

class Question(BaseModel):
    question: str = Field(..., description="The text of the question.")
    options: List[str] = Field(..., description="A list of possible answer options.")
    answer: str = Field(..., description="The correct answer option (e.g., 'B').")

class Quiz(BaseModel):
    questions: List[Question] = Field(..., description="A list of question objects.")

class QuizRequest(BaseModel):
    topic: str
    content: str
    level: str = "beginner"
    num_questions: int = 5
    difficulty: str = "easy"