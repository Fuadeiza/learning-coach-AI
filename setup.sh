#!/bin/bash

# Learning Coach Platform Setup Script
# This script sets up the complete development environment

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Configuration
PYTHON_MIN_VERSION="3.10"
DB_NAME="learning_coach_db"
DB_USER="${DB_USER:-postgres}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
VENV_NAME="venv"

# Helper functions
print_header() {
    echo -e "\n${BLUE}=====================================${NC}"
    echo -e "${WHITE}$1${NC}"
    echo -e "${BLUE}=====================================${NC}\n"
}

print_step() {
    echo -e "${CYAN}📋 $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${PURPLE}💡 $1${NC}"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check Python version
check_python_version() {
    if command_exists python3; then
        local python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        if python3 -c "import sys; exit(0 if sys.version_info >= tuple(map(int, '$PYTHON_MIN_VERSION'.split('.'))) else 1)"; then
            print_success "Python $python_version found"
            return 0
        else
            print_error "Python $PYTHON_MIN_VERSION+ required, found $python_version"
            return 1
        fi
    else
        print_error "Python 3 not found"
        return 1
    fi
}

# Check PostgreSQL
check_postgresql() {
    if command_exists psql; then
        if pg_isready -h $DB_HOST -p $DB_PORT -U $DB_USER >/dev/null 2>&1; then
            print_success "PostgreSQL is running and accessible"
            return 0
        else
            print_error "PostgreSQL is not running or not accessible"
            print_info "Start PostgreSQL:"
            print_info "  macOS (Homebrew): brew services start postgresql"
            print_info "  Linux: sudo systemctl start postgresql"
            print_info "  Docker: docker run --name postgres -e POSTGRES_PASSWORD=password -p 5432:5432 -d postgres:15"
            return 1
        fi
    else
        print_error "PostgreSQL (psql) not found"
        print_info "Install PostgreSQL:"
        print_info "  macOS: brew install postgresql"
        print_info "  Ubuntu: sudo apt-get install postgresql postgresql-contrib"
        print_info "  CentOS: sudo yum install postgresql postgresql-server"
        return 1
    fi
}

# Check if we're in the right directory
check_project_directory() {
    if [[ ! -f "mcp_server/main.py" || ! -f "requirements.txt" ]]; then
        print_error "This doesn't appear to be the Learning Coach Platform directory"
        print_info "Make sure you're in the root directory of the cloned repository"
        return 1
    fi
    print_success "Project directory verified"
    return 0
}

# Create virtual environment
setup_virtual_environment() {
    print_step "Setting up Python virtual environment..."
    
    if [[ -d "$VENV_NAME" ]]; then
        print_warning "Virtual environment already exists"
        read -p "Do you want to recreate it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$VENV_NAME"
        else
            print_info "Using existing virtual environment"
            return 0
        fi
    fi
    
    python3 -m venv "$VENV_NAME"
    print_success "Virtual environment created"
    
    # Activate virtual environment
    source "$VENV_NAME/bin/activate"
    print_success "Virtual environment activated"
    
    # Upgrade pip
    pip install --upgrade pip setuptools wheel
    print_success "pip upgraded"
}

# Install dependencies
install_dependencies() {
    print_step "Installing Python dependencies..."
    
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
        print_success "Dependencies installed"
    else
        print_error "requirements.txt not found"
        return 1
    fi
}

# Setup environment variables
setup_environment() {
    print_step "Setting up environment variables..."
    
    if [[ -f ".env" ]]; then
        print_warning ".env file already exists"
        read -p "Do you want to overwrite it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Keeping existing .env file"
            return 0
        fi
    fi
    
    # Generate secure JWT secret
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    
    # Create .env file
    cat > .env << EOF
# Database Configuration
DATABASE_URL=postgresql://$DB_USER@$DB_HOST:$DB_PORT/$DB_NAME
DB_HOST=$DB_HOST
DB_PORT=$DB_PORT
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=

# JWT Authentication
JWT_SECRET_KEY=$JWT_SECRET
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# AI Services
OPENAI_API_KEY=your_openai_api_key_here

# CORS Origins (comma-separated)
CORS_ORIGINS=http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000

# Environment
ENVIRONMENT=development

# Logging
LOG_LEVEL=INFO

# Rate Limiting
LOGIN_RATE_LIMIT_ATTEMPTS=5
LOGIN_RATE_LIMIT_WINDOW_MINUTES=15
REGISTRATION_RATE_LIMIT_ATTEMPTS=3
REGISTRATION_RATE_LIMIT_WINDOW_MINUTES=60

# Frontend URL
FRONTEND_URL=http://localhost:3000
EOF
    
    print_success ".env file created with secure JWT secret"
    print_warning "Don't forget to add your OpenAI API key to .env"
}

# Setup database
setup_database() {
    print_step "Setting up database..."
    
    # Check if database exists
    if psql -h $DB_HOST -p $DB_PORT -U $DB_USER -lqt | cut -d \| -f 1 | grep -qw $DB_NAME; then
        print_warning "Database '$DB_NAME' already exists"
        read -p "Do you want to recreate it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            dropdb -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME
            print_info "Dropped existing database"
        else
            print_info "Using existing database"
            # Still run schema to ensure it's up to date
            psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f db/schema.sql >/dev/null 2>&1 || true
            print_success "Database schema updated"
            return 0
        fi
    fi
    
    # Create database
    createdb -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME
    print_success "Database '$DB_NAME' created"
    
    # Run schema
    if [[ -f "db/schema.sql" ]]; then
        psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f db/schema.sql
        print_success "Database schema applied"
    else
        print_error "db/schema.sql not found"
        return 1
    fi
    
    # Verify database setup
    local table_count=$(psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ')
    
    if [[ "$table_count" -gt 0 ]]; then
        print_success "Database setup verified ($table_count tables created)"
    else
        print_error "Database setup verification failed"
        return 1
    fi
}

# Test the setup
test_setup() {
    print_step "Testing setup..."
    
    # Test database connection
    python3 -c "
import asyncio
import sys
import os
sys.path.append('.')

async def test_db():
    try:
        from db.postgres_client import get_db_pool
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchval('SELECT 1')
            if result == 1:
                print('✅ Database connection test passed')
                return True
            else:
                print('❌ Database connection test failed')
                return False
        await pool.close()
    except Exception as e:
        print(f'❌ Database connection test failed: {e}')
        return False

result = asyncio.run(test_db())
sys.exit(0 if result else 1)
" || {
        print_error "Database connection test failed"
        return 1
    }
    
    # Test authentication utilities
    python3 -c "
import sys
sys.path.append('.')

try:
    from auth.auth_utils import AuthUtils, validate_auth_config
    
    # Test password hashing
    test_password = 'TestPassword123!'
    hashed = AuthUtils.hash_password(test_password)
    verified = AuthUtils.verify_password(test_password, hashed)
    
    if verified:
        print('✅ Password hashing test passed')
    else:
        print('❌ Password hashing test failed')
        sys.exit(1)
    
    # Test JWT tokens
    token = AuthUtils.create_access_token({'sub': 'test-user'})
    payload = AuthUtils.verify_token(token)
    
    if payload and payload.get('sub') == 'test-user':
        print('✅ JWT token test passed')
    else:
        print('❌ JWT token test failed')
        sys.exit(1)
    
    # Check configuration
    issues = validate_auth_config()
    if issues:
        print('⚠️  Configuration issues found:')
        for issue in issues:
            print(f'    - {issue}')
    else:
        print('✅ Authentication configuration test passed')
    
except Exception as e:
    print(f'❌ Authentication test failed: {e}')
    sys.exit(1)
" || {
        print_error "Authentication test failed"
        return 1
    }
    
    print_success "All tests passed!"
}

