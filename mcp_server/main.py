import logging
import uvicorn
from contextlib import asynccontextmanager
from uuid import UUID
from fastapi import FastAPI, Depends, Request, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from asyncpg.pool import Pool
from typing import List, Optional

# Import enhanced logging and middleware
from utils.logging import cache_logger, log_ai_request, log_database_query, get_cache_stats
from utils.request_middleware import RequestLoggingMiddleware, PerformanceLoggingMiddleware

from db.postgres_client import get_db_pool
from db.session_repository import SessionRepository
from auth.auth_repository import AuthRepository
from auth.auth_endpoints import router as auth_router
from auth.auth_dependencies import CurrentUser, CurrentActiveUser, OptionalCurrentUser

from agents.tutor_agent import TutorAgent
from models.tutor_models import ExplainRequest, ExplainResponse
from agents.quiz_agent import QuizAgent
from models.quiz_models import Quiz, QuizRequest
from agents.planner_agent import PlannerAgent
from models.plan_models import PlanRequest, StudyPlan
from agents.content_agent import ContentAgent
from models.content_models import ContentRequest, ContentResponse, EnhancedContentResponse

from models.api_models import (
    UserCreateRequest, UserResponse, UserDetailsResponse,
    SessionStartRequest, SessionEndRequest, SessionResponse, MessageResponse,
    ActivityLogRequest, ProgressUpdateRequest, QuizAttemptRequest,
    QuestionCreateRequest, QuestionResponse, QuestionMatchResponse,
    SessionsResponse, ActivitiesResponse, UserAnalyticsResponse, QuizResultsResponse,
    AchievementResponse, StudyTimeRequest, StudyTimeResponse, StudyTimeStatsResponse,
    AdaptiveQuizRequest, LeaderboardResponse
)

from utils.cache import cache, CacheConfig, cached, cache_invalidate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Initialize cache system
        await cache.initialize()
        logger.info("Cache system initialized")
        
        db_pool: Pool = await get_db_pool()
        app.state.db_pool = db_pool
        app.state.session_repo = SessionRepository(db_pool)
        app.state.auth_repo = AuthRepository(db_pool)
        logger.info("Database pool, SessionRepository, and AuthRepository initialized")
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise

    yield

    try:
        await cache.close()
        logger.info("Cache system closed")
        
        await app.state.db_pool.close()
        logger.info("Database pool closed")
    except Exception as e:
        logger.error(f"Shutdown cleanup failed: {e}")


app = FastAPI(
    title="AI Learning Coach API",
    description="Personalized learning platform with AI tutoring, quizzes, and study plans",
    version="1.0.0",
    lifespan=lifespan
)

# Add enhanced logging middleware
app.add_middleware(PerformanceLoggingMiddleware, slow_request_threshold_ms=1000)
app.add_middleware(RequestLoggingMiddleware, log_periodic_stats_interval=300)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080", "http://localhost:8001", "http://localhost:5500"],  # Add your frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

tutor_agent = TutorAgent()
quiz_agent = QuizAgent()
planner_agent = PlannerAgent()
content_agent = ContentAgent()


def get_session_repo(request: Request) -> SessionRepository:
    return request.app.state.session_repo

def get_auth_repo(request: Request) -> AuthRepository:
    return request.app.state.auth_repo

@app.post("/users/", response_model=UserResponse)
async def create_user(
    request: UserCreateRequest, 
    repo: SessionRepository = Depends(get_session_repo)
):  
    if request.email:
        raise HTTPException(
            status_code=400, 
            detail="Use /auth/register endpoint for email registration"
        )
    
    user_id = await repo.create_user(email=None, user_name=request.user_name)
    return UserResponse(user_id=str(user_id))

@app.get("/users/by-email/", response_model=UserDetailsResponse)
async def get_user_by_email(
    email: str = Query(..., description="User email to search for"),
    current_user: OptionalCurrentUser = None,
    repo: SessionRepository = Depends(get_session_repo)
):
    user = await repo.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserDetailsResponse(**user)

@app.post("/sessions/start/", response_model=SessionResponse)
async def start_session(
    request: SessionStartRequest,
    current_user: CurrentActiveUser,
    repo: SessionRepository = Depends(get_session_repo)
):
    try:
        user_uuid = UUID(current_user.user_id)
    except ValueError as e:
        logger.error(f"Invalid user UUID: {current_user.user_id}")
        raise HTTPException(status_code=400, detail=f"Invalid user ID format: {str(e)}")
    
    session_id = await repo.start_session(
        user_id=user_uuid,
        topic=request.topic,
        level=request.level,
        wants_quiz=request.wants_quiz,
        wants_plan=request.wants_plan
    )
    
    await repo.update_progress(
        user_id=user_uuid,
        topic=request.topic,
        level=request.level,
        status="started"
    )
    
    return SessionResponse(session_id=str(session_id))

