from ..providers.base import ChatMessage
from ..providers.json_utils import extract_json
from .base import AgentContext, AgentResult, BaseAgent

REVIEWER_SYSTEM = """You are the Code Review Agent of Arynox AI.

Review the provided source files for: bugs, security issues, bad architecture, duplicate code,
performance problems and missing tests. Be specific and reference file paths.

Respond with STRICT JSON only:
{
  "summary": "overall assessment",
  "critical": [{"file": "path", "issue": "..."}],
  "warnings": [{"file": "path", "issue": "..."}],
  "suggestions": [{"file": "path", "issue": "..."}]
}
No markdown outside the JSON."""


class CodeReviewAgent(BaseAgent):
    name = "reviewer"
    display_name = "Code Review Agent"

    async def run(self, ctx: AgentContext) -> AgentResult:
        await ctx.status("🔍 Reviewing code...")
        messages = [
            ChatMessage(role="system", content=REVIEWER_SYSTEM),
            ChatMessage(role="user", content=f"Review request:\n{ctx.prompt}\n\nContext:\n{ctx.context_json}"),
        ]
        response = await ctx.provider.chat(messages, model=ctx.model, json_mode=True)
        data = extract_json(response)
        if not data:
            return AgentResult(False, error="Reviewer could not produce a valid review", output=response)
        critical = data.get("critical", [])
        warnings = data.get("warnings", [])
        suggestions = data.get("suggestions", [])
        out = data.get("summary", "")
        out += f"\n\nCritical: {len(critical)} | Warnings: {len(warnings)} | Suggestions: {len(suggestions)}"
        await ctx.emit("review.result", data)
        await ctx.status("✅ Review complete")
        return AgentResult(True, output=out, data=data)
