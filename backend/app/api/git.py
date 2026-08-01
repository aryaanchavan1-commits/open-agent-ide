from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Checkpoint, Project
from ..schemas import CheckpointCreate, GitBranchCreate, GitCommitRequest
from ..services import git_service

router = APIRouter(prefix="/projects/{project_id}/git", tags=["git"])


async def _project_path(project_id: int, db: Session) -> Path:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    path = Path(project.workspace_path)
    if not (path / ".git").exists():
        await git_service.ensure_git_repo(path)
    return path


@router.get("/status")
async def git_status(project_id: int, db: Session = Depends(get_db)):
    path = await _project_path(project_id, db)
    return await git_service.git_status(path)


@router.get("/diff")
async def git_diff(project_id: int, staged: bool = False, db: Session = Depends(get_db)):
    path = await _project_path(project_id, db)
    diff = await git_service.git_diff(path, staged)
    files = await git_service.git_diff_files(path, staged)
    return {"diff": diff, "files": files}


@router.post("/commit")
async def git_commit(project_id: int, data: GitCommitRequest, db: Session = Depends(get_db)):
    path = await _project_path(project_id, db)
    return await git_service.git_commit(path, data.message)


@router.get("/branches")
async def git_branches(project_id: int, db: Session = Depends(get_db)):
    path = await _project_path(project_id, db)
    return {"branches": await git_service.git_branches(path)}


@router.post("/branches")
async def git_create_branch(project_id: int, data: GitBranchCreate, db: Session = Depends(get_db)):
    path = await _project_path(project_id, db)
    return await git_service.git_create_branch(path, data.name)


@router.post("/checkout")
async def git_checkout(project_id: int, branch: str, db: Session = Depends(get_db)):
    path = await _project_path(project_id, db)
    return await git_service.git_checkout_branch(path, branch)


@router.get("/log")
async def git_log(project_id: int, db: Session = Depends(get_db)):
    path = await _project_path(project_id, db)
    return {"commits": await git_service.git_log(path)}


@router.get("/checkpoints")
def list_checkpoints(project_id: int, db: Session = Depends(get_db)):
    return (
        db.query(Checkpoint)
        .filter(Checkpoint.project_id == project_id)
        .order_by(Checkpoint.id.desc())
        .all()
    )


@router.post("/checkpoints", status_code=201)
async def create_checkpoint(project_id: int, data: CheckpointCreate, db: Session = Depends(get_db)):
    path = await _project_path(project_id, db)
    name = data.name or f"checkpoint-{datetime.now(timezone.utc).strftime('%Y-%m-%d-%H%M%S')}"
    result = await git_service.git_checkpoint(path, name, data.message or "AI checkpoint")
    cp = Checkpoint(
        project_id=project_id,
        name=name,
        commit_hash=result.get("commit", ""),
        message=data.message or "AI checkpoint",
    )
    db.add(cp)
    db.commit()
    db.refresh(cp)
    return cp


@router.post("/checkpoints/{checkpoint_id}/restore")
async def restore_checkpoint(project_id: int, checkpoint_id: int, db: Session = Depends(get_db)):
    cp = db.get(Checkpoint, checkpoint_id)
    if not cp or cp.project_id != project_id:
        raise HTTPException(404, "Checkpoint not found")
    path = await _project_path(project_id, db)
    result = await git_service.git_reset_hard(path, cp.commit_hash)
    if not result.get("ok"):
        raise HTTPException(400, result.get("message", "Restore failed"))
    return {"ok": True, "message": f"Restored checkpoint '{cp.name}'"}