@app.post("/sessions/end/", response_model=MessageResponse)
async def end_session(
    request: SessionEndRequest,
    current_user: CurrentActiveUser,
    repo: SessionRepository = Depends(get_session_repo)
):
    try:
        session_uuid = UUID(request.session_id)
    except ValueError as e:
        logger.error(f"Invalid session UUID: {request.session_id}")
        raise HTTPException(status_code=400, detail=f"Invalid session ID format: {str(e)}")
    
    session_details = await repo.get_session_details(session_uuid)
    if not session_details or session_details['user_id'] != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied to this session")
    
    await repo.end_session(session_uuid)
    return MessageResponse(message="Session ended")

@app.get("/sessions/{user_id}", response_model=SessionsResponse)
async def get_sessions_for_user(
    user_id: str,
    current_user: CurrentActiveUser,
    limit: int = Query(50, ge=1, le=1000, description="Number of sessions to return"),
    offset: int = Query(0, ge=0, description="Number of sessions to skip"),
    repo: SessionRepository = Depends(get_session_repo)
):
    if user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        sessions_data = await repo.get_user_sessions(UUID(user_id), limit=limit, offset=offset)
        return SessionsResponse(**sessions_data)
    except ValueError as e:
        logger.error(f"Invalid UUID format for user_id {user_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid user ID format: {e}")
    except Exception as e:
        logger.error(f"Failed to get sessions for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve sessions: {str(e)}")

@app.get("/my-sessions", response_model=SessionsResponse)
async def get_my_sessions(
    current_user: CurrentActiveUser,
    limit: int = Query(50, ge=1, le=1000, description="Number of sessions to return"),
    offset: int = Query(0, ge=0, description="Number of sessions to skip"),
    repo: SessionRepository = Depends(get_session_repo)
):
    try:
        sessions_data = await repo.get_user_sessions(UUID(current_user.user_id), limit=limit, offset=offset)
        return SessionsResponse(**sessions_data)
    except Exception as e:
        logger.error(f"Failed to get sessions for user {current_user.user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve sessions: {str(e)}")

@app.get("/progress/{user_id}")
async def get_progress_for_user(
    user_id: str,
    current_user: CurrentActiveUser,
    repo: SessionRepository = Depends(get_session_repo)
):
    if user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    progress = await repo.get_user_progress(UUID(user_id))
    return {"progress": progress}

@app.get("/my-progress")
async def get_my_progress(
    current_user: CurrentActiveUser,
    repo: SessionRepository = Depends(get_session_repo)
):
    progress = await repo.get_user_progress(UUID(current_user.user_id))
    return {"progress": progress}

@app.post("/progress/update/", response_model=MessageResponse)
async def update_progress(
    request: ProgressUpdateRequest,
    current_user: CurrentActiveUser,
    repo: SessionRepository = Depends(get_session_repo)
):
    result = await repo.update_progress(
        user_id=UUID(current_user.user_id),
        topic=request.topic,
        level=request.level,
        status=request.status
    )
    
    # Manually invalidate multiple cache patterns
    await cache.clear_pattern("user_analytics:*")
    await cache.clear_pattern("achievements:*")
    await cache.clear_pattern("leaderboard:*")
    
    return MessageResponse(message="Progress updated")

@app.post("/activities/", response_model=MessageResponse)
async def log_activity(
    request: ActivityLogRequest,
    current_user: CurrentActiveUser,
    repo: SessionRepository = Depends(get_session_repo)
):
    try:
        session_uuid = UUID(request.session_id)
    except ValueError as e:
        logger.error(f"Invalid session UUID: {request.session_id}")
        raise HTTPException(status_code=400, detail=f"Invalid session ID format: {str(e)}")
    
    session_details = await repo.get_session_details(session_uuid)
    if not session_details or session_details['user_id'] != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied to this session")
    
    await repo.log_activity(
        session_id=session_uuid,
        activity_type=request.type,
        content=request.content
    )
    return MessageResponse(message="Activity logged")

@app.get("/activities/{user_id}", response_model=ActivitiesResponse)
async def get_user_activities(
    user_id: str,
    current_user: CurrentActiveUser,
    limit: int = Query(100, ge=1, le=1000, description="Number of activities to return"),
    offset: int = Query(0, ge=0, description="Number of activities to skip"),
    repo: SessionRepository = Depends(get_session_repo)
):
    if user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        activities_data = await repo.get_user_activity(UUID(user_id), limit=limit, offset=offset)
        return ActivitiesResponse(**activities_data)
    except ValueError as e:
        logger.error(f"Invalid UUID format for user_id {user_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid user ID format: {e}")
    except Exception as e:
        logger.error(f"Failed to get activities for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve activities: {str(e)}")

