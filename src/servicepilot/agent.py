import json
import re
from pathlib import Path
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import interrupt

from servicepilot.config import Settings
from servicepilot.connectors import TOOL_SCHEMAS, ToolRegistry
from servicepilot.models import AgentAnswer, Principal, Source, TicketDraft
from servicepilot.security import DomainError, authorize, content_policy, normalize, redact
from servicepilot.storage import Store


class AgentState(TypedDict, total=False):
    run_id: str
    query: str
    messages: Annotated[list[AnyMessage], add_messages]
    evidence: list[dict]
    trace: list[dict]
    calls: int
    answer: dict
    proposal: dict
    ticket_id: str
    rejected: bool
    stop_reason: str


def service_from_query(query: str) -> str | None:
    text = normalize(query)
    found = [s for s in ("atlas", "nova", "orion", "vpn") if re.search(rf"\b{s}\b", text)]
    return found[0] if len(found) == 1 else None


def wants_ticket(query: str) -> bool:
    return any(term in normalize(query) for term in ("ticket", "signaler", "ouvrir un incident"))


def diagnostic(query: str) -> bool:
    return any(
        term in normalize(query)
        for term in (
            "panne",
            "probleme",
            "incident",
            "impossible",
            "acced",
            "connexion",
            "etat",
            "status",
            "down",
            "ticket",
        )
    )


class OfflineEngine:
    """Deterministic fixture policy. It uses no language model and makes no AI claim."""

    def next(self, state: AgentState) -> AIMessage:
        seen = [event["tool"] for event in state["trace"]]
        service = service_from_query(state["query"])
        if "search_procedures" not in seen:
            name, args = "search_procedures", {"query": state["query"]}
        elif service and diagnostic(state["query"]) and "get_service_status" not in seen:
            name, args = "get_service_status", {"service_id": service}
        elif service and diagnostic(state["query"]) and "find_recent_incidents" not in seen:
            name, args = "find_recent_incidents", {"service_id": service}
        else:
            return AIMessage(content="Evidence gathering complete.")
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "name": name,
                    "args": args,
                    "id": f"call-{len(seen)}",
                    "type": "tool_call",
                }
            ],
        )

    def summarize(self, state: AgentState) -> AgentAnswer:
        service = service_from_query(state["query"])
        sources = [
            Source(**source)
            for evidence in state["evidence"]
            for source in evidence.get("sources", [])
        ]
        status = next((e for e in state["evidence"] if "status" in e), None)
        failed = any(t["outcome"] != "ok" for t in state["trace"])
        if not sources and not status:
            return AgentAnswer(
                status="needs_information",
                summary="Précisez le service et le problème rencontré : les éléments disponibles ne suffisent pas.",
            )
        summary = f"Procédures disponibles : {', '.join(s.title for s in sources)}."
        if status:
            summary = f"{service.upper()} : {status['status']}. {status['message']} " + summary
        if failed:
            summary += " Une consultation a échoué ; le diagnostic est incomplet."
        actions = ["Suivre la procédure citée et contacter le support si le problème persiste."]
        draft = None
        if wants_ticket(state["query"]) and service:
            draft = TicketDraft(
                service_id=service,
                title=f"Assistance {service.upper()}",
                description=redact(state["query"]),
                priority="normal",
            )
        return AgentAnswer(
            status="unavailable" if failed else "answered",
            summary=summary,
            sources=sources,
            recommended_actions=actions,
            ticket_draft=draft,
        )


class LLMEngine:
    def __init__(self, settings: Settings):
        from langchain_openai import ChatOpenAI

        self.model = ChatOpenAI(
            model=settings.model,
            api_key=settings.api_key.get_secret_value(),
            temperature=0,
            timeout=30,
            max_retries=1,
        )
        self.tools_model = self.model.bind_tools(TOOL_SCHEMAS, parallel_tool_calls=False)
        self.output_model = self.model.with_structured_output(AgentAnswer, method="json_schema")
        self.prompt = (Path(__file__).parent / "prompts" / "support-v1.txt").read_text()

    def next(self, state: AgentState) -> AIMessage:
        return self.tools_model.invoke([SystemMessage(self.prompt), *state["messages"]])

    def summarize(self, state: AgentState) -> AgentAnswer:
        # A separate structured call avoids mixing tool schemas with the final output contract.
        return self.output_model.invoke(
            [
                SystemMessage(
                    self.prompt + "\nReturn the final structured diagnosis. Do not call tools."
                ),
                HumanMessage(
                    json.dumps(
                        {"query": state["query"], "evidence": state["evidence"]}, ensure_ascii=False
                    )
                ),
            ]
        )


