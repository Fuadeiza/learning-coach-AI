from pydantic import BaseModel, Field
from typing import Optional, List

class UserCreateRequest(BaseModel):
    email: Optional[str] = Field(None, description="User email (optional for anonymous users)")
    user_name: Optional[str] = Field(None, description="Display name for the user")

class UserResponse(BaseModel):
    user_id: str
    
class UserDetailsResponse(BaseModel):
    id: str
    email: Optional[str]
    user_name: Optional[str]

class SessionStartRequest(BaseModel):
    user_id: str = Field(..., description="UUID of the user")
    topic: str = Field(..., description="Learning topic")
    level: str = Field(..., description="Difficulty level: beginner, intermediate, advanced")
    wants_quiz: bool = Field(default=False, description="Whether user wants quiz generation")
    wants_plan: bool = Field(default=False, description="Whether user wants study plan generation")

class SessionEndRequest(BaseModel):
    session_id: str = Field(..., description="UUID of the session to end")

class SessionResponse(BaseModel):
    session_id: str

class MessageResponse(BaseModel):
    message: str

class ActivityLogRequest(BaseModel):
    session_id: str = Field(..., description="UUID of the session")
    type: str = Field(..., description="Activity type: explanation, quiz, plan, materials")
    content: dict = Field(..., description="Activity content as JSON")

class ProgressUpdateRequest(BaseModel):
    user_id: str = Field(..., description="UUID of the user")
    topic: str = Field(..., description="Learning topic")
    level: str = Field(..., description="Difficulty level")
    status: str = Field(default="started", description="Progress status: started, completed, reviewed")

class QuizAttemptRequest(BaseModel):
    session_id: str = Field(..., description="UUID of the session")
    question_id: str = Field(..., description="UUID of the question")
    user_answer: str = Field(..., description="User's answer")
    is_correct: bool = Field(..., description="Whether the answer was correct")
    difficulty: str = Field(..., description="Question difficulty: easy, intermediate, hard")

class QuestionCreateRequest(BaseModel):
    topic: str = Field(..., description="Question topic")
    level: str = Field(..., description="Difficulty level")
    difficulty: str = Field(..., description="Question difficulty")
    question_text: str = Field(..., description="The question text")
    correct_answer: str = Field(..., description="The correct answer")
    options: List[str] = Field(..., description="List of answer options")

class QuestionResponse(BaseModel):
    question_id: str

class QuestionMatchResponse(BaseModel):
    question_id: Optional[str]

class PaginationParams(BaseModel):
    limit: int = Field(default=50, ge=1, le=1000, description="Number of items to return")
    offset: int = Field(default=0, ge=0, description="Number of items to skip")

class PaginationInfo(BaseModel):
    total_count: int
    limit: int
    offset: int
    current_page: int
    total_pages: int
    has_more: bool
    has_previous: bool

class SessionsResponse(BaseModel):
    sessions: List[dict]
    total_count: int
    limit: int
    offset: int
    has_more: bool

class ActivitiesResponse(BaseModel):
    activities: List[dict]
    total_count: int
    limit: int
    offset: int
    has_more: bool

class UserAnalyticsResponse(BaseModel):
    user_id: str
    total_sessions: int
    completed_sessions: int
    active_sessions: int
    total_topics: int
    completed_topics: int
    completion_rate: float
    learning_streak: int
    quiz_accuracy: float
    favorite_topics: List[dict]
    progress_distribution: dict
    recent_activity: dict

class QuizResultsResponse(BaseModel):
    session_id: str
    topic: str
    level: str
    total_questions: int
    attempts: List[dict]
    summary: dict
    recommendations: dict

class AchievementResponse(BaseModel):
    current_streak: int
    longest_streak: int
    achievements: List[dict]
    next_milestone: dict

class StudyTimeRequest(BaseModel):
    topic: str = Field(..., description="Topic being studied")
    level: str = Field(default="beginner", description="Study level")

class StudyTimeResponse(BaseModel):
    study_session_id: str
    started_at: str

class StudyTimeStatsResponse(BaseModel):
    today: str
    this_week: str
    average_daily: str
    most_productive_time: str

class AdaptiveQuizRequest(BaseModel):
    topic: str
    content: str
    level: str = "beginner"
    user_performance_history: Optional[List[dict]] = None

class LeaderboardEntry(BaseModel):
    rank: int
    user_id: str
    user_name: Optional[str]
    points: int
    level: str
    achievements_count: int
    streak_days: int
    topics_completed: int
    quiz_accuracy: float

class LeaderboardResponse(BaseModel):
    leaderboard: List[LeaderboardEntry]
    user_rank: Optional[int]
    total_users: int
    timeframe: str
    last_updated: str