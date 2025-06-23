#!/bin/bash

# Docker Utility Scripts for AI Learning Coach Platform
# This script provides convenient commands for Docker operations

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
    echo -e "\n${BLUE}=====================================${NC}"
    echo -e "${WHITE}$1${NC}"
    echo -e "${BLUE}=====================================${NC}\n"
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
    echo -e "${CYAN}💡 $1${NC}"
}

# Check if Docker is installed and running
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        print_error "Docker is not running"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed"
        exit 1
    fi
}

# Development commands
dev_build() {
    print_header "Building Development Environment"
    docker-compose build --no-cache
    print_success "Development build completed"
}

dev_up() {
    print_header "Starting Development Environment"
    docker-compose up -d
    print_success "Development environment started"
    print_info "API: http://localhost:8000"
    print_info "API Docs: http://localhost:8000/docs"
    print_info "Adminer: http://localhost:8080"
    print_info "Redis Commander: http://localhost:8081"
}

dev_up_with_logs() {
    print_header "Starting Development Environment (with logs)"
    docker-compose up
}

dev_down() {
    print_header "Stopping Development Environment"
    docker-compose down
    print_success "Development environment stopped"
}

dev_restart() {
    print_header "Restarting Development Environment"
    docker-compose restart
    print_success "Development environment restarted"
}

dev_logs() {
    print_header "Development Logs"
    docker-compose logs -f --tail=100
}

dev_shell() {
    print_header "Opening Shell in Web Container"
    docker-compose exec web bash
}

# Production commands
prod_build() {
    print_header "Building Production Environment"
    docker-compose -f docker-compose.prod.yml build --no-cache
    print_success "Production build completed"
}

prod_up() {
    print_header "Starting Production Environment"
    docker-compose -f docker-compose.prod.yml up -d
    print_success "Production environment started"
    print_info "Application will be available on configured ports"
}

prod_down() {
    print_header "Stopping Production Environment"
    docker-compose -f docker-compose.prod.yml down
    print_success "Production environment stopped"
}

prod_logs() {
    print_header "Production Logs"
    docker-compose -f docker-compose.prod.yml logs -f --tail=100
}

prod_scale() {
    local replicas=${1:-2}
    print_header "Scaling Production Web Service to $replicas replicas"
    docker-compose -f docker-compose.prod.yml up -d --scale web=$replicas
    print_success "Scaled to $replicas replicas"
}

# Database commands
db_backup() {
    print_header "Creating Database Backup"
    local backup_file="backup_$(date +%Y%m%d_%H%M%S).sql"
    docker-compose exec db pg_dump -U postgres learning_coach_db > "$backup_file"
    print_success "Database backup created: $backup_file"
}

db_restore() {
    local backup_file=$1
    if [ -z "$backup_file" ]; then
        print_error "Please provide backup file path"
        echo "Usage: $0 db-restore <backup_file>"
        exit 1
    fi
    
    print_header "Restoring Database from $backup_file"
    docker-compose exec -T db psql -U postgres learning_coach_db < "$backup_file"
    print_success "Database restored from $backup_file"
}

db_reset() {
    print_header "Resetting Database"
    print_warning "This will delete all data!"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker-compose exec db psql -U postgres -c "DROP DATABASE IF EXISTS learning_coach_db;"
        docker-compose exec db psql -U postgres -c "CREATE DATABASE learning_coach_db;"
        docker-compose exec db psql -U postgres learning_coach_db -f /docker-entrypoint-initdb.d/01-schema.sql
        print_success "Database reset completed"
    else
        print_info "Database reset cancelled"
    fi
}

db_shell() {
    print_header "Opening Database Shell"
    docker-compose exec db psql -U postgres learning_coach_db
}

# Maintenance commands
cleanup() {
    print_header "Cleaning Up Docker Resources"
    docker system prune -f
    docker volume prune -f
    docker network prune -f
    print_success "Cleanup completed"
}

