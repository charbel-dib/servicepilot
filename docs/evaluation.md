# Evaluation

The 14-scenario fixture suite checks required/forbidden tools, typed answer and run statuses, absence of unapproved writes and tool budget. Inputs are visible under `src/servicepilot/data/scenarios.json`.

```bash
uv run --frozen servicepilot evaluate --output reports/evaluation.json
```

The command exits nonzero on a deterministic behavior failure. JSON and HTML reports contain case-level checks, answers, tool outcomes and timings. These are local fixture timings, not general performance claims.

Tests separately cover user/scope boundaries, approval expiry/tampering, concurrent retries, persistence, HTTP failures, citation filtering and loops. Adapter tests use fakes. Browser smoke uses actual local HTTP. CI also exercises Java and Compose.

## Optional judge

```bash
uv run --frozen servicepilot evaluate --judge
```

This uses the configured API key to grade **offline outputs** for groundedness and usefulness, with an advisory 0–4 score. It does not switch the tested agent to live mode. Judge outputs never authorize actions or replace deterministic security checks. Record the model and rubric with results.

The judge receives the available evidence, including current status and historical incidents. A historical incident must not be mistaken for proof of the current cause.

Before claiming answer quality, annotate a sample manually and inspect disagreements with the judge. Keep unseen scenarios when iterating on prompts. The small visible fixture suite cannot support general robustness claims.

## Live behavior

Enable `SERVICEPILOT_PROVIDER=openai` and inspect UI runs and traces. These calls need your key and are not made by default workflows. Use synthetic data. The optional semantic backend and real provider need separate validation in your environment.
