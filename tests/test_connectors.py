import httpx
import pytest

from servicepilot.connectors import HttpStatusConnector
from servicepilot.retrieval import KnowledgeBase
from servicepilot.security import DomainError


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500),
        httpx.Response(200, text="not JSON"),
        httpx.Response(200, json={"service_id": "nova", "status": "operational"}),
        httpx.Response(200, json={"service_id": "atlas", "status": "made-up"}),
        httpx.Response(200, json=[]),
    ],
)
def test_bad_http_responses(response):
    connector = HttpStatusConnector(
        "http://fixture", transport=httpx.MockTransport(lambda _: response)
    )
    with pytest.raises(DomainError, match="unavailable"):
        connector.get_status("atlas")
    connector.close()


def test_timeout_is_explicit(settings, alice):
    from servicepilot.sdk import ServicePilot

    def fail(request):
        raise httpx.ReadTimeout("timeout")

    connector = HttpStatusConnector("http://fixture", transport=httpx.MockTransport(fail))
    with ServicePilot(settings, status_connector=connector) as sdk:
        result = sdk.run("Problème de connexion Atlas", alice)
        assert result.answer.status == "unavailable"
        assert any(t.outcome == "error" for t in result.trace)


@pytest.mark.parametrize(
    "tool,args",
    [
        ("get_service_status", {"service_id": "orion"}),
        ("find_recent_incidents", {"service_id": "orion"}),
    ],
)
def test_tool_authorization_is_independent_of_prompt(sdk, alice, tool, args):
    result, event = sdk.tools.execute(tool, args, alice)
    assert event["outcome"] == "denied" and "error" in result


@pytest.mark.parametrize(
    "tool,args",
    [
        ("get_service_status", {"service_id": "atlas/../../etc/passwd"}),
        ("find_recent_incidents", {"service_id": "atlas' OR 1=1 --"}),
        ("search_procedures", {"query": "Atlas", "path": "/etc/passwd"}),
        ("delete_database", {}),
    ],
)
def test_unknown_tools_and_invalid_args(sdk, alice, tool, args):
    result, event = sdk.tools.execute(tool, args, alice)
    assert "error" in result and event["outcome"] == "error"


def test_vector_retrieval_scopes_are_isolated(sdk, alice, bob):
    assert not any(
        s["id"].startswith("orion") for s in sdk.knowledge.search("Orion finance", alice)
    )
    assert any(s["id"].startswith("orion") for s in sdk.knowledge.search("Orion finance", bob))
    assert all(
        s["id"].startswith("atlas") for s in sdk.knowledge.search("Panne Atlas connexion", bob)
    )


def test_filesystem_escape_is_rejected(tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("secret")
    root = tmp_path / "kb"
    root.mkdir()
    try:
        (root / "escape.md").symlink_to(outside)
    except OSError:
        pytest.skip("Creating symlinks is not permitted on this platform")
    with pytest.raises(ValueError, match="outside"):
        KnowledgeBase(root)
