install:
	pip install -e .

test:
	pytest tests/

format:
	ruff format .

lint:
	ruff check .
