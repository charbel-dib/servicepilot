# Contributing

Use Python 3.12 and `uv sync --frozen --extra dev`. Before submitting a change run Ruff, pytest, offline evaluation and the browser smoke script described in README.

Include a small scenario or test when changing an authorization boundary, tool contract or persistence behavior. Keep fixture data fictional. Document changes to prompts and rerun relevant evaluations. Update both lockfiles for dependency changes.

Describe the user-visible change and how it was verified. Do not commit runtime state, provider keys or generated local reports.
