.PHONY: check lint typecheck test fmt fetch scaffold baselines score rules hybrid sheet labels freeze verify test-baselines test-rules test-hybrid test-score sheet-fix labels-fix freeze-fix verify-fix test-score-fix

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

sheet:
	uv run python -m padan.sheet new $(SPEC)

labels:
	uv run python -m padan.sheet fill $(SPEC)

freeze:
	uv run python -m padan.sheet freeze

verify:
	uv run python -m padan.sheet verify

baselines:
	uv run python -m padan.baselines data/predictions

score:
	uv run python -m padan.report $(PRED)

rules:
	uv run python -m padan.engine data/predictions

hybrid:
	uv run --env-file .env python -m padan.hybrid data/predictions $(MODEL) $(BASE) $(SPECS)

# Test set (Amendment 6): every target checks the freeze first and reads data/labels/test/.
test-baselines:
	uv run python -m padan.baselines data/predictions/test --test

test-rules:
	uv run python -m padan.engine data/predictions/test --test

test-hybrid:
	uv run --env-file .env python -m padan.hybrid data/predictions/test claude-opus-5-5 general --test

test-score:
	uv run python -m padan.report $(PRED) --test

# Slip fixes after the run (Amendment 6): a full copy of the test set in data/labels/test-corrected/,
# sealed on its own. The original stays sealed; report scores both.
sheet-fix:
	uv run python -m padan.sheet new $(SPEC) --corrected

labels-fix:
	uv run python -m padan.sheet fill $(SPEC) --corrected

freeze-fix:
	uv run python -m padan.sheet freeze --corrected

verify-fix:
	uv run python -m padan.sheet verify --corrected

test-score-fix:
	uv run python -m padan.report $(PRED) --test --corrected
