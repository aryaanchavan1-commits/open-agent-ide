import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..mcp_bridge import get_mcp_bridge
from ..models import Project
from ..providers import refresh_providers
from ..services.github_service import ensure_and_push, list_repos, validate_token
from ..services.settings_service import get_app_setting, get_runtime_settings, set_app_setting

router = APIRouter(prefix="/integrations", tags=["integrations"])


class KeysRequest(BaseModel):
    openai_api_key: str | None = None
    openrouter_api_key: str | None = None
    github_token: str | None = None
    mcp_servers: str | None = None


class GithubTokenRequest(BaseModel):
    token: str


class GithubPushRequest(BaseModel):
    project_id: int
    repo: str
    create_if_missing: bool = False
    branch: str = "main"


class McpConfigRequest(BaseModel):
    servers: str


class AutoPushRequest(BaseModel):
    enabled: bool


@router.get("/status")
def integration_status(db: Session = Depends(get_db)):
    settings = get_runtime_settings()
    token = get_app_setting(db, "github_token")
    user = get_app_setting(db, "github_user")
    return {
        "github": {"token_set": bool(token), "user": user or None},
        "openai_key_set": bool(settings.openai_api_key),
        "openrouter_key_set": bool(settings.openrouter_api_key),
        "auto_push": get_app_setting(db, "auto_push", "false").lower() in ("true", "1", "yes"),
        "mcp_servers": list(get_mcp_bridge().tool_names()[:50]),
    }


@router.post("/keys")
def save_keys(data: KeysRequest, db: Session = Depends(get_db)):
    if data.openai_api_key is not None:
        set_app_setting(db, "openai_api_key", data.openai_api_key)
    if data.openrouter_api_key is not None:
        set_app_setting(db, "openrouter_api_key", data.openrouter_api_key)
    if data.github_token is not None:
        set_app_setting(db, "github_token", data.github_token)
    if data.mcp_servers is not None:
        set_app_setting(db, "mcp_servers", data.mcp_servers)
    refresh_providers()
    return {"ok": True}


@router.post("/github/test")
async def github_test(data: GithubTokenRequest):
    try:
        result = await validate_token(data.token)
        return result
    except Exception as e:
        raise HTTPException(400, f"GitHub token rejected: {e}")


@router.post("/github/save")
async def github_save(data: GithubTokenRequest, db: Session = Depends(get_db)):
    try:
        result = await validate_token(data.token)
    except Exception as e:
        raise HTTPException(400, f"GitHub token rejected: {e}")
    set_app_setting(db, "github_token", data.token)
    set_app_setting(db, "github_user", result["login"])
    return {"ok": True, "user": result["login"]}


@router.get("/github/repos")
async def github_repos(db: Session = Depends(get_db)):
    token = get_app_setting(db, "github_token")
    if not token:
        raise HTTPException(400, "No GitHub token configured — save one in Settings > Integrations")
    try:
        return {"repos": await list_repos(token)}
    except Exception as e:
        raise HTTPException(502, f"Failed to list repositories: {e}")


@router.post("/github/push")
async def github_push(data: GithubPushRequest, db: Session = Depends(get_db)):
    project = db.get(Project, data.project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    token = get_app_setting(db, "github_token")
    if not token:
        raise HTTPException(400, "No GitHub token configured — save one in Settings > Integrations")
    workspace = Path(project.workspace_path)
    try:
        result = await ensure_and_push(
            workspace, token, data.repo, data.branch, data.create_if_missing
        )
        result["ok"] = True
        return result
    except Exception as e:
        raise HTTPException(502, f"Push failed: {e}")


@router.get("/mcp")
def mcp_status():
    bridge = get_mcp_bridge()
    return {
        "enabled": bridge.enabled,
        "connected_tools": bridge.describe_tools(),
        "servers": json.dumps(get_runtime_settings().mcp_servers, indent=2),
    }


@router.post("/mcp")
async def mcp_save(data: McpConfigRequest, db: Session = Depends(get_db)):
    try:
        parsed = json.loads(data.servers) if data.servers.strip() else {}
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"Invalid JSON: {e}")
    if not isinstance(parsed, dict):
        raise HTTPException(400, "MCP servers must be a JSON object")
    set_app_setting(db, "mcp_servers", json.dumps(parsed))
    bridge = get_mcp_bridge()
    bridge.reset()
    connected = await bridge.connect_all()
    return {"ok": True, "connected": connected}


@router.post("/auto-push")
def auto_push(data: AutoPushRequest, db: Session = Depends(get_db)):
    set_app_setting(db, "auto_push", "true" if data.enabled else "false")
    return {"ok": True, "enabled": data.enabled}


@router.get("/project/{project_id}")
def project_integrations(project_id: int, db: Session = Depends(get_db)):
    from ..services.settings_service import auto_push_enabled

    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return {
        "auto_push": auto_push_enabled(db, project_id),
        "github_user": get_app_setting(db, "github_user") or None,
    }