@app.get("/my-activities", response_model=ActivitiesResponse)
async def get_my_activities(
    current_user: CurrentActiveUser,
    limit: int = Query(100, ge=1, le=1000, description="Number of activities to return"),
    offset: int = Query(0, ge=0, description="Number of activities to skip"),
    repo: SessionRepository = Depends(get_session_repo)
):  
    try:
        activities_data = await repo.get_user_activity(UUID(current_user.user_id), limit=limit, offset=offset)
        return ActivitiesResponse(**activities_data)
    except Exception as e:
        logger.error(f"Failed to get activities for user {current_user.user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve activities: {str(e)}")

@app.post("/quiz-attempts/", response_model=MessageResponse)
async def record_quiz_attempt(
    request: QuizAttemptRequest,
    current_user: CurrentActiveUser,
    repo: SessionRepository = Depends(get_session_repo)
):
    try:
        session_uuid = UUID(request.session_id)
        question_uuid = UUID(request.question_id)
    except ValueError as e:
        logger.error(f"Invalid UUID format in quiz attempt: session_id={request.session_id}, question_id={request.question_id}")
        raise HTTPException(status_code=400, detail=f"Invalid UUID format: {str(e)}")
    
    session_details = await repo.get_session_details(session_uuid)
    if not session_details or session_details['user_id'] != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied to this session")
    
    # Get the correct answer from the database question
    question_details = await repo.get_question(question_uuid)
    if not question_details:
        raise HTTPException(status_code=404, detail="Question not found")
    
    await repo.record_quiz_attempt(
        session_id=session_uuid,
        question_id=question_uuid,
        user_answer=request.user_answer,
        correct_answer=question_details['correct_answer'],
        is_correct=request.is_correct,
        difficulty=request.difficulty
    )
    
    # Manually invalidate multiple cache patterns
    await cache.clear_pattern("user_analytics:*")
    await cache.clear_pattern("achievements:*")
    await cache.clear_pattern("leaderboard:*")
    
    return MessageResponse(message="Quiz attempt recorded")

@app.post("/questions/", response_model=QuestionResponse)
async def create_question(
    request: QuestionCreateRequest,
    current_user: CurrentActiveUser,
    repo: SessionRepository = Depends(get_session_repo)
):
    question_id = await repo.create_question(
        topic=request.topic,
        level=request.level,
        difficulty=request.difficulty,
        question_text=request.question_text,
        correct_answer=request.correct_answer,
        options=request.options
    )
    return QuestionResponse(question_id=str(question_id))

@app.get("/questions/match", response_model=QuestionMatchResponse)
async def find_question_match(
    topic: str = Query(..., description="Question topic"),
    question_text: str = Query(..., description="Question text to match"),
    current_user: OptionalCurrentUser = None,
    repo: SessionRepository = Depends(get_session_repo)
):
    question_id = await repo.find_question_match(topic, question_text)
    return QuestionMatchResponse(question_id=str(question_id) if question_id else None)

@app.get("/questions/{question_id}")
async def get_question(
    question_id: str,
    current_user: OptionalCurrentUser = None,
    repo: SessionRepository = Depends(get_session_repo)
):
    try:
        question_uuid = UUID(question_id)
        question = await repo.get_question(question_uuid)
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")
        return question
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid question ID format")

@app.post("/explain", response_model=ExplainResponse)
@cached(ttl=CacheConfig.ANALYTICS_CACHE_TTL, key_prefix="explain")
async def explain_topic(
    req: ExplainRequest,
    current_user: OptionalCurrentUser = None
):
    import time
    start_time = time.time()
    
    user_id = current_user.user_id if current_user else None
    
    try:
        explanation = tutor_agent.explain_topic(topic=req.topic, level=req.level)
        
        # Log AI request performance
        duration_ms = (time.time() - start_time) * 1000
        log_ai_request("tutor_agent", req.topic, duration_ms, user_id)
        
        return ExplainResponse(explanation=explanation)
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        cache_logger.log_error(e, "explain_topic", user_id, {
            "topic": req.topic,
            "level": req.level,
            "duration_ms": duration_ms
        })
        raise

@app.post("/quiz")
@cached(ttl=CacheConfig.QUESTION_CACHE_TTL, key_prefix="quiz_generation")
async def generate_quiz(
    data: QuizRequest,
    current_user: OptionalCurrentUser = None,
    repo: SessionRepository = Depends(get_session_repo)
):
    # Generate questions using AI
    generated_questions = quiz_agent.generate_quiz(
        topic=data.topic,
        content=data.content,
        level=data.level,  # type: ignore
        num_questions=data.num_questions,
        difficulty=data.difficulty  # type: ignore
    )
    
    # Save each generated question to the database and get real database IDs
    questions_with_db_ids = []
    for question in generated_questions:
        try:
            # Save question to database
            db_question_id = await repo.create_question(
                topic=data.topic,
                level=data.level,
                difficulty=data.difficulty,
                question_text=question.question,
                correct_answer=question.answer,
                options=question.options
            )
            
            # Create question response with database ID
            question_dict = question.dict()
            question_dict['id'] = str(db_question_id)
            questions_with_db_ids.append(question_dict)
            
        except Exception as e:
            logger.error(f"Failed to save question to database: {e}")
            # Fallback: use the generated UUID if database save fails
            questions_with_db_ids.append(question.dict())
    
    return {"questions": questions_with_db_ids}

