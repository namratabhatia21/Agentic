.PHONY: install dev test lint fmt up down logs monitoring

install:
	pip install -e ".[dev]"

dev:  ## run the API locally against compose's postgres+redis
	docker compose up -d postgres redis
	uvicorn app.main:app --reload --port 8000

test:
	pytest -q

lint:
	ruff check . && ruff format --check .

fmt:
	ruff check --fix . && ruff format .

up:
	docker compose up -d --build

monitoring:
	docker compose --profile monitoring up -d --build

down:
	docker compose down

logs:
	docker compose logs -f api
