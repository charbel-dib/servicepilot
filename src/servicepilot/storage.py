import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from servicepilot.models import Principal, TicketDraft
from servicepilot.security import DomainError, authorize


def canonical(draft: TicketDraft) -> str:
    return json.dumps(draft.model_dump(), sort_keys=True, ensure_ascii=False, separators=(",", ":"))


class Store:
    """SQLite authority for ownership, immutable proposals and idempotent writes."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, query TEXT NOT NULL,
                    created REAL NOT NULL, result TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS proposals (
                    id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE REFERENCES runs(id),
                    owner TEXT NOT NULL, payload TEXT NOT NULL, digest TEXT NOT NULL,
                    expires REAL NOT NULL, status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tickets (
                    id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL UNIQUE REFERENCES proposals(id),
                    owner TEXT NOT NULL, service_id TEXT NOT NULL, payload TEXT NOT NULL,
                    created REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY, service_id TEXT NOT NULL, summary TEXT NOT NULL,
                    resolution TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, time REAL NOT NULL,
                    owner TEXT NOT NULL, run_id TEXT NOT NULL, action TEXT NOT NULL
                );
            """)
            rows = []
            for service in ("atlas", "nova", "orion", "vpn"):
                for i in range(1, 6):
                    rows.append(
                        (
                            f"INC-{service}-{i}",
                            service,
                            f"{service.upper()} : incident de connexion historique #{i}",
                            "Vérifier l'état du service et suivre la procédure de connexion.",
                        )
                    )
            db.executemany("INSERT OR IGNORE INTO incidents VALUES (?,?,?,?)", rows)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def new_run(self, run_id: str, principal: Principal, query: str, result: dict):
        with self.connection() as db:
            db.execute(
                "INSERT INTO runs VALUES (?,?,?,?,?)",
                (
                    run_id,
                    principal.user_id,
                    query,
                    time.time(),
                    json.dumps(result),
                ),
            )

    def require_owner(self, run_id: str, principal: Principal) -> dict:
        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM runs WHERE id=? AND owner=?",
                (
                    run_id,
                    principal.user_id,
                ),
            ).fetchone()
        if not row:
            raise DomainError("Run not found", 404)
        return dict(row)

    def save_result(self, run_id: str, result: dict):
        with self.connection() as db:
            db.execute("UPDATE runs SET result=? WHERE id=?", (json.dumps(result), run_id))

    def list_runs(self, principal: Principal) -> list[dict]:
        with self.connection() as db:
            rows = db.execute(
                "SELECT result FROM runs WHERE owner=? ORDER BY created DESC LIMIT 50",
                (principal.user_id,),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def incidents(self, principal: Principal, service_id: str) -> list[dict]:
        authorize(principal, service_id)
        with self.connection() as db:
            rows = db.execute("SELECT * FROM incidents WHERE service_id=? LIMIT 5", (service_id,))
            return [dict(row) for row in rows]

    def prepare(self, run_id: str, principal: Principal, draft: TicketDraft, ttl: int) -> dict:
        self.require_owner(run_id, principal)
        authorize(principal, draft.service_id)
        payload = canonical(draft)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        with self.connection() as db:
            db.execute(
                "INSERT OR IGNORE INTO proposals VALUES (?,?,?,?,?,?,?)",
                (
                    str(uuid.uuid4()),
                    run_id,
                    principal.user_id,
                    payload,
                    digest,
                    time.time() + ttl,
                    "pending",
                ),
            )
            row = dict(db.execute("SELECT * FROM proposals WHERE run_id=?", (run_id,)).fetchone())
        if row["payload"] != payload:
            raise DomainError("A different proposal already exists for this run", 409)
        return self.proposal(run_id)

    def proposal(self, run_id: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM proposals WHERE run_id=?", (run_id,)).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "digest": row["digest"],
            "expires_at": row["expires"],
            "status": row["status"],
            "draft": json.loads(row["payload"]),
        }

    def decide(
        self, run_id: str, principal: Principal, proposal_id: str, digest: str, approve: bool
    ):
        self.require_owner(run_id, principal)
        target = "approved" if approve else "rejected"
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM proposals WHERE run_id=? AND owner=?",
                (
                    run_id,
                    principal.user_id,
                ),
            ).fetchone()
            if not row or row["id"] != proposal_id or row["digest"] != digest:
                raise DomainError("Proposal does not match", 409)
            authorize(principal, json.loads(row["payload"])["service_id"])
            if row["status"] in {target, "executed" if approve else target}:
                return  # idempotent retries of the same decision
            if row["status"] != "pending":
                raise DomainError("Proposal already decided", 409)
            if row["expires"] < time.time():
                raise DomainError("Proposal expired; submit a new request", 409)
            db.execute("UPDATE proposals SET status=? WHERE id=?", (target, proposal_id))
            db.execute(
                "INSERT INTO audit(time,owner,run_id,action) VALUES (?,?,?,?)",
                (
                    time.time(),
                    principal.user_id,
                    run_id,
                    target,
                ),
            )

    def execute_ticket(self, run_id: str, principal: Principal, draft: TicketDraft) -> str:
        """Check authority and write exactly once, in the same transaction."""
        self.require_owner(run_id, principal)
        authorize(principal, draft.service_id)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            proposal = db.execute(
                "SELECT * FROM proposals WHERE run_id=? AND owner=?",
                (
                    run_id,
                    principal.user_id,
                ),
            ).fetchone()
            if not proposal or proposal["payload"] != canonical(draft):
                raise DomainError("Ticket content differs from the proposal", 409)
            if proposal["status"] not in {"approved", "executed"}:
                raise DomainError("Human approval is required", 403)
            existing = db.execute(
                "SELECT id FROM tickets WHERE proposal_id=?", (proposal["id"],)
            ).fetchone()
            if existing:
                return existing[0]
            if proposal["expires"] < time.time():
                raise DomainError("Proposal expired before execution", 409)
            ticket_id = "SP-" + uuid.uuid4().hex[:10].upper()
            db.execute(
                "INSERT INTO tickets VALUES (?,?,?,?,?,?)",
                (
                    ticket_id,
                    proposal["id"],
                    principal.user_id,
                    draft.service_id,
                    canonical(draft),
                    time.time(),
                ),
            )
            db.execute("UPDATE proposals SET status='executed' WHERE id=?", (proposal["id"],))
            db.execute(
                "INSERT INTO audit(time,owner,run_id,action) VALUES (?,?,?,?)",
                (
                    time.time(),
                    principal.user_id,
                    run_id,
                    "ticket_created",
                ),
            )
            return ticket_id

    def tickets(self, principal: Principal) -> list[dict]:
        with self.connection() as db:
            rows = db.execute(
                "SELECT * FROM tickets WHERE owner=? ORDER BY created DESC", (principal.user_id,)
            )
            return [
                dict(row) | {"payload": json.loads(row["payload"])}
                for row in rows
                if row["service_id"] in principal.services
            ]
