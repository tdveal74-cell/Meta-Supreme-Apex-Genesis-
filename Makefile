.PHONY: help install standalone test-offline up down logs api web test lint clean

help:
	@echo "Meta Supreme Apex Genesis"
	@echo ""
	@echo "  make standalone    Run flagship offline API (no DB)"
	@echo "  make test-offline  Billing + definition unit tests"
	@echo "  make install       Install full monorepo deps (needs layout)"
	@echo "  make up / down     Docker stack (needs monorepo)"
	@echo "  make test          Full pytest (needs monorepo + DB)"

standalone:
	uvicorn standalone_api:app --reload --host 0.0.0.0 --port 8000

test-offline:
	pytest test_billing.py test_definition.py -q

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
