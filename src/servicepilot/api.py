import hashlib
import hmac
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles

from servicepilot.config import Settings
from servicepilot.models import ApprovalRequest, Principal, RunRequest, RunResult
from servicepilot.sdk import ServicePilot
from servicepilot.security import DomainError

STATIC = Path(__file__).parent / "static"


def create_app(settings: Settings | None = None, sdk: ServicePilot | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        app.state.sdk = sdk or ServicePilot(settings)
        yield
        if sdk is None:
            app.state.sdk.close()

    app = FastAPI(title="ServicePilot API", version="0.1.0", lifespan=lifespan)
    auth = HTTPBearer(auto_error=False)
    identities = [
        (hashlib.sha256(token.encode()).digest(), Principal(**identity))
        for token, identity in settings.identities.items()
    ]
    buckets = defaultdict(deque)

    def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(auth)) -> Principal:
        if credentials is not None:
            hashed = hashlib.sha256(credentials.credentials.encode()).digest()
            for expected, principal in identities:
                if hmac.compare_digest(expected, hashed):
                    return principal
        raise DomainError("A valid bearer token is required", 401)

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return JSONResponse(
            {"detail": str(exc)},
            status_code=exc.status_code,
            headers={"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else {},
        )

    @app.middleware("http")
    async def boundaries(request: Request, call_next):
        if (
            request.headers.get("content-length", "").isdigit()
            and int(request.headers["content-length"]) > 16384
        ):
            return JSONResponse({"detail": "Request body is too large"}, status_code=413)
        if request.url.path.startswith("/api/"):
            now = time.monotonic()
            host = request.client.host if request.client else "unknown"
            bucket = buckets[host]
            while bucket and now - bucket[0] > 60:
                bucket.popleft()
            if len(bucket) >= 120:
                return JSONResponse(
                    {"detail": "Rate limit exceeded"},
                    status_code=429,
                    headers={"Retry-After": "60"},
                )
            bucket.append(now)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        if request.url.path == "/":
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
            )
        return response

    @app.get("/health", tags=["Operations"])
    def health():
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/ready", tags=["Operations"])
    def ready(request: Request):
        with request.app.state.sdk.store.connection() as db:
            db.execute("SELECT 1")
        return {"status": "ready"}

    @app.get("/api/config", tags=["Configuration"])
    def config():
        data = {
            "environment": settings.environment,
            "provider": settings.provider,
            "embeddings": settings.embedding_backend,
            "demo_identities": [],
        }
        if settings.environment == "demo":
            data["demo_identities"] = [
                {"token": token, "user_id": identity["user_id"]}
                for token, identity in settings.identities.items()
                if token.startswith("demo-")
            ]
        return data

    @app.get("/api/me", tags=["Identity"])
    def me(principal: Principal = Depends(current_user)):
        return principal

    @app.post("/api/runs", response_model=RunResult, tags=["Runs"])
    def run(body: RunRequest, request: Request, principal: Principal = Depends(current_user)):
        return request.app.state.sdk.run(body.query, principal)

    @app.get("/api/runs", response_model=list[RunResult], tags=["Runs"])
    def runs(request: Request, principal: Principal = Depends(current_user)):
        return request.app.state.sdk.list_runs(principal)

    @app.get("/api/runs/{run_id}", response_model=RunResult, tags=["Runs"])
    def get_run(run_id: str, request: Request, principal: Principal = Depends(current_user)):
        return request.app.state.sdk.get(run_id, principal)

    @app.post("/api/runs/{run_id}/decision", response_model=RunResult, tags=["Approvals"])
    def decide(
        run_id: str,
        body: ApprovalRequest,
        request: Request,
        principal: Principal = Depends(current_user),
    ):
        return request.app.state.sdk.decide(run_id, principal, **body.model_dump())

    @app.get("/api/tickets", tags=["Tickets"])
    def tickets(request: Request, principal: Principal = Depends(current_user)):
        return request.app.state.sdk.store.tickets(principal)

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
