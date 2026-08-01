import os
import platform
import subprocess
from typing import Any, AsyncIterator, Callable, Optional

import httpx

from .base import AIProvider, ChatMessage, ModelInfo, ProviderError


class OllamaProvider(AIProvider):
    name = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434", auto_pull: bool = True):
        self.base_url = base_url.rstrip("/")
        self.auto_pull = auto_pull
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=httpx.Timeout(600.0, connect=3.0))

    async def close(self):
        await self._client.aclose()

    async def is_available(self) -> bool:
        try:
            r = await self._client.get("/api/tags", timeout=3.0)
            return r.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[ModelInfo]:
        r = await self._client.get("/api/tags")
        if r.status_code != 200:
            return []
        models = []
        for m in r.json().get("models", []):
            models.append(
                ModelInfo(
                    id=m.get("name", ""),
                    name=m.get("name", ""),
                    provider="ollama",
                    local=True,
                    size_bytes=m.get("size", 0),
                )
            )
        return models

    async def ensure_model(self, model: str) -> bool:
        """Return True if the model is present, otherwise pull it."""
        if not model:
            return False
        local = {m.id for m in await self.list_models()}
        if model in local:
            return True
        if ":" not in model:
            if any(m.split(":")[0] == model for m in local):
                return True
        elif model.endswith(":latest"):
            if any(m.split(":")[0] == model.split(":")[0] for m in local):
                return True
        if not self.auto_pull:
            return False
        ok = await self.pull_model(model)
        return ok

    async def pull_model(self, model: str, progress_cb: Optional[Callable] = None) -> bool:
        async with self._client.stream("POST", "/api/pull", json={"model": model, "stream": True}) as r:
            if r.status_code != 200:
                raise ProviderError(f"Failed to pull model {model}: {r.status_code}")
            async for line in r.aiter_lines():
                if not line:
                    continue
                import json as _json

                try:
                    data = _json.loads(line)
                except Exception:
                    continue
                if progress_cb:
                    await progress_cb(data)
                if data.get("status") in ("success",):
                    return True
                if data.get("error"):
                    raise ProviderError(str(data["error"]))
        return False

    async def chat(
        self,
        messages: list[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        system: Optional[str] = None,
    ) -> str:
        model = model or ""
        await self.ensure_model(model)
        payload: dict[str, Any] = {
            "model": model,
            "messages": [m.model_dump() for m in messages],
            "stream": False,
            "options": {"temperature": temperature},
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        if json_mode:
            payload["format"] = "json"
        r = await self._client.post("/api/chat", json=payload)
        if r.status_code != 200:
            raise ProviderError(f"Ollama chat error {r.status_code}: {r.text[:500]}")
        data = r.json()
        return data.get("message", {}).get("content", "")

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        system: Optional[str] = None,
    ) -> AsyncIterator[str]:
        model = model or ""
        await self.ensure_model(model)
        payload: dict[str, Any] = {
            "model": model,
            "messages": [m.model_dump() for m in messages],
            "stream": True,
            "options": {"temperature": temperature},
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        if json_mode:
            payload["format"] = "json"
        async with self._client.stream("POST", "/api/chat", json=payload) as r:
            if r.status_code != 200:
                raise ProviderError(f"Ollama chat error {r.status_code}: {await r.aread()}")
            async for line in r.aiter_lines():
                if not line:
                    continue
                import json as _json

                try:
                    data = _json.loads(line)
                except Exception:
                    continue
                chunk = data.get("message", {}).get("content", "")
                if chunk:
                    yield chunk


def detect_system() -> dict[str, Any]:
    """Detect OS, RAM and GPU to recommend an appropriate local model."""
    info: dict[str, Any] = {
        "os": platform.system(),
        "arch": platform.machine(),
        "cpu_cores": os.cpu_count() or 4,
    }
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if platform.system() == "Windows" and ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            info["ram_gb"] = round(stat.ullTotalPhys / (1024**3), 1)
    except Exception:
        info["ram_gb"] = None
    gpu = detect_gpu()
    if gpu:
        info["gpu"] = gpu
    info["recommended_model"] = recommend_model(info)
    return info


def detect_gpu() -> Optional[str]:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().splitlines()[0]
    except Exception:
        pass
    return None


def recommend_model(info: dict[str, Any]) -> str:
    ram = info.get("ram_gb") or 8
    gpu = info.get("gpu", "")
    if "nvidia" in gpu.lower() or "rtx" in gpu.lower():
        return "qwen2.5-coder:14b" if ram >= 16 else "qwen2.5-coder:7b"
    if ram >= 16:
        return "qwen2.5-coder:7b"
    if ram >= 8:
        return "qwen2.5-coder:3b"
    return "qwen2.5-coder:1.5b"
