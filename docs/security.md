# Security model

User text, model output and retrieved content are untrusted. The host application's authenticated identity layer supplies `Principal`.

| Threat | Control | Limit |
|---|---|---|
| Other user's runs | Owner checks, 404 for foreign runs | Static-token authentication |
| Unauthorized retrieval | Separate authorized FAISS index | Trusted local ingestion corpus |
| Unauthorized tool calls | Allowlisted IDs and per-call scope checks | No enterprise IAM integration |
| Prompt-driven writes | No write tool; server approval ledger | Text answers may remain misleading |
| Approval replay | Unique proposal-to-ticket relationship | One app instance |
| Proposal tampering | Exact payload, digest, owner and expiry | Host/database administrators trusted |
| Document injection | Untrusted-data prompt plus independent permissions | Prompting is not a complete defense |
| SQL/path injection | Parameterized SQL and rooted file loading | No arbitrary uploads |
| Sensitive traces | Minimized requests/outputs, no public argument trace | Not comprehensive DLP; checkpoints retain evidence |
| Unbounded execution | Tool budget, graph limit, provider timeouts | No global spend budget |
| Content abuse | Transparent input/output policy | Small regex baseline |
| Browser injection | `textContent`, restrictive workspace CSP | Swagger documentation uses its own assets |

## Human approval

Neither model output nor the interrupt resume payload grants approval. Only the authenticated decision endpoint or trusted SDK host can update the ledger. Draft editing is unsupported: a new request creates a new proposal. The server validates current permission again at execution.

## Deployment boundary

Demo mode intentionally exposes its public fixture identities. CLI and Compose bind the public app port to loopback. Do not expose demo mode to a shared network.

Production configuration requires explicit non-demo tokens of at least 32 characters and hides fixture credentials. Generate random tokens, for example with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. The app cannot verify token entropy.

The production flag is **not a production-readiness certification**. Real deployments need HTTPS/SSO, centralized authorization, retention rules, encrypted disks, monitoring and infrastructure limits. Enforce streaming request-body limits at a reverse proxy: the application's content-length check alone is not comprehensive. The rate limiter is process-local and IP-based, not a distributed quota.

## Retention

Secrets, runtime databases, reports and caches are gitignored. SQLite is not encrypted by the app. Checkpoints can contain authorized source evidence and model messages. Define a retention and backup policy before using real data. Stop the app before moving/deleting its state.

External LLM mode sends evidence to the selected provider. Use synthetic data unless a suitable data-handling arrangement is established. Full provider exception bodies are not returned to API callers.

## Vulnerability reports

Use GitHub private vulnerability reporting if enabled. Do not include keys or private data in public issues; provide a sanitized reproduction with fictional fixtures.

References: [OWASP excessive agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/), [prompt injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/).
