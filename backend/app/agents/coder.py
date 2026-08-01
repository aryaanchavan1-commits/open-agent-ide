from ..models import Task
from ..providers.base import ChatMessage
from ..providers.json_utils import extract_json
from .base import AgentContext, AgentResult, BaseAgent, propose_changes

CODER_SYSTEM = """You are the Coding Agent of Arynox AI, an AI software engineering platform.

You implement a task inside an existing project workspace. The context JSON below contains
the project description, the task, and relevant existing files.

IMPORTANT RULES:
1. First inspect the provided existing file contents. Modify what is needed; do NOT regenerate
   files that already exist and are unrelated to the task.
2. You never run commands yourself. Instead list required commands in "commands".
3. For every file you create or modify, provide the COMPLETE new file content in "content".
4. Do not include placeholder "TODO" code. The code must be complete and coherent.
5. Respect the existing technology stack.

Respond with STRICT JSON only, in this exact shape:
{
  "summary": "short summary of what changed",
  "files": [
    {"path": "relative/path/to/file", "content": "COMPLETE new file content"}
  ],
  "commands": [
    {"command": "pip install fastapi", "reason": "dependency needed by the new code"}
  ],
  "tests": [
    {"command": "pytest", "reason": "verify the implementation"}
  ]
}
- "path" must be relative to the project source directory (e.g. "src/app.py", "package.json").
- Create directories implicitly via the path.
- Include package/dependency manifest changes in "files" when adding dependencies.
- No markdown, no commentary outside the JSON."""


class CoderAgent(BaseAgent):
    name = "coder"
    display_name = "Coding Agent"

    async def run(self, ctx: AgentContext) -> AgentResult:
        await ctx.status("💻 Inspecting existing project...")
        task_label = ""
        if ctx.task:
            task_label = f"TASK {ctx.task.task_id}: {ctx.task.title}\n{ctx.task.description}"
        user_content = f"{task_label}\n\nUser request:\n{ctx.prompt}\n\nContext:\n{ctx.context_json}"
        messages = [
            ChatMessage(role="system", content=CODER_SYSTEM),
            ChatMessage(role="user", content=user_content),
        ]
        await ctx.status("💻 Writing code...")
        response = await ctx.provider.chat(messages, model=ctx.model, json_mode=True)
        data = extract_json(response)
        if not data:
            await ctx.status("⚠️ Retrying - model output was not valid JSON...")
            messages.append(ChatMessage(role="assistant", content=response))
            messages.append(
                ChatMessage(
                    role="user",
                    content="Your previous response was not valid JSON. Reply with STRICT JSON matching the requested shape exactly.",
                )
            )
            response = await ctx.provider.chat(messages, model=ctx.model, json_mode=True)
            data = extract_json(response)
        if not data:
            return AgentResult(
                False,
                error="Coding agent could not produce a valid change plan (invalid JSON)",
                output=response,
            )

        files = data.get("files", [])
        commands = data.get("commands", [])
        tests = data.get("tests", [])
        if not files:
            return AgentResult(False, error="Coding agent produced no file changes", output=response)

        await ctx.status(f"📋 Proposing changes for {len(files)} file(s)...")
        plan = await propose_changes(ctx, data.get("summary", "Coding agent changes"), files, commands)
        if plan and plan.status == "rejected":
            return AgentResult(False, error="Change plan was rejected by the user", output=data.get("summary", ""))

        if ctx.task and data:
            task = ctx.db.get(Task, ctx.task.id) if isinstance(ctx.task, Task) else ctx.task
            if task:
                task.status = "completed"
                ctx.db.commit()

        summary = data.get("summary", "Changes applied.")
        result = f"{summary}\n\nFiles: {', '.join(f['path'] for f in files)}"
        await ctx.status("✅ Code changes applied")
        return AgentResult(True, output=result, data={"files": files, "commands": commands, "tests": tests})
