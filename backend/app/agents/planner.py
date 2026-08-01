import json

from ..models import Task
from ..providers.base import ChatMessage
from ..providers.json_utils import extract_json
from .base import AgentContext, AgentResult, BaseAgent

PLANNER_SYSTEM = """You are the Planner Agent of Arynox AI, an AI software engineering platform.

Break the requested software project into a structured, dependency-ordered list of implementation tasks.
Each task must be small enough to implement in a single coding session.

Respond with STRICT JSON only, in this exact shape:
{
  "summary": "one paragraph plan overview",
  "tasks": [
    {
      "task_id": "TASK-001",
      "title": "short imperative title",
      "description": "what to implement, which files, which technology",
      "priority": "high|medium|low",
      "dependencies": ["TASK-000"]
    }
  ]
}
Rules:
- First tasks should scaffold the project (structure, config, dependency install).
- Include a testing task near the end.
- Max 12 tasks.
- No markdown, no commentary outside the JSON."""


class PlannerAgent(BaseAgent):
    name = "planner"
    display_name = "Planner Agent"

    async def run(self, ctx: AgentContext) -> AgentResult:
        await ctx.status("🧠 Breaking the request into tasks...")
        context = ctx.prompt
        messages = [
            ChatMessage(role="system", content=PLANNER_SYSTEM),
            ChatMessage(role="user", content=context),
        ]
        response = await ctx.provider.chat(messages, model=ctx.model, json_mode=True)
        data = extract_json(response)
        if not data or not data.get("tasks"):
            return AgentResult(False, error="Planner could not produce a valid task list", output=response)

        tasks = data["tasks"]
        for t in tasks:
            existing = (
                ctx.db.query(Task)
                .filter(Task.project_id == ctx.project.id, Task.task_id == t.get("task_id", ""))
                .first()
            )
            if existing:
                continue
            task = Task(
                project_id=ctx.project.id,
                task_id=t.get("task_id", f"TASK-{len(tasks)}"),
                title=t.get("title", "Untitled task"),
                description=t.get("description", ""),
                priority=t.get("priority", "medium"),
                dependencies=t.get("dependencies", []),
                status="pending",
                agent_type="coder",
            )
            ctx.db.add(task)
        ctx.project.status = "planned"
        ctx.db.commit()

        result_txt = json.dumps(
            [{"task_id": t.get("task_id"), "title": t.get("title"), "priority": t.get("priority")} for t in tasks],
            indent=2,
        )
        await ctx.status(f"✅ Plan created: {len(tasks)} tasks")
        await ctx.emit("plan.created", {"summary": data.get("summary", ""), "tasks": tasks})
        return AgentResult(True, output=f"Plan created with {len(tasks)} tasks.\n\n{result_txt}", data=tasks)