# Create test user
create_test_user() {
    print_step "Creating test user..."
    
    read -p "Do you want to create a test user? (Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        print_info "Skipping test user creation"
        return 0
    fi
    
    # Default test user credentials
    TEST_EMAIL="test@learningcoach.com"
    TEST_PASSWORD="TestPassword123!"
    TEST_NAME="Test User"
    
    echo -e "${CYAN}Creating test user with credentials:${NC}"
    echo -e "  Email: ${WHITE}$TEST_EMAIL${NC}"
    echo -e "  Password: ${WHITE}$TEST_PASSWORD${NC}"
    echo -e "  Name: ${WHITE}$TEST_NAME${NC}"
    echo
    
    python3 -c "
import asyncio
import sys
sys.path.append('.')

async def create_test_user():
    try:
        from auth.auth_repository import AuthRepository
        from db.postgres_client import get_db_pool
        
        pool = await get_db_pool()
        auth_repo = AuthRepository(pool)
        
        # Check if user already exists
        existing = await auth_repo.get_user_by_email('$TEST_EMAIL')
        if existing:
            print('⚠️  Test user already exists')
            await pool.close()
            return True
        
        # Create test user
        user_id = await auth_repo.create_user_with_password(
            email='$TEST_EMAIL',
            password='$TEST_PASSWORD',
            user_name='$TEST_NAME'
        )
        
        # Verify email automatically for test user
        await auth_repo.verify_email(user_id)
        
        print(f'✅ Test user created successfully')
        print(f'   User ID: {user_id}')
        
        await pool.close()
        return True
    except Exception as e:
        print(f'❌ Failed to create test user: {e}')
        return False

result = asyncio.run(create_test_user())
sys.exit(0 if result else 1)
" || {
        print_error "Test user creation failed"
        return 1
    }
}

