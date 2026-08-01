import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from .. import events
from ..models import AgentRun, PlanChange, Project, ToolCall
from ..providers.base import AIProvider
from ..services.workspace import project_source_dir


@dataclass
class AgentContext:
    project: Project
    db: Session
    provider: AIProvider
    model: str
    run: AgentRun
    prompt: str = ""
    conversation_id: Optional[int] = None
    task: Any = None
    mode: str = "ask"
    context_json: str = ""
    approval_cache: dict = field(default_factory=dict)

    def emit(self, event_type: str, data: Any = None):
        return events.emit(self.project.id, event_type, data)

    async def status(self, message: str, emoji: str = "🤖"):
        await self.emit("agent.status", {"agent": self.run.agent_type, "message": message, "emoji": emoji})

    async def log_tool(self, tool_name: str, arguments: str, result: str, status: str = "ok", error: str = ""):
        call = ToolCall(
            project_id=self.project.id,
            agent_run_id=self.run.id,
            tool_name=tool_name,
            arguments=arguments[:2000],
            result=result[:4000],
            status=status,
            error=error,
        )
        self.db.add(call)
        self.db.commit()

    @property
    def source_dir(self) -> Path:
        return project_source_dir(self.project)


class AgentResult:
    def __init__(self, ok: bool, output: str = "", error: str = "", data: Any = None):
        self.ok = ok
        self.output = output
        self.error = error
        self.data = data


class BaseAgent:
    name = "base"
    display_name = "Base Agent"

    async def run(self, ctx: AgentContext) -> AgentResult:
        raise NotImplementedError


def make_diff(rel_path: str, old_content: str, new_content: str) -> str:
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}",
            lineterm="",
        )
    )


async def propose_changes(
    ctx: AgentContext,
    summary: str,
    files: list[dict],
    commands: list[dict] | None = None,
) -> Optional[PlanChange]:
    """Create a PlanChange with diffs, request approval if mode is ask, then apply."""
    source = ctx.source_dir
    prepared = []
    diffs = []
    for f in files:
        rel = f["path"].lstrip("/")
        target = source / rel
        old_content = ""
        action = "create"
        if target.exists():
            try:
                old_content = target.read_text(encoding="utf-8", errors="replace")
            except Exception:
                old_content = ""
            if target.read_text(encoding="utf-8", errors="replace") != f.get("content", ""):
                action = "edit"
            else:
                action = "unchanged"
        diff = make_diff(rel, old_content, f.get("content", ""))
        prepared.append({"path": rel, "action": action, "content": f.get("content", "")})
        if action != "unchanged":
            diffs.append({"path": rel, "action": action, "diff": diff})

    plan = PlanChange(
        project_id=ctx.project.id,
        agent_run_id=ctx.run.id,
        summary=summary,
        diff="\n".join(d["diff"] for d in diffs),
        files=prepared,
        status="proposed",
    )
    ctx.db.add(plan)
    ctx.db.commit()
    ctx.db.refresh(plan)

    await ctx.emit(
        "changes.proposed",
        {
            "plan_id": plan.id,
            "summary": summary,
            "files": [{"path": d["path"], "action": d["action"], "diff": d["diff"]} for d in diffs],
            "commands": commands or [],
        },
    )

    approved = True
    if ctx.mode == "ask" and diffs:
        events.register_approval(plan.id)
        responded = await events.wait_approval(plan.id, timeout=1800)
        ctx.db.refresh(plan)
        if not responded or plan.status == "rejected":
            approved = False
            plan.status = "rejected"
            ctx.db.commit()
            await ctx.emit("changes.rejected", {"plan_id": plan.id})
            return plan

    if approved:
        for f in prepared:
            if f["action"] == "unchanged":
                continue
            target = source / f["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f["content"], encoding="utf-8")
            await ctx.emit("file.changed", {"path": f["path"], "action": f["action"]})
        plan.status = "applied"
        ctx.db.commit()
        await ctx.emit("changes.applied", {"plan_id": plan.id, "files": [f["path"] for f in prepared if f["action"] != "unchanged"]})
    return plan


async def finish_run(ctx: AgentContext, result: AgentResult, output: str = ""):
    ctx.run.status = "completed" if result.ok else "failed"
    ctx.run.output_text = output or result.output
    ctx.run.error = result.error or ""
    ctx.db.commit()
    await ctx.emit("run.status", {"run_id": ctx.run.id, "status": ctx.run.status, "agent": ctx.run.agent_type})
