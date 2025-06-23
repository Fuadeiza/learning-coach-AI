#!/bin/bash
# Quick Setup Script for Learning Coach Platform
# Minimal version for experienced developers

set -e

echo "🚀 Quick Setup for Learning Coach Platform"

# Basic checks
[[ -f "mcp_server/main.py" ]] || { echo "❌ Run this from the project root directory"; exit 1; }
command -v python3 >/dev/null || { echo "❌ Python 3 required"; exit 1; }
command -v psql >/dev/null || { echo "❌ PostgreSQL required"; exit 1; }

# Setup virtual environment
echo "📦 Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Setup environment
echo "⚙️ Creating .env file..."
if [[ ! -f ".env" ]]; then
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    cat > .env << EOF
DATABASE_URL=postgresql://postgres@localhost:5432/learning_coach_db
JWT_SECRET_KEY=$JWT_SECRET
ACCESS_TOKEN_EXPIRE_MINUTES=30
OPENAI_API_KEY=your_openai_api_key_here
CORS_ORIGINS=http://localhost:3000,http://localhost:8080
ENVIRONMENT=development
LOG_LEVEL=INFO
EOF
    echo "✅ .env created"
else
    echo "⚠️ .env already exists"
fi

# Setup database
echo "🗄️ Setting up database..."
createdb learning_coach_db 2>/dev/null || echo "Database might already exist"
psql learning_coach_db -f db/schema.sql

# Test setup
echo "🧪 Testing setup..."
python3 -c "
import asyncio
import sys
sys.path.append('.')
from db.postgres_client import get_db_pool

async def test():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval('SELECT 1')
        print('✅ Database connected!' if result == 1 else '❌ Connection failed')
    await pool.close()

asyncio.run(test())
"

# Create run script
cat > run_server.sh << 'EOF'
#!/bin/bash
source venv/bin/activate 2>/dev/null || true
uvicorn mcp_server.main:app --reload --host 0.0.0.0 --port 8000
EOF
chmod +x run_server.sh

echo ""
echo "🎉 Setup complete!"
echo "1. Add your OpenAI API key to .env"
echo "2. Start server: ./run_server.sh"
echo "3. Visit: http://localhost:8000/docs"