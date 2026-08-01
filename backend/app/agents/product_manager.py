from ..providers.base import ChatMessage
from ..providers.json_utils import extract_json
from .base import AgentContext, AgentResult, BaseAgent, propose_changes

PM_SYSTEM = """You are the Product Manager Agent of Arynox AI.

Analyze the user's project request and create a requirements document.

Respond with STRICT JSON only:
{
  "summary": "short summary",
  "clarifying_questions": ["question 1", "question 2"] or [],
  "functional_requirements": ["REQ-001: ..."],
  "user_stories": ["As a ..., I want ... so that ..."],
  "acceptance_criteria": ["Given ... When ... Then ..."],
  "files": [
    {"path": "docs/requirements.md", "content": "full markdown document with all of the above"}
  ]
}
If the request is ambiguous, list up to 3 clarifying questions but still produce the best-effort requirements.
No markdown outside the JSON."""


class ProductManagerAgent(BaseAgent):
    name = "product_manager"
    display_name = "Product Manager Agent"

    async def run(self, ctx: AgentContext) -> AgentResult:
        await ctx.status("🧠 Analyzing requirements...")
        messages = [
            ChatMessage(role="system", content=PM_SYSTEM),
            ChatMessage(role="user", content=f"Project request:\n{ctx.prompt}\n\nContext:\n{ctx.context_json}"),
        ]
        response = await ctx.provider.chat(messages, model=ctx.model, json_mode=True)
        data = extract_json(response)
        if not data:
            return AgentResult(False, error="Product manager could not produce requirements", output=response)
        questions = data.get("clarifying_questions", [])
        files = data.get("files", [])
        if files:
            plan = await propose_changes(ctx, data.get("summary", "Requirements document"), files, [])
            if plan and plan.status == "rejected":
                return AgentResult(False, error="Requirements document rejected by user", output=data.get("summary", ""))
        out = data.get("summary", "")
        if questions:
            out += "\n\nClarifying questions:\n- " + "\n- ".join(questions)
        await ctx.status("✅ Requirements analyzed")
        return AgentResult(True, output=out, data=data)
