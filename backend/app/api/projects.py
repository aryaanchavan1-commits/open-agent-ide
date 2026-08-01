import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import events
from ..agents import list_agents, run_agent
from ..agents.base import AgentContext
from ..config import get_settings
from ..database import SessionLocal, get_db
from ..models import AgentRun, Conversation, ErrorLog, Message, Project, Task, TestRun
from ..orchestrator.orchestrator import orchestrator_run
from ..providers import get_provider
from ..schemas import (
    AgentRunRequest,
    ChatRequest,
    ExecuteRequest,
    MessageOut,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    TaskCreate,
    TaskOut,
    TaskUpdate,
)
from ..security.command_safety import execute_with_approval
from ..services.context import build_context
from ..services.workspace import create_workspace, delete_workspace, project_source_dir

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    project = create_workspace(db, data)
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.execute(select(Project).order_by(Project.created_at.desc())).scalars().all()


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: int, data: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    path = Path(project.workspace_path)
    delete_workspace(project)
    db.delete(project)
    db.commit()
    return None


@router.get("/{project_id}/events")
async def project_events(project_id: int):
    queue = await events.subscribe(project_id)

    async def event_generator():
        try:
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield message
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            events.unsubscribe(project_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/{project_id}/conversations")
def list_conversations(project_id: int, db: Session = Depends(get_db)):
    return (
        db.execute(select(Conversation).where(Conversation.project_id == project_id).order_by(Conversation.id.desc()))
        .scalars()
        .all()
    )


@router.get("/{project_id}/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(project_id: int, conversation_id: int, db: Session = Depends(get_db)):
    return (
        db.execute(
            select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id)
        )
        .scalars()
        .all()
    )


async def _run_chat_background(project_id: int, message: str, conversation_id: int | None, provider: str | None):
    db = SessionLocal()
    try:
        await orchestrator_run(db, project_id, message, conversation_id, provider)
    finally:
        db.close()


@router.post("/{project_id}/chat")
async def chat(project_id: int, data: ChatRequest):
    project = None
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
    finally:
        db.close()
    if not project:
        raise HTTPException(404, "Project not found")
    asyncio.create_task(_run_chat_background(project_id, data.message, data.conversation_id, None))
    return {"ok": True, "streaming": True}


@router.get("/{project_id}/agents")
def agents_list(project_id: int, db: Session = Depends(get_db)):
    return list_agents()


@router.post("/{project_id}/agents/run")
async def run_agent_endpoint(project_id: int, data: AgentRunRequest):
    db = SessionLocal()
    project = db.get(Project, project_id)
    if not project:
        db.close()
        raise HTTPException(404, "Project not found")

    async def _runner():
        try:
            run = AgentRun(
                project_id=project_id,
                conversation_id=data.conversation_id,
                agent_type=data.agent_type,
                status="running",
                input_text=data.prompt[:4000],
            )
            db.add(run)
            db.commit()
            db.refresh(run)
            provider = get_provider()
            model = project.default_model or get_settings().effective_default_model
            context = build_context(db, project, data.prompt)
            ctx = AgentContext(
                project=project,
                db=db,
                provider=provider,
                model=model,
                run=run,
                prompt=data.prompt,
                conversation_id=data.conversation_id,
                mode=project.permission_mode,
                context_json=json.dumps(context, default=str),
            )
            await run_agent(ctx)
        except Exception as e:
            log = ErrorLog(project_id=project_id, source="agent_run", message=str(e))
            db.add(log)
            db.commit()
        finally:
            db.close()

    asyncio.create_task(_runner())
    return {"ok": True, "streaming": True}


@router.get("/{project_id}/runs")
def list_runs(project_id: int, db: Session = Depends(get_db)):
    return (
        db.execute(select(AgentRun).where(AgentRun.project_id == project_id).order_by(AgentRun.id.desc()).limit(50))
        .scalars()
        .all()
    )


@router.get("/{project_id}/tasks", response_model=list[TaskOut])
def list_tasks(project_id: int, db: Session = Depends(get_db)):
    return (
        db.execute(select(Task).where(Task.project_id == project_id).order_by(Task.id))
        .scalars()
        .all()
    )


@router.post("/{project_id}/tasks", response_model=TaskOut, status_code=201)
def create_task(project_id: int, data: TaskCreate, db: Session = Depends(get_db)):
    existing = db.execute(select(Task).where(Task.project_id == project_id)).scalars().all()
    task_id = data.task_id or f"TASK-{len(existing) + 1:03d}"
    task = Task(
        project_id=project_id,
        task_id=task_id,
        title=data.title,
        description=data.description,
        priority=data.priority,
        dependencies=data.dependencies,
        status=data.status,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/{project_id}/tasks/{task_id}", response_model=TaskOut)
def update_task(project_id: int, task_id: str, data: TaskUpdate, db: Session = Depends(get_db)):
    task = db.execute(
        select(Task).where(Task.project_id == project_id, Task.task_id == task_id)
    ).scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


@router.post("/{project_id}/execute")
async def execute_command(project_id: int, data: ExecuteRequest):
    db = SessionLocal()
    project = db.get(Project, project_id)
    if not project:
        db.close()
        raise HTTPException(404, "Project not found")
    mode = project.permission_mode
    source = project_source_dir(project)
    result = await execute_with_approval(
        db,
        project_id,
        data.command,
        source,
        agent="user",
        reason=data.reason or "Manual command from terminal",
        mode=mode,
        timeout=data.timeout,
    )
    db.close()
    return result


@router.get("/{project_id}/logs")
def get_logs(project_id: int, db: Session = Depends(get_db)):
    errors = (
        db.execute(select(ErrorLog).where(ErrorLog.project_id == project_id).order_by(ErrorLog.id.desc()).limit(50))
        .scalars()
        .all()
    )
    runs = (
        db.execute(select(AgentRun).where(AgentRun.project_id == project_id).order_by(AgentRun.id.desc()).limit(20))
        .scalars()
        .all()
    )
    tests = (
        db.execute(select(TestRun).where(TestRun.project_id == project_id).order_by(TestRun.id.desc()).limit(20))
        .scalars()
        .all()
    )
    return {"errors": errors, "runs": runs, "tests": tests}


@router.get("/{project_id}/context")
def get_context(project_id: int, q: str = Query("", max_length=500), db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return build_context(db, project, q)
