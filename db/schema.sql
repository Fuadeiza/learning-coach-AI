-- Learning Coach Platform Database Schema with Authentication
-- PostgreSQL compatible schema

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create enums
CREATE TYPE activity_type AS ENUM ('explanation', 'quiz', 'plan', 'materials');
CREATE TYPE progress_status AS ENUM ('started', 'completed', 'reviewed');
CREATE TYPE user_level AS ENUM ('beginner', 'intermediate', 'advanced');
CREATE TYPE quiz_difficulty AS ENUM ('easy', 'intermediate', 'hard');

-- Users table with authentication fields
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE, -- nullable, optional auth
    user_name VARCHAR(100), -- nullable, for personalization without requiring email
    password_hash VARCHAR(255), -- bcrypt hashed password for email/password authentication
    is_active BOOLEAN DEFAULT TRUE, -- whether the user account is active
    is_verified BOOLEAN DEFAULT FALSE, -- whether the user has verified their email address
    last_login TIMESTAMP WITH TIME ZONE, -- timestamp of last successful login
    created_by_oauth BOOLEAN DEFAULT FALSE, -- whether user was created via OAuth provider
    oauth_provider VARCHAR(50), -- OAuth provider name (google, github, etc.)
    oauth_id VARCHAR(255), -- user ID from OAuth provider
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Sessions table
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    topic VARCHAR(255) NOT NULL,
    level user_level NOT NULL,
    wants_quiz BOOLEAN DEFAULT FALSE,
    wants_plan BOOLEAN DEFAULT FALSE,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    ended_at TIMESTAMP WITH TIME ZONE
);

