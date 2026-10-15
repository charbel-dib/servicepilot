# Operations and GitHub delivery

## Configuration

All variables use the `SERVICEPILOT_` prefix. `.env` is optional and gitignored.

| Setting | Default | Meaning |
|---|---|---|
| ENVIRONMENT | demo | Demo fixtures or explicit production identities |
| PROVIDER | offline | Deterministic policy or openai |
| MODEL | gpt-4.1-mini | Tool/schema-capable provider model |
| API_KEY | unset | Secret provider credential |
| DATA_DIR | .servicepilot | SQLite and checkpoint directory |
| PROCEDURES_DIR | bundled procedures | Custom Markdown corpus |
| STATUS_URL | http://127.0.0.1:8001 | Read-only status service |
| STATUS_TIMEOUT | 3 | HTTP timeout in seconds |
| MAX_TOOL_CALLS | 6 | Per-run read-tool budget |
| APPROVAL_TTL_SECONDS | 900 | Proposal validity |
| IDENTITIES_JSON | fixture identities | Token-to-identity mapping |
| EMBEDDING_BACKEND | hashing | hashing or sentence-transformers |
| EMBEDDING_MODEL | multilingual MiniLM | Optional semantic model |

## GitHub first push

Create an empty GitHub repository, then from the extracted directory:

```bash
git init -b main
git add .
git commit -m "Initial ServicePilot implementation"
git remote add origin https://github.com/YOUR-USER/servicepilot.git
git push -u origin main
```

Replace `YOUR-USER` with your account. No GitHub token is bundled. Review `.env` and ignored files before adding anything.

Under GitHub Actions, allow the repository workflows to run. Branch protection is a repository setting: require the CI jobs and review before merging. Workflows are provided, not pre-executed on GitHub.

## CI

- Python matrix 3.11/3.12/3.13, frozen uv environment, Ruff, pytest and 80% minimum coverage.
- Offline evaluations and Python wheel/source distribution.
- Chromium UI smoke with desktop/mobile screenshots as artifacts.
- Java 17 compilation and public HTTP contract.
- Dependency vulnerability audit against the runtime lock.
- Compose build and integrated HTTP diagnosis.

Default workflows make no paid model calls and require no model secrets. The semantic optional extra is not installed in CI.

## Release/CD

```bash
git tag v0.1.0
git push origin v0.1.0
```

After checks pass, the release workflow creates a GitHub Release containing the wheel, source distribution and source ZIP. A separate job pushes the app image to `ghcr.io/<owner>/<repository>` using the repository's `GITHUB_TOKEN`, with provenance and SBOM enabled. Repository policy must allow package publication.

The manual release workflow builds downloadable artifacts without publishing a versioned release or image. Update `pyproject.toml`, API/UI version labels and release notes before a new version.

This CD covers **delivery**, not automatic deployment to an unspecified host. No SSH keys, cloud credentials or server endpoints are invented. The Java fixture image is built locally by Compose; only the app image is published to GHCR.

## Dependency updates

`uv.lock` covers Python environments and optional extras. `requirements.lock` is the hashed runtime export used by Docker and audit.

```bash
uv lock --upgrade
uv export --frozen --no-dev --no-emit-project --format requirements-txt --output-file requirements.lock
uv sync --frozen --extra dev
```

Run checks and commit both lockfiles together. Dependabot updates uv dependencies and action/image references; re-export `requirements.lock` when merging a Python dependency update. Actions use version tags; stricter environments can pin reviewed commit SHAs.

## Java standalone

Requires JDK 17 or newer:

```bash
mkdir -p status-service/out
javac --release 17 -d status-service/out status-service/src/StatusServer.java
java --add-modules jdk.httpserver -cp status-service/out StatusServer
```

In another terminal run `python scripts/status_contract.py` and `uv run servicepilot serve`. On Windows, create the output directory using PowerShell `New-Item -ItemType Directory -Force status-service/out`.

## Troubleshooting

- **Port 8000 in use:** `uv run servicepilot demo --port 8010`.
- **Status unavailable:** `demo` starts its own fixture. `serve` requires a separate status API and matching STATUS_URL.
- **401:** check the bearer token; demo tokens are only local convenience identities.
- **409:** proposal expired, changed or previously decided. Submit a new request if expired.
- **Execution error in real LLM mode:** verify model access, key and model support for tools/structured outputs. Provider details are deliberately not exposed to callers.
- **Semantic model cannot download:** use default hashing mode or pre-provision the model cache.
- **PowerShell execution restrictions:** use the three Quickstart commands directly instead of changing machine-wide policy.
- **Browser dependency errors on Linux:** `uv run playwright install --with-deps chromium`.

Stop the app before backing up both SQLite files. Deleting `.servicepilot` resets local demo state. `docker compose down -v` deletes the Compose data volume; ordinary `down` keeps it.
