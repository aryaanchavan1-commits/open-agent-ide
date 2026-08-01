import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import events
from ..config import get_settings
from ..database import get_db
from ..models import Project, ProjectSetting
from ..providers import get_provider, list_providers
from ..providers.base import ChatMessage
from ..providers.ollama import detect_system
from ..schemas import ModelPullRequest

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/providers")
def providers():
    return {"providers": list_providers(), "current": get_settings().ai_provider}


@router.get("/system-check")
async def system_check():
    info = detect_system()
    try:
        ollama = get_provider("ollama")
        info["ollama_running"] = await ollama.is_available()
        if info["ollama_running"]:
            info["local_models"] = [m.model_dump() for m in await ollama.list_models()]
        else:
            info["local_models"] = []
    except Exception as e:
        info["ollama_running"] = False
        info["local_models"] = []
        info["ollama_error"] = str(e)
    return info


@router.get("/available")
async def available_models(provider: str | None = None):
    provider = provider or get_settings().ai_provider
    try:
        prov = get_provider(provider)
        models = await prov.list_models()
        return {"provider": provider, "models": [m.model_dump() for m in models], "error": None}
    except Exception as e:
        return {"provider": provider, "models": [], "error": str(e)}


@router.post("/pull")
async def pull_model(data: ModelPullRequest):
    provider = get_provider("ollama")

    async def progress_cb(payload: dict):
        status = payload.get("status", "")
        if status == "downloading" or ":" in status:
            await events.emit(0, "model.pull", {
                "model": data.model,
                "status": "downloading",
                "completed": payload.get("completed", 0),
                "total": payload.get("total", 0),
            })
        elif status == "success":
            await events.emit(0, "model.pull", {"model": data.model, "status": "success"})

    try:
        await provider.ensure_model(data.model)
        return {"ok": True, "model": data.model}
    except Exception as e:
        raise HTTPException(500, f"Failed to pull model: {e}")


@router.get("/current")
def current_model(db: Session = Depends(get_db)):
    settings = get_settings()
    return {
        "provider": settings.ai_provider,
        "model": settings.effective_default_model,
    }


@router.get("/providers-status")
async def providers_status():
    statuses = {}
    for pid in ("ollama", "openai", "openrouter"):
        try:
            prov = get_provider(pid)
            statuses[pid] = await prov.is_available()
        except Exception:
            statuses[pid] = False
    return statuses


@router.post("/test")
async def test_model(model: str, provider: str | None = None):
    try:
        prov = get_provider(provider)
        response = await prov.chat(
            [ChatMessage(role="user", content="Reply with exactly: MODEL_OK")],
            model=model,
            max_tokens=16,
        )
        ok = "MODEL_OK" in (response or "").upper()
        return {"ok": ok, "response": response[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/project/{project_id}")
def project_model(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return {
        "project_id": project_id,
        "provider": get_settings().ai_provider,
        "model": project.default_model or get_settings().effective_default_model,
    }


@router.post("/project/{project_id}")
def set_project_model(project_id: int, model: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    project.default_model = model
    db.commit()
    return {"ok": True, "model": model}


@router.get("/settings")
def model_settings(db: Session = Depends(get_db)):
    settings = get_settings()
    return {
        "ai_provider": settings.ai_provider,
        "ai_model": settings.effective_default_model,
        "ollama_base_url": settings.ollama_base_url,
        "ollama_model": settings.ollama_model,
        "ollama_auto_pull": settings.ollama_auto_pull,
        "openai_base_url": settings.openai_base_url,
        "openai_model": settings.openai_model,
        "openrouter_model": settings.openrouter_model,
        "openai_key_set": bool(settings.openai_api_key),
        "openrouter_key_set": bool(settings.openrouter_api_key),
    }
