import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import api_router
from .config import get_settings
from .database import init_db
from .tools.files import WorkspaceError

PUBLIC_PATHS = {"/", "/health", "/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _cleanup_stale_runs()
    from .mcp_bridge import get_mcp_bridge

    async def _connect_mcp():
        try:
            bridge = get_mcp_bridge()
            if bridge.enabled:
                connected = await bridge.connect_all()
                print(f"[mcp] connected servers: {connected or 'none'}")
        except Exception as e:
            print(f"[mcp] init error: {e}")

    asyncio.create_task(_connect_mcp())
    yield


def _cleanup_stale_runs() -> None:
    from sqlalchemy import update

    from .database import SessionLocal
    from .models import AgentRun

    with SessionLocal() as db:
        db.execute(
            update(AgentRun)
            .where(AgentRun.status == "running")
            .values(status="failed", error="Interrupted by server restart")
        )
        db.commit()
    print("[startup] marked stale agent runs as failed")


settings = get_settings()

app = FastAPI(
    title="Arynox AI",
    version=settings.app_version,
    description="Local-first AI software engineering platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.middleware("http")
async def api_token_guard(request: Request, call_next):
    token = settings.api_token
    if token:
        path = request.url.path
        if path.startswith(("/api", "/events")) and path not in PUBLIC_PATHS:
            provided = request.headers.get("x-api-token") or request.query_params.get("token")
            if provided != token:
                return JSONResponse(status_code=401, content={"detail": "Missing or invalid X-API-Token header"})
    return await call_next(request)


@app.exception_handler(WorkspaceError)
async def workspace_error_handler(request: Request, exc: WorkspaceError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/")
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "provider": settings.ai_provider,
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}
