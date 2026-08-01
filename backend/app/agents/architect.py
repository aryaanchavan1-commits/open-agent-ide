import json

from ..providers.base import ChatMessage
from ..providers.json_utils import extract_json
from .base import AgentContext, AgentResult, BaseAgent, propose_changes

ARCHITECT_SYSTEM = """You are the Architect Agent of Arynox AI.

Design the system architecture for the requested software project. Write three markdown documents
as files: architecture.md, database-schema.md and api-specification.md (paths are relative to the
project source directory; use a "docs" folder).

Respond with STRICT JSON only:
{
  "summary": "architecture overview in a few sentences",
  "files": [
    {"path": "docs/architecture.md", "content": "full markdown"},
    {"path": "docs/database-schema.md", "content": "full markdown"},
    {"path": "docs/api-specification.md", "content": "full markdown"}
  ]
}
No markdown outside the JSON."""


class ArchitectAgent(BaseAgent):
    name = "architect"
    display_name = "Architect Agent"

    async def run(self, ctx: AgentContext) -> AgentResult:
        await ctx.status("🏗️ Designing system architecture...")
        messages = [
            ChatMessage(role="system", content=ARCHITECT_SYSTEM),
            ChatMessage(role="user", content=f"Project:\n{ctx.prompt}\n\nContext:\n{ctx.context_json}"),
        ]
        response = await ctx.provider.chat(messages, model=ctx.model, json_mode=True)
        data = extract_json(response)
        if not data:
            return AgentResult(False, error="Architect could not produce a valid design", output=response)
        files = data.get("files", [])
        if not files:
            return AgentResult(False, error="Architect produced no documents", output=response)
        await ctx.status("📄 Writing architecture documents...")
        plan = await propose_changes(ctx, data.get("summary", "Architecture documents"), files, [])
        if plan and plan.status == "rejected":
            return AgentResult(False, error="Architecture documents rejected by user", output=data.get("summary", ""))
        await ctx.status("✅ Architecture designed")
        return AgentResult(True, output=data.get("summary", ""), data={"files": files})