def build_graph(
    settings: Settings, principal: Principal, tools: ToolRegistry, store: Store, saver, engine=None
):
    engine = engine or (OfflineEngine() if settings.provider == "offline" else LLMEngine(settings))

    def guard(state: AgentState):
        reason = content_policy(state["query"])
        service = service_from_query(state["query"])
        if not reason and service:
            try:
                authorize(principal, service)
            except DomainError:
                reason = "Vous n'avez pas accès à ce service."
        if reason:
            return {"answer": AgentAnswer(status="refused", summary=reason).model_dump()}
        if wants_ticket(state["query"]) and not service:
            return {
                "answer": AgentAnswer(
                    status="needs_information",
                    summary="Pour quel service souhaitez-vous créer un ticket : Atlas, Nova, Orion ou VPN ?",
                ).model_dump()
            }
        return {}

    def agent(state: AgentState):
        if state["calls"] >= settings.max_tool_calls:
            return {"stop_reason": "tool_budget"}
        return {"messages": [engine.next(state)]}

    def execute_tools(state: AgentState):
        evidence, trace = list(state["evidence"]), list(state["trace"])
        messages = []
        calls = state["calls"]
        for call in state["messages"][-1].tool_calls:
            if calls >= settings.max_tool_calls:
                result = {"error": "Tool budget exhausted"}
            else:
                result, event = tools.execute(call["name"], call["args"], principal)
                evidence.append(result)
                trace.append(event)
                calls += 1
            messages.append(
                ToolMessage(content=json.dumps(result, ensure_ascii=False), tool_call_id=call["id"])
            )
        return {"evidence": evidence, "trace": trace, "messages": messages, "calls": calls}

    def summarize(state: AgentState):
        answer = AgentAnswer.model_validate(engine.summarize(state))
        # A model cannot invent source IDs or replace a retrieved excerpt with malicious text.
        known = {s["id"]: Source(**s) for e in state["evidence"] for s in e.get("sources", [])}
        answer.sources = [known[s.id] for s in answer.sources if s.id in known]
        answer.summary = redact(answer.summary)
        answer.recommended_actions = [redact(a) for a in answer.recommended_actions]
        if content_policy(answer.summary):
            answer = AgentAnswer(
                status="refused", summary="La réponse a été bloquée par la politique de contenu."
            )
        if answer.ticket_draft:
            if not wants_ticket(state["query"]) or answer.status in {
                "refused",
                "needs_information",
            }:
                answer.ticket_draft = None
            else:
                service = service_from_query(state["query"])
                if answer.ticket_draft.service_id != service:
                    raise DomainError("Draft service differs from the requested service", 409)
                authorize(principal, answer.ticket_draft.service_id)
                answer.ticket_draft.title = redact(answer.ticket_draft.title)
                answer.ticket_draft.description = redact(answer.ticket_draft.description)
        return {"answer": answer.model_dump()}

    def prepare(state: AgentState):
        draft = TicketDraft.model_validate(state["answer"]["ticket_draft"])
        proposal = store.prepare(state["run_id"], principal, draft, settings.approval_ttl_seconds)
        return {"proposal": proposal}

    def approval(state: AgentState):
        # No side effect before interrupt: this node is replayed when resumed.
        interrupt({"kind": "ticket_approval", "proposal": state["proposal"]})
        # Ignore the model/resume payload. The authoritative decision is in SQLite.
        proposal = store.proposal(state["run_id"])
        if proposal["status"] == "rejected":
            return {"rejected": True}
        if proposal["status"] not in {"approved", "executed"}:
            raise DomainError("No server-side approval exists", 403)
        return {"rejected": False}

    def create_ticket(state: AgentState):
        ticket_id = store.execute_ticket(
            state["run_id"],
            principal,
            TicketDraft.model_validate(state["answer"]["ticket_draft"]),
        )
        return {"ticket_id": ticket_id}

    graph = StateGraph(AgentState)
    for name, node in {
        "guard": guard,
        "agent": agent,
        "tools": execute_tools,
        "summarize": summarize,
        "prepare": prepare,
        "approval": approval,
        "create_ticket": create_ticket,
    }.items():
        graph.add_node(name, node)
    graph.add_edge(START, "guard")
    graph.add_conditional_edges(
        "guard", lambda s: "done" if s.get("answer") else "go", {"done": END, "go": "agent"}
    )
    graph.add_conditional_edges(
        "agent",
        lambda s: (
            "tools" if not s.get("stop_reason") and s["messages"][-1].tool_calls else "summarize"
        ),
    )
    graph.add_edge("tools", "agent")
    graph.add_conditional_edges(
        "summarize",
        lambda s: "prepare" if s["answer"].get("ticket_draft") else "done",
        {"prepare": "prepare", "done": END},
    )
    graph.add_edge("prepare", "approval")
    graph.add_conditional_edges(
        "approval",
        lambda s: "done" if s.get("rejected") else "create",
        {"done": END, "create": "create_ticket"},
    )
    graph.add_edge("create_ticket", END)
    return graph.compile(checkpointer=saver)
