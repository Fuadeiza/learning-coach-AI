# 🎓 AI Learning Coach Platform

A comprehensive AI-powered learning platform with personalized tutoring, adaptive quizzes, progress tracking, and gamification features.

Live Demo here: https://youtu.be/7iQzjRc635U?feature=shared

## ✨ Features

### 🤖 AI-Powered Learning
- **Smart Explanations**: Get detailed explanations tailored to your learning level
- **Adaptive Quizzes**: Dynamic difficulty adjustment based on your performance
- **Study Plans**: Personalized learning paths generated by AI
- **Learning Materials**: Curated resources with rich metadata and recommendations

### 📊 Progress Tracking & Analytics
- **Learning Streaks**: Track consecutive days of learning activity
- **Achievement System**: Earn badges and points for milestones
- **Detailed Analytics**: Comprehensive stats on your learning journey
- **Study Time Tracking**: Monitor and optimize your study sessions

### 🏆 Gamification & Social Features
- **Global Leaderboard**: Compete with other learners worldwide
- **User Levels**: Progress from beginner to expert
- **Points System**: Earn points for completing topics and quizzes
- **Achievement Badges**: Unlock rewards for consistent learning

### 🚀 Performance & Reliability
- **Advanced Caching**: Multi-layer caching system for lightning-fast responses
- **Enhanced Logging**: Comprehensive request tracking and performance monitoring
- **Robust Authentication**: Secure JWT-based authentication with refresh tokens
- **Database Optimization**: Efficient PostgreSQL queries with connection pooling

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python 3.10+)
- **Database**: PostgreSQL 15+
- **AI**: OpenAI GPT models via LangChain
- **Caching**: Redis + In-memory LRU cache
- **Authentication**: JWT with bcrypt password hashing
- **Documentation**: Auto-generated OpenAPI/Swagger docs

## 📋 Prerequisites

Before setting up the project, ensure you have:

- **Python 3.10+** installed
- **PostgreSQL 15+** installed and running
- **Redis** (optional, for distributed caching)
- **Git** for cloning the repository
- **OpenAI API Key** (get one from [OpenAI](https://platform.openai.com/api-keys))

### Quick Prerequisite Check

```bash
python3 --version    # Should be 3.10+
psql --version       # Should be 15+
redis-server --version  # Optional
git --version        # Any recent version
```

## 🚀 Quick Start

### Option 1: Docker (Recommended for Easy Setup)

The fastest way to get started with all services configured:

```bash
# 1. Clone the repository
git clone https://github.com/Fuadeiza/learning-coach-platform.git
cd learning-coach-platform

# 2. Copy and configure environment file
cp env.docker.example .env
nano .env  # Edit OPENAI_API_KEY=your_key_here

# 3. Start with Docker Compose
docker-compose up -d

# 4. Access the application
# API: http://localhost:8000
# API Docs: http://localhost:8000/docs
# Database Admin: http://localhost:8080 (dev profile)
```

**What Docker setup includes:**
- ✅ PostgreSQL database with automatic schema setup
- ✅ Redis cache for optimal performance
- ✅ Web application with all dependencies
- ✅ Development tools (Adminer, Redis Commander)
- ✅ Automatic health checks and restart policies
- ✅ Persistent data volumes
- ✅ Optimized networking between services

### Option 2: Quick Setup (Native Installation)

Perfect for developers who want to get up and running quickly:

```bash
# 1. Clone the repository
git clone https://github.com/Fuadeiza/learning-coach-platform.git
cd learning-coach-platform

# 2. Run the quick setup script
chmod +x quick_setup.sh
./quick_setup.sh

# 3. Add your OpenAI API key to .env
nano .env  # Edit OPENAI_API_KEY=your_key_here

# 4. Start the server
./run_server.sh
```

**What `quick_setup.sh` does:**
- ✅ Checks basic prerequisites (Python, PostgreSQL)
- ✅ Creates Python virtual environment
- ✅ Installs all dependencies from requirements.txt
- ✅ Generates secure JWT secret key
- ✅ Creates `.env` configuration file
- ✅ Sets up PostgreSQL database and schema
- ✅ Creates `run_server.sh` utility script
- ✅ Tests database connection

### Option 3: Full Setup (Recommended for Development)

Comprehensive setup with guided configuration, testing, and development tools:

```bash
# 1. Clone the repository
git clone https://github.com/Fuadeiza/learning-coach-platform.git
cd learning-coach-platform

# 2. Run the full setup script
chmod +x setup.sh
./setup.sh
```

**What `setup.sh` does:**
- ✅ Comprehensive prerequisite checks with helpful error messages
- ✅ Interactive prompts for existing files/databases
- ✅ Creates and configures Python virtual environment
- ✅ Installs all dependencies with version verification
- ✅ Generates secure JWT secret and other security keys
- ✅ Creates comprehensive `.env` configuration file
- ✅ Sets up PostgreSQL database with proper error handling
- ✅ Runs complete database schema setup
- ✅ Performs extensive testing (database, auth, JWT, etc.)
- ✅ Creates multiple utility scripts:
  - `run_server.sh` - Start development server
  - `run_tests.sh` - Run test suite
  - `dev_tools.sh` - Development utilities (formatting, linting, etc.)
- ✅ Provides detailed success/failure reporting
- ✅ Offers troubleshooting guidance

### Option 4: Manual Setup

<details>
<summary>Click to expand manual setup instructions</summary>

```bash
# 1. Clone repository
git clone https://github.com/Fuadeiza/learning-coach-platform.git
cd learning-coach-platform

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Create .env file
cp .env.example .env  # If available, or create manually
nano .env  # Configure your settings

# 5. Generate JWT secret
python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))" >> .env

# 6. Set up database
createdb learning_coach_db
psql learning_coach_db -f db/schema.sql

# 7. Start server
uvicorn mcp_server.main:app --reload --host 0.0.0.0 --port 8000
```

</details>

## 🐳 Docker Setup (Detailed)

### Prerequisites for Docker

- **Docker** 20.10+ installed and running
- **Docker Compose** 2.0+ installed
- **Git** for cloning the repository
- **OpenAI API Key** (get one from [OpenAI](https://platform.openai.com/api-keys))

### Docker Quick Start

```bash
# Clone and enter directory
git clone https://github.com/Fuadeiza/learning-coach-platform.git
cd learning-coach-platform

# Copy and configure environment
cp env.docker.example .env
nano .env  # Add your OPENAI_API_KEY

# Start all services
docker-compose up -d

# Check status
docker-compose ps
```

### Docker Utility Script

We provide a comprehensive utility script for Docker operations:

```bash
# Make script executable
chmod +x docker-scripts.sh

# Development commands
./docker-scripts.sh dev-up          # Start development environment
./docker-scripts.sh dev-logs        # View logs
./docker-scripts.sh dev-shell       # Open shell in web container
./docker-scripts.sh dev-down        # Stop environment

# Production commands
./docker-scripts.sh prod-build      # Build production images
./docker-scripts.sh prod-up         # Start production environment
./docker-scripts.sh prod-scale 3    # Scale to 3 web replicas

# Database operations
./docker-scripts.sh db-backup       # Create database backup
./docker-scripts.sh db-shell        # Open database shell
./docker-scripts.sh db-reset        # Reset database (careful!)

# Maintenance
./docker-scripts.sh health-check    # Check system health
./docker-scripts.sh status          # Show container status
./docker-scripts.sh cleanup         # Clean up Docker resources
```

### Docker Services

#### Development Environment (`docker-compose.yml`)

- **Web Application** (Port 8000)
  - FastAPI application with hot reload
  - Automatic dependency installation
  - Volume mounts for development

- **PostgreSQL Database** (Port 5432)
  - PostgreSQL 15 with automatic schema setup
  - Persistent data storage
  - Health checks included

- **Redis Cache** (Port 6379)
  - Redis 7 with persistence enabled
  - Optimized for caching workloads
  - Memory limits configured

- **Adminer** (Port 8080) - *Development Profile*
  - Web-based database administration
  - Easy database management and queries

- **Redis Commander** (Port 8081) - *Development Profile*
  - Web-based Redis management
  - View cache contents and statistics

#### Production Environment (`docker-compose.prod.yml`)

- **Multi-replica Web Application**
  - Load balancing across multiple instances
  - Resource limits and reservations
  - Rolling updates with zero downtime

- **Nginx Reverse Proxy** (Ports 80/443)
  - SSL termination
  - Load balancing
  - Static file serving

- **Enhanced Security**
  - Non-root containers
  - Secrets management
  - Network isolation

- **Resource Management**
  - CPU and memory limits
  - Health checks and auto-restart
  - Persistent volume configuration

### Docker Environment Configuration

Create `.env` file from template:

```bash
cp env.docker.example .env
```

**Required Variables:**
```bash
# AI Services (Required)
OPENAI_API_KEY=sk-your-actual-openai-api-key-here

# Database (Auto-configured for Docker)
DATABASE_URL=postgresql://postgres:password@db:5432/learning_coach_db
DB_PASSWORD=password

# Redis (Optional but recommended)
REDIS_URL=redis://redis:6379/0
REDIS_PASSWORD=your_redis_password_here

# JWT Security
JWT_SECRET_KEY=your-super-secure-jwt-secret-key
```

### Docker Development Workflow

```bash
# 1. Start development environment
./docker-scripts.sh dev-up

# 2. View logs in real-time
./docker-scripts.sh dev-logs

# 3. Make code changes (auto-reload enabled)
# Edit your Python files...

# 4. Access services
# API: http://localhost:8000/docs
# Database: http://localhost:8080 (Adminer)
# Redis: http://localhost:8081 (Redis Commander)

# 5. Run database operations
./docker-scripts.sh db-shell      # SQL queries
./docker-scripts.sh db-backup     # Backup data

# 6. Debug in container
./docker-scripts.sh dev-shell     # Shell access

# 7. Clean shutdown
./docker-scripts.sh dev-down
```

### Production Deployment

```bash
# 1. Configure production environment
cp env.docker.example .env.prod
nano .env.prod  # Set production values

# 2. Build production images
./docker-scripts.sh prod-build

# 3. Start production environment
./docker-scripts.sh prod-up

# 4. Scale as needed
./docker-scripts.sh prod-scale 5  # 5 web replicas

# 5. Monitor
./docker-scripts.sh prod-logs
./docker-scripts.sh health-check
```

### Docker Troubleshooting

**Common Issues:**

**Port Already in Use:**
```bash
# Check what's using the port
lsof -i :8000
# Stop conflicting services or change ports in docker-compose.yml
```

**Database Connection Issues:**
```bash
# Check database health
docker-compose exec db pg_isready -U postgres
# View database logs
docker-compose logs db
```

**Out of Disk Space:**
```bash
# Clean up Docker resources
./docker-scripts.sh cleanup
# Or manually
docker system prune -a --volumes
```

**Container Won't Start:**
```bash
# Check container logs
docker-compose logs web
# Check system resources
docker stats
```

### Docker Performance Optimization

**For Development:**
- Use volume mounts for fast code changes
- Enable BuildKit for faster builds: `export DOCKER_BUILDKIT=1`
- Use `.dockerignore` to exclude unnecessary files

**For Production:**
- Multi-stage builds for smaller images
- Resource limits to prevent resource exhaustion
- Health checks for automatic recovery
- Persistent volumes for data safety

## ⚙️ Configuration

### Environment Variables

After running either setup script, edit `.env` to configure your API keys and settings:

```bash
# Edit the configuration file
nano .env  # or your preferred editor
```

**Required Variables:**
```bash
# AI Services (Required)
OPENAI_API_KEY=sk-your-actual-openai-api-key-here

# Database (Auto-configured by setup scripts)
DATABASE_URL=postgresql://postgres@localhost:5432/learning_coach_db
DB_HOST=localhost
DB_PORT=5432
DB_NAME=learning_coach_db
DB_USER=postgres

# Authentication (Auto-generated by setup scripts)
JWT_SECRET_KEY=your-secure-jwt-secret
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

**Optional Variables:**
```bash
# CORS Configuration
CORS_ORIGINS=http://localhost:3000,http://localhost:8080

# Redis Caching (Optional)
REDIS_URL=redis://localhost:6379/0

# Logging
LOG_LEVEL=INFO

# Rate Limiting
LOGIN_RATE_LIMIT_ATTEMPTS=5
LOGIN_RATE_LIMIT_WINDOW_MINUTES=15
```

### Custom Database Configuration

To use different database settings, set environment variables before running setup:

```bash
export DB_USER=myuser
export DB_HOST=myhost  
export DB_PORT=5433
export DB_NAME=my_learning_db
./setup.sh
```

## 🧪 Testing Your Setup

### 1. Health Check

```bash
# Start the server
./run_server.sh

# In another terminal, test the health endpoint
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "message": "AI Learning Coach API is running"
}
```

### 2. Database Connection Test

```bash
# Test database connection
python3 -c "
import asyncio
import sys
sys.path.append('.')
from db.postgres_client import get_db_pool

async def test():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval('SELECT 1')
        print('✅ Database OK!' if result == 1 else '❌ Database failed!')
    await pool.close()

asyncio.run(test())
"
```

### 3. Authentication Test

```bash
# Run the comprehensive test suite (if created by full setup)
./run_tests.sh
```

### 4. API Documentation

Visit **http://localhost:8000/docs** to explore the interactive API documentation.

### 5. Cache System Test

```bash
# Test cache statistics endpoint
curl http://localhost:8000/cache/stats
```

## 🛠️ Development Tools

The full setup script (`setup.sh`) creates several utility scripts for development:

### Server Management
```bash
./run_server.sh          # Start development server with auto-reload
```

### Testing
```bash
./run_tests.sh          # Run complete test suite
```

### Development Utilities
```bash
./dev_tools.sh format      # Format code with black/isort
./dev_tools.sh lint        # Lint with flake8  
./dev_tools.sh type-check  # Type check with mypy
./dev_tools.sh security    # Security scan with bandit
./dev_tools.sh deps        # Check outdated dependencies
./dev_tools.sh backup-db   # Backup database
```

## 📚 API Endpoints

### Core Learning Features
- `POST /explain` - Get AI explanations for topics
- `POST /quiz` - Generate quizzes with AI
- `POST /quiz/adaptive` - Generate adaptive difficulty quizzes
- `POST /plan` - Create personalized study plans
- `POST /materials` - Get curated learning materials

### Progress & Analytics
- `GET /analytics/user-stats` - Comprehensive learning analytics
- `GET /achievements` - User achievements and streaks
- `GET /leaderboard` - Global user rankings
- `POST /progress/update` - Update learning progress
- `GET /study-time/stats` - Study time analytics

### Authentication
- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `POST /auth/refresh` - Refresh JWT tokens

### Session Management
- `POST /sessions/start` - Start learning session
- `POST /sessions/end` - End learning session
- `GET /my-sessions` - Get user sessions

For complete API documentation, visit `/docs` after starting the server.

## 🚨 Troubleshooting

### Common Issues

**PostgreSQL Connection Error:**
```bash
# Check if PostgreSQL is running
pg_isready -h localhost -p 5432 -U postgres

# Start PostgreSQL (varies by system)
brew services start postgresql  # macOS with Homebrew
sudo systemctl start postgresql # Linux systemd
```

**Python Version Error:**
```bash
# Check Python version
python3 --version

# Install Python 3.10+ if needed
# macOS: brew install python@3.10
# Ubuntu: sudo apt install python3.10 python3.10-venv
```

**Permission Denied:**
```bash
# Make scripts executable
chmod +x setup.sh quick_setup.sh run_server.sh
```

**OpenAI API Errors:**
- Verify your API key is correct in `.env`
- Check your OpenAI account has sufficient credits
- Ensure API key has proper permissions

**Database Already Exists:**
Both setup scripts will ask if you want to recreate existing databases. Choose 'y' for a fresh start.

**Redis Connection Issues (Optional):**
```bash
# Start Redis if using distributed caching
redis-server
# Or via Docker
docker run -d -p 6379:6379 redis:alpine
```

### Getting Help

If you encounter issues:

1. **Check the logs** - Setup scripts provide detailed output
2. **Review prerequisites** - Ensure all required software is installed  
3. **Check permissions** - Verify you can create databases and files
4. **Environment variables** - Ensure your `.env` file is configured correctly
5. **Open an issue** - Create a GitHub issue with error details

### Setup Script Output Examples

**Successful Quick Setup:**
```
🚀 Quick Setup for Learning Coach Platform
📦 Setting up virtual environment...
✅ .env created
🗄️ Setting up database...
🧪 Testing setup...
✅ Database connected!
🎉 Setup complete!
1. Add your OpenAI API key to .env
2. Start server: ./run_server.sh
3. Visit: http://localhost:8000/docs
```

**Successful Full Setup:**
```
🎓 Learning Coach Platform Setup
=====================================
📋 Checking prerequisites...
✅ Python 3.11.5 found
✅ PostgreSQL is running and accessible
✅ Project directory verified
📋 Setting up Python virtual environment...
✅ Virtual environment created
✅ Dependencies installed
📋 Setting up environment variables...
✅ .env file created with secure JWT secret
📋 Setting up database...
✅ Database schema applied
📋 Testing setup...
✅ All tests passed!
🎉 SETUP COMPLETED SUCCESSFULLY!
```

## 🔄 Updating Your Installation

To update after pulling new changes:

```bash
# Pull latest changes
git pull origin main

# Update dependencies and database
source venv/bin/activate
pip install -r requirements.txt

# Update database schema if needed
psql learning_coach_db -f db/schema.sql

# Or rerun full setup
./setup.sh
```

## 🏗️ Project Structure

```
learning-coach-platform/
├── agents/              # AI agents (tutor, quiz, planner, content)
├── auth/               # Authentication system
├── db/                 # Database client and repositories
├── models/             # Pydantic models
├── utils/              # Utilities (caching, logging, middleware)
├── mcp_server/         # FastAPI application
├── tests/              # Test files
├── logs/               # Application logs
├── setup.sh           # Full setup script
├── quick_setup.sh     # Quick setup script
├── requirements.txt   # Python dependencies
└── README.md          # This file
```

## 🚀 Performance Features

### Caching System
- **Multi-layer caching**: L1 (in-memory) + L2 (Redis) 
- **Smart TTL strategy**: Different cache durations for different data types
- **Cache hit rates**: Typically 70-90% for repeated requests
- **Performance gains**: 10-3700x faster responses for cached content

### Logging & Monitoring
- **Request tracking**: Complete request lifecycle logging
- **Performance monitoring**: Automatic slow request detection
- **Cache analytics**: Real-time hit/miss rates and statistics
- **Error tracking**: Detailed error context and stack traces

## 🔐 Security Features

- **JWT Authentication**: Secure token-based authentication
- **Password Hashing**: bcrypt with salt for secure password storage
- **Rate Limiting**: Protection against brute force attacks
- **CORS Configuration**: Configurable cross-origin resource sharing
- **Input Validation**: Comprehensive request validation with Pydantic

## 🎯 Next Steps

After successful setup:

1. **Configure your API key**: Add your OpenAI API key to `.env`
2. **Start the server**: Run `./run_server.sh`
3. **Explore the API**: Visit http://localhost:8000/docs
4. **Run tests**: Execute `./run_tests.sh` (if available)
5. **Build your frontend**: Use the comprehensive API for your learning application
6. **Monitor performance**: Check `/cache/stats` and `/logs/stats` endpoints

## 📖 Additional Documentation

- **[API Frontend Guide](API_FRONTEND_GUIDE.md)** - Complete guide for frontend developers
- **[Caching Implementation Guide](CACHING_IMPLEMENTATION_GUIDE.md)** - Detailed caching system documentation
- **[Enhanced Logging Guide](ENHANCED_LOGGING_GUIDE.md)** - Logging and monitoring documentation
- **[Security Guide](security_guide.md)** - Security best practices and configuration

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and test thoroughly
4. Commit your changes: `git commit -am 'Add feature'`
5. Push to the branch: `git push origin feature-name`
6. Create a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

Ready to build amazing AI-powered learning experiences! 🎓✨

**Quick Links:**
- 📚 [API Documentation](http://localhost:8000/docs) (after starting server)
- 🔧 [Setup Scripts](#quick-start)
- 🚨 [Troubleshooting](#troubleshooting)
- 📊 [Performance Monitoring](http://localhost:8000/cache/stats) (after starting server)