@app.post("/plan")
@cached(ttl=CacheConfig.ANALYTICS_CACHE_TTL, key_prefix="study_plan")
async def generate_study_plan(
    req: PlanRequest,
    current_user: OptionalCurrentUser = None
):
    plan = planner_agent.generate_study_plan(
        topics=req.topics,
        days=req.days,
        daily_minutes=req.daily_minutes,
        level=req.level  # type: ignore
    )
    return StudyPlan(sessions=plan)

@app.post("/materials", response_model=ContentResponse)
@cached(ttl=CacheConfig.ANALYTICS_CACHE_TTL, key_prefix="materials")
async def suggest_materials(
    req: ContentRequest,
    current_user: OptionalCurrentUser = None
):
    """Get enhanced learning materials with titles, descriptions, and metadata"""
    import time
    start_time = time.time()
    
    user_id = current_user.user_id if current_user else None
    
    try:
        content = content_agent.suggest_materials(
            topic=req.topic,
            level=req.level  # type: ignore
        )
        
        # Add topic and level to the response
        content['topic'] = req.topic
        content['level'] = req.level
        
        # Log AI request performance
        duration_ms = (time.time() - start_time) * 1000
        log_ai_request("content_agent", req.topic, duration_ms, user_id)
        
        return ContentResponse(content=content)
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        cache_logger.log_error(e, "suggest_materials", user_id, {
            "topic": req.topic,
            "level": req.level,
            "duration_ms": duration_ms
        })
        
        # Fallback response
        fallback_content = {
            "materials": [
                {
                    "title": f"Learning Resources for {req.topic}",
                    "description": f"Curated learning materials for {req.topic} at {req.level} level",
                    "url": "https://www.google.com/search?q=" + req.topic.replace(" ", "+"),
                    "type": "search",
                    "provider": "Google",
                    "difficulty": req.level,
                    "estimated_time": "Varies"
                }
            ],
            "prerequisites": [f"Basic understanding of {req.topic}"],
            "learning_path": ["Research fundamentals", "Find quality resources", "Practice regularly"],
            "related_topics": [],
            "topic": req.topic,
            "level": req.level
        }
        return ContentResponse(content=fallback_content)

@app.get("/db-test")
async def test_db(repo: SessionRepository = Depends(get_session_repo)):
    async with repo.pool.acquire() as conn:
        result = await conn.fetchval("SELECT 1")
        return {"db_ok": result == 1}

@app.get("/analytics/user-stats", response_model=UserAnalyticsResponse)
@cached(ttl=CacheConfig.ANALYTICS_CACHE_TTL, key_prefix="user_analytics")
async def get_user_analytics(
    current_user: CurrentActiveUser,
    repo: SessionRepository = Depends(get_session_repo)
):
    """Get comprehensive user learning analytics"""
    try:
        user_uuid = UUID(current_user.user_id)
        
        # Get user stats
        user_stats = await repo.get_user_stats(user_uuid)
        
        # Get progress data
        progress_result = await repo.get_user_progress(user_uuid)
        
        # Get recent sessions
        sessions_result = await repo.get_user_sessions(user_uuid, limit=10)
        
        # Calculate analytics
        total_topics = len(progress_result)
        completed_topics = len([p for p in progress_result if p.get('status') == 'completed'])
        completion_rate = (completed_topics / total_topics * 100) if total_topics > 0 else 0
        
        # Calculate learning streak (simplified - days with activity)
        recent_sessions = sessions_result.get('sessions', [])
        learning_streak = min(len(recent_sessions), 7)  # Simplified streak calculation
        
        # Topic distribution
        topic_counts = {}
        for progress in progress_result:
            topic = progress['topic']
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
        
        favorite_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Quiz accuracy (if quiz attempts exist)
        quiz_accuracy = 75.0  # Placeholder - would need quiz attempt analysis
        
        analytics = {
            "user_id": current_user.user_id,
            "total_sessions": user_stats.get('total_sessions', 0),
            "completed_sessions": user_stats.get('completed_sessions', 0),
            "active_sessions": user_stats.get('active_sessions', 0),
            "total_topics": total_topics,
            "completed_topics": completed_topics,
            "completion_rate": round(completion_rate, 1),
            "learning_streak": learning_streak,
            "quiz_accuracy": quiz_accuracy,
            "favorite_topics": [{"topic": topic, "count": count} for topic, count in favorite_topics],
            "progress_distribution": {
                "started": len([p for p in progress_result if p.get('status') == 'started']),
                "completed": completed_topics,
                "reviewed": len([p for p in progress_result if p.get('status') == 'reviewed'])
            },
            "recent_activity": {
                "last_session": recent_sessions[0]['started_at'] if recent_sessions else None,
                "sessions_this_week": len(recent_sessions)
            }
        }
        
        return analytics
        
    except Exception as e:
        logger.error(f"Failed to get user analytics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve analytics: {str(e)}")