# Create useful scripts
create_scripts() {
    print_step "Creating utility scripts..."
    
    # Create run script
    cat > run_server.sh << 'EOF'
#!/bin/bash
# Start the Learning Coach Platform server

echo "🚀 Starting Learning Coach Platform server..."

# Activate virtual environment if it exists
if [[ -d "venv" ]]; then
    source venv/bin/activate
    echo "✅ Virtual environment activated"
fi

# Check if .env exists
if [[ ! -f ".env" ]]; then
    echo "❌ .env file not found. Please run setup.sh first."
    exit 1
fi

# Start server
echo "🌐 Server starting at http://localhost:8000"
echo "📖 API docs available at http://localhost:8000/docs"
echo "❓ Health check at http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop the server"

uvicorn mcp_server.main:app --reload --host 0.0.0.0 --port 8000
EOF
    
    chmod +x run_server.sh
    print_success "Created run_server.sh"
    
    # Create test script
    cat > run_tests.sh << 'EOF'
#!/bin/bash
# Run tests for Learning Coach Platform

echo "🧪 Running Learning Coach Platform tests..."

# Activate virtual environment if it exists
if [[ -d "venv" ]]; then
    source venv/bin/activate
fi

# Check if server is running
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo "⚠️  Server is not running. Please start it first:"
    echo "    ./run_server.sh"
    echo ""
    echo "Running offline tests only..."
    python -m pytest tests/ -v -k "not (api or endpoint)"
else
    echo "✅ Server detected, running all tests..."
    
    # Run end-to-end tests
    echo "🔄 Running end-to-end API tests..."
    python tests/test_end_to_end.py
    
    # Run individual endpoint tests
    echo "🔄 Running individual endpoint tests..."
    python tests/test_individual_endpoints.py
fi

echo "🏁 Tests completed!"
EOF
    
    chmod +x run_tests.sh
    print_success "Created run_tests.sh"
    
    # Create development helper script
    cat > dev_tools.sh << 'EOF'
#!/bin/bash
# Development tools for Learning Coach Platform

case "$1" in
    "format")
        echo "🎨 Formatting code..."
        black .
        isort .
        echo "✅ Code formatted"
        ;;
    "lint")
        echo "🔍 Linting code..."
        flake8 .
        ;;
    "type-check")
        echo "🔍 Type checking..."
        mypy .
        ;;
    "security")
        echo "🔒 Security check..."
        bandit -r . -f json
        ;;
    "deps")
        echo "📦 Checking dependencies..."
        pip list --outdated
        ;;
    "backup-db")
        echo "💾 Backing up database..."
        pg_dump learning_coach_db > "backup_$(date +%Y%m%d_%H%M%S).sql"
        echo "✅ Database backed up"
        ;;
    *)
        echo "🛠️  Learning Coach Development Tools"
        echo ""
        echo "Usage: $0 {format|lint|type-check|security|deps|backup-db}"
        echo ""
        echo "Commands:"
        echo "  format      - Format code with black and isort"
        echo "  lint        - Lint code with flake8"
        echo "  type-check  - Type check with mypy"
        echo "  security    - Security scan with bandit"
        echo "  deps        - Check outdated dependencies"
        echo "  backup-db   - Backup database"
        ;;
