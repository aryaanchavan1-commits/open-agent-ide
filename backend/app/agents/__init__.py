from .architect import ArchitectAgent
from .base import AgentContext, AgentResult, BaseAgent, finish_run
from .coder import CoderAgent
from .debugger import DebuggerAgent
from .documentation import DocumentationAgent
from .planner import PlannerAgent
from .product_manager import ProductManagerAgent
from .reviewer import CodeReviewAgent
from .tester import TesterAgent

AGENTS: dict[str, BaseAgent] = {
    "planner": PlannerAgent(),
    "coder": CoderAgent(),
    "tester": TesterAgent(),
    "debugger": DebuggerAgent(),
    "architect": ArchitectAgent(),
    "product_manager": ProductManagerAgent(),
    "reviewer": CodeReviewAgent(),
    "documentation": DocumentationAgent(),
}


def get_agent(name: str) -> BaseAgent:
    if name not in AGENTS:
        raise ValueError(f"Unknown agent '{name}'. Available: {list(AGENTS)}")
    return AGENTS[name]


def list_agents() -> list[dict]:
    return [
        {"id": "planner", "name": "Planner Agent", "description": "Breaks projects into tasks", "emoji": "🧠"},
        {"id": "product_manager", "name": "Product Manager", "description": "Requirements, user stories, acceptance criteria", "emoji": "📋"},
        {"id": "architect", "name": "Architect Agent", "description": "Architecture, database schema, API design", "emoji": "🏗️"},
        {"id": "coder", "name": "Coding Agent", "description": "Creates and modifies files with approval", "emoji": "💻"},
        {"id": "tester", "name": "Testing Agent", "description": "Detects framework, runs tests, reports results", "emoji": "🧪"},
        {"id": "debugger", "name": "Debugging Agent", "description": "Analyzes errors and proposes fixes", "emoji": "🐛"},
        {"id": "reviewer", "name": "Code Review Agent", "description": "Bugs, security, architecture, performance", "emoji": "🔍"},
        {"id": "documentation", "name": "Documentation Agent", "description": "README, setup, architecture docs", "emoji": "📝"},
    ]


async def run_agent(ctx: AgentContext) -> AgentResult:
    agent = get_agent(ctx.run.agent_type)
    try:
        await ctx.emit("agent.started", {"agent": ctx.run.agent_type, "run_id": ctx.run.id})
        result = await agent.run(ctx)
        await finish_run(ctx, result)
        return result
    except Exception as e:
        import traceback

        tb = traceback.format_exc()
        result = AgentResult(False, error=f"{type(e).__name__}: {e}", output=tb)
        await finish_run(ctx, result)
        return result
