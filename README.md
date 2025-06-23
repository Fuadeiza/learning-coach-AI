# 🚀 Learning Coach Platform - Setup Instructions

## 📋 Prerequisites

Before running the setup script, ensure you have:

- **Python 3.10+** installed
- **PostgreSQL 15+** installed and running
- **Git** for cloning the repository
- **OpenAI API Key** (get one from [OpenAI](https://platform.openai.com/api-keys))

### Quick Prerequisite Check

```bash
python3 --version    # Should be 3.10+
psql --version       # Should be 15+
git --version        # Any recent version
```

## 🎯 Setup Options

### Option 1: Full Automated Setup (Recommended)

The complete setup script with guided configuration, testing, and helpful utilities:

```bash
# 1. Clone the repository
git clone https://github.com/Fuadeiza/learning-coach-platform.git
cd learning-coach-platform

# 2. Make setup script executable
chmod +x setup.sh

# 3. Run the setup script
./setup.sh
```

**What this script does:**
- ✅ Checks all prerequisites
- ✅ Creates Python virtual environment
- ✅ Installs all dependencies
- ✅ Generates secure JWT secret
- ✅ Creates .env configuration file
- ✅ Sets up PostgreSQL database
- ✅ Runs database schema
- ✅ Tests the complete setup
- ✅ Creates test user (optional)
- ✅ Creates utility scripts (`run_server.sh`, `run_tests.sh`, `dev_tools.sh`)

### Option 2: Quick Setup (For Experienced Developers)

Minimal setup script that gets you running quickly:

```bash
# 1. Clone and enter directory
git clone https://github.com/Fuadeiza/learning-coach-platform.git
cd learning-coach-platform

# 2. Run quick setup
chmod +x quick_setup.sh
./quick_setup.sh
```

**What this script does:**
- ✅ Basic prerequisite checks
- ✅ Creates virtual environment
- ✅ Installs dependencies
- ✅ Creates minimal .env file
- ✅ Sets up database
- ✅ Creates run script

### Option 3: Manual Setup

If you prefer to set up manually, follow these steps:

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
cp .env.example .env
# Edit .env with your configuration

# 5. Generate JWT secret
python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))" >> .env

# 6. Set up database
createdb learning_coach_db
psql learning_coach_db -f db/schema.sql

# 7. Start server
uvicorn mcp_server.main:app --reload
```

</details>

## 🔧 Configuration

### Required Environment Variables

After running the setup script, edit `.env` to add your API keys:

```bash
# Edit the .env file
nano .env  # or your preferred editor

# Add your OpenAI API key
OPENAI_API_KEY=sk-your-actual-openai-api-key-here
```

### Database Configuration

The setup script uses these default database settings:

```bash
DB_NAME=learning_coach_db
DB_USER=postgres
DB_HOST=localhost
DB_PORT=5432
```

To use different settings, set environment variables before running setup:

```bash
export DB_USER=myuser
export DB_HOST=myhost
export DB_PORT=5433
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

### 2. Database Test

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
# Run the comprehensive test suite
./run_tests.sh
```

### 4. API Documentation

Visit http://localhost:8000/docs to see the interactive API documentation.

## 🛠️ Utility Scripts Created

The setup script creates several helpful utility scripts:

### `run_server.sh`
Starts the development server with auto-reload:
```bash
./run_server.sh
```

### `run_tests.sh`
Runs the complete test suite:
```bash
./run_tests.sh
```

### `dev_tools.sh`
Development utilities:
```bash
./dev_tools.sh format      # Format code with black/isort
./dev_tools.sh lint        # Lint with flake8
./dev_tools.sh type-check  # Type check with mypy
./dev_tools.sh security    # Security scan with bandit
./dev_tools.sh deps        # Check outdated dependencies
./dev_tools.sh backup-db   # Backup database
```

## 🚨 Troubleshooting

### Common Issues

**PostgreSQL Connection Error:**
```bash
# Check if PostgreSQL is running
pg_isready -h localhost -p 5432 -U postgres

# Start PostgreSQL (varies by system)
brew services start postgresql  # macOS
sudo systemctl start postgresql # Linux
```

**Python Version Error:**
```bash
# Check Python version
python3 --version

# Install Python 3.10+ if needed
# macOS: brew install python@3.10
# Ubuntu: sudo apt install python3.10
```

**Permission Denied:**
```bash
# Make scripts executable
chmod +x setup.sh
chmod +x quick_setup.sh
```

**Database Already Exists:**
The setup script will ask if you want to recreate it. Choose 'y' for a fresh start.

### Getting Help

If you encounter issues:

1. **Check the logs** - The setup script provides detailed output
2. **Review prerequisites** - Ensure all required software is installed
3. **Check permissions** - Make sure you can create databases and files
4. **Environment variables** - Verify your .env file is correct
5. **Open an issue** - If problems persist, create a GitHub issue

### Script Output Examples

**Successful Setup:**
```
🎓 Learning Coach Platform Setup
=====================================

📋 Checking prerequisites...
✅ Python 3.11.5 found
✅ PostgreSQL is running and accessible
✅ Project directory verified

📋 Setting up Python virtual environment...
✅ Virtual environment created
✅ Virtual environment activated
✅ pip upgraded

📋 Installing Python dependencies...
✅ Dependencies installed

📋 Setting up environment variables...
✅ .env file created with secure JWT secret

📋 Setting up database...
✅ Database 'learning_coach_db' created
✅ Database schema applied
✅ Database setup verified (8 tables created)

📋 Testing setup...
✅ Database connection test passed
✅ Password hashing test passed
✅ JWT token test passed
✅ Authentication configuration test passed
✅ All tests passed!

🎉 SETUP COMPLETED SUCCESSFULLY!
```

## 🔄 Updating Your Setup

To update your setup after pulling new changes:

```bash
# Pull latest changes
git pull origin main

# Rerun setup (it will update existing installation)
./setup.sh

# Or just update dependencies
source venv/bin/activate
pip install -r requirements.txt

# Update database schema if needed
psql learning_coach_db -f db/schema.sql
```

## 🚀 Next Steps

After successful setup:

1. **Add your OpenAI API key** to `.env`
2. **Start the server** with `./run_server.sh`
3. **Explore the API** at http://localhost:8000/docs
4. **Run tests** with `./run_tests.sh`
5. **Start building** your frontend or integrations!

Ready to build amazing learning experiences! 🎓✨