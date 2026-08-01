import json
from typing import Any, Optional

from .config import get_settings


class MCPBridge:
    """Client for MCP (Model Context Protocol) servers.

    Tools exposed by configured MCP servers are registered in the tool
    registry under the name `mcp.<server>.<tool>` so agents can call them.
    """

    def __init__(self):
        self._sessions: dict[str, Any] = {}
        self._tools: dict[str, dict] = {}
        self._available = True
        try:
            import mcp  # noqa: F401
        except ImportError:
            self._available = False

    @property
    def enabled(self) -> bool:
        return self._available

    def _parse_config(self) -> dict[str, dict]:
        try:
            raw = get_settings().mcp_servers
            if not raw:
                return {}
            return json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            return {}

    async def connect_all(self) -> list[str]:
        if not self._available:
            return []
        servers = self._parse_config()
        connected = []
        for name, cfg in servers.items():
            try:
                if await self._connect_server(name, cfg):
                    connected.append(name)
            except Exception as e:
                print(f"[mcp] failed to connect server '{name}': {e}")
        return connected

    async def _connect_server(self, name: str, cfg: dict) -> bool:
        import asyncio
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        from mcp.client.streamable_http import streamablehttp_client

        if "command" in cfg:

            async def _open_stdio():
                params = StdioServerParameters(command=cfg["command"], args=cfg.get("args", []), env=cfg.get("env"))
                stdio_ctx = stdio_client(params)
                s, w = await stdio_ctx.__aenter__()
                session = await ClientSession(s, w).__aenter__()
                await session.initialize()
                return session, stdio_ctx

            session, stdio_ctx = await _open_stdio()
            self._sessions[name] = {"session": session}
        elif "url" in cfg:

            async def _open_http():
                sse_ctx = streamablehttp_client(cfg["url"])
                s, w = await sse_ctx.__aenter__()
                session = await ClientSession(s, w).__aenter__()
                await session.initialize()
                return session, sse_ctx

            session, http_ctx = await _open_http()
            self._sessions[name] = {"session": session}
        else:
            return False

        tools = await self._sessions[name]["session"].list_tools()
        for tool in tools.tools:
            full = f"mcp.{name}.{tool.name}"
            self._tools[full] = {
                "server": name,
                "tool_name": tool.name,
                "description": getattr(tool, "description", "") or "",
                "input_schema": getattr(tool, "inputSchema", None) or {},
            }
        return True

    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def reset(self) -> None:
        for entry in self._sessions.values():
            session = entry.get("session")
            if session:
                try:
                    session._context.__aexit__(None, None, None)
                except Exception:
                    pass
        self._sessions.clear()
        self._tools.clear()

    def describe_tools(self) -> list[dict]:
        return [
            {
                "name": full,
                "description": info["description"],
                "schema": info["input_schema"],
            }
            for full, info in self._tools.items()
        ]

    async def call_tool(self, full_name: str, arguments: dict) -> Any:
        info = self._tools.get(full_name)
        if not info:
            raise ValueError(f"MCP tool not found: {full_name}")
        entry = self._sessions.get(info["server"])
        if not entry:
            raise ValueError(f"MCP server not connected: {info['server']}")
        result = await entry["session"].call_tool(info["tool_name"], arguments)
        parts = []
        for content in result.content:
            if getattr(content, "type", "") == "text":
                parts.append(content.text)
            elif getattr(content, "type", "") == "resource":
                parts.append(str(content))
        return "\n".join(parts)


_bridge: Optional[MCPBridge] = None


def get_mcp_bridge() -> MCPBridge:
    global _bridge
    if _bridge is None:
        _bridge = MCPBridge()
    return _bridge