esac
EOF
    
    chmod +x dev_tools.sh
    print_success "Created dev_tools.sh"
}

# Print next steps
print_next_steps() {
    print_header "🎉 SETUP COMPLETED SUCCESSFULLY!"
    
    echo -e "${GREEN}Your Learning Coach Platform is ready to go!${NC}\n"
    
    echo -e "${CYAN}📋 NEXT STEPS:${NC}"
    echo -e "${WHITE}1. Add your OpenAI API key:${NC}"
    echo -e "   Edit .env file and add: OPENAI_API_KEY=your_actual_api_key"
    echo ""
    
    echo -e "${WHITE}2. Start the server:${NC}"
    echo -e "   ${YELLOW}./run_server.sh${NC}"
    echo ""
    
    echo -e "${WHITE}3. Test the API:${NC}"
    echo -e "   ${YELLOW}./run_tests.sh${NC}"
    echo ""
    
    echo -e "${WHITE}4. Access the application:${NC}"
    echo -e "   • API Server: ${BLUE}http://localhost:8000${NC}"
    echo -e "   • API Docs: ${BLUE}http://localhost:8000/docs${NC}"
    echo -e "   • Health Check: ${BLUE}http://localhost:8000/health${NC}"
    echo ""
    
    echo -e "${WHITE}5. Test with curl:${NC}"
    echo -e "   ${YELLOW}curl http://localhost:8000/health${NC}"
    echo ""
    
    if [[ -f ".env" ]] && grep -q "your_openai_api_key_here" .env; then
        echo -e "${YELLOW}⚠️  IMPORTANT: Don't forget to add your OpenAI API key to .env${NC}"
        echo ""
    fi
    
    echo -e "${CYAN}🛠️  DEVELOPMENT TOOLS:${NC}"
    echo -e "   • Format code: ${YELLOW}./dev_tools.sh format${NC}"
    echo -e "   • Run tests: ${YELLOW}./run_tests.sh${NC}"
    echo -e "   • Development help: ${YELLOW}./dev_tools.sh${NC}"
    echo ""
    
    echo -e "${CYAN}📚 LEARN MORE:${NC}"
    echo -e "   • Read README.md for detailed documentation"
    echo -e "   • Check security_guide.md for production deployment"
    echo -e "   • Explore the API at http://localhost:8000/docs"
    echo ""
    
    echo -e "${GREEN}Happy coding! 🚀${NC}"
}

# Main execution
main() {
    print_header "🎓 Learning Coach Platform Setup"
    
    print_info "This script will set up your development environment"
    print_info "Make sure you have Python 3.10+ and PostgreSQL installed"
    echo ""
    
    # Check prerequisites
    print_step "Checking prerequisites..."
    check_project_directory || exit 1
    check_python_version || exit 1
    check_postgresql || exit 1
    
    print_success "All prerequisites met!"
    
    # Setup steps
    setup_virtual_environment || exit 1
    install_dependencies || exit 1
    setup_environment || exit 1
    setup_database || exit 1
    test_setup || exit 1
    create_test_user || exit 1
    create_scripts || exit 1
    
    # Success!
    print_next_steps
}

# Handle script interruption
trap 'echo -e "\n${RED}Setup interrupted by user${NC}"; exit 1' INT

# Handle errors
trap 'echo -e "\n${RED}Setup failed on line $LINENO${NC}"; exit 1' ERR

# Check if running as source (should be executed directly)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
else
    echo -e "${RED}This script should be executed directly, not sourced${NC}"
    echo -e "Run: ${YELLOW}bash setup.sh${NC}"
fi