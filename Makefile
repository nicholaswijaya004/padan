.PHONY: check lint typecheck test fmt fetch scaffold baselines score rules

check: lint typecheck test

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy

test:
	uv run pytest

fmt:
	uv run ruff format .
	uv run ruff check --fix .

fetch:
	uv run python -m padan.fetch

scaffold:
	uv run python -m padan.extract $(SPEC)

baselines:
	uv run python -m padan.baselines data/predictions

score:
	uv run python -m padan.report $(PRED)

rules:
	uv run python -m padan.engine data/predictions
