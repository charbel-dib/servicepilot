def test_public_health_and_demo_metadata(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/ready").status_code == 200
    assert client.get("/api/config").json()["provider"] == "offline"
    assert "default-src" in client.get("/").headers["content-security-policy"]
    assert client.get("/static/app.js").status_code == 200


def test_auth_and_validation(client, auth):
    assert client.post("/api/runs", json={"query": "Panne Atlas"}).status_code == 401
    assert client.get("/api/me", headers=auth).json()["user_id"] == "alice"
    assert client.post("/api/runs", headers=auth, json={"query": "ab"}).status_code == 422
    assert (
        client.post("/api/runs", headers=auth, json={"query": "abc", "user_id": "bob"}).status_code
        == 422
    )
    assert client.post("/api/runs", headers=auth, content="x" * 17000).status_code == 413


def test_full_ticket_flow(client, auth):
    run = client.post(
        "/api/runs", headers=auth, json={"query": "Crée un ticket pour la panne Atlas"}
    ).json()
    assert run["status"] == "approval_required"
    run_id, proposal = run["run_id"], run["proposal"]
    body = {"proposal_id": proposal["id"], "digest": proposal["digest"], "approve": True}
    other = {"Authorization": "Bearer demo-bob-token"}
    assert client.get(f"/api/runs/{run_id}", headers=other).status_code == 404
    assert client.post(f"/api/runs/{run_id}/decision", headers=other, json=body).status_code == 404
    result = client.post(f"/api/runs/{run_id}/decision", headers=auth, json=body)
    assert result.status_code == 200 and result.json()["ticket_id"]
    assert len(client.get("/api/tickets", headers=auth).json()) == 1
    assert client.get("/api/tickets", headers=other).json() == []
    assert len(client.get("/api/runs", headers=auth).json()) == 1


def test_rate_limit(client, auth):
    for _ in range(120):
        assert client.get("/api/me", headers=auth).status_code == 200
    assert client.get("/api/me", headers=auth).status_code == 429
