.PHONY: help dev build up down logs migrate frontend-install lint test clean

help:
	@echo "AI Agent Platform - Available Commands"
	@echo ""
	@echo "  make dev          - Start development environment"
	@echo "  make build        - Build all Docker images"
	@echo "  make up           - Start all services"
	@echo "  make down         - Stop all services"
	@echo "  make logs         - View logs"
	@echo "  make migrate      - Run DB migrations"
	@echo "  make frontend-install - Install frontend dependencies"
	@echo "  make lint         - Run linters"
	@echo "  make test         - Run tests"
	@echo "  make clean        - Clean up containers and volumes"

dev:
	docker compose up -d postgres redis
	@echo "Starting backend..."
	cd backend && uv run uvicorn app.main:app --reload --port 8500 &
	@echo "Starting frontend..."
	cd frontend && npm run dev

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	cd backend && uv run alembic upgrade head

frontend-install:
	cd frontend && npm install

lint:
	cd backend && uv run ruff check .
	cd frontend && npm run lint

test:
	cd backend && uv run pytest tests/ -v

sandbox-build:
	docker build -t ai-agent-sandbox:latest ./sandbox-image/

clean:
	docker compose down -v --remove-orphans
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
