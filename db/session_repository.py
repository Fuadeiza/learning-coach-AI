import logging
import json
from typing import Optional, List
from uuid import UUID
from asyncpg import Pool
from utils.cache import cached, cache_invalidate, CacheConfig, CacheKeys, CacheInvalidationPatterns


class SessionRepository:
    VALID_ACTIVITY_TYPES = {'explanation', 'quiz', 'plan', 'materials'}
    VALID_PROGRESS_STATUS = {'started', 'completed', 'reviewed'}
    VALID_USER_LEVELS = {'beginner', 'intermediate', 'advanced'}
    VALID_QUIZ_DIFFICULTIES = {'easy', 'intermediate', 'hard'}

    def __init__(self, db_pool: Pool):
        self.pool = db_pool
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("SessionRepository initialized")

    def _validate_enum(self, value: str, valid_values: set, enum_name: str) -> str:
        """Validate enum values before database operations"""
        if value not in valid_values:
            error_msg = f"Invalid {enum_name}: '{value}'. Valid values: {sorted(valid_values)}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        return value

    def _ensure_uuid(self, value) -> UUID:
        """Convert value to UUID if it's not already one"""
        if isinstance(value, UUID):
            return value
        elif isinstance(value, str):
            return UUID(value)
        else:
            # Handle asyncpg UUID objects
            return UUID(str(value))

    def _serialize_json(self, data) -> str:
        """Serialize data to JSON string for JSONB columns"""
        if data is None:
            return "{}"
        if isinstance(data, str):
            return data  # Already a JSON string
        return json.dumps(data)

    def _deserialize_json(self, json_str):
        """Deserialize JSON string back to Python object"""
        if json_str is None:
            return {}
        if isinstance(json_str, (dict, list)):
            return json_str  # Already deserialized
        if isinstance(json_str, str):
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                return {}
        return {}

    async def create_user(self, email: Optional[str], user_name: Optional[str]) -> UUID:
        self.logger.info(f"Creating user with email: {email}, user_name: {user_name}")
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    user_id = await connection.fetchval(
                        "INSERT INTO users (email, user_name) VALUES ($1, $2) RETURNING id",
                        email,
                        user_name
                    )
                    user_uuid = self._ensure_uuid(user_id)
                    self.logger.info(f"Successfully created user with ID: {user_uuid}")
                    return user_uuid
        except Exception as e:
            self.logger.error(f"Failed to create user: {e}")
            raise

    @cached(ttl=CacheConfig.USER_CACHE_TTL, key_prefix="user_by_email")
    async def get_user_by_email(self, email: str) -> Optional[dict]:
        self.logger.debug(f"Fetching user by email: {email}")
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    user = await connection.fetchrow(
                        "SELECT id, email, user_name FROM users WHERE email = $1",
                        email
                    )
                    if user:
                        result = dict(user)
                        # Convert UUID to string for JSON serialization
                        result['id'] = str(result['id'])
                        self.logger.debug(f"Found user with ID: {result['id']}")
                        return result
                    else:
                        self.logger.debug(f"No user found with email: {email}")
                        return None
        except Exception as e:
            self.logger.error(f"Failed to fetch user by email {email}: {e}")
            raise

    @cache_invalidate("sessions:*")
    async def start_session(self, user_id: UUID, topic: str, level: str, wants_quiz: bool, wants_plan: bool) -> UUID:
        validated_level = self._validate_enum(level, self.VALID_USER_LEVELS, "user_level")
        
        self.logger.info(f"Starting session for user {user_id}: topic={topic}, level={validated_level}, wants_quiz={wants_quiz}, wants_plan={wants_plan}")
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    session_id = await connection.fetchval(
                        "INSERT INTO sessions (user_id, topic, level, wants_quiz, wants_plan) VALUES ($1, $2, $3, $4, $5) RETURNING id",
                        user_id,
                        topic,
                        validated_level,
                        wants_quiz,
                        wants_plan
                    )
                    session_uuid = self._ensure_uuid(session_id)
                    self.logger.info(f"Successfully started session with ID: {session_uuid}")
                    return session_uuid
        except Exception as e:
            self.logger.error(f"Failed to start session for user {user_id}: {e}")
            raise

    async def end_session(self, session_id: UUID) -> None:
        self.logger.info(f"Ending session: {session_id}")
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    result = await connection.execute(
                        "UPDATE sessions SET ended_at = NOW() WHERE id = $1",
                        session_id
                    )
                    if result == "UPDATE 0":
                        self.logger.warning(f"No session found with ID: {session_id}")
                    else:
                        self.logger.info(f"Successfully ended session: {session_id}")
        except Exception as e:
            self.logger.error(f"Failed to end session {session_id}: {e}")
            raise

    async def log_activity(self, session_id: UUID, activity_type: str, content: dict) -> None:
        validated_type = self._validate_enum(activity_type, self.VALID_ACTIVITY_TYPES, "activity_type")
        
        self.logger.debug(f"Logging activity for session {session_id}: type={validated_type}")
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    # Convert content dict to JSON string for JSONB column
                    content_json = self._serialize_json(content)
                    
                    await connection.execute(
                        "INSERT INTO activities (session_id, type, content) VALUES ($1, $2, $3)",
                        session_id,
                        validated_type,
                        content_json
                    )
                    self.logger.debug(f"Successfully logged activity for session {session_id}")
        except Exception as e:
            self.logger.error(f"Failed to log activity for session {session_id}: {e}")
            raise

    @cache_invalidate("user_progress:*")
    async def update_progress(self, user_id: UUID, topic: str, level: str, status: str = 'started') -> None:
        validated_level = self._validate_enum(level, self.VALID_USER_LEVELS, "user_level")
        validated_status = self._validate_enum(status, self.VALID_PROGRESS_STATUS, "progress_status")
        
        self.logger.info(f"Updating progress for user {user_id}: topic={topic}, level={validated_level}, status={validated_status}")
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    await connection.execute(
                        """INSERT INTO progress (user_id, topic, level, status) VALUES ($1, $2, $3, $4) 
                        ON CONFLICT (user_id, topic, level) 
                        DO UPDATE SET status = $4, last_interaction_at = NOW()""",
                        user_id,
                        topic,
                        validated_level,
                        validated_status
                    )
                    self.logger.info(f"Successfully updated progress for user {user_id}")
        except Exception as e:
            self.logger.error(f"Failed to update progress for user {user_id}: {e}")
            raise

    async def record_quiz_attempt(self, session_id: UUID, question_id: UUID, user_answer: str, correct_answer: str, is_correct: bool, difficulty: str) -> None:
        validated_difficulty = self._validate_enum(difficulty, self.VALID_QUIZ_DIFFICULTIES, "quiz_difficulty")
        
        self.logger.debug(f"Recording quiz attempt for session {session_id}: question_id={question_id}, is_correct={is_correct}, difficulty={validated_difficulty}")
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    await connection.execute(
                        "INSERT INTO quiz_attempts (session_id, question_id, user_answer, is_correct, difficulty) VALUES ($1, $2, $3, $4, $5)",
                        session_id,
                        question_id,
                        user_answer,
                        is_correct,
                        validated_difficulty
                    )
                    self.logger.debug(f"Successfully recorded quiz attempt for session {session_id}")
        except Exception as e:
            self.logger.error(f"Failed to record quiz attempt for session {session_id}: {e}")
            raise

    async def create_question(self, topic: str, level: str, difficulty: str, question_text: str, correct_answer: str, options: List[str]) -> UUID:
        validated_level = self._validate_enum(level, self.VALID_USER_LEVELS, "user_level")
        validated_difficulty = self._validate_enum(difficulty, self.VALID_QUIZ_DIFFICULTIES, "quiz_difficulty")
        
        self.logger.info(f"Creating question: topic={topic}, level={validated_level}, difficulty={validated_difficulty}")
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    # Convert options list to JSON string for JSONB column
                    options_json = self._serialize_json(options)
                    
                    question_id = await connection.fetchval(
                        "INSERT INTO questions (topic, level, difficulty, question_text, correct_answer, options) VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
                        topic,
                        validated_level,
                        validated_difficulty,
                        question_text,
                        correct_answer,
                        options_json
                    )
                    question_uuid = self._ensure_uuid(question_id)
                    self.logger.info(f"Successfully created question with ID: {question_uuid}")
                    return question_uuid
        except Exception as e:
            self.logger.error(f"Failed to create question: {e}")
            raise

    async def find_question_match(self, topic: str, question_text: str) -> Optional[UUID]:
        self.logger.debug(f"Searching for existing question: topic={topic}")
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    question_id = await connection.fetchval(
                        "SELECT id FROM questions WHERE topic = $1 AND question_text = $2",
                        topic,
                        question_text
                    )
                    result = self._ensure_uuid(question_id) if question_id else None
                    if result:
                        self.logger.debug(f"Found existing question with ID: {result}")
                    else:
                        self.logger.debug("No matching question found")
                    return result
        except Exception as e:
            self.logger.error(f"Failed to find question match: {e}")
            raise
    
    @cached(ttl=CacheConfig.SESSION_CACHE_TTL, key_prefix="session_details")
    async def get_session_details(self, session_id: UUID) -> Optional[dict]:
        self.logger.debug(f"Fetching session details for: {session_id}")
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    session_details = await connection.fetchrow(
                        """SELECT s.id, s.user_id, s.topic, s.level, s.wants_quiz, s.wants_plan, 
                        s.started_at, s.ended_at, u.email, u.user_name 
                        FROM sessions s LEFT JOIN users u ON s.user_id = u.id WHERE s.id = $1""",
                        session_id
                    )
                    if session_details:
                        result = dict(session_details)
                        # Convert UUIDs to strings for JSON serialization
                        result['id'] = str(result['id'])
                        result['user_id'] = str(result['user_id'])
                        self.logger.debug(f"Found session details for: {session_id}")
                        return result
                    else:
                        self.logger.warning(f"No session found with ID: {session_id}")
                        return None
        except Exception as e:
            self.logger.error(f"Failed to get session details for {session_id}: {e}")
            raise

    @cached(ttl=CacheConfig.PROGRESS_CACHE_TTL, key_prefix="user_progress")
    async def get_user_progress(self, user_id: UUID) -> List[dict]:
        self.logger.debug(f"Fetching user progress for: {user_id}")
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    progress = await connection.fetch(
                        "SELECT topic, level, status, last_interaction_at FROM progress WHERE user_id = $1 ORDER BY last_interaction_at DESC",
                        user_id
                    )
                    result = [dict(row) for row in progress]
                    self.logger.debug(f"Found {len(result)} progress records for user {user_id}")
                    return result
        except Exception as e:
            self.logger.error(f"Failed to get user progress for {user_id}: {e}")
            raise
    
    async def get_quiz_attempts(self, session_id: UUID) -> List[dict]:
        self.logger.debug(f"Fetching quiz attempts for session: {session_id}")
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    attempts = await connection.fetch(
                        "SELECT question_id, user_answer, is_correct, difficulty, created_at FROM quiz_attempts WHERE session_id = $1 ORDER BY created_at",
                        session_id
                    )
                    result = []
                    for row in attempts:
                        row_dict = dict(row)
                        # Convert UUID to string for JSON serialization
                        row_dict['question_id'] = str(row_dict['question_id'])
                        result.append(row_dict)
                    self.logger.debug(f"Found {len(result)} quiz attempts for session {session_id}")
                    return result
        except Exception as e:
            self.logger.error(f"Failed to get quiz attempts for session {session_id}: {e}")
            raise

    def _validate_pagination(self, limit: int, offset: int) -> tuple[int, int]:
        if limit < 1:
            self.logger.warning(f"Invalid limit {limit}, using default of 50")
            limit = 50
        elif limit > 1000:
            self.logger.warning(f"Limit {limit} too high, capping at 1000")
            limit = 1000
            
        if offset < 0:
            self.logger.warning(f"Invalid offset {offset}, using 0")
            offset = 0
            
        return limit, offset

    def _convert_uuids_to_strings(self, data: dict) -> dict:
        """Convert UUID objects to strings for JSON serialization"""
        result = {}
        for key, value in data.items():
            if hasattr(value, 'hex'):  # UUID objects have a hex attribute
                result[key] = str(value)
            else:
                result[key] = value
        return result

    async def get_user_sessions(self, user_id: UUID, limit: int = 50, offset: int = 0) -> dict:
        limit, offset = self._validate_pagination(limit, offset)
        self.logger.debug(f"Fetching user sessions for: {user_id} (limit={limit}, offset={offset})")
        
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    total_count = await connection.fetchval(
                        "SELECT COUNT(*) FROM sessions WHERE user_id = $1",
                        user_id
                    )
                    
                    sessions = await connection.fetch(
                        """SELECT id, topic, level, wants_quiz, wants_plan, started_at, ended_at 
                        FROM sessions WHERE user_id = $1 
                        ORDER BY started_at DESC 
                        LIMIT $2 OFFSET $3""",
                        user_id, limit, offset
                    )
                    
                    sessions_list = []
                    for row in sessions:
                        row_dict = dict(row)
                        # Convert UUID to string
                        row_dict['id'] = str(row_dict['id'])
                        sessions_list.append(row_dict)
                    
                    has_more = (offset + len(sessions_list)) < total_count
                    
                    result = {
                        'sessions': sessions_list,
                        'total_count': total_count,
                        'limit': limit,
                        'offset': offset,
                        'has_more': has_more
                    }
                    
                    self.logger.debug(f"Found {len(sessions_list)} sessions for user {user_id} (total: {total_count})")
                    return result
        except Exception as e:
            self.logger.error(f"Failed to get user sessions for {user_id}: {e}")
            raise
    
    async def get_user_stats(self, user_id: UUID) -> dict:
        self.logger.debug(f"Fetching user stats for: {user_id}")
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    stats = await connection.fetchrow(
                        """SELECT COUNT(id) as total_sessions, 
                        COUNT(CASE WHEN ended_at IS NOT NULL THEN 1 END) as completed_sessions, 
                        COUNT(CASE WHEN ended_at IS NULL THEN 1 END) as active_sessions 
                        FROM sessions WHERE user_id = $1""",
                        user_id
                    )
                    result = dict(stats) if stats else {}
                    self.logger.debug(f"Retrieved user stats for {user_id}: {result}")
                    return result
        except Exception as e:
            self.logger.error(f"Failed to get user stats for {user_id}: {e}")
            raise

    async def get_question_stats(self, question_id: UUID) -> dict:
        self.logger.debug(f"Fetching question stats for: {question_id}")
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    stats = await connection.fetchrow(
                        """SELECT COUNT(id) as total_attempts, 
                        COUNT(CASE WHEN is_correct THEN 1 END) as correct_attempts, 
                        ROUND(COUNT(CASE WHEN is_correct THEN 1 END)::decimal / NULLIF(COUNT(id), 0) * 100, 2) AS accuracy 
                        FROM quiz_attempts WHERE question_id = $1""",
                        question_id
                    )
                    result = dict(stats) if stats else {}
                    self.logger.debug(f"Retrieved question stats for {question_id}: {result}")
                    return result
        except Exception as e:
            self.logger.error(f"Failed to get question stats for {question_id}: {e}")
            raise
            
    async def get_question_history(self, question_id: UUID) -> List[dict]:
        self.logger.debug(f"Fetching question history for: {question_id}")
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    history = await connection.fetch(
                        """SELECT session_id, user_answer, is_correct, difficulty, created_at 
                        FROM quiz_attempts WHERE question_id = $1 ORDER BY created_at DESC""",
                        question_id
                    )
                    result = []
                    for row in history:
                        row_dict = dict(row)
                        # Convert UUID to string
                        row_dict['session_id'] = str(row_dict['session_id'])
                        result.append(row_dict)
                    self.logger.debug(f"Found {len(result)} history records for question {question_id}")
                    return result
        except Exception as e:
            self.logger.error(f"Failed to get question history for {question_id}: {e}")
            raise

    @cached(ttl=CacheConfig.QUESTION_CACHE_TTL, key_prefix="question")
    async def get_question(self, question_id: UUID) -> Optional[dict]:
        """Get a single question by ID with properly parsed options"""
        self.logger.debug(f"Fetching question: {question_id}")
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    question = await connection.fetchrow(
                        """SELECT id, topic, level, difficulty, question_text, correct_answer, options, created_at 
                        FROM questions WHERE id = $1""",
                        question_id
                    )
                    if question:
                        result = dict(question)
                        # Convert UUID to string
                        result['id'] = str(result['id'])
                        # Ensure options is properly deserialized
                        result['options'] = self._deserialize_json(result['options'])
                        self.logger.debug(f"Found question: {question_id}")
                        return result
                    else:
                        self.logger.debug(f"No question found with ID: {question_id}")
                        return None
        except Exception as e:
            self.logger.error(f"Failed to get question {question_id}: {e}")
            raise

    async def get_all_questions(self, topic: Optional[str] = None, level: Optional[str] = None, 
                               difficulty: Optional[str] = None, limit: int = 50, offset: int = 0) -> dict:
        """Get questions with optional filtering and pagination, with properly parsed options"""
        # Validate enum filters if provided
        if level:
            level = self._validate_enum(level, self.VALID_USER_LEVELS, "user_level")
        if difficulty:
            difficulty = self._validate_enum(difficulty, self.VALID_QUIZ_DIFFICULTIES, "quiz_difficulty")
            
        limit, offset = self._validate_pagination(limit, offset)
        self.logger.debug(f"Fetching questions with filters: topic={topic}, level={level}, difficulty={difficulty} (limit={limit}, offset={offset})")
        
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    # Build dynamic query
                    where_conditions = []
                    params = []
                    param_counter = 1
                    
                    if topic:
                        where_conditions.append(f"topic = ${param_counter}")
                        params.append(topic)
                        param_counter += 1
                    
                    if level:
                        where_conditions.append(f"level = ${param_counter}")
                        params.append(level)
                        param_counter += 1
                        
                    if difficulty:
                        where_conditions.append(f"difficulty = ${param_counter}")
                        params.append(difficulty)
                        param_counter += 1
                    
                    where_clause = " WHERE " + " AND ".join(where_conditions) if where_conditions else ""
                    
                    # Get total count
                    count_query = f"SELECT COUNT(*) FROM questions{where_clause}"
                    total_count = await connection.fetchval(count_query, *params)
                    
                    # Get paginated questions
                    params.extend([limit, offset])
                    questions_query = f"""
                        SELECT id, topic, level, difficulty, question_text, correct_answer, options, created_at
                        FROM questions{where_clause}
                        ORDER BY created_at DESC
                        LIMIT ${param_counter} OFFSET ${param_counter + 1}
                    """
                    
                    questions = await connection.fetch(questions_query, *params)
                    
                    questions_list = []
                    for row in questions:
                        row_dict = dict(row)
                        # Convert UUID to string
                        row_dict['id'] = str(row_dict['id'])
                        # Ensure options is properly deserialized
                        row_dict['options'] = self._deserialize_json(row_dict['options'])
                        questions_list.append(row_dict)
                    
                    has_more = (offset + len(questions_list)) < total_count
                    
                    result = {
                        'questions': questions_list,
                        'total_count': total_count,
                        'limit': limit,
                        'offset': offset,
                        'has_more': has_more,
                        'filters': {
                            'topic': topic,
                            'level': level,
                            'difficulty': difficulty
                        }
                    }
                    
                    self.logger.debug(f"Found {len(questions_list)} questions (total: {total_count})")
                    return result
        except Exception as e:
            self.logger.error(f"Failed to get questions: {e}")
            raise

    async def get_user_activity(self, user_id: UUID, limit: int = 100, offset: int = 0) -> dict:
        limit, offset = self._validate_pagination(limit, offset)
        self.logger.debug(f"Fetching user activity for: {user_id} (limit={limit}, offset={offset})")
        
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    total_count = await connection.fetchval(
                        """SELECT COUNT(a.id)
                        FROM activities a
                        JOIN sessions s ON a.session_id = s.id
                        WHERE s.user_id = $1""",
                        user_id
                    )
                    
                    activity = await connection.fetch(
                        """SELECT a.session_id, a.type, a.content, a.created_at
                        FROM activities a
                        JOIN sessions s ON a.session_id = s.id
                        WHERE s.user_id = $1
                        ORDER BY a.created_at DESC
                        LIMIT $2 OFFSET $3""",
                        user_id, limit, offset
                    )
                    
                    activities_list = []
                    for row in activity:
                        row_dict = dict(row)
                        # Convert UUID to string
                        row_dict['session_id'] = str(row_dict['session_id'])
                        # Ensure content is properly deserialized
                        row_dict['content'] = self._deserialize_json(row_dict['content'])
                        activities_list.append(row_dict)
                    
                    has_more = (offset + len(activities_list)) < total_count
                    
                    result = {
                        'activities': activities_list,
                        'total_count': total_count,
                        'limit': limit,
                        'offset': offset,
                        'has_more': has_more
                    }
                    
                    self.logger.debug(f"Found {len(activities_list)} activity records for user {user_id} (total: {total_count})")
                    return result
        except Exception as e:
            self.logger.error(f"Failed to get user activity for {user_id}: {e}")
            raise

    async def get_leaderboard_data(self, timeframe: str = "all_time", limit: int = 50) -> List[dict]:
        """Get leaderboard data with user rankings"""
        self.logger.debug(f"Fetching leaderboard data: timeframe={timeframe}, limit={limit}")
        
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    # Base query for user statistics
                    base_query = """
                    WITH user_stats AS (
                        SELECT 
                            u.id,
                            u.user_name,
                            u.email,
                            COUNT(DISTINCT s.id) as total_sessions,
                            COUNT(DISTINCT p.topic) as topics_started,
                            COUNT(DISTINCT CASE WHEN p.status = 'completed' THEN p.topic END) as topics_completed,
                            COUNT(DISTINCT qa.id) as quiz_attempts,
                            COUNT(DISTINCT CASE WHEN qa.is_correct THEN qa.id END) as correct_answers,
                            COALESCE(
                                ROUND(
                                    COUNT(CASE WHEN qa.is_correct THEN 1 END)::decimal / 
                                    NULLIF(COUNT(qa.id), 0) * 100, 1
                                ), 0
                            ) as quiz_accuracy
                        FROM users u
                        LEFT JOIN sessions s ON u.id = s.user_id
                        LEFT JOIN progress p ON u.id = p.user_id
                        LEFT JOIN quiz_attempts qa ON s.id = qa.session_id
                        WHERE u.is_active = TRUE
                    """
                    
                    # Add timeframe filter if needed
                    if timeframe == "weekly":
                        base_query += " AND s.started_at >= NOW() - INTERVAL '7 days'"
                    elif timeframe == "monthly":
                        base_query += " AND s.started_at >= NOW() - INTERVAL '30 days'"
                    
                    base_query += """
                        GROUP BY u.id, u.user_name, u.email
                    ),
                    ranked_users AS (
                        SELECT 
                            *,
                            -- Calculate points based on activities
                            (
                                (topics_completed * 100) +           -- 100 points per completed topic
                                (correct_answers * 10) +             -- 10 points per correct answer
                                (total_sessions * 5) +               -- 5 points per session
                                CASE 
                                    WHEN quiz_accuracy >= 90 THEN 50  -- Bonus for high accuracy
                                    WHEN quiz_accuracy >= 80 THEN 30
                                    WHEN quiz_accuracy >= 70 THEN 10
                                    ELSE 0
                                END
                            ) as points,
                            -- Calculate learning streak (simplified)
                            LEAST(total_sessions, 30) as streak_days,
                            -- Determine user level based on points
                            CASE 
                                WHEN (topics_completed * 100 + correct_answers * 10 + total_sessions * 5) >= 1000 THEN 'expert'
                                WHEN (topics_completed * 100 + correct_answers * 10 + total_sessions * 5) >= 500 THEN 'intermediate'
                                ELSE 'beginner'
                            END as level,
                            -- Count achievements (simplified)
                            CASE 
                                WHEN total_sessions > 0 THEN 1 ELSE 0
                            END +
                            CASE 
                                WHEN topics_completed >= 5 THEN 1 ELSE 0
                            END +
                            CASE 
                                WHEN quiz_accuracy >= 80 THEN 1 ELSE 0
                            END as achievements_count
                        FROM user_stats
                        WHERE total_sessions > 0  -- Only include active users
                    )
                    SELECT 
                        ROW_NUMBER() OVER (ORDER BY points DESC, quiz_accuracy DESC, topics_completed DESC) as rank,
                        id as user_id,
                        user_name,
                        points,
                        level,
                        achievements_count,
                        streak_days,
                        topics_completed,
                        quiz_accuracy
                    FROM ranked_users
                    ORDER BY points DESC, quiz_accuracy DESC, topics_completed DESC
                    LIMIT $1
                    """
                    
                    leaderboard = await connection.fetch(base_query, limit)
                    
                    result = []
                    for row in leaderboard:
                        row_dict = dict(row)
                        row_dict['user_id'] = str(row_dict['user_id'])
                        result.append(row_dict)
                    
                    self.logger.debug(f"Found {len(result)} leaderboard entries")
                    return result
                    
        except Exception as e:
            self.logger.error(f"Failed to get leaderboard data: {e}")
            raise

    async def get_user_rank(self, user_id: UUID, timeframe: str = "all_time") -> Optional[int]:
        """Get a specific user's rank in the leaderboard"""
        self.logger.debug(f"Fetching user rank for: {user_id}, timeframe={timeframe}")
        
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    # Simplified rank calculation
                    rank_query = """
                    WITH user_stats AS (
                        SELECT 
                            u.id,
                            COUNT(DISTINCT s.id) as total_sessions,
                            COUNT(DISTINCT CASE WHEN p.status = 'completed' THEN p.topic END) as topics_completed,
                            COUNT(DISTINCT CASE WHEN qa.is_correct THEN qa.id END) as correct_answers,
                            (
                                (COUNT(DISTINCT CASE WHEN p.status = 'completed' THEN p.topic END) * 100) +
                                (COUNT(DISTINCT CASE WHEN qa.is_correct THEN qa.id END) * 10) +
                                (COUNT(DISTINCT s.id) * 5)
                            ) as points
                        FROM users u
                        LEFT JOIN sessions s ON u.id = s.user_id
                        LEFT JOIN progress p ON u.id = p.user_id
                        LEFT JOIN quiz_attempts qa ON s.id = qa.session_id
                        WHERE u.is_active = TRUE
                    """
                    
                    if timeframe == "weekly":
                        rank_query += " AND s.started_at >= NOW() - INTERVAL '7 days'"
                    elif timeframe == "monthly":
                        rank_query += " AND s.started_at >= NOW() - INTERVAL '30 days'"
                    
                    rank_query += """
                        GROUP BY u.id
                        HAVING COUNT(DISTINCT s.id) > 0
                    ),
                    ranked_users AS (
                        SELECT 
                            id,
                            points,
                            ROW_NUMBER() OVER (ORDER BY points DESC) as rank
                        FROM user_stats
                    )
                    SELECT rank FROM ranked_users WHERE id = $1
                    """
                    
                    rank = await connection.fetchval(rank_query, user_id)
                    return rank
                    
        except Exception as e:
            self.logger.error(f"Failed to get user rank for {user_id}: {e}")
            return None