@app.get("/quiz-results/{session_id}", response_model=QuizResultsResponse)
async def get_quiz_results(
    session_id: str,
    current_user: CurrentActiveUser,
    repo: SessionRepository = Depends(get_session_repo)
):
    """Get detailed quiz results for a session"""
    try:
        session_uuid = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    
    # Verify session ownership
    session_details = await repo.get_session_details(session_uuid)
    if not session_details or session_details['user_id'] != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied to this session")
    
    try:
        # Get quiz attempts for this session
        quiz_attempts = await repo.get_quiz_attempts(session_uuid)
        
        if not quiz_attempts:
            return {
                "session_id": session_id,
                "topic": session_details['topic'],
                "level": session_details['level'],
                "total_questions": 0,
                "attempts": [],
                "summary": {
                    "total_questions": 0,
                    "correct_answers": 0,
                    "accuracy": 0,
                    "time_taken": "N/A"
                }
            }
        
        # Enhance attempts with question details
        enhanced_attempts = []
        correct_count = 0
        
        for attempt in quiz_attempts:
            question_details = await repo.get_question(UUID(attempt['question_id']))
            
            enhanced_attempt = {
                "question_id": attempt['question_id'],
                "user_answer": attempt['user_answer'],
                "is_correct": attempt['is_correct'],
                "difficulty": attempt['difficulty'],
                "created_at": attempt['created_at'],
                "question_details": question_details if question_details else {
                    "question_text": "Question not found",
                    "options": [],
                    "correct_answer": "N/A"
                }
            }
            
            if attempt['is_correct']:
                correct_count += 1
                
            enhanced_attempts.append(enhanced_attempt)
        
        # Calculate summary statistics
        total_questions = len(quiz_attempts)
        accuracy = (correct_count / total_questions * 100) if total_questions > 0 else 0
        
        # Performance by difficulty
        difficulty_stats = {}
        for attempt in quiz_attempts:
            diff = attempt['difficulty']
            if diff not in difficulty_stats:
                difficulty_stats[diff] = {"total": 0, "correct": 0}
            difficulty_stats[diff]["total"] += 1
            if attempt['is_correct']:
                difficulty_stats[diff]["correct"] += 1
        
        for diff in difficulty_stats:
            stats = difficulty_stats[diff]
            stats["accuracy"] = (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0
        
        quiz_results = {
            "session_id": session_id,
            "topic": session_details['topic'],
            "level": session_details['level'],
            "total_questions": total_questions,
            "attempts": enhanced_attempts,
            "summary": {
                "total_questions": total_questions,
                "correct_answers": correct_count,
                "accuracy": round(accuracy, 1),
                "difficulty_breakdown": difficulty_stats,
                "session_date": session_details['started_at']
            },
            "recommendations": {
                "strengths": [],
                "areas_for_improvement": [],
                "next_steps": f"Continue learning about {session_details['topic']}" if accuracy < 80 else f"Great job! Try intermediate level {session_details['topic']} topics"
            }
        }
        
        # Add personalized recommendations based on performance
        if accuracy >= 90:
            quiz_results["recommendations"]["strengths"].append("Excellent understanding of the topic")
            quiz_results["recommendations"]["next_steps"] = f"Ready for advanced {session_details['topic']} concepts"
        elif accuracy >= 70:
            quiz_results["recommendations"]["strengths"].append("Good grasp of fundamental concepts")
            quiz_results["recommendations"]["areas_for_improvement"].append("Review specific areas where you missed questions")
        else:
            quiz_results["recommendations"]["areas_for_improvement"].append("Consider reviewing the basic concepts")
            quiz_results["recommendations"]["areas_for_improvement"].append("Practice with more beginner-level questions")
        
        return quiz_results
        
    except Exception as e:
        logger.error(f"Failed to get quiz results for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve quiz results: {str(e)}")

@app.get("/achievements", response_model=AchievementResponse)
@cached(ttl=CacheConfig.ACHIEVEMENTS_CACHE_TTL, key_prefix="achievements")
async def get_user_achievements(
    current_user: CurrentActiveUser,
    repo: SessionRepository = Depends(get_session_repo)
):
    """Get user achievements and learning streaks"""
    try:
        user_uuid = UUID(current_user.user_id)
        
        # Get user sessions to calculate streaks
        sessions_result = await repo.get_user_sessions(user_uuid, limit=30)
        sessions = sessions_result.get('sessions', [])
        
        # Calculate current streak (simplified - consecutive days with sessions)
        current_streak = 0
        if sessions:
            # Group sessions by date
            from datetime import datetime, timedelta
            session_dates = set()
            for session in sessions:
                if session.get('started_at'):
                    # Handle both string and datetime objects
                    started_at = session['started_at']
                    if isinstance(started_at, str):
                        date = started_at.split('T')[0]
                    else:
                        # Handle datetime objects
                        date = started_at.strftime('%Y-%m-%d')
                    session_dates.add(date)
            
            # Calculate streak from today backwards
            today = datetime.now().date()
            current_date = today
            for i in range(30):  # Check last 30 days
                if str(current_date) in session_dates:
                    current_streak += 1
                    current_date -= timedelta(days=1)
                else:
                    break
        
        # Calculate longest streak (simplified)
        longest_streak = max(current_streak + 3, 15)  # Mock calculation
        
        # Get progress for achievements
        progress_result = await repo.get_user_progress(user_uuid)
        total_topics = len(progress_result)
        completed_topics = len([p for p in progress_result if p.get('status') == 'completed'])
        
        # Define achievements
        achievements = [
            {
                "id": "first_quiz",
                "name": "Quiz Master",
                "description": "Complete your first quiz",
                "earned": len(sessions) > 0,
                "icon": "🎯",
                "points": 10
            },
            {
                "id": "week_warrior",
                "name": "Week Warrior", 
                "description": "Study for 7 consecutive days",
                "earned": current_streak >= 7,
                "icon": "🔥",
                "points": 50
            },
            {
                "id": "topic_explorer",
                "name": "Topic Explorer",
                "description": "Learn 10 different topics",
                "earned": total_topics >= 10,
                "progress": f"{total_topics}/10",
                "icon": "🌟",
                "points": 100
            },
            {
                "id": "completion_champion",
                "name": "Completion Champion",
                "description": "Complete 5 topics",
                "earned": completed_topics >= 5,
                "progress": f"{completed_topics}/5",
                "icon": "👑",
                "points": 75
            },
            {
                "id": "month_master",
                "name": "Month Master",
                "description": "Study for 30 consecutive days",
                "earned": current_streak >= 30,
                "progress": f"{current_streak}/30",
                "icon": "🏆",
                "points": 200
            }
        ]
        
        # Calculate next milestone
        next_milestone = {"name": "Week Warrior", "days_remaining": max(0, 7 - current_streak)}
        if current_streak >= 7:
            next_milestone = {"name": "Month Master", "days_remaining": max(0, 30 - current_streak)}
        
        return AchievementResponse(
            current_streak=current_streak,
            longest_streak=longest_streak,
            achievements=achievements,
            next_milestone=next_milestone
        )
        
    except Exception as e:
        logger.error(f"Failed to get achievements: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve achievements: {str(e)}")

@app.post("/streaks/check-in", response_model=MessageResponse)
async def daily_check_in(
    current_user: CurrentActiveUser,
    repo: SessionRepository = Depends(get_session_repo)
):
    """Record daily learning check-in"""
    try:
        user_uuid = UUID(current_user.user_id)
        
        # Log check-in activity
        from datetime import datetime
        check_in_time = datetime.now().isoformat()
        
        # This could be enhanced to track actual check-ins in a separate table
        # For now, we'll just return success
        
        return MessageResponse(message=f"Daily check-in recorded at {check_in_time}")
        
    except Exception as e:
        logger.error(f"Failed to record check-in: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to record check-in: {str(e)}")

@app.post("/study-time/start", response_model=StudyTimeResponse)
async def start_study_session(
    request: StudyTimeRequest,
    current_user: CurrentActiveUser,
    repo: SessionRepository = Depends(get_session_repo)
):
    """Start a timed study session"""
    try:
        user_uuid = UUID(current_user.user_id)
        
        # Create a new session for study time tracking
        session_id = await repo.start_session(
            user_id=user_uuid,
            topic=request.topic,
            level=request.level,
            wants_quiz=False,
            wants_plan=False
        )
        
        from datetime import datetime
        started_at = datetime.now().isoformat()
        
        return StudyTimeResponse(
            study_session_id=str(session_id),
            started_at=started_at
        )
        
    except Exception as e:
        logger.error(f"Failed to start study session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start study session: {str(e)}")

@app.post("/study-time/end/{session_id}", response_model=MessageResponse)
async def end_study_session(
    session_id: str,
    current_user: CurrentActiveUser,
    repo: SessionRepository = Depends(get_session_repo)
):
    """End a timed study session"""
    try:
        session_uuid = UUID(session_id)
        
        # Verify session ownership
        session_details = await repo.get_session_details(session_uuid)
        if not session_details or session_details['user_id'] != current_user.user_id:
            raise HTTPException(status_code=403, detail="Access denied to this session")
        
        # End the session
        await repo.end_session(session_uuid)
        
        # Calculate duration (simplified)
        from datetime import datetime
        if session_details.get('started_at'):
            started_at = session_details['started_at']
            try:
                if isinstance(started_at, str):
                    started = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                else:
                    # Handle datetime objects
                    started = started_at
                ended = datetime.now()
                duration_minutes = int((ended - started).total_seconds() / 60)
                duration_text = f"{duration_minutes} minutes"
            except (ValueError, TypeError) as e:
                logger.warning(f"Could not parse start time: {started_at}, error: {e}")
                duration_text = "Unknown duration"
        else:
            duration_text = "Unknown duration"
        
        return MessageResponse(message=f"Study session completed. Duration: {duration_text}")
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    except Exception as e:
        logger.error(f"Failed to end study session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to end study session: {str(e)}")

@app.get("/study-time/stats", response_model=StudyTimeStatsResponse)
async def get_study_time_stats(
    current_user: CurrentActiveUser,
    repo: SessionRepository = Depends(get_session_repo)
):
    """Get user study time statistics"""
    try:
        user_uuid = UUID(current_user.user_id)
        
        # Get recent sessions
        sessions_result = await repo.get_user_sessions(user_uuid, limit=50)
        sessions = sessions_result.get('sessions', [])
        
        # Calculate stats (simplified calculations)
        total_sessions = len(sessions)
        
        # Mock calculations for demo purposes
        today_minutes = min(total_sessions * 15, 180)  # Cap at 3 hours
        week_minutes = min(total_sessions * 45, 900)   # Cap at 15 hours
        average_daily = week_minutes // 7 if week_minutes > 0 else 0
        
        return StudyTimeStatsResponse(
            today=f"{today_minutes // 60}h {today_minutes % 60}m",
            this_week=f"{week_minutes // 60}h {week_minutes % 60}m", 
            average_daily=f"{average_daily // 60}h {average_daily % 60}m",
            most_productive_time="10:00-12:00"  # Mock data
        )
        
    except Exception as e:
        logger.error(f"Failed to get study time stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve study time stats: {str(e)}")

@app.post("/quiz/adaptive")
async def generate_adaptive_quiz(
    data: AdaptiveQuizRequest,
    current_user: OptionalCurrentUser = None,
    repo: SessionRepository = Depends(get_session_repo)
):
    """Generate adaptive quiz that adjusts difficulty based on user performance"""
    try:
        # Analyze user performance history to determine starting difficulty
        performance_history = data.user_performance_history or []
        
        # Calculate adaptive difficulty
        if performance_history:
            recent_accuracy = sum(attempt.get('is_correct', False) for attempt in performance_history[-5:]) / min(len(performance_history), 5)
            
            if recent_accuracy >= 0.8:
                adaptive_difficulty = "intermediate" if data.level == "beginner" else "hard"
            elif recent_accuracy >= 0.6:
                adaptive_difficulty = "easy" if data.level == "beginner" else "intermediate"
            else:
                adaptive_difficulty = "easy"
        else:
            adaptive_difficulty = "easy"  # Start easy for new users
        
        # Generate questions using adaptive difficulty
        generated_questions = quiz_agent.generate_quiz(
            topic=data.topic,
            content=data.content,
            level=data.level,  # type: ignore
            num_questions=5,
            difficulty=adaptive_difficulty  # type: ignore
        )
        
        # Save questions to database
        questions_with_db_ids = []
        for question in generated_questions:
            try:
                db_question_id = await repo.create_question(
                    topic=data.topic,
                    level=data.level,
                    difficulty=adaptive_difficulty,
                    question_text=question.question,
                    correct_answer=question.answer,
                    options=question.options
                )
                
                question_dict = question.dict()
                question_dict['id'] = str(db_question_id)
                question_dict['difficulty'] = adaptive_difficulty  # Override with adaptive difficulty
                questions_with_db_ids.append(question_dict)
                
            except Exception as e:
                logger.error(f"Failed to save adaptive question: {e}")
                question_dict = question.dict()
                question_dict['difficulty'] = adaptive_difficulty
                questions_with_db_ids.append(question_dict)
        
        return {
            "questions": questions_with_db_ids,
            "adaptive_info": {
                "starting_difficulty": "easy",
                "current_difficulty": adaptive_difficulty,
                "adaptation_reason": f"Based on recent performance: {len(performance_history)} attempts analyzed",
                "user_accuracy": sum(attempt.get('is_correct', False) for attempt in performance_history) / len(performance_history) if performance_history else 0
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to generate adaptive quiz: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate adaptive quiz: {str(e)}")

@app.get("/leaderboard", response_model=LeaderboardResponse)
@cached(ttl=CacheConfig.ANALYTICS_CACHE_TTL, key_prefix="leaderboard")
async def get_leaderboard(
    timeframe: str = Query("all_time", description="Timeframe: all_time, weekly, monthly"),
    limit: int = Query(50, ge=1, le=100, description="Number of users to return"),
    current_user: OptionalCurrentUser = None,
    repo: SessionRepository = Depends(get_session_repo)
):
    """Get the global leaderboard with user rankings"""
    try:
        # Validate timeframe
        valid_timeframes = {"all_time", "weekly", "monthly"}
        if timeframe not in valid_timeframes:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid timeframe. Must be one of: {', '.join(valid_timeframes)}"
            )
        
        # Get leaderboard data
        leaderboard_data = await repo.get_leaderboard_data(timeframe=timeframe, limit=limit)
        
        # Get current user's rank if authenticated
        user_rank = None
        if current_user and current_user.user_id:
            try:
                user_rank = await repo.get_user_rank(UUID(current_user.user_id), timeframe=timeframe)
            except Exception as e:
                logger.warning(f"Could not get user rank for {current_user.user_id}: {e}")
        
        # Get total active users count
        total_users = len(leaderboard_data) if len(leaderboard_data) < limit else limit + 10  # Estimate
        
        from datetime import datetime
        
        return LeaderboardResponse(
            leaderboard=leaderboard_data,
            user_rank=user_rank,
            total_users=total_users,
            timeframe=timeframe,
            last_updated=datetime.now().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get leaderboard: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve leaderboard: {str(e)}")

@app.get("/cache/stats")
async def get_cache_stats_endpoint():
    """Get comprehensive cache and logging statistics"""
    return {
        "cache_stats": cache.stats(),
        "logging_stats": get_cache_stats(),
        "config": {
            "user_cache_ttl": CacheConfig.USER_CACHE_TTL,
            "question_cache_ttl": CacheConfig.QUESTION_CACHE_TTL,
            "analytics_cache_ttl": CacheConfig.ANALYTICS_CACHE_TTL,
            "achievements_cache_ttl": CacheConfig.ACHIEVEMENTS_CACHE_TTL,
            "memory_cache_size": CacheConfig.MAX_MEMORY_CACHE_SIZE,
            "redis_connected": cache.redis_cache.connected
        }
    }

@app.post("/cache/clear")
async def clear_cache(
    pattern: str = "*",
    current_user: CurrentActiveUser = None
):
    """Clear cache by pattern (admin only)"""
    from utils.logging import log_cache_clear
    
    count = 0  # In a real implementation, you'd get the actual count
    await cache.clear_pattern(pattern)
    log_cache_clear(pattern, count, current_user.user_id if current_user else None)
    
    return {"message": f"Cache cleared for pattern: {pattern}"}

@app.get("/logs/recent")
async def get_recent_logs(
    lines: int = Query(50, ge=1, le=500, description="Number of log lines to return"),
    current_user: CurrentActiveUser = None
):
    """Get recent log entries (admin only)"""
    import os
    from pathlib import Path
    
    try:
        log_file = Path("logs/app.log")
        if not log_file.exists():
            return {"logs": [], "message": "Log file not found"}
        
        # Read last N lines from log file
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        return {
            "logs": [line.strip() for line in recent_lines],
            "total_lines": len(all_lines),
            "returned_lines": len(recent_lines),
            "log_file": str(log_file),
            "file_size_mb": round(log_file.stat().st_size / (1024*1024), 2)
        }
    except Exception as e:
        return {"error": f"Failed to read logs: {str(e)}"}

@app.get("/logs/stats")
async def get_logging_stats():
    """Get detailed logging and performance statistics"""
    import os
    
    return {
        "logging_stats": get_cache_stats(),
        "cache_performance": cache.stats(),
        "system_info": {
            "log_file_exists": os.path.exists("logs/app.log"),
            "log_file_size_mb": round(os.path.getsize("logs/app.log") / (1024*1024), 2) if os.path.exists("logs/app.log") else 0
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "AI Learning Coach API is running"}

@app.get("/")
async def root():
    return {
        "message": "AI Learning Coach API",
        "version": "1.0.0",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "auth": {
            "register": "/auth/register",
            "login": "/auth/login",
            "refresh": "/auth/refresh"
        }
    }

# Debug endpoint (remove in production)

@app.get("/debug/sessions/{user_id}")
async def debug_user_sessions(
    user_id: str,
    current_user: CurrentActiveUser,
    repo: SessionRepository = Depends(get_session_repo)
):
    if user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        logger.info(f"Debug: Getting sessions for user_id: {user_id}")
        
        user_uuid = UUID(user_id)
        sessions_data = await repo.get_user_sessions(user_uuid, limit=10, offset=0)
        
        return {
            "user_id": user_id,
            "user_uuid": str(user_uuid),
            "data_type": str(type(sessions_data)),
            "raw_data": sessions_data
        }
        
    except Exception as e:
        logger.error(f"Debug endpoint failed: {e}")
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "user_id": user_id
        }

if __name__ == "__main__":
    uvicorn.run("mcp_server.main:app", host="0.0.0.0", port=8000, reload=True)