.PHONY: test test-domain test-services lint format check dev frontend-dev

test:
	pytest tests/ -v

test-domain:
	pytest tests/domain/ -v

test-services:
	pytest tests/services/ -v

lint:
	ruff check .

format:
	ruff format .

check:
	ruff check . && ruff format --check .

dev:
	uvicorn api.main:app --reload --port 8000

frontend-dev:
	cd frontend && npm run dev
