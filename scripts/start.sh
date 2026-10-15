#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv sync --frozen --extra dev
exec uv run --frozen servicepilot demo --port "${1:-8000}"
