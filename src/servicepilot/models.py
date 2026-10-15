from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ServiceId = Literal["atlas", "nova", "orion", "vpn"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Principal(StrictModel):
    user_id: str
    services: frozenset[str]


class Source(StrictModel):
    id: str
    title: str
    excerpt: str


class TicketDraft(StrictModel):
    service_id: ServiceId
    title: str = Field(min_length=5, max_length=120)
    description: str = Field(min_length=10, max_length=2000)
    priority: Literal["low", "normal", "high"] = "normal"


class AgentAnswer(StrictModel):
    status: Literal["answered", "needs_information", "unavailable", "refused"]
    summary: str = Field(min_length=1, max_length=4000)
    sources: list[Source] = Field(default_factory=list, max_length=8)
    recommended_actions: list[str] = Field(default_factory=list, max_length=8)
    ticket_draft: TicketDraft | None = None


class TraceEvent(StrictModel):
    tool: str
    outcome: Literal["ok", "error", "denied"]
    duration_ms: float


class Proposal(StrictModel):
    id: str
    digest: str
    expires_at: float
    status: str
    draft: TicketDraft


class RunResult(StrictModel):
    run_id: str
    status: Literal["running", "complete", "approval_required", "rejected", "error"]
    mode: str
    answer: AgentAnswer | None = None
    proposal: Proposal | None = None
    ticket_id: str | None = None
    trace: list[TraceEvent] = Field(default_factory=list)
    error: str | None = None


class RunRequest(StrictModel):
    query: str = Field(min_length=3, max_length=2000)


class ApprovalRequest(StrictModel):
    proposal_id: str
    digest: str = Field(min_length=64, max_length=64)
    approve: bool
