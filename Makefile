.PHONY: install test format lint api worker clean

install:
	pip install -e ".[all]"

test:
	python -m pytest tests/ -v

test-cov:
	python -m pytest tests/ --cov=. --cov-report=term-missing

format:
	ruff format .

lint:
	ruff check .

api:
	uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload

worker:
	python -m apps.worker.main

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov

docker-up:
	docker compose up -d

docker-down:
	docker compose down

db-migrate:
	alembic upgrade head

db-create:
	alembic revision --autogenerate -m "new migration"
