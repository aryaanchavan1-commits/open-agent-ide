import json
import re
from pathlib import Path
from sqlalchemy.orm import Session

from .. import events
from ..agents import run_agent
from ..agents.base import AgentContext
from ..config import get_settings
from ..models import AgentRun, Conversation, ErrorLog, Message, Project, Task
from ..providers import get_provider
from ..services.context import build_context
from ..services.git_service import ensure_git_repo
from ..services.settings_service import auto_push_enabled, get_app_setting
from . import intent


def detect_intent(message: str) -> str:
    m = message.lower()
    if re.search(r"\b(debug|fix error|traceback|exception|failing test|error:\s|why (is|does) (this|it))", m):
        return "debug"
    if re.search(r"\b(test|pytest|jest|run tests|coverage)\b", m):
        return "test"
    if re.search(r"\b(review|audit|code quality|code smell)\b", m):
        return "review"
    if re.search(r"\b(document|readme|docs?)\b", m):
        return "document"
    if re.search(r"\b(architect|architecture|database schema|api design|design the)\b", m):
        return "architect"
    if re.search(r"\b(requirement|user story|acceptance criteria|product manager)\b", m):
        return "product"
    if re.search(r"\b(plan|task|break down|split into|roadmap)\b", m):
        return "plan"
    if re.search(r"\b(create|build|add|implement|feature|new project|make an|generate)\b", m):
        return "build"
    return "code"


async def orchestrator_run(
    db: Session,
    project_id: int,
    message: str,
    conversation_id: int | None = None,
    provider_name: str | None = None,
) -> dict:
    settings = get_settings()
    project = db.get(Project, project_id)
    if not project:
        return {"ok": False, "error": "Project not found"}

    await ensure_git_repo(Path(project.workspace_path))

    provider = get_provider(provider_name)
    model = project.default_model or settings.effective_default_model

    if conversation_id is None:
        conversation = Conversation(project_id=project.id, title=message[:80])
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        conversation_id = conversation.id
    else:
        conversation = db.get(Conversation, conversation_id)
        if not conversation:
            return {"ok": False, "error": "Conversation not found"}

    user_msg = Message(
        conversation_id=conversation_id,
        role="user",
        content=message,
        agent_type="user",
    )
    db.add(user_msg)
    db.commit()

    await events.emit(project.id, "conversation.started", {"conversation_id": conversation_id})

    intent_type = detect_intent(message)
    agent_sequence = intent.build_sequence(intent_type, message, db, project)

    final_parts: list[str] = []

    async def run_one(
        agent_type: str, prompt: str, task_id: str | None
    ) -> None:
        nonlocal final_parts
        task_model = None
        if task_id:
            task_model = (
                db.query(Task).filter(Task.project_id == project.id, Task.task_id == task_id).first()
            )
        run = AgentRun(
            project_id=project.id,
            conversation_id=conversation_id,
            agent_type=agent_type,
            status="running",
            input_text=prompt[:4000],
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        try:
            context = build_context(db, project, prompt, task_model)
            ctx = AgentContext(
                project=project,
                db=db,
                provider=provider,
                model=model,
                run=run,
                prompt=prompt,
                conversation_id=conversation_id,
                task=task_model,
                mode=project.permission_mode,
                context_json=json.dumps(context, default=str),
            )
            result = await run_agent(ctx)
            final_parts.append(result.output or "")
            if not result.ok:
                log = ErrorLog(
                    project_id=project.id,
                    agent_run_id=run.id,
                    source=agent_type,
                    message=result.error or "Agent failed",
                    traceback=result.output[:4000],
                )
                db.add(log)
                db.commit()
                await events.emit(
                    project.id,
                    "run.failed",
                    {"run_id": run.id, "agent": agent_type, "error": result.error},
                )
        except Exception as e:
            import traceback

            run.status = "failed"
            run.error = str(e)
            db.commit()
            log = ErrorLog(
                project_id=project.id,
                agent_run_id=run.id,
                source="orchestrator",
                message=str(e),
                traceback=traceback.format_exc(),
            )
            db.add(log)
            db.commit()
            final_parts.append(f"⚠️ Agent '{agent_type}' failed: {e}")

    planned_task_ids = {t for _, _, t in agent_sequence if t}

    for agent_type, prompt, task_id in agent_sequence:
        await run_one(agent_type, prompt, task_id)

    if intent_type == "build":
        pending = (
            db.query(Task)
            .filter(Task.project_id == project.id, Task.status.in_(["pending", "in_progress"]))
            .order_by(Task.id)
            .limit(3)
            .all()
        )
        pending = [t for t in pending if t.task_id not in planned_task_ids]
        for task in pending:
            await run_one(
                "coder",
                f"Implement task {task.task_id}: {task.title}\n{task.description}",
                task.task_id,
            )
        if pending:
            await run_one("tester", "Run the project tests and report results.", None)

    summary = "\n\n".join(p for p in final_parts if p)
    assistant_msg = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=summary or "The request has been processed.",
        agent_type="orchestrator",
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)
    await events.emit(
        project.id,
        "chat.message",
        {
            "message_id": assistant_msg.id,
            "conversation_id": conversation_id,
            "content": summary,
            "agent_type": "orchestrator",
        },
    )
    await events.emit(project.id, "run.finished", {"conversation_id": conversation_id})

    try:
        if auto_push_enabled(db, project.id):
            token = get_app_setting(db, "github_token")
            if token:
                from ..services.github_service import push_workspace

                user = get_app_setting(db, "github_user") or "owner"
                repo = f"{user}/{Path(project.workspace_path).name}"
                result = await push_workspace(Path(project.workspace_path), token, repo)
                await events.emit(
                    project.id,
                    "run.finished",
                    {"conversation_id": conversation_id, "pushed": result.get("repo")},
                )
    except Exception as e:
        print(f"[auto-push] failed: {e}")

    return {"ok": True, "conversation_id": conversation_id, "message_id": assistant_msg.id}
