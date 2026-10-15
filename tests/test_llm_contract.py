from langchain_core.messages import AIMessage

from servicepilot.agent import LLMEngine, OfflineEngine
from servicepilot.evaluation import JudgeVerdict, judge_answer
from servicepilot.models import AgentAnswer, TicketDraft
from servicepilot.sdk import ServicePilot


class LoopEngine(OfflineEngine):
    def next(self, state):
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_service_status",
                    "args": {"service_id": "atlas"},
                    "id": f"loop-{state['calls']}",
                    "type": "tool_call",
                }
            ],
        )


def test_tool_loop_is_bounded(settings, connector, alice):
    settings.max_tool_calls = 2
    with ServicePilot(settings, status_connector=connector, engine=LoopEngine()) as sdk:
        run = sdk.run("Problème Atlas", alice)
        assert run.status == "complete"
        assert len(run.trace) == 2


class ForgingEngine(OfflineEngine):
    def summarize(self, state):
        return AgentAnswer(
            status="answered",
            summary="Une réponse avec une source inventée.",
            sources=[{"id": "invented", "title": "Fake", "excerpt": "Fake"}],
            ticket_draft=TicketDraft(
                service_id="atlas",
                title="Unsolicited ticket",
                description="Should never be created.",
            ),
        )


def test_unknown_citations_removed_and_unsolicited_ticket_ignored(settings, connector, alice):
    with ServicePilot(settings, status_connector=connector, engine=ForgingEngine()) as sdk:
        run = sdk.run("Procédure Atlas", alice)
        assert not run.answer.sources
        assert not run.answer.ticket_draft
        assert not run.proposal


class ExplodingEngine(OfflineEngine):
    def next(self, state):
        raise RuntimeError("super-secret-provider-key")


def test_provider_exception_is_not_exposed(settings, connector, alice):
    with ServicePilot(settings, status_connector=connector, engine=ExplodingEngine()) as sdk:
        run = sdk.run("Procédure Atlas", alice)
        assert run.status == "error"
        assert "super-secret" not in run.model_dump_json()


def test_native_tool_binding_and_structured_output_are_wired(settings, monkeypatch):
    """Tests the adapter contract, not a claim about a live provider response."""
    calls = {}

    class FakeModel:
        def __init__(self, **kwargs):
            calls["init"] = kwargs

        def bind_tools(self, schemas, **kwargs):
            calls["tools"] = schemas
            return self

        def with_structured_output(self, schema, **kwargs):
            calls["output_schema"] = schema
            return self

        def invoke(self, messages):
            return AgentAnswer(status="answered", summary="Fixture")

    monkeypatch.setattr("langchain_openai.ChatOpenAI", FakeModel)
    from pydantic import SecretStr

    settings.api_key = SecretStr("test-only")
    engine = LLMEngine(settings)
    assert len(calls["tools"]) == 3
    assert calls["output_schema"] is AgentAnswer
    assert engine.summarize({"query": "Atlas", "evidence": []}).summary == "Fixture"


def test_judge_receives_rubric_and_structured_schema():
    class Model:
        def with_structured_output(self, schema, **kwargs):
            assert schema is JudgeVerdict
            return self

        def invoke(self, messages):
            assert "untrusted" not in messages[0].content or "data" in messages[0].content
            return JudgeVerdict(grounded=True, useful=True, score=3, explanation="Supported")

    assert judge_answer("Atlas", {"summary": "Known outage"}, [], Model())["score"] == 3
