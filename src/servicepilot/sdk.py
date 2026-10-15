import sqlite3
import threading
import uuid

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from servicepilot.agent import LLMEngine, OfflineEngine, build_graph
from servicepilot.config import Settings
from servicepilot.connectors import HttpStatusConnector, ToolRegistry
from servicepilot.models import Principal, RunResult
from servicepilot.retrieval import HashEmbedder, KnowledgeBase, SemanticEmbedder
from servicepilot.security import DomainError, redact
from servicepilot.storage import Store


class ServicePilot:
    """Synchronous SDK; create once and close on application shutdown.

    One process owns a data directory. The lock serializes graph writes; SQLite
    enforces proposal/ticket integrity in addition to this application lock.
    """

    def __init__(self, settings: Settings | None = None, *, status_connector=None, engine=None):
        self.settings = settings or Settings()
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.store = Store(self.settings.data_dir / "servicepilot.db")
        embedder = (
            HashEmbedder()
            if self.settings.embedding_backend == "hashing"
            else SemanticEmbedder(self.settings.embedding_model)
        )
        self.knowledge = KnowledgeBase(self.settings.procedures_dir, embedder)
        self.status = status_connector or HttpStatusConnector(
            self.settings.status_url,
            self.settings.status_timeout,
        )
        self.tools = ToolRegistry(self.knowledge, self.store, self.status)
        self.connection = sqlite3.connect(
            self.settings.data_dir / "checkpoints.db",
            check_same_thread=False,
        )
        self.saver = SqliteSaver(self.connection)
        self.lock = threading.RLock()
        self.engine = engine or (
            OfflineEngine() if self.settings.provider == "offline" else LLMEngine(self.settings)
        )

    def graph(self, principal: Principal):
        return build_graph(
            self.settings, principal, self.tools, self.store, self.saver, self.engine
        )

    def _config(self, run_id: str) -> dict:
        return {"configurable": {"thread_id": run_id}, "recursion_limit": 40}

    def _snapshot(self, run_id: str, graph) -> RunResult:
        snapshot = graph.get_state(self._config(run_id))
        values = snapshot.values
        status = "complete"
        if snapshot.next:
            status = "approval_required" if any(t.interrupts for t in snapshot.tasks) else "error"
        if values.get("rejected"):
            status = "rejected"
        result = RunResult(
            run_id=run_id,
            status=status,
            mode=self.settings.provider,
            answer=values.get("answer"),
            proposal=self.store.proposal(run_id),
            trace=values.get("trace", []),
            ticket_id=values.get("ticket_id"),
        )
        self.store.save_result(run_id, result.model_dump())
        return result

    def run(self, query: str, principal: Principal) -> RunResult:
        if not 3 <= len(query.strip()) <= 2000:
            raise DomainError("Query must contain 3 to 2000 characters", 422)
        with self.lock:
            run_id = str(uuid.uuid4())
            query = redact(query.strip())
            initial = RunResult(run_id=run_id, status="running", mode=self.settings.provider)
            self.store.new_run(run_id, principal, query, initial.model_dump())
            graph = self.graph(principal)
            try:
                graph.invoke(
                    {
                        "run_id": run_id,
                        "query": query,
                        "messages": [HumanMessage(query)],
                        "evidence": [],
                        "trace": [],
                        "calls": 0,
                    },
                    self._config(run_id),
                )
                return self._snapshot(run_id, graph)
            except Exception:
                # Never leak provider bodies, prompts or exception messages to API callers.
                result = initial.model_copy(
                    update={
                        "status": "error",
                        "error": "Execution failed. Check configuration and retry with a new run.",
                    }
                )
                self.store.save_result(run_id, result.model_dump())
                return result

    def get(self, run_id: str, principal: Principal) -> RunResult:
        row = self.store.require_owner(run_id, principal)
        result = RunResult.model_validate_json(row["result"])
        if result.answer and any(s not in principal.services for s in self._run_services(run_id)):
            raise DomainError("Run access has been revoked", 403)
        return result

    def _run_services(self, run_id: str) -> set[str]:
        graph = self.graph(Principal(user_id="internal", services=frozenset()))
        snapshot = graph.get_state(self._config(run_id))
        sources = {d["id"]: d["service_id"] for d in self.knowledge.documents}
        found = set()
        for evidence in snapshot.values.get("evidence", []):
            if evidence.get("service_id"):
                found.add(evidence["service_id"])
            found.update(
                sources[s["id"]] for s in evidence.get("sources", []) if s["id"] in sources
            )
            found.update(i["service_id"] for i in evidence.get("incidents", []))
        return found

    def decide(
        self, run_id: str, principal: Principal, *, proposal_id: str, digest: str, approve: bool
    ) -> RunResult:
        with self.lock:
            self.get(run_id, principal)
            graph = self.graph(principal)
            self.store.decide(run_id, principal, proposal_id, digest, approve)
            snapshot = graph.get_state(self._config(run_id))
            if snapshot.next:
                graph.invoke(Command(resume={"decision_recorded": True}), self._config(run_id))
            return self._snapshot(run_id, graph)

    def list_runs(self, principal: Principal) -> list[RunResult]:
        results = []
        with self.lock:
            for item in self.store.list_runs(principal):
                try:
                    results.append(self.get(item["run_id"], principal))
                except DomainError:
                    continue
        return results

    def close(self):
        self.connection.close()
        if hasattr(self.status, "close"):
            self.status.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
