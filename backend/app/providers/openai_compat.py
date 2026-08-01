from typing import AsyncIterator, Optional

import httpx

from .base import AIProvider, ChatMessage, ModelInfo, ProviderError


class OpenAICompatProvider(AIProvider):
    name = "openai"

    def __init__(
        self,
        base_url: str = "https://api.openai.com/v1",
        api_key: str = "",
        default_model: str = "gpt-4o-mini",
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_model = default_model
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=10.0))

    async def close(self):
        await self._client.aclose()

    async def is_available(self) -> bool:
        if not self.api_key and "localhost" not in self.base_url:
            return False
        return True

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    async def list_models(self) -> list[ModelInfo]:
        if not self.api_key:
            return []
        try:
            r = await self._client.get(f"{self.base_url}/models", headers=self._headers(), timeout=10.0)
            if r.status_code != 200:
                return []
            models = []
            for m in r.json().get("data", []):
                models.append(
                    ModelInfo(
                        id=m.get("id", ""),
                        name=m.get("id", ""),
                        provider=self.name,
                        local=False,
                    )
                )
            return models
        except Exception:
            return []

    async def chat(
        self,
        messages: list[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        system: Optional[str] = None,
    ) -> str:
        payload = self._build_payload(messages, model, temperature, max_tokens, json_mode, system)
        r = await self._client.post(f"{self.base_url}/chat/completions", headers=self._headers(), json=payload)
        if r.status_code != 200:
            raise ProviderError(f"{self.name} chat error {r.status_code}: {r.text[:500]}")
        data = r.json()
        return data["choices"][0]["message"]["content"] or ""

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        system: Optional[str] = None,
    ) -> AsyncIterator[str]:
        payload = self._build_payload(messages, model, temperature, max_tokens, json_mode, system)
        payload["stream"] = True
        async with self._client.stream(
            "POST", f"{self.base_url}/chat/completions", headers=self._headers(), json=payload
        ) as r:
            if r.status_code != 200:
                raise ProviderError(f"{self.name} chat error {r.status_code}: {await r.aread()}")
            async for line in r.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                import json as _json

                try:
                    obj = _json.loads(data)
                except Exception:
                    continue
                delta = obj.get("choices", [{}])[0].get("delta", {}).get("content", "")
                if delta:
                    yield delta

    def _build_payload(
        self,
        messages: list[ChatMessage],
        model: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
        json_mode: bool,
        system: Optional[str],
    ) -> dict:
        msgs: list[dict] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(m.model_dump() for m in messages)
        payload: dict = {
            "model": model or self.default_model,
            "messages": msgs,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if json_mode and "gpt" in (model or self.default_model):
            payload["response_format"] = {"type": "json_object"}
        return payload


class OpenRouterProvider(OpenAICompatProvider):
    name = "openrouter"

    def __init__(
        self,
        base_url: str = "https://openrouter.ai/api/v1",
        api_key: str = "",
        default_model: str = "anthropic/claude-3.5-sonnet",
    ):
        super().__init__(base_url=base_url, api_key=api_key, default_model=default_model)

    def _headers(self) -> dict:
        h = super()._headers()
        h["HTTP-Referer"] = "http://localhost:3000"
        h["X-Title"] = "Arynox AI"
        return h
