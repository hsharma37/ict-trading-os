# ICT Trading OS — Development Makefile
.PHONY: help up down restart logs psql migrate test format lint install

# ────────────────────────────────────────────────
# Docker Compose
# ────────────────────────────────────────────────
up: ## Start all services (detached)
	docker compose up -d

up-build: ## Build and start all services
	docker compose up --build -d

down: ## Stop all services
	docker compose down

down-volumes: ## Stop all services and remove volumes (WARNING: destroys data)
	docker compose down -v

restart: down up ## Restart all services

logs: ## Tail logs for all services
	docker compose logs -f

logs-backend: ## Tail backend logs only
	docker compose logs -f backend

logs-celery: ## Tail celery worker logs only
	docker compose logs -f celery-worker

# ────────────────────────────────────────────────
# Database
# ────────────────────────────────────────────────
psql: ## Open PostgreSQL CLI
	docker compose exec -it postgres psql -U ictos -d ictos

migrate: ## Run Alembic database migrations
	docker compose exec backend alembic upgrade head

migrate-make: ## Create a new Alembic migration (auto-detect changes)
	docker compose exec backend alembic revision --autogenerate -m "$(m)"

init-db: ## Initialize database (create tables via Alembic)
	docker compose exec backend alembic upgrade head
	docker compose exec backend python -m scripts.init_db

# ────────────────────────────────────────────────
# Backend (Python)
# ────────────────────────────────────────────────
test: ## Run Pytest backend tests
	docker compose exec backend pytest -v

test-cov: ## Run tests with coverage
	docker compose exec backend pytest -v --cov=app --cov-report=term-missing

format: ## Format Python code with black and isort
	docker compose exec backend black app/ scripts/
	docker compose exec backend isort app/ scripts/

lint: ## Lint Python code with ruff and mypy
	docker compose exec backend ruff check app/ scripts/
	docker compose exec backend mypy app/

backend-shell: ## Open Python shell in backend container
	docker compose exec backend python

# ────────────────────────────────────────────────
# Frontend (React/Vite)
# ────────────────────────────────────────────────
frontend-install: ## Install frontend dependencies
	docker compose exec frontend npm install

frontend-build: ## Build frontend for production
	docker compose exec frontend npm run build

frontend-lint: ## Lint frontend code
	docker compose exec frontend npm run lint

frontend-typecheck: ## Type-check frontend code
	docker compose exec frontend npm run typecheck

# ────────────────────────────────────────────────
# AI / Ollama
# ────────────────────────────────────────────────
ollama-pull: ## Pull default models into Ollama
	docker compose exec ollama ollama pull $(OLLAMA_MODEL)
	docker compose exec ollama ollama pull $(EMBEDDING_MODEL)

ollama-list: ## List installed Ollama models
	docker compose exec ollama ollama list

# ────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────
status: ## Show running container status
	docker compose ps

health: ## Check health of all services
	@echo "PostgreSQL:"
	@docker compose exec postgres pg_isready -U ictos || echo "  ❌ Not ready"
	@echo "Redis:"
	@docker compose exec redis redis-cli ping || echo "  ❌ Not ready"
	@echo "Backend:"
	@curl -s http://localhost:8000/health || echo "  ❌ Not ready"

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
