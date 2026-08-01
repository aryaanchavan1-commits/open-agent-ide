from ..providers.base import ChatMessage
from ..providers.json_utils import extract_json
from .base import AgentContext, AgentResult, BaseAgent, propose_changes

DEBUGGER_SYSTEM = """You are the Debugging Agent of Arynox AI.

An error occurred in a project. You are given the error output and relevant source files.

IMPORTANT RULES:
1. Identify the root cause precisely by reading the relevant files.
2. Do NOT modify unrelated files.
3. For each file that needs a fix, provide the COMPLETE new file content.
4. If you are not confident, set "fixes" to an empty list and explain.

Respond with STRICT JSON only:
{
  "root_cause": "precise explanation of the root cause",
  "fixes": [
    {"path": "relative/path", "content": "COMPLETE fixed file content"}
  ],
  "verify": [{"command": "pytest", "reason": "re-run tests to verify the fix"}]
}
No markdown, no commentary outside the JSON."""


class DebuggerAgent(BaseAgent):
    name = "debugger"
    display_name = "Debugging Agent"

    async def run(self, ctx: AgentContext) -> AgentResult:
        await ctx.status("🐛 Reading the error...")
        messages = [
            ChatMessage(role="system", content=DEBUGGER_SYSTEM),
            ChatMessage(
                role="user",
                content=f"Error output:\n{ctx.prompt}\n\nContext:\n{ctx.context_json}",
            ),
        ]
        await ctx.status("🐛 Inspecting relevant files...")
        response = await ctx.provider.chat(messages, model=ctx.model, json_mode=True)
        data = extract_json(response)
        if not data:
            return AgentResult(False, error="Debugger could not produce a valid analysis", output=response)
        root_cause = data.get("root_cause", "Unknown")
        fixes = data.get("fixes", [])
        verify = data.get("verify", [])
        if fixes:
            await ctx.status(f"🐛 Proposing fix for {len(fixes)} file(s)...")
            plan = await propose_changes(ctx, f"Debug fix: {root_cause[:200]}", fixes, verify)
            if plan and plan.status == "rejected":
                return AgentResult(False, error="Fix rejected by user", output=root_cause)
            await ctx.status("🐛 Fix applied")
        else:
            await ctx.status("⚠️ No confident fix identified")
        return AgentResult(True, output=f"Root cause: {root_cause}\n\nFiles fixed: {[f['path'] for f in fixes]}", data=data)
