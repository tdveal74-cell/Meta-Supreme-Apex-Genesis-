.PHONY: help install dev up down logs api web test lint clean

help:
	@echo "Meta Supreme Apex Genesis — common commands"
	@echo ""
	@echo "  make install   Install frontend + backend dependencies"
	@echo "  make up        Start full stack with Docker Compose"
	@echo "  make down      Stop Docker Compose stack"
	@echo "  make logs      Tail Docker Compose logs"
	@echo "  make api       Run API locally (requires venv + DB)"
	@echo "  make web       Run Next.js frontend"
	@echo "  make test      Run backend tests"
	@echo "  make lint      Lint frontend + backend"
	@echo "  make clean     Remove caches and build artifacts"

install:
	pnpm install
	cd apps/api && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

up:
	docker compose -f infrastructure/docker/docker-compose.yml up -d --build

down:
	docker compose -f infrastructure/docker/docker-compose.yml down

logs:
	docker compose -f infrastructure/docker/docker-compose.yml logs -f

api:
	cd apps/api && . .venv/bin/activate && PYTHONPATH=../..:$$PYTHONPATH uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

web:
	pnpm --filter @meta-supreme/web dev

test:
	cd apps/api && . .venv/bin/activate && pytest -q

lint:
	pnpm -r lint || true
	cd apps/api && . .venv/bin/activate && ruff check . || true

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".next" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf apps/api/.venv 2>/dev/null || true
