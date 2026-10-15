# SDK and API

Create one `ServicePilot` instance per process. Use its context manager or close it on shutdown. Methods are synchronous; an async host should execute them in a worker thread.

```python
from servicepilot import Principal, ServicePilot

user = Principal(user_id="alice", services=frozenset({"atlas", "vpn"}))
with ServicePilot() as pilot:
    run = pilot.run("Crée un ticket Atlas pour une panne", user)
    if run.status == "approval_required":
        print(run.proposal.draft.model_dump_json(indent=2))
        # Wait for an actual authenticated human, never a model decision.
        if input("Approve? [y/N] ").lower() == "y":
            run = pilot.decide(
                run.run_id,
                user,
                proposal_id=run.proposal.id,
                digest=run.proposal.digest,
                approve=True,
            )
            print(run.ticket_id)
```

`Principal` belongs to the trusted host boundary, not to arbitrary client input. The API derives it from credentials. The model never receives a write tool.

## Routes

Interactive docs: `/docs`. Schema: `/openapi.json`.

| Method | Route | Meaning |
|---|---|---|
| GET | `/health` | Liveness |
| GET | `/ready` | SQLite readiness, not downstream availability |
| GET | `/api/config` | Public configuration; fixture tokens only in demo |
| GET | `/api/me` | Current authenticated identity |
| POST | `/api/runs` | One support task |
| GET | `/api/runs` | Last 50 authorized own runs |
| GET | `/api/runs/{id}` | Own run |
| POST | `/api/runs/{id}/decision` | Exact proposal approval/rejection |
| GET | `/api/tickets` | Own tickets within current service scope |

Protected routes require `Authorization: Bearer <token>`.

```bash
curl http://127.0.0.1:8000/api/runs \
  -H 'Authorization: Bearer demo-alice-token' \
  -H 'Content-Type: application/json' \
  -d '{"query":"Crée un ticket pour la panne Atlas"}'
```

Use returned IDs and digest in the decision body:

```json
{"proposal_id":"returned-id","digest":"returned-64-character-digest","approve":true}
```

Clients must inspect `RunResult.status`: execution failures can return HTTP 200 with `status=error`. Identity and proposal errors use 401/403/404/409; invalid input 422; body limits 413; throttling 429.

## Procedures and connectors

Each `.md` file starts with a scope tag:

```markdown
service: nova
# Onboarding documentation

Request a Nova account from the support team. Never include a password.
```

Set `SERVICEPILOT_PROCEDURES_DIR` to an absolute directory and restart to rebuild the index. Unknown scope tags are not returned. Escaping symlinks fail ingestion.

A custom `StatusConnector` implements `get_status(service_id) -> dict`. Pass it to `ServicePilot(status_connector=...)`. Keep expected availability failures explicit with `DomainError`. The registry still checks scope before invoking the connector.

`examples/onboarding.py` demonstrates a second documentation-only consumer with its own corpus. This SDK remains support-domain-specific; it does not promise arbitrary agent construction.