status() {
    print_header "Docker Containers Status"
    docker-compose ps
    echo
    print_header "Docker Images"
    docker images | grep learning_coach
    echo
    print_header "Docker Volumes"
    docker volume ls | grep learning_coach
}

health_check() {
    print_header "Health Check"
    
    # Check if containers are running
    if docker-compose ps | grep -q "Up"; then
        print_success "Containers are running"
    else
        print_error "Some containers are not running"
        docker-compose ps
        return 1
    fi
    
    # Check API health
    if curl -f http://localhost:8000/health &> /dev/null; then
        print_success "API is healthy"
    else
        print_error "API health check failed"
        return 1
    fi
    
    # Check database connection
    if docker-compose exec -T db pg_isready -U postgres &> /dev/null; then
        print_success "Database is ready"
    else
        print_error "Database is not ready"
        return 1
    fi
    
    print_success "All health checks passed"
}

# Update commands
update() {
    print_header "Updating Application"
    git pull origin main
    docker-compose build --no-cache
    docker-compose up -d
    print_success "Application updated"
}

# Show usage
usage() {
    echo -e "${WHITE}AI Learning Coach Platform - Docker Utility Scripts${NC}"
    echo
    echo -e "${CYAN}Development Commands:${NC}"
    echo "  dev-build         Build development environment"
    echo "  dev-up            Start development environment (detached)"
    echo "  dev-up-logs       Start development environment (with logs)"
    echo "  dev-down          Stop development environment"
    echo "  dev-restart       Restart development environment"
    echo "  dev-logs          Show development logs"
    echo "  dev-shell         Open shell in web container"
    echo
    echo -e "${CYAN}Production Commands:${NC}"
    echo "  prod-build        Build production environment"
    echo "  prod-up           Start production environment"
    echo "  prod-down         Stop production environment"
    echo "  prod-logs         Show production logs"
    echo "  prod-scale [N]    Scale web service to N replicas (default: 2)"
    echo
    echo -e "${CYAN}Database Commands:${NC}"
    echo "  db-backup         Create database backup"
    echo "  db-restore <file> Restore database from backup"
    echo "  db-reset          Reset database (WARNING: deletes all data)"
    echo "  db-shell          Open database shell"
    echo
    echo -e "${CYAN}Maintenance Commands:${NC}"
    echo "  cleanup           Clean up Docker resources"
    echo "  status            Show containers, images, and volumes status"
    echo "  health-check      Perform health checks"
    echo "  update            Update application from git and rebuild"
    echo
    echo -e "${CYAN}Examples:${NC}"
    echo "  $0 dev-up         # Start development environment"
    echo "  $0 prod-scale 3   # Scale production to 3 replicas"
    echo "  $0 db-backup      # Create database backup"
    echo "  $0 health-check   # Check system health"
}

# Main script logic
main() {
    check_docker
    
    case "$1" in
        dev-build)
            dev_build
            ;;
        dev-up)
            dev_up
            ;;
        dev-up-logs)
            dev_up_with_logs
            ;;
        dev-down)
            dev_down
            ;;
        dev-restart)
            dev_restart
            ;;
        dev-logs)
            dev_logs
            ;;
        dev-shell)
            dev_shell
            ;;
        prod-build)
            prod_build
            ;;
        prod-up)
            prod_up
            ;;
        prod-down)
            prod_down
            ;;
        prod-logs)
            prod_logs
            ;;
        prod-scale)
            prod_scale "$2"
            ;;
        db-backup)
            db_backup
            ;;
        db-restore)
            db_restore "$2"
            ;;
        db-reset)
            db_reset
            ;;
        db-shell)
            db_shell
            ;;
        cleanup)
            cleanup
            ;;
        status)
            status
            ;;
        health-check)
            health_check
            ;;
        update)
            update
            ;;
        *)
            usage
            ;;
    esac
}

# Run main function with all arguments
main "$@" 