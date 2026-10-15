.PHONY: install demo test lint format eval build check
install:
	uv sync --frozen --extra dev
demo:
	uv run servicepilot demo
test:
	uv run pytest --cov=servicepilot --cov-report=term-missing --cov-report=xml:reports/coverage.xml --cov-fail-under=80
lint:
	uv run ruff check .
	uv run ruff format --check .
format:
	uv run ruff check . --fix
	uv run ruff format .
eval:
	uv run servicepilot evaluate
build:
	uv run python -m build
check: lint test eval build
