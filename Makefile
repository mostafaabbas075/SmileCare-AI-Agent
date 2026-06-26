# =============================================================================
# AI Dental Clinic Receptionist — Makefile
# =============================================================================
# Usage: make <target>
# Run `make help` to see all available commands.
# =============================================================================

.PHONY: help up down restart logs shell-backend shell-db \
        migrate migrate-create migrate-history migrate-downgrade \
        lint format typecheck test \
        install dev-install clean

# Colours
RESET  := \033[0m
BOLD   := \033[1m
GREEN  := \033[32m
YELLOW := \033[33m
CYAN   := \033[36m

help: ## Show this help message
	@echo ""
	@echo "$(BOLD)AI Dental Clinic Receptionist$(RESET)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "$(CYAN)%-25s$(RESET) %s\n", "Target", "Description"} \
	      /^[a-zA-Z_-]+:.*?##/ { printf "$(GREEN)%-25s$(RESET) %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo ""

# =============================================================================
# Docker
# =============================================================================

up: ## Start all Docker services
	docker compose up -d

up-infra: ## Start only DB + Qdrant (no backend)
	docker compose up -d db qdrant

down: ## Stop all Docker services
	docker compose down

restart: down up ## Restart all services

logs: ## Stream backend logs
	docker compose logs -f backend

logs-db: ## Stream database logs
	docker compose logs -f db

shell-backend: ## Open a shell inside the backend container
	docker compose exec backend bash

shell-db: ## Open a psql shell
	docker compose exec db psql -U $${POSTGRES_USER:-dental_user} -d $${POSTGRES_DB:-dental_receptionist}

# =============================================================================
# Migrations (Alembic)
# =============================================================================

migrate: ## Apply all pending migrations
	cd backend && alembic upgrade head

migrate-create: ## Create a new migration — usage: make migrate-create MSG="add column"
	cd backend && alembic revision --autogenerate -m "$(MSG)"

migrate-history: ## Show migration history
	cd backend && alembic history --verbose

migrate-downgrade: ## Downgrade one step
	cd backend && alembic downgrade -1

# =============================================================================
# Code Quality
# =============================================================================

lint: ## Run ruff linter
	cd backend && ruff check app/

format: ## Format code with ruff
	cd backend && ruff format app/

typecheck: ## Run mypy type checker
	cd backend && mypy app/

check: lint typecheck ## Run all checks

# =============================================================================
# Testing
# =============================================================================

test: ## Run test suite
	cd backend && pytest tests/ -v --tb=short

test-cov: ## Run tests with coverage
	cd backend && pytest tests/ -v --tb=short --cov=app --cov-report=html

# =============================================================================
# Local Development
# =============================================================================

install: ## Install Python dependencies
	cd backend && pip install -r requirements.txt

dev-install: ## Install with dev dependencies
	cd backend && pip install -r requirements.txt -r requirements-dev.txt

dev: ## Run backend locally (outside Docker)
	cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# =============================================================================
# Housekeeping
# =============================================================================

clean: ## Remove Python cache files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
