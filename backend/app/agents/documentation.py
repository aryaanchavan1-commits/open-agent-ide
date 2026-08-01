from ..providers.base import ChatMessage
from ..providers.json_utils import extract_json
from .base import AgentContext, AgentResult, BaseAgent, propose_changes

DOC_SYSTEM = """You are the Documentation Agent of Arynox AI.

Write clear developer documentation for the project. Use the provided context to be accurate.

Respond with STRICT JSON only:
{
  "summary": "short summary",
  "files": [
    {"path": "README.md", "content": "full markdown"},
    {"path": "docs/setup.md", "content": "full markdown"},
    {"path": "docs/architecture.md", "content": "full markdown"}
  ]
}
README.md must include: overview, features, setup/installation instructions, usage, and environment variables.
No markdown outside the JSON."""


class DocumentationAgent(BaseAgent):
    name = "documentation"
    display_name = "Documentation Agent"

    async def run(self, ctx: AgentContext) -> AgentResult:
        await ctx.status("📝 Writing documentation...")
        messages = [
            ChatMessage(role="system", content=DOC_SYSTEM),
            ChatMessage(role="user", content=f"Documentation request:\n{ctx.prompt}\n\nContext:\n{ctx.context_json}"),
        ]
        response = await ctx.provider.chat(messages, model=ctx.model, json_mode=True)
        data = extract_json(response)
        if not data:
            return AgentResult(False, error="Documentation agent could not produce documents", output=response)
        files = data.get("files", [])
        if not files:
            return AgentResult(False, error="No documents produced", output=response)
        plan = await propose_changes(ctx, data.get("summary", "Project documentation"), files, [])
        if plan and plan.status == "rejected":
            return AgentResult(False, error="Documentation rejected by user", output=data.get("summary", ""))
        await ctx.status("✅ Documentation written")
        return AgentResult(True, output=data.get("summary", "") + f"\n\nFiles: {', '.join(f['path'] for f in files)}")