-- Activities table
CREATE TABLE activities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    type activity_type NOT NULL,
    content JSONB, -- Using JSONB for better performance in PostgreSQL
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Progress table
CREATE TABLE progress (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    topic VARCHAR(255) NOT NULL,
    level user_level NOT NULL,
    status progress_status DEFAULT 'started',
    last_interaction_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Questions table (normalized quiz questions for reusability)
CREATE TABLE questions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic VARCHAR(255) NOT NULL,
    level user_level NOT NULL,
    difficulty quiz_difficulty NOT NULL,
    question_text TEXT NOT NULL,
    correct_answer TEXT NOT NULL,
    options JSONB NOT NULL, -- Store answer options as JSON array
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Quiz attempts table
CREATE TABLE quiz_attempts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    question_id UUID REFERENCES questions(id) ON DELETE CASCADE,
    user_answer TEXT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    difficulty quiz_difficulty NOT NULL, -- Track difficulty level of this attempt
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Refresh tokens table for JWT authentication
CREATE TABLE refresh_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_used_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for better performance
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_user_name ON users(user_name);
CREATE INDEX idx_users_email_active ON users(email, is_active) WHERE email IS NOT NULL;
CREATE INDEX idx_users_oauth ON users(oauth_provider, oauth_id) WHERE oauth_provider IS NOT NULL;
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
CREATE INDEX idx_sessions_started_at ON sessions(started_at);
CREATE INDEX idx_activities_session_id ON activities(session_id);
CREATE INDEX idx_activities_type ON activities(type);
CREATE INDEX idx_activities_created_at ON activities(created_at);
CREATE INDEX idx_progress_user_id ON progress(user_id);
CREATE INDEX idx_progress_topic_level ON progress(topic, level);
CREATE INDEX idx_progress_status ON progress(status);
CREATE INDEX idx_progress_last_interaction_at ON progress(last_interaction_at);
CREATE INDEX idx_questions_topic_level_difficulty ON questions(topic, level, difficulty);
CREATE INDEX idx_questions_created_at ON questions(created_at);
CREATE INDEX idx_quiz_attempts_session_id ON quiz_attempts(session_id);
CREATE INDEX idx_quiz_attempts_question_id ON quiz_attempts(question_id);
CREATE INDEX idx_quiz_attempts_created_at ON quiz_attempts(created_at);
CREATE INDEX idx_quiz_attempts_is_correct ON quiz_attempts(is_correct);
CREATE INDEX idx_quiz_attempts_difficulty ON quiz_attempts(difficulty);
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_expires ON refresh_tokens(expires_at);
CREATE INDEX idx_refresh_tokens_hash ON refresh_tokens(token_hash);

-- Composite indexes for common queries
CREATE INDEX idx_sessions_user_topic_level ON sessions(user_id, topic, level);
CREATE INDEX idx_progress_user_topic_status ON progress(user_id, topic, status);

-- Unique constraint to prevent duplicate progress entries per user/topic/level
CREATE UNIQUE INDEX idx_progress_user_topic_level_unique ON progress(user_id, topic, level);

-- Unique constraints for authentication
ALTER TABLE users ADD CONSTRAINT users_email_unique UNIQUE (email);
ALTER TABLE users ADD CONSTRAINT users_oauth_unique UNIQUE (oauth_provider, oauth_id);

-- Comments for documentation
COMMENT ON TABLE users IS 'User accounts with optional email authentication and personalization';
COMMENT ON TABLE sessions IS 'Learning sessions tracking user interactions with topics';
COMMENT ON TABLE activities IS 'Detailed log of activities within each session';
COMMENT ON TABLE progress IS 'User progress tracking across topics and levels';
COMMENT ON TABLE questions IS 'Normalized quiz questions for reusability across sessions';
COMMENT ON TABLE quiz_attempts IS 'Individual quiz question attempts and results';
COMMENT ON TABLE refresh_tokens IS 'JWT refresh tokens for maintaining user sessions';

COMMENT ON COLUMN users.email IS 'Optional email for authentication, can be null for anonymous users';
COMMENT ON COLUMN users.user_name IS 'Optional display name for personalization without requiring email';
COMMENT ON COLUMN users.password_hash IS 'Bcrypt hashed password for email/password authentication';
COMMENT ON COLUMN users.is_active IS 'Whether the user account is active';
COMMENT ON COLUMN users.is_verified IS 'Whether the user has verified their email address';
COMMENT ON COLUMN users.last_login IS 'Timestamp of last successful login';
COMMENT ON COLUMN users.created_by_oauth IS 'Whether user was created via OAuth provider';
COMMENT ON COLUMN users.oauth_provider IS 'OAuth provider name (google, github, etc.)';
COMMENT ON COLUMN users.oauth_id IS 'User ID from OAuth provider';
COMMENT ON COLUMN sessions.wants_quiz IS 'Whether user requested quiz generation for this session';
COMMENT ON COLUMN sessions.wants_plan IS 'Whether user requested study plan generation for this session';
COMMENT ON COLUMN activities.content IS 'JSONB content storing activity-specific data (explanations, quiz questions, plans, etc.)';
COMMENT ON COLUMN progress.status IS 'Current status of user progress on this topic/level combination';
COMMENT ON COLUMN questions.options IS 'JSONB array storing answer options for multiple choice questions';
COMMENT ON COLUMN quiz_attempts.is_correct IS 'Whether the user answer matches the correct answer';
COMMENT ON COLUMN quiz_attempts.difficulty IS 'Difficulty level of the quiz question when attempted';
COMMENT ON COLUMN refresh_tokens.token_hash IS 'Hashed refresh token for security';
COMMENT ON COLUMN refresh_tokens.expires_at IS 'When this refresh token expires';
COMMENT ON COLUMN refresh_tokens.is_revoked IS 'Whether token has been manually revoked';
COMMENT ON COLUMN refresh_tokens.last_used_at IS 'When token was last used to refresh access token';

-- Views for analytics
CREATE VIEW session_stats AS
SELECT 
    s.id,
    s.topic,
    s.level,
    s.started_at,
    s.ended_at,
    EXTRACT(EPOCH FROM (COALESCE(s.ended_at, CURRENT_TIMESTAMP) - s.started_at))/60 AS duration_minutes,
    COUNT(a.id) AS activity_count,
    COUNT(qa.id) AS quiz_attempts_count,
    CASE 
        WHEN COUNT(qa.id) > 0 THEN 
            ROUND(AVG(CASE WHEN qa.is_correct THEN 1.0 ELSE 0.0 END) * 100, 2)
        ELSE NULL 
    END AS quiz_accuracy_percentage,
    COUNT(DISTINCT qa.difficulty) AS difficulty_levels_attempted
FROM sessions s
LEFT JOIN activities a ON s.id = a.session_id
LEFT JOIN quiz_attempts qa ON s.id = qa.session_id
GROUP BY s.id, s.topic, s.level, s.started_at, s.ended_at;

-- View for question reusability analytics
CREATE VIEW question_stats AS
SELECT 
    q.id,
    q.topic,
    q.level,
    q.difficulty,
    q.question_text,
    COUNT(qa.id) AS times_attempted,
    CASE 
        WHEN COUNT(qa.id) > 0 THEN 
            ROUND(AVG(CASE WHEN qa.is_correct THEN 1.0 ELSE 0.0 END) * 100, 2)
        ELSE NULL 
    END AS success_rate_percentage,
    q.created_at
FROM questions q
LEFT JOIN quiz_attempts qa ON q.id = qa.question_id
GROUP BY q.id, q.topic, q.level, q.difficulty, q.question_text, q.created_at;