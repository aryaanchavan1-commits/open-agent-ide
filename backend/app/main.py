import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import api_router
from .config import get_settings
from .database import init_db
from .tools.files import WorkspaceError

PUBLIC_PATHS = {"/", "/health", "/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}

# Static frontend build (frontend/out or bundled EXE data). When present, the
# backend serves the IDE itself, making the app a single distributable.
STATIC_DIR = None
_env_static = os.environ.get("ARYNOX_STATIC_DIR")
if _env_static:
    STATIC_DIR = Path(_env_static)
else:
    _repo_out = Path(__file__).resolve().parent.parent.parent / "frontend" / "out"
    if _repo_out.is_dir():
        STATIC_DIR = _repo_out

STATIC_INDEX = STATIC_DIR / "index.html" if STATIC_DIR else None


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
    if STATIC_INDEX and STATIC_INDEX.exists():
        return FileResponse(STATIC_INDEX)
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


if STATIC_DIR:
    _next_dir = STATIC_DIR / "_next"
    if _next_dir.is_dir():
        app.mount("/_next", StaticFiles(directory=str(_next_dir)), name="next-static")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        if full_path.startswith(("api/", "events", "docs", "health", "openapi.json", "redoc")):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (STATIC_DIR / full_path).resolve()
        try:
            candidate.relative_to(STATIC_DIR.resolve())
        except ValueError:
            raise HTTPException(status_code=404, detail="Not found")
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_INDEX)
