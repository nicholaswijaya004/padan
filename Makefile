.PHONY: check lint typecheck test fmt fetch

check: lint typecheck test

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy

test:
	uv run pytest

fmt:
	uv run ruff check --fix .
	uv run ruff format .

fetch:
	uv run python -m padan.fetch