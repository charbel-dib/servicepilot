# Validation snapshot

Validated on 2026-10-15 using Python 3.12.14 on Linux.

| Check | Result |
|---|---|
| Python tests | 56 passed |
| Measured statement coverage | 97.60% (CLI entrypoint excluded by configuration) |
| Deterministic behavior scenarios | 14 / 14 passed |
| Ruff lint and formatting | Passed |
| Browser JavaScript syntax | Passed |
| Browser smoke | Diagnosis, approval, identity isolation and mobile overflow check passed |
| UI inspection | Desktop and mobile layouts visually reviewed |
| Java fixture | Compiled to Java 17 bytecode with Eclipse compiler; executed on Java 25 |
| Java HTTP contract | 5 checks passed |
| Runtime dependency audit | 61 dependencies audited; no known vulnerabilities reported |
| Python distributions | Wheel and source distribution built |
| Isolated wheel installation | Installed from the hashed runtime lock; bundled UI, prompts, corpus and evaluations checked |
| Workflow / Compose YAML | Parsed successfully |

The browser check used Chrome Headless Shell 131 through `SERVICEPILOT_BROWSER_EXECUTABLE` in this environment. Normally the script uses the Chromium version installed by Playwright. The browser checks exercised actual local HTTP servers.

OpenAI adapter and judge contracts were checked with fake models; **no real provider calls were made**. The optional sentence-transformer backend was not downloaded or benchmarked.

Docker was unavailable in the authoring environment. Dockerfiles and Compose are included with an integrated CI smoke job, but no local Docker build is claimed. GitHub workflows, their Python version matrix, Java 17 runtime job, release publication and GHCR pushes can only be verified after pushing and running Actions.

This snapshot records executed checks, not general security, production readiness or live LLM accuracy. Re-run the documented commands after changing code, dependencies or prompts.
