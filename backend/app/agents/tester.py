import json
import re

from ..models import TestRun
from ..providers.base import ChatMessage
from ..providers.json_utils import extract_json
from ..security.command_safety import execute_with_approval
from .base import AgentContext, AgentResult, BaseAgent, propose_changes

TESTER_SYSTEM = """You are the Testing Agent of Arynox AI.

Analyze test failures or test coverage needs and produce STRICT JSON:
{
  "summary": "what tests exist / what failed",
  "issues": [{"file": "path", "issue": "description of the failure and likely cause"}],
  "fixes": [
    {"path": "relative/path", "content": "COMPLETE new file content if a fix is needed"}
  ],
  "tests": [{"command": "pytest", "reason": "rerun after fixes"}]
}
If tests already pass, "fixes" should be empty."""


def detect_test_command(source_dir, project) -> tuple[str, str]:
    pyproject = source_dir / "pyproject.toml"
    package_json = source_dir / "package.json"
    setup_py = source_dir / "setup.py"
    if package_json.exists():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            scripts = data.get("scripts", {})
            if "test" in scripts:
                return "npm test", "package.json has a test script"
        except Exception:
            pass
        return "npm test", "npm project detected"
    if pyproject.exists() or setup_py.exists() or (source_dir / "requirements.txt").exists():
        return "pytest", "python project detected"
    return "pytest", "default test runner"


def parse_test_output(output: str) -> tuple[int, int]:
    passed = 0
    failed = 0
    m = re.search(r"(\d+)\s+passed", output)
    if m:
        passed = int(m.group(1))
    m = re.search(r"(\d+)\s+failed", output)
    if m:
        failed = int(m.group(1))
    m = re.search(r"Tests:\s*(\d+)\s+passed", output)
    if m and passed == 0:
        passed = int(m.group(1))
    m = re.search(r"Tests:\s*(\d+)\s+failed", output)
    if m and failed == 0:
        failed = int(m.group(1))
    return passed, failed


class TesterAgent(BaseAgent):
    name = "tester"
    display_name = "Testing Agent"

    async def run(self, ctx: AgentContext) -> AgentResult:
        await ctx.status("🧪 Detecting testing framework...")
        command, reason = detect_test_command(ctx.source_dir, ctx.project)
        await ctx.status(f"🧪 Running tests: {command}")
        buffer: list[str] = []
        result = await execute_with_approval(
            ctx.db,
            ctx.project.id,
            command,
            ctx.source_dir,
            agent="tester",
            reason=reason,
            mode=ctx.mode,
            timeout=900,
            output_buffer=buffer,
        )
        output = result.get("output", "")
        if result.get("denied"):
            await ctx.status("⛔ Test command was blocked or rejected")
            return AgentResult(False, error=f"Test command blocked/rejected: {result.get('reason', '')}", output=output)
        passed, failed = parse_test_output(output)
        test_run = TestRun(
            project_id=ctx.project.id,
            agent_run_id=ctx.run.id,
            command=command,
            status="passed" if result.get("exit_code") == 0 else "failed",
            output=output[-20000:],
            passed=passed,
            failed=failed,
            error=result.get("reason", ""),
        )
        ctx.db.add(test_run)
        ctx.db.commit()
        await ctx.emit(
            "test.result",
            {
                "test_run_id": test_run.id,
                "command": command,
                "status": test_run.status,
                "passed": passed,
                "failed": failed,
                "exit_code": result.get("exit_code"),
            },
        )
        status_line = f"✅ Tests passed: {passed} passed" if result.get("exit_code") == 0 else f"❌ Tests failed: {failed} failed"
        await ctx.status(status_line)
        return AgentResult(
            True if result.get("exit_code") == 0 else False,
            output=f"{status_line}\nCommand: {command}\n\n{output[-4000:]}",
        )
