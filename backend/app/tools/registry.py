from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]
    requires_approval: bool = False
    category: str = "file"


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def descriptions(self) -> str:
        lines = []
        for t in self._tools.values():
            params = ", ".join(f"{k}: {v.get('type', 'any')}" for k, v in t.parameters.items())
            lines.append(f"- {t.name}({params}) - {t.description}")
        return "\n".join(lines)

    def call(self, name: str, arguments: dict, context: Optional[dict] = None) -> dict:
        tool = self._tools.get(name)
        if not tool:
            return {"ok": False, "error": f"Unknown tool: {name}"}
        try:
            result = tool.handler(**arguments)
            if isinstance(result, dict) and "ok" in result:
                return result
            return {"ok": True, "result": result}
        except Exception as e:
            return {"ok": False, "error": str(e)}